# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""PDF form template directory management, XFA detection, auto-mapping, and validation."""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import yaml

ENV_PDF_TEMPLATES_DIR = "PDF_TEMPLATES_DIR"
ENV_PDF_OUTPUT_DIR = "PDF_OUTPUT_DIR"
DEFAULT_PDF_TEMPLATES_DIRNAME = "pdf_templates"
PYMUPDF_INSTALL_HINT = 'PyMuPDF is required for PDF commands. Run: pip install "skillware[office_pdf_form_filler]"'

_PII_KEYWORDS = ("ssn", "tax id", "tin", "birth", "ein")
_SECTION_HEADER_RE = re.compile(
    r"^(?:part|section)\s+(?:[ivxlcdm]+|\d+)(?:\s*[:.\-\u2013\u2014]?\s+.*)?$",
    re.IGNORECASE,
)

# PyMuPDF widget type constants (kept as ints so module imports without fitz).
_WIDGET_TYPE_CHECKBOX = 2
_WIDGET_TYPE_COMBOBOX = 3
_WIDGET_TYPE_LISTBOX = 4
_WIDGET_TYPE_RADIOBUTTON = 5
_WIDGET_TYPE_SIGNATURE = 6
_WIDGET_TYPE_TEXT = 7

_SCHEMA_TYPE_TO_WIDGET_TYPES: Dict[str, Set[int]] = {
    "text": {_WIDGET_TYPE_TEXT},
    "date": {_WIDGET_TYPE_TEXT},
    "signature": {_WIDGET_TYPE_SIGNATURE, _WIDGET_TYPE_TEXT},
    "checkbox": {_WIDGET_TYPE_CHECKBOX},
    "combobox": {_WIDGET_TYPE_COMBOBOX, _WIDGET_TYPE_LISTBOX},
    "dropdown": {_WIDGET_TYPE_COMBOBOX, _WIDGET_TYPE_LISTBOX},
    "listbox": {_WIDGET_TYPE_LISTBOX, _WIDGET_TYPE_COMBOBOX},
    "radio": {_WIDGET_TYPE_RADIOBUTTON},
}

_WIDGET_TYPE_TO_SCHEMA_TYPE: Dict[int, str] = {
    _WIDGET_TYPE_TEXT: "text",
    _WIDGET_TYPE_SIGNATURE: "signature",
    _WIDGET_TYPE_CHECKBOX: "checkbox",
    _WIDGET_TYPE_COMBOBOX: "combobox",
    _WIDGET_TYPE_LISTBOX: "combobox",
    _WIDGET_TYPE_RADIOBUTTON: "radio",
}


class PyMuPDFMissingError(RuntimeError):
    """Raised when PyMuPDF (fitz) is not installed."""


def _require_fitz() -> Any:
    """Import and return PyMuPDF (fitz), or raise PyMuPDFMissingError."""
    try:
        import fitz  # type: ignore[import-untyped]

        return fitz
    except ImportError as exc:
        raise PyMuPDFMissingError(PYMUPDF_INSTALL_HINT) from exc


@dataclass
class PdfSettings:
    """Optional PDF template and output settings from YAML ``pdf:`` section."""

    templates_dir: Optional[str] = None
    output_dir: Optional[str] = None


def parse_pdf_block(raw: Any) -> PdfSettings:
    """Parse a ``pdf:`` YAML mapping into PdfSettings."""
    if not isinstance(raw, dict):
        return PdfSettings()
    raw_dir = raw.get("templates_dir")
    t_val = str(raw_dir).strip() if raw_dir is not None else ""
    raw_out = raw.get("output_dir")
    o_val = str(raw_out).strip() if raw_out is not None else ""
    return PdfSettings(templates_dir=t_val or None, output_dir=o_val or None)


def merge_pdf_settings(layers: Sequence[PdfSettings]) -> PdfSettings:
    """Merge layered PdfSettings; later non-empty values override earlier ones."""
    merged = PdfSettings()
    for layer in layers:
        if layer.templates_dir:
            merged.templates_dir = layer.templates_dir
        if layer.output_dir:
            merged.output_dir = layer.output_dir
    return merged


def resolve_output_dir(
    *,
    env_output_dir: Optional[str] = None,
    start: Optional[Path] = None,
) -> Tuple[str, Optional[Path]]:
    """
    Resolve default PDF output directory using 3-tier precedence:
    1. ``PDF_OUTPUT_DIR`` env var (or explicit ``env_output_dir``)
    2. Project ``.skillware.yaml`` -> ``pdf.output_dir``
    3. Global ``config.yaml`` -> ``pdf.output_dir``
    4. Default fallback: ``None`` (current working directory / alongside input PDF)
    """
    env_val = (
        env_output_dir
        if env_output_dir is not None
        else os.environ.get(ENV_PDF_OUTPUT_DIR, "")
    ).strip()
    if env_val:
        return ("env", Path(env_val).expanduser().resolve())

    from skillware.core.config import find_project_config_file, global_config_path

    proj_cfg = find_project_config_file(start)
    if proj_cfg is not None:
        try:
            data = yaml.safe_load(proj_cfg.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                pdf_cfg = data.get("pdf")
                if isinstance(pdf_cfg, dict) and pdf_cfg.get("output_dir"):
                    raw = str(pdf_cfg["output_dir"]).strip()
                    if raw:
                        p = Path(raw).expanduser()
                        return (
                            "project",
                            (
                                p.resolve()
                                if p.is_absolute()
                                else (proj_cfg.parent / p).resolve()
                            ),
                        )
        except Exception:
            pass

    g_cfg = global_config_path()
    if g_cfg.is_file():
        try:
            data = yaml.safe_load(g_cfg.read_text(encoding="utf-8")) or {}
            if isinstance(data, dict):
                pdf_cfg = data.get("pdf")
                if isinstance(pdf_cfg, dict) and pdf_cfg.get("output_dir"):
                    raw = str(pdf_cfg["output_dir"]).strip()
                    if raw:
                        return ("global", Path(raw).expanduser().resolve())
        except Exception:
            pass

    return ("default", None)


def save_pdf_output_dir(
    output_dir: str,
    *,
    global_scope: bool = False,
    start: Optional[Path] = None,
) -> Tuple[Path, Path]:
    """
    Create ``output_dir`` (if missing) and persist ``pdf.output_dir`` in
    ``.skillware.yaml`` (default) or global ``config.yaml`` (when ``global_scope=True``).
    """
    from skillware.core.config import (
        clear_config_cache,
        global_config_path,
        project_config_write_path,
    )

    base = (start or Path.cwd()).resolve()
    raw_path = Path(output_dir).expanduser()
    target_dir = (
        raw_path.resolve() if raw_path.is_absolute() else (base / raw_path).resolve()
    )
    target_dir.mkdir(parents=True, exist_ok=True)

    cfg_target = (
        global_config_path() if global_scope else project_config_write_path(start)
    )
    cfg_target.parent.mkdir(parents=True, exist_ok=True)

    document: Dict[str, Any] = {}
    if cfg_target.is_file():
        raw = yaml.safe_load(cfg_target.read_text(encoding="utf-8")) or {}
        if isinstance(raw, dict):
            document = dict(raw)

    pdf_block = document.get("pdf")
    pdf_block = dict(pdf_block) if isinstance(pdf_block, dict) else {}

    if not global_scope:
        try:
            rel = target_dir.resolve().relative_to(cfg_target.parent.resolve())
            pdf_block["output_dir"] = f"./{rel.as_posix()}"
        except ValueError:
            pdf_block["output_dir"] = str(target_dir.resolve())
    else:
        pdf_block["output_dir"] = str(target_dir.resolve())

    document["pdf"] = pdf_block
    cfg_target.write_text(
        yaml.safe_dump(document, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    clear_config_cache()
    return target_dir, cfg_target.resolve()


def format_pdf_config_lines(settings: Optional[PdfSettings] = None) -> List[str]:
    """Return human-readable lines for ``skillware config show``."""
    tier, active_dir = resolve_active_templates_dir()
    status = "present" if active_dir.is_dir() else "missing — run: skillware pdf init"
    out_tier, out_dir = resolve_output_dir()
    if out_dir is not None:
        out_status = "present" if out_dir.is_dir() else "will auto-create on fill"
        out_line = f"  output_dir ({out_tier}): {out_dir} ({out_status})"
    else:
        out_line = (
            "  output_dir (default): current working directory "
            "(customize via: skillware pdf output-dir <path>)"
        )
    lines = [
        f"  templates_dir ({tier}): {active_dir} ({status})",
        out_line,
        f"  bundled fallback: {bundled_pdf_kb_dir()}",
    ]
    if settings is not None and settings.templates_dir:
        lines.insert(0, f"  configured pdf.templates_dir: {settings.templates_dir}")
    if settings is not None and settings.output_dir:
        lines.insert(
            1 if (settings.templates_dir) else 0,
            f"  configured pdf.output_dir: {settings.output_dir}",
        )
    return lines


@dataclass(frozen=True)
class TemplateRoot:
    """One resolved template directory tier."""

    tier: str
    path: Path


@dataclass
class ValidationResult:
    """Outcome of validating a YAML schema map against a physical PDF."""

    valid: bool
    pdf_path: str
    schema_path: str
    field_count: int = 0
    is_xfa: bool = False
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class TemplateAuditEntry:
    """Audit status for a single discovered PDF form template."""

    template_id: str
    source: str
    pdf_type: str
    map_status: str
    fields: Optional[int]
    path: Path
    schema_path: Optional[Path] = None
    errors: List[str] = field(default_factory=list)


@dataclass
class ImportItemResult:
    """Result for a single PDF processed by batch import."""

    source_path: Path
    dest_path: Optional[Path]
    status: str  # "imported", "skipped", "xfa", "invalid"
    message: str
    map_path: Optional[Path] = None
    map_status: Optional[str] = None


def bundled_pdf_kb_dir() -> Path:
    """Return the bundled read-only KB directory for office/pdf_form_filler."""
    repo_candidate = (
        Path(__file__).resolve().parents[2]
        / "skills"
        / "office"
        / "pdf_form_filler"
        / "kb"
    )
    if repo_candidate.is_dir():
        return repo_candidate
    try:
        import skills.office.pdf_form_filler.kb as kb_pkg

        return Path(kb_pkg.__file__).resolve().parent
    except Exception:
        return repo_candidate


def default_user_pdf_templates_dir() -> Path:
    """Return the default user-level PDF templates directory."""
    from skillware.core.config import global_config_dir

    return global_config_dir() / DEFAULT_PDF_TEMPLATES_DIRNAME


def project_pdf_templates_dir(start: Optional[Path] = None) -> Optional[Path]:
    """Read ``pdf.templates_dir`` from the nearest ``.skillware.yaml`` if present."""
    from skillware.core.config import find_project_config_file

    cfg_path = find_project_config_file(start)
    if cfg_path is None:
        return None
    try:
        data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    pdf_cfg = data.get("pdf")
    if isinstance(pdf_cfg, dict) and pdf_cfg.get("templates_dir"):
        raw = str(pdf_cfg["templates_dir"]).strip()
        if raw:
            p = Path(raw).expanduser()
            return p if p.is_absolute() else (cfg_path.parent / p).resolve()
    return None


def resolve_active_templates_dir(
    *,
    env_templates_dir: Optional[str] = None,
    start: Optional[Path] = None,
) -> Tuple[str, Path]:
    """
    Resolve the primary writable template directory using 3-tier precedence:
    1. ``PDF_TEMPLATES_DIR`` env var
    2. Project ``.skillware.yaml`` -> ``pdf.templates_dir``
    3. User config ``~/.config/skillware/pdf_templates/`` (or ``%APPDATA%`` on Windows)
    """
    env_val = (
        env_templates_dir
        if env_templates_dir is not None
        else os.environ.get(ENV_PDF_TEMPLATES_DIR, "")
    ).strip()
    if env_val:
        return ("env", Path(env_val).expanduser().resolve())

    proj_dir = project_pdf_templates_dir(start)
    if proj_dir is not None:
        return ("project", proj_dir)

    return ("user", default_user_pdf_templates_dir())


def get_template_roots(
    *,
    env_templates_dir: Optional[str] = None,
    start: Optional[Path] = None,
    include_bundled: bool = True,
) -> List[TemplateRoot]:
    """Return ordered template roots following 3-tier + bundled precedence."""
    roots: List[TemplateRoot] = []
    seen_paths: Set[Path] = set()

    def _add(tier: str, path: Path) -> None:
        resolved = path.expanduser().resolve()
        if resolved not in seen_paths:
            seen_paths.add(resolved)
            roots.append(TemplateRoot(tier=tier, path=resolved))

    env_val = (
        env_templates_dir
        if env_templates_dir is not None
        else os.environ.get(ENV_PDF_TEMPLATES_DIR, "")
    ).strip()
    if env_val:
        _add("env", Path(env_val))

    proj_dir = project_pdf_templates_dir(start)
    if proj_dir is not None:
        _add("project", proj_dir)

    _add("user", default_user_pdf_templates_dir())

    if include_bundled:
        _add("bundled", bundled_pdf_kb_dir())

    return roots


def save_project_pdf_templates_dir(
    templates_dir: Path,
    *,
    start: Optional[Path] = None,
) -> Path:
    """Persist ``pdf.templates_dir`` in ``.skillware.yaml`` without clobbering other keys."""
    from skillware.core.config import clear_config_cache, project_config_write_path

    target = project_config_write_path(start)
    target.parent.mkdir(parents=True, exist_ok=True)
    document: Dict[str, Any] = {}
    if target.is_file():
        raw = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
        if isinstance(raw, dict):
            document = dict(raw)

    pdf_block = document.get("pdf")
    if not isinstance(pdf_block, dict):
        pdf_block = {}
    else:
        pdf_block = dict(pdf_block)

    try:
        rel = templates_dir.resolve().relative_to(target.parent.resolve())
        pdf_block["templates_dir"] = f"./{rel.as_posix()}"
    except ValueError:
        pdf_block["templates_dir"] = str(templates_dir.resolve())

    document["pdf"] = pdf_block
    target.write_text(
        yaml.safe_dump(document, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    clear_config_cache()
    return target.resolve()


def init_templates_dir(
    custom_dir: Optional[str] = None,
    *,
    output_dir: Optional[str] = None,
    start: Optional[Path] = None,
) -> Tuple[Path, Optional[Path]]:
    """
    Create the PDF templates directory (and optionally configure ``pdf.output_dir``).

    If ``custom_dir`` is provided, creates that directory and records it in
    project ``.skillware.yaml`` under ``pdf.templates_dir``.
    If ``output_dir`` is provided, creates that directory and records it in
    project ``.skillware.yaml`` under ``pdf.output_dir``.
    Returns ``(created_templates_dir, project_config_path_or_none)``.
    """
    cfg_path: Optional[Path] = None
    if custom_dir:
        base = (start or Path.cwd()).resolve()
        raw_path = Path(custom_dir).expanduser()
        target_dir = (
            raw_path.resolve()
            if raw_path.is_absolute()
            else (base / raw_path).resolve()
        )
        target_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = save_project_pdf_templates_dir(target_dir, start=start)
    else:
        target_dir = default_user_pdf_templates_dir()
        target_dir.mkdir(parents=True, exist_ok=True)

    if output_dir:
        _, out_cfg = save_pdf_output_dir(output_dir, global_scope=False, start=start)
        cfg_path = out_cfg

    return target_dir, cfg_path


def is_xfa_document(doc: Any) -> bool:
    """Return True if a PyMuPDF document contains a dynamic XFA form."""
    if getattr(doc, "is_xfa", False):
        return True
    try:
        cat_xref = doc.pdf_catalog()
        acro_val = doc.xref_get_key(cat_xref, "AcroForm/XFA")
        if acro_val[0] not in ("null", "undefined"):
            return True
        acro_type, acro_str = doc.xref_get_key(cat_xref, "AcroForm")
        if acro_type == "xref":
            acro_xref = int(acro_str.replace("0 R", "").strip())
            xfa_val = doc.xref_get_key(acro_xref, "XFA")
            if xfa_val[0] not in ("null", "undefined"):
                return True
    except Exception:
        pass
    return False


def _widget_button_states(widget: Any) -> List[str]:
    """Extract non-Off export state names from a PyMuPDF button widget."""
    states: List[str] = []
    try:
        raw = widget.button_states()
    except Exception:
        raw = None

    if isinstance(raw, dict):
        for key in ("normal", "down"):
            vals = raw.get(key)
            if isinstance(vals, (list, tuple, set)):
                for val in vals:
                    s = str(val)
                    if s and s.lower() != "off" and s not in states:
                        states.append(s)
    elif isinstance(raw, (list, tuple, set)):
        for val in raw:
            s = str(val)
            if s and s.lower() != "off" and s not in states:
                states.append(s)

    on_state = None
    try:
        on_state = widget.on_state()
    except Exception:
        on_state = None
    if on_state:
        s = str(on_state)
        if s.lower() != "off" and s not in states:
            states.append(s)

    return states


def _widget_choice_values(widget: Any) -> List[str]:
    """Extract dropdown/listbox choice values from a PyMuPDF widget."""
    choices: List[str] = []
    raw = getattr(widget, "choice_values", None)
    if not raw:
        return choices
    for item in raw:
        if isinstance(item, (list, tuple)) and item:
            val = str(item[0])
        else:
            val = str(item)
        if val and val not in choices:
            choices.append(val)
    return choices


def _extract_nearby_text(page: Any, rect: Any, radius: int = 100) -> str:
    """Extract printed text near a widget bounding box."""
    fitz = _require_fitz()
    search_rect = fitz.Rect(rect)
    search_rect.x0 -= radius
    search_rect.y0 -= radius
    search_rect.x1 += radius
    search_rect.y1 += radius
    search_rect.intersect(page.rect)
    text = page.get_text("text", clip=search_rect).strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " | ".join(lines)


def _slugify_snake(text: str, fallback: str = "field") -> str:
    """Convert arbitrary text to a clean snake_case semantic identifier."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    cleaned = re.sub(r"_+", "_", cleaned)
    if not cleaned or cleaned[0].isdigit():
        if cleaned:
            cleaned = f"f_{cleaned}"
        else:
            cleaned = fallback
    # Keep semantic IDs concise (up to 48 chars)
    if len(cleaned) > 48:
        cleaned = cleaned[:48].rstrip("_")
    return cleaned or fallback


def _extract_closest_label(page: Any, rect: Any, radius: int = 100) -> str:
    """Extract the printed text line closest to a widget bounding box within radius."""
    fitz = _require_fitz()
    search_rect = fitz.Rect(rect)
    search_rect.x0 -= radius
    search_rect.y0 -= radius
    search_rect.x1 += radius
    search_rect.y1 += radius
    search_rect.intersect(page.rect)

    wx = (rect.x0 + rect.x1) / 2.0
    wy = (rect.y0 + rect.y1) / 2.0
    best_text = ""
    best_dist = float("inf")

    try:
        blocks = page.get_text("dict", clip=search_rect).get("blocks") or []
        for blk in blocks:
            for line in blk.get("lines") or []:
                spans = line.get("spans") or []
                txt = "".join(str(s.get("text") or "") for s in spans).strip()
                if not txt:
                    continue
                bbox = line.get("bbox")
                if not bbox or len(bbox) < 4:
                    continue
                lx = (bbox[0] + bbox[2]) / 2.0
                ly = (bbox[1] + bbox[3]) / 2.0
                dist = (lx - wx) ** 2 + (ly - wy) ** 2
                if dist < best_dist:
                    best_dist = dist
                    best_text = txt
    except Exception:
        pass

    if best_text:
        return best_text
    nearby = _extract_nearby_text(page, rect, radius=radius)
    return nearby.split(" | ")[0].strip() if nearby else ""


def _is_sensitive_label(label: str, field_id: str, native_name: str = "") -> bool:
    """Return True when label, field ID, or native name matches PII sensitivity indicators."""
    haystack = f"{label} {field_id} {native_name}".lower()
    return any(kw in haystack for kw in _PII_KEYWORDS)


def _infer_profile_key(
    label: str, field_id: str, native_name: str = ""
) -> Optional[str]:
    """Infer a standard ``addressbook.yaml`` ``legal_profile`` key from field metadata."""
    haystack = f"{label} {field_id} {native_name}".lower()
    if any(
        k in haystack for k in ("date of birth", "date_of_birth", "dob", "birth date")
    ):
        return "date_of_birth"
    if any(k in haystack for k in ("citizenship", "nationality")):
        return "citizenship"
    if any(k in haystack for k in ("foreign tax", "foreign_tin", "ftin")):
        return "tin.foreign"
    if "giin" in haystack:
        return "tin.giin"
    if any(k in haystack for k in ("ein", "employer identification")):
        return "tin.us_ein"
    if any(k in haystack for k in ("ssn", "social security", "itin", "u.s. taxpayer")):
        return "tin.us"
    if any(k in haystack for k in ("tax id", "tax_id", "tin", "afm", "vat")):
        return "tin.local"
    if any(k in haystack for k in ("city", "state", "postal", "zip")) and any(
        k in haystack for k in ("city", "postal", "zip")
    ):
        return "residence_address.city_state_postal"
    if any(
        k in haystack
        for k in ("street", "permanent residence address", "address_street")
    ):
        return "residence_address.street"
    if "country" in haystack and "citizen" not in haystack:
        return "residence_address.country"
    if any(
        k in haystack
        for k in ("beneficial owner", "legal name", "legal_name", "organization_name")
    ):
        return "legal_name"
    if "email" in haystack:
        return "email"
    if "phone" in haystack or "telephone" in haystack:
        return "phone"
    return None


def inspect_pdf(pdf_path: Path) -> Dict[str, Any]:
    """
    Inspect a single PDF file and return its XFA status, widgets, and radio groups.
    """
    fitz = _require_fitz()
    path = Path(pdf_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found: {path}")

    doc = fitz.open(str(path))
    try:
        xfa = is_xfa_document(doc)
        widgets_info: List[Dict[str, Any]] = []
        radio_groups: Dict[str, Dict[str, Any]] = {}

        for page_index, page in enumerate(doc):
            for widget in page.widgets() or []:
                native_name = str(getattr(widget, "field_name", "") or "")
                w_type = int(getattr(widget, "field_type", _WIDGET_TYPE_TEXT))
                schema_type = _WIDGET_TYPE_TO_SCHEMA_TYPE.get(w_type, "text")
                rect = getattr(widget, "rect", None)
                bbox = (
                    [
                        round(rect.x0, 2),
                        round(rect.y0, 2),
                        round(rect.x1, 2),
                        round(rect.y1, 2),
                    ]
                    if rect is not None
                    else []
                )
                label_ctx = (
                    _extract_nearby_text(page, rect, radius=100)
                    if rect is not None
                    else ""
                )
                button_states = _widget_button_states(widget)
                choice_values = _widget_choice_values(widget)

                entry: Dict[str, Any] = {
                    "native_name": native_name,
                    "field_type": schema_type,
                    "widget_type_code": w_type,
                    "page": page_index,
                    "bbox": bbox,
                    "label_context": label_ctx,
                    "current_value": getattr(widget, "field_value", None),
                }
                if button_states:
                    entry["button_states"] = button_states
                if choice_values:
                    entry["choice_values"] = choice_values
                widgets_info.append(entry)

                if schema_type == "radio" and native_name:
                    grp = radio_groups.setdefault(
                        native_name,
                        {
                            "native_name": native_name,
                            "page": page_index,
                            "export_values": [],
                        },
                    )
                    for st in button_states:
                        if st not in grp["export_values"]:
                            grp["export_values"].append(st)

        return {
            "pdf_path": str(path),
            "pages": len(doc),
            "is_xfa": xfa,
            "pdf_type": "XFA" if xfa else "AcroForm",
            "widget_count": len(widgets_info),
            "widgets": widgets_info,
            "radio_groups": list(radio_groups.values()),
        }
    finally:
        doc.close()


def _detect_page_section_headers(page: Any) -> List[Tuple[float, str]]:
    """
    Detect structural section headings (e.g., ``Part I: ...``, ``Section 2 ...``)
    on a PDF page, returned as ``(y0, title)`` sorted top-to-bottom.
    """
    headers: List[Tuple[float, str]] = []
    try:
        blocks = page.get_text("dict").get("blocks") or []
    except Exception:
        return headers

    candidates: List[Tuple[float, float, str]] = []
    for blk in blocks:
        for line in blk.get("lines") or []:
            spans = line.get("spans") or []
            txt = " ".join(
                str(s.get("text") or "").strip()
                for s in spans
                if str(s.get("text") or "").strip()
            ).strip()
            if not txt or len(txt) < 6 or len(txt) > 110:
                continue
            if not _SECTION_HEADER_RE.match(txt):
                continue
            bbox = line.get("bbox")
            if not bbox or len(bbox) < 4:
                continue
            candidates.append((float(bbox[1]), float(bbox[0]), txt))

    candidates.sort(key=lambda item: (item[0], item[1]))
    for y0, _x0, txt in candidates:
        if headers and abs(y0 - headers[-1][0]) < 6.0:
            # Merge split spans on the same horizontal band if needed
            prev_y, prev_txt = headers[-1]
            if txt not in prev_txt:
                headers[-1] = (prev_y, f"{prev_txt} {txt}".strip())
            continue
        headers.append((y0, txt))
    return headers


def generate_schema_map(
    pdf_path: Path,
    out_path: Optional[Path] = None,
    *,
    force: bool = False,
) -> Tuple[Path, Dict[str, Any]]:
    """
    Auto-generate a boilerplate YAML schema map from a static AcroForm PDF.

    Safety invariant: never overwrites an existing YAML map unless ``force=True``.
    """
    fitz = _require_fitz()
    src = Path(pdf_path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(f"PDF file not found: {src}")

    target = (
        Path(out_path).expanduser().resolve() if out_path else src.with_suffix(".yaml")
    )
    if target.exists() and not force:
        raise FileExistsError(
            f"Schema map already exists at '{target}'. Pass --force to overwrite."
        )

    doc = fitz.open(str(src))
    try:
        if is_xfa_document(doc):
            raise ValueError(
                f"Dynamic XFA form detected in '{src.name}'. Static AcroForm PDF is required."
            )

        sections: List[Dict[str, Any]] = []
        used_ids: Set[str] = set()
        used_section_ids: Set[str] = set()

        for page_index, page in enumerate(doc):
            page_entries: List[Tuple[float, Dict[str, Any]]] = []
            seen_radios: Dict[str, Dict[str, Any]] = {}

            raw_widgets = list(page.widgets() or [])
            raw_widgets.sort(
                key=lambda w: (
                    round(float(getattr(getattr(w, "rect", None), "y0", 0.0)), 1),
                    round(float(getattr(getattr(w, "rect", None), "x0", 0.0)), 1),
                )
            )

            for widget in raw_widgets:
                native_name = str(getattr(widget, "field_name", "") or "").strip()
                if not native_name:
                    continue
                w_type = int(getattr(widget, "field_type", _WIDGET_TYPE_TEXT))
                schema_type = _WIDGET_TYPE_TO_SCHEMA_TYPE.get(w_type, "text")
                rect = getattr(widget, "rect", None)
                closest = (
                    _extract_closest_label(page, rect, radius=100)
                    if rect is not None
                    else ""
                )
                primary_label = closest or native_name

                if schema_type == "radio":
                    states = _widget_button_states(widget)
                    if native_name in seen_radios:
                        existing = seen_radios[native_name]
                        opts = existing.setdefault("options", [])
                        for st in states:
                            if st not in opts:
                                opts.append(st)
                        continue

                base_id = _slugify_snake(
                    closest if closest else native_name,
                    fallback=_slugify_snake(native_name, fallback="field"),
                )
                sem_id = base_id
                suffix = 2
                while sem_id in used_ids:
                    sem_id = f"{base_id}_{suffix}"
                    suffix += 1
                used_ids.add(sem_id)

                field_entry: Dict[str, Any] = {
                    "id": sem_id,
                    "pdf_field_name": native_name,
                    "field_type": schema_type,
                    "page": page_index,
                    "label": primary_label,
                    "required": False,
                }

                if _is_sensitive_label(primary_label, sem_id, native_name):
                    field_entry["sensitive"] = True

                inferred_pk = _infer_profile_key(primary_label, sem_id, native_name)
                if inferred_pk:
                    field_entry["profile_key"] = inferred_pk

                if schema_type == "checkbox":
                    states = _widget_button_states(widget)
                    if states:
                        field_entry["export_value"] = states[0]
                elif schema_type == "radio":
                    states = _widget_button_states(widget)
                    field_entry["options"] = states
                    seen_radios[native_name] = field_entry
                elif schema_type == "combobox":
                    choices = _widget_choice_values(widget)
                    if choices:
                        field_entry["options"] = choices

                w_y0 = float(getattr(rect, "y0", 0.0)) if rect is not None else 0.0
                page_entries.append((w_y0, field_entry))

            if not page_entries:
                continue

            detected_headers = _detect_page_section_headers(page)
            # Only chunk by header when at least 2 headers or a header precedes widgets
            usable_headers = [
                (hy, htitle)
                for hy, htitle in detected_headers
                if any(wy >= hy - 4.0 for wy, _ in page_entries)
            ]

            if len(usable_headers) >= 2:
                grouped: Dict[int, List[Dict[str, Any]]] = {}
                for wy, f_entry in page_entries:
                    assigned_idx = -1
                    for idx, (hy, _htitle) in enumerate(usable_headers):
                        if hy <= wy + 4.0:
                            assigned_idx = idx
                        else:
                            break
                    grouped.setdefault(assigned_idx, []).append(f_entry)

                for idx in sorted(grouped.keys()):
                    fields_chunk = grouped[idx]
                    if idx == -1:
                        sec_title = f"Page {page_index + 1} Header"
                        base_sec_id = f"page_{page_index + 1}_header"
                    else:
                        sec_title = usable_headers[idx][1]
                        base_sec_id = _slugify_snake(
                            sec_title,
                            fallback=f"page_{page_index + 1}_section_{idx + 1}",
                        )
                    sec_id = base_sec_id
                    sec_suffix = 2
                    while sec_id in used_section_ids:
                        sec_id = f"{base_sec_id}_{sec_suffix}"
                        sec_suffix += 1
                    used_section_ids.add(sec_id)
                    sections.append(
                        {
                            "id": sec_id,
                            "title": sec_title,
                            "fields": fields_chunk,
                        }
                    )
            else:
                sec_id = f"page_{page_index + 1}"
                used_section_ids.add(sec_id)
                sections.append(
                    {
                        "id": sec_id,
                        "title": f"Page {page_index + 1}",
                        "fields": [f_entry for _, f_entry in page_entries],
                    }
                )

        # Compute source_pdf relative to target's directory when possible
        try:
            rel_pdf = src.relative_to(target.parent).as_posix()
        except ValueError:
            rel_pdf = src.name

        schema_doc: Dict[str, Any] = {
            "form_id": _slugify_snake(src.stem, fallback="custom_form"),
            "template_id": src.stem,
            "title": src.stem.replace("_", " ").replace("-", " ").title(),
            "source_pdf": rel_pdf,
            "pages": len(doc),
            "sections": sections,
        }

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            yaml.safe_dump(schema_doc, sort_keys=False, default_flow_style=False),
            encoding="utf-8",
        )
        return target, schema_doc
    finally:
        doc.close()


def validate_schema_map(pdf_path: Path, schema_path: Path) -> ValidationResult:
    """
    Validate a YAML schema map against a physical PDF's AcroForm widgets.
    """
    fitz = _require_fitz()
    pdf = Path(pdf_path).expanduser().resolve()
    schema_file = Path(schema_path).expanduser().resolve()

    errors: List[str] = []
    warnings: List[str] = []

    if not pdf.is_file():
        return ValidationResult(
            valid=False,
            pdf_path=str(pdf),
            schema_path=str(schema_file),
            errors=[f"PDF file not found: {pdf}"],
        )
    if not schema_file.is_file():
        return ValidationResult(
            valid=False,
            pdf_path=str(pdf),
            schema_path=str(schema_file),
            errors=[f"Schema file not found: {schema_file}"],
        )

    try:
        schema = yaml.safe_load(schema_file.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        return ValidationResult(
            valid=False,
            pdf_path=str(pdf),
            schema_path=str(schema_file),
            errors=[f"Invalid YAML syntax: {exc}"],
        )

    if not isinstance(schema, dict):
        return ValidationResult(
            valid=False,
            pdf_path=str(pdf),
            schema_path=str(schema_file),
            errors=["Schema root must be a YAML mapping."],
        )

    doc = fitz.open(str(pdf))
    try:
        if is_xfa_document(doc):
            return ValidationResult(
                valid=False,
                pdf_path=str(pdf),
                schema_path=str(schema_file),
                is_xfa=True,
                errors=[
                    "PDF is a dynamic XFA form (doc.is_xfa == True); static AcroForm required."
                ],
            )

        # Index physical widgets by (page_index, field_name)
        widgets_by_page_name: Dict[Tuple[int, str], List[Dict[str, Any]]] = {}
        page_count = len(doc)
        for p_idx, page in enumerate(doc):
            for widget in page.widgets() or []:
                w_name = str(getattr(widget, "field_name", "") or "")
                if not w_name:
                    continue
                widgets_by_page_name.setdefault((p_idx, w_name), []).append(
                    {
                        "type": int(getattr(widget, "field_type", _WIDGET_TYPE_TEXT)),
                        "button_states": _widget_button_states(widget),
                        "choice_values": _widget_choice_values(widget),
                    }
                )

        sections = schema.get("sections")
        if not isinstance(sections, list):
            errors.append("Schema must define a 'sections' list.")
            sections = []

        field_count = 0
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            for fld in sec.get("fields") or []:
                if not isinstance(fld, dict):
                    continue
                field_count += 1
                fid = str(fld.get("id") or f"field_{field_count}")
                pdf_name = str(fld.get("pdf_field_name") or "").strip()
                f_type = str(fld.get("field_type") or "text").strip().lower()
                page_idx = fld.get("page", 0)

                if not pdf_name:
                    errors.append(f"[{fid}] Missing required 'pdf_field_name'.")
                    continue
                if (
                    not isinstance(page_idx, int)
                    or page_idx < 0
                    or page_idx >= page_count
                ):
                    errors.append(
                        f"[{fid}] Page {page_idx} out of range (PDF has {page_count} page(s))."
                    )
                    continue

                matched = widgets_by_page_name.get((page_idx, pdf_name))
                if not matched:
                    errors.append(
                        f"[{fid}] Widget '{pdf_name}' not found on page {page_idx}."
                    )
                    continue

                expected_codes = _SCHEMA_TYPE_TO_WIDGET_TYPES.get(f_type)
                actual_codes = {w["type"] for w in matched}
                if expected_codes is None:
                    errors.append(f"[{fid}] Unknown field_type '{f_type}'.")
                elif not (actual_codes & expected_codes):
                    actual_names = sorted(
                        {
                            _WIDGET_TYPE_TO_SCHEMA_TYPE.get(c, str(c))
                            for c in actual_codes
                        }
                    )
                    errors.append(
                        f"[{fid}] Type mismatch for '{pdf_name}': schema says '{f_type}', "
                        f"PDF widget is {', '.join(actual_names)}."
                    )

                # Validate radio export_value / options against button_states()
                if f_type == "radio":
                    all_states: Set[str] = set()
                    for w in matched:
                        all_states.update(w["button_states"])
                    export_val = fld.get("export_value")
                    if (
                        export_val is not None
                        and all_states
                        and str(export_val) not in all_states
                    ):
                        errors.append(
                            f"[{fid}] Radio export_value '{export_val}' not in widget states "
                            f"{sorted(all_states)}."
                        )
                    yaml_opts = fld.get("options")
                    if isinstance(yaml_opts, list) and all_states:
                        for opt in yaml_opts:
                            val = (
                                str(opt.get("export_value"))
                                if isinstance(opt, dict) and "export_value" in opt
                                else str(opt)
                            )
                            if val not in all_states:
                                errors.append(
                                    f"[{fid}] Radio option '{val}' not in widget states "
                                    f"{sorted(all_states)}."
                                )

                # Validate combobox/dropdown options against choice_values
                if f_type in ("combobox", "dropdown", "listbox"):
                    all_choices: Set[str] = set()
                    for w in matched:
                        all_choices.update(w["choice_values"])
                    yaml_opts = fld.get("options")
                    if isinstance(yaml_opts, list) and all_choices:
                        for opt in yaml_opts:
                            val = str(opt)
                            if val not in all_choices:
                                errors.append(
                                    f"[{fid}] Dropdown option '{val}' not in widget choice_values "
                                    f"{sorted(all_choices)}."
                                )

        return ValidationResult(
            valid=len(errors) == 0,
            pdf_path=str(pdf),
            schema_path=str(schema_file),
            field_count=field_count,
            is_xfa=False,
            errors=errors,
            warnings=warnings,
        )
    finally:
        doc.close()


def _discover_pdfs_in_root(root: Path) -> List[Tuple[Path, Optional[Path]]]:
    """
    Discover ``(pdf_path, matching_schema_path_or_none)`` pairs under a template root.

    Supports both flat layout (``root/form.pdf`` + ``root/form.yaml``) and
    bundled KB layout (``root/templates/form.pdf`` + ``root/schemas/form.yaml``).
    """
    if not root.is_dir():
        return []

    pairs: List[Tuple[Path, Optional[Path]]] = []
    seen_pdfs: Set[Path] = set()

    # 1. Bundled/structured layout: templates/*.pdf + schemas/*.yaml
    templates_sub = root / "templates"
    schemas_sub = root / "schemas"
    if templates_sub.is_dir():
        for pdf in sorted(templates_sub.glob("*.pdf")):
            resolved = pdf.resolve()
            if resolved in seen_pdfs:
                continue
            seen_pdfs.add(resolved)
            schema_candidate = schemas_sub / f"{pdf.stem}.yaml"
            if not schema_candidate.is_file():
                schema_candidate = root / f"{pdf.stem}.yaml"
            pairs.append(
                (resolved, schema_candidate if schema_candidate.is_file() else None)
            )

    # 2. Flat layout: root/*.pdf + root/*.yaml
    for pdf in sorted(root.glob("*.pdf")):
        resolved = pdf.resolve()
        if resolved in seen_pdfs:
            continue
        seen_pdfs.add(resolved)
        schema_candidate = root / f"{pdf.stem}.yaml"
        if not schema_candidate.is_file() and schemas_sub.is_dir():
            schema_candidate = schemas_sub / f"{pdf.stem}.yaml"
        pairs.append(
            (resolved, schema_candidate if schema_candidate.is_file() else None)
        )

    return pairs


def audit_templates(
    *,
    env_templates_dir: Optional[str] = None,
    start: Optional[Path] = None,
    include_bundled: bool = True,
) -> List[TemplateAuditEntry]:
    """Scan all configured template roots and audit PDF type and schema map validity."""
    fitz = _require_fitz()
    entries: List[TemplateAuditEntry] = []
    seen_ids: Set[Tuple[str, str]] = set()

    for root in get_template_roots(
        env_templates_dir=env_templates_dir,
        start=start,
        include_bundled=include_bundled,
    ):
        for pdf_path, schema_path in _discover_pdfs_in_root(root.path):
            tid = pdf_path.stem
            key = (root.tier, tid)
            if key in seen_ids:
                continue
            seen_ids.add(key)

            try:
                doc = fitz.open(str(pdf_path))
                try:
                    xfa = is_xfa_document(doc)
                finally:
                    doc.close()
            except Exception as exc:
                entries.append(
                    TemplateAuditEntry(
                        template_id=tid,
                        source=root.tier,
                        pdf_type="Invalid",
                        map_status="[MAP INVALID]",
                        fields=0,
                        path=pdf_path,
                        schema_path=schema_path,
                        errors=[f"Failed to open PDF: {exc}"],
                    )
                )
                continue

            if xfa:
                entries.append(
                    TemplateAuditEntry(
                        template_id=tid,
                        source=root.tier,
                        pdf_type="XFA [!]",
                        map_status="[UNSUPPORTED]",
                        fields=None,
                        path=pdf_path,
                        schema_path=schema_path,
                        errors=["Dynamic XFA form is not supported."],
                    )
                )
                continue

            if schema_path is None:
                entries.append(
                    TemplateAuditEntry(
                        template_id=tid,
                        source=root.tier,
                        pdf_type="AcroForm",
                        map_status="[UNMAPPED]",
                        fields=0,
                        path=pdf_path,
                        schema_path=None,
                    )
                )
                continue

            result = validate_schema_map(pdf_path, schema_path)
            if result.valid:
                entries.append(
                    TemplateAuditEntry(
                        template_id=tid,
                        source=root.tier,
                        pdf_type="AcroForm",
                        map_status="[MAPPED - VALID]",
                        fields=result.field_count,
                        path=pdf_path,
                        schema_path=schema_path,
                    )
                )
            else:
                entries.append(
                    TemplateAuditEntry(
                        template_id=tid,
                        source=root.tier,
                        pdf_type="AcroForm",
                        map_status="[MAP INVALID]",
                        fields=result.field_count,
                        path=pdf_path,
                        schema_path=schema_path,
                        errors=result.errors,
                    )
                )

    return entries


def import_pdf_forms(
    source_path: Path,
    *,
    dest_dir: Optional[Path] = None,
    symlink: bool = False,
    auto_map: bool = False,
    env_templates_dir: Optional[str] = None,
    start: Optional[Path] = None,
) -> Tuple[Path, List[ImportItemResult]]:
    """
    Batch-import PDF forms from ``source_path`` (directory or single PDF) into the
    active template directory.
    """
    fitz = _require_fitz()
    src = Path(source_path).expanduser().resolve()
    if not src.exists():
        raise FileNotFoundError(f"Source path not found: {src}")

    if dest_dir is None:
        _, target_dir = resolve_active_templates_dir(
            env_templates_dir=env_templates_dir, start=start
        )
    else:
        target_dir = Path(dest_dir).expanduser().resolve()

    target_dir.mkdir(parents=True, exist_ok=True)

    pdf_files: List[Path] = [src] if src.is_file() else sorted(src.glob("*.pdf"))
    results: List[ImportItemResult] = []

    for pdf in pdf_files:
        try:
            doc = fitz.open(str(pdf))
            try:
                xfa = is_xfa_document(doc)
            finally:
                doc.close()
        except Exception as exc:
            results.append(
                ImportItemResult(
                    source_path=pdf,
                    dest_path=None,
                    status="invalid",
                    message=f"Not a valid PDF: {exc}",
                )
            )
            continue

        dest_pdf = target_dir / pdf.name
        if dest_pdf.exists() or dest_pdf.is_symlink():
            if dest_pdf.resolve() != pdf.resolve():
                if symlink:
                    dest_pdf.unlink()
                    os.symlink(pdf, dest_pdf)
                else:
                    shutil.copy2(pdf, dest_pdf)
        else:
            if symlink:
                os.symlink(pdf, dest_pdf)
            else:
                shutil.copy2(pdf, dest_pdf)

        if xfa:
            results.append(
                ImportItemResult(
                    source_path=pdf,
                    dest_path=dest_pdf,
                    status="xfa",
                    message="Imported, but dynamic XFA form detected (unsupported for filling).",
                )
            )
            continue

        map_path: Optional[Path] = None
        map_status: Optional[str] = None
        if auto_map:
            candidate_map = dest_pdf.with_suffix(".yaml")
            if candidate_map.exists():
                map_path = candidate_map
                map_status = "preserved"
            else:
                try:
                    map_path, _ = generate_schema_map(
                        dest_pdf, candidate_map, force=False
                    )
                    map_status = "generated"
                except Exception as exc:
                    map_status = f"error: {exc}"

        results.append(
            ImportItemResult(
                source_path=pdf,
                dest_path=dest_pdf,
                status="imported",
                message="Linked" if symlink else "Copied",
                map_path=map_path,
                map_status=map_status,
            )
        )

    return target_dir, results


def generate_missing_maps(
    *,
    env_templates_dir: Optional[str] = None,
    start: Optional[Path] = None,
) -> List[Tuple[Path, Optional[Path], str]]:
    """
    Generate schema maps for all unmapped AcroForm PDFs in the active writable
    template directory. Never overwrites existing maps.

    Returns list of ``(pdf_path, map_path_or_none, status_message)``.
    """
    _require_fitz()
    _, active_dir = resolve_active_templates_dir(
        env_templates_dir=env_templates_dir, start=start
    )
    outcomes: List[Tuple[Path, Optional[Path], str]] = []
    if not active_dir.is_dir():
        return outcomes

    for pdf_path, schema_path in _discover_pdfs_in_root(active_dir):
        if schema_path is not None:
            outcomes.append((pdf_path, schema_path, "skipped (map exists)"))
            continue
        try:
            target_map = pdf_path.with_suffix(".yaml")
            created, _ = generate_schema_map(pdf_path, target_map, force=False)
            outcomes.append((pdf_path, created, "generated"))
        except ValueError as exc:
            outcomes.append((pdf_path, None, f"skipped ({exc})"))
        except Exception as exc:
            outcomes.append((pdf_path, None, f"error ({exc})"))
    return outcomes

# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Template & section-chunked schema registry for office/pdf_form_filler."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import yaml


def _bundled_kb_dir() -> Path:
    return Path(__file__).resolve().parent


def _user_templates_dir() -> Path:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "skillware" / "pdf_templates"
    return Path.home() / ".config" / "skillware" / "pdf_templates"


def _project_templates_dir() -> Optional[Path]:
    cfg_path = Path.cwd() / ".skillware.yaml"
    if not cfg_path.is_file():
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
            return p if p.is_absolute() else (Path.cwd() / p)
    return None


def get_template_roots() -> List[Tuple[str, Path]]:
    """Return ordered (tier_name, root_dir) pairs per 3-tier + bundled precedence."""
    roots: List[Tuple[str, Path]] = []

    env_dir = os.environ.get("PDF_TEMPLATES_DIR", "").strip()
    if env_dir:
        roots.append(("env", Path(env_dir).expanduser()))

    proj_dir = _project_templates_dir()
    if proj_dir is not None:
        roots.append(("project", proj_dir))

    roots.append(("user", _user_templates_dir()))
    roots.append(("bundled", _bundled_kb_dir()))
    return roots


def _iter_schema_files() -> List[Tuple[str, Path, Path]]:
    """Yield (tier, root_dir, schema_path) in precedence order."""
    found: List[Tuple[str, Path, Path]] = []
    for tier, root in get_template_roots():
        if not root.exists():
            continue
        schemas_dir = root / "schemas" if (root / "schemas").is_dir() else root
        for yml in sorted(schemas_dir.glob("*.yaml")):
            found.append((tier, root, yml))
    return found


def load_schema_file(
    schema_path: Path, tier: str = "custom", root: Optional[Path] = None
) -> Dict[str, Any]:
    """Load and normalize a template YAML schema."""
    data = yaml.safe_load(schema_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Schema '{schema_path}' must be a YAML mapping.")
    data.setdefault("template_id", schema_path.stem)
    data.setdefault("form_id", data["template_id"])
    data["_tier"] = tier
    data["_root_dir"] = str((root or schema_path.parent).resolve())
    data["_schema_path"] = str(schema_path.resolve())
    return data


def resolve_template_pdf_path(schema: Dict[str, Any]) -> Optional[Path]:
    """Resolve source_pdf safely inside the schema's root directory."""
    source_pdf = schema.get("source_pdf")
    if not source_pdf:
        return None
    root_dir = Path(schema.get("_root_dir") or _bundled_kb_dir()).resolve()
    rel = str(source_pdf).strip()
    # Allow schemas that write "kb/templates/foo.pdf" or "templates/foo.pdf"
    if rel.startswith("kb/"):
        rel = rel[3:]
    candidate = (root_dir / rel).resolve()
    try:
        candidate.relative_to(root_dir)
    except ValueError as exc:
        raise ValueError(
            f"Unsafe source_pdf '{source_pdf}' escapes template root '{root_dir}'."
        ) from exc
    if not candidate.is_file():
        return None
    return candidate


def list_templates(
    category: Optional[str] = None,
    jurisdiction: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Return summary metadata for all discovered templates."""
    cat_filter = category.strip().lower() if category else None
    jur_filter = jurisdiction.strip().lower() if jurisdiction else None

    seen: Set[str] = set()
    items: List[Dict[str, Any]] = []

    for tier, root, yml_path in _iter_schema_files():
        try:
            schema = load_schema_file(yml_path, tier=tier, root=root)
        except Exception:
            continue

        tid = str(schema.get("template_id") or yml_path.stem)
        if tid in seen:
            continue
        seen.add(tid)

        t_cat = str(schema.get("category") or "").strip()
        t_jur = str(schema.get("jurisdiction") or "").strip()
        if cat_filter and t_cat.lower() != cat_filter:
            continue
        if jur_filter and t_jur.lower() != jur_filter:
            continue

        sections = schema.get("sections") or []
        field_count = sum(
            len(sec.get("fields") or []) for sec in sections if isinstance(sec, dict)
        )
        pdf_path = resolve_template_pdf_path(schema)

        items.append(
            {
                "template_id": tid,
                "form_id": schema.get("form_id", tid),
                "title": schema.get("title", tid),
                "revision": schema.get("revision", ""),
                "jurisdiction": t_jur,
                "category": t_cat,
                "pages": schema.get("pages", 1),
                "section_count": len(sections),
                "field_count": field_count,
                "tier": tier,
                "pdf_available": pdf_path is not None,
            }
        )

    return items


def get_template_schema(
    template_id: str,
    section: Optional[str] = None,
) -> Dict[str, Any]:
    """Load a template schema by template_id or form_id, optionally filtered to one section."""
    target = template_id.strip().lower()
    matched_schema: Optional[Dict[str, Any]] = None

    for tier, root, yml_path in _iter_schema_files():
        try:
            schema = load_schema_file(yml_path, tier=tier, root=root)
        except Exception:
            continue
        tid = str(schema.get("template_id") or "").lower()
        fid = str(schema.get("form_id") or "").lower()
        if target in (tid, fid):
            matched_schema = schema
            break

    if matched_schema is None:
        available = [t["template_id"] for t in list_templates()]
        raise KeyError(
            f"Unknown template_id '{template_id}'. Available templates: {available}"
        )

    sections = matched_schema.get("sections") or []
    section_index = [
        {
            "id": sec.get("id"),
            "title": sec.get("title"),
            "field_count": len(sec.get("fields") or []),
        }
        for sec in sections
        if isinstance(sec, dict)
    ]

    result: Dict[str, Any] = {
        "template_id": matched_schema.get("template_id"),
        "form_id": matched_schema.get("form_id"),
        "title": matched_schema.get("title"),
        "revision": matched_schema.get("revision"),
        "jurisdiction": matched_schema.get("jurisdiction"),
        "category": matched_schema.get("category"),
        "pages": matched_schema.get("pages"),
        "tier": matched_schema.get("_tier"),
        "sections_index": section_index,
        "_pdf_path": str(resolve_template_pdf_path(matched_schema) or ""),
    }

    if section is not None:
        sec_target = section.strip().lower()
        chosen = [
            sec
            for sec in sections
            if isinstance(sec, dict) and str(sec.get("id") or "").lower() == sec_target
        ]
        if not chosen:
            valid_ids = [s.get("id") for s in section_index]
            raise KeyError(
                f"Unknown section '{section}' for template '{template_id}'. "
                f"Available sections: {valid_ids}"
            )
        result["section"] = chosen[0]
        result["fields"] = chosen[0].get("fields") or []
    else:
        result["sections"] = sections

    return result


def _all_schema_fields(schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    fields: List[Dict[str, Any]] = []
    for sec in schema.get("sections") or []:
        if isinstance(sec, dict):
            for f in sec.get("fields") or []:
                if isinstance(f, dict):
                    fields.append(f)
    return fields


def _validate_date_str(val: str, date_format: str) -> bool:
    if date_format.upper() == "MM-DD-YYYY":
        try:
            datetime.strptime(val.strip(), "%m-%d-%Y")
            return True
        except ValueError:
            return False
    return bool(val.strip())


def map_edits_with_schema(
    schema: Dict[str, Any],
    edits: Dict[str, Any],
    *,
    auto_date: bool = True,
    check_required: bool = True,
) -> Tuple[Dict[str, Any], Set[str], List[Dict[str, str]]]:
    """
    Map semantic schema field IDs to native PDF field names and validate schema rules.

    Returns (native_edits, sensitive_keys, errors).
    """
    fields = _all_schema_fields(schema)
    by_id: Dict[str, Dict[str, Any]] = {}
    by_pdf: Dict[str, Dict[str, Any]] = {}
    sensitive_keys: Set[str] = set()

    for f in fields:
        fid = str(f.get("id") or "")
        pname = str(f.get("pdf_field_name") or "")
        if fid:
            by_id[fid] = f
        if pname:
            by_pdf[pname] = f
        if f.get("sensitive"):
            if fid:
                sensitive_keys.add(fid)
            if pname:
                sensitive_keys.add(pname)

    working_edits = dict(edits)

    # Auto-populate auto_date fields when omitted or "auto"
    if auto_date:
        today_mmddyyyy = datetime.now(timezone.utc).strftime("%m-%d-%Y")
        for f in fields:
            if f.get("signature_mode") == "auto_date":
                fid = str(f.get("id") or "")
                pname = str(f.get("pdf_field_name") or "")
                has_val = (
                    fid in working_edits
                    and str(working_edits[fid]).strip().lower() not in ("", "auto")
                ) or (
                    pname in working_edits
                    and str(working_edits[pname]).strip().lower() not in ("", "auto")
                )
                if not has_val and fid:
                    working_edits[fid] = today_mmddyyyy

    mapped: Dict[str, Any] = {}
    errors: List[Dict[str, str]] = []
    provided_field_ids: Set[str] = set()

    for raw_key, value in working_edits.items():
        f_def = by_id.get(raw_key) or by_pdf.get(raw_key)
        if f_def is None:
            errors.append(
                {
                    "field": raw_key,
                    "reason": f"Field '{raw_key}' is not defined in schema '{schema.get('template_id')}'.",
                }
            )
            continue

        fid = str(f_def.get("id") or raw_key)
        pname = str(f_def.get("pdf_field_name") or raw_key)
        provided_field_ids.add(fid)
        ftype = str(f_def.get("field_type") or "text").lower()

        if ftype == "date" and value is not None and str(value).strip():
            fmt = str(f_def.get("date_format") or "MM-DD-YYYY")
            if not _validate_date_str(str(value), fmt):
                errors.append(
                    {
                        "field": fid,
                        "reason": f"Field '{fid}' must match date format {fmt}.",
                    }
                )
                continue

        if ftype == "radio" and f_def.get("options"):
            opts = f_def["options"]
            val_s = str(value).strip()
            matched_opt = None
            for opt in opts:
                if not isinstance(opt, dict):
                    continue
                exp = str(opt.get("export_value") or "")
                lbl = str(opt.get("label") or "")
                if val_s.lower() in (exp.lower(), lbl.lower()):
                    matched_opt = exp or lbl
                    break
            if matched_opt is None:
                errors.append(
                    {
                        "field": fid,
                        "reason": f"Value '{value}' is not a valid radio option for '{fid}'.",
                    }
                )
                continue
            value = matched_opt

        mapped[pname] = value

    if check_required:
        for f in fields:
            if not f.get("required"):
                continue
            fid = str(f.get("id") or "")
            if fid not in provided_field_ids:
                errors.append(
                    {
                        "field": fid,
                        "reason": f"Required field '{fid}' ({f.get('label', fid)}) is missing.",
                    }
                )
            else:
                pname = str(f.get("pdf_field_name") or fid)
                val = mapped.get(pname)
                if f.get("field_type") == "checkbox":
                    if not (
                        val is True
                        or str(val).strip().lower()
                        in ("true", "1", "yes", "on", "checked")
                    ):
                        errors.append(
                            {
                                "field": fid,
                                "reason": f"Required checkbox '{fid}' must be checked (true).",
                            }
                        )
                elif val is None or not str(val).strip():
                    errors.append(
                        {
                            "field": fid,
                            "reason": f"Required field '{fid}' cannot be empty.",
                        }
                    )

    return mapped, sensitive_keys, errors


def redact_sensitive_edits(
    edits: Dict[str, Any], sensitive_keys: Set[str]
) -> Dict[str, Any]:
    """Mask PII/sensitive field values for previews and logs."""
    redacted: Dict[str, Any] = {}
    for k, v in edits.items():
        if k in sensitive_keys and v is not None:
            s = str(v)
            redacted[k] = f"***{s[-4:]}" if len(s) > 4 else "***REDACTED***"
        else:
            redacted[k] = v
    return redacted


def build_default_output_path(
    template_id: str,
    edits: Dict[str, Any],
    *,
    filler_name: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> str:
    """Generate <template_id>_<YYYYMMDD_HHMMSS>_<filler_name>.pdf in output_dir or CWD."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    raw_name = (
        filler_name
        or edits.get("beneficial_owner_name")
        or edits.get("signer_name")
        or "filled"
    )
    safe_name = (
        re.sub(r"[^a-zA-Z0-9_-]+", "_", str(raw_name).strip()).strip("_").lower()
    )
    if not safe_name:
        safe_name = "filled"
    safe_tpl = re.sub(r"[^a-zA-Z0-9_-]+", "_", template_id.strip()).strip("_").lower()
    filename = f"{safe_tpl}_{ts}_{safe_name}.pdf"
    base_dir = Path(output_dir).expanduser() if output_dir else Path.cwd()
    return str(base_dir / filename)

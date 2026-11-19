# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""CLI commands for PDF form template management, inspection, mapping, and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Optional, Tuple

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from skillware.cli_os import open_path_in_os
from skillware.cli_theme import THEMES, active_theme
from skillware.core.pdf_templates import (
    PyMuPDFMissingError,
    audit_templates,
    generate_missing_maps,
    generate_schema_map,
    get_template_roots,
    import_pdf_forms,
    init_templates_dir,
    inspect_pdf,
    resolve_active_templates_dir,
    resolve_output_dir,
    save_pdf_output_dir,
    validate_schema_map,
)

_DEFAULT_PALETTE = THEMES["pastel"]
TABLE_STYLE = _DEFAULT_PALETTE.heading_style
ID_STYLE = _DEFAULT_PALETTE.id_style
BORDER_STYLE = _DEFAULT_PALETTE.border_style
MENU_STYLE = _DEFAULT_PALETTE.menu_style
ERROR_STYLE = f"bold {_DEFAULT_PALETTE.error_color}"
ERROR_DIM_STYLE = f"dim {_DEFAULT_PALETTE.error_color}"

_NAV_EXIT = "exit"
_NAV_BACK = "back"

_PDF_SUBMENU = [
    ("1", "status", "audit active paths, templates, maps, and XFA forms"),
    ("2", "init", "initialize user/project PDF templates or output directory"),
    ("3", "import", "batch-import PDF forms from a folder"),
    ("4", "map-generate", "auto-generate boilerplate YAML schema maps"),
    ("5", "inspect", "inspect widgets, XFA status, and radio groups"),
    ("6", "map-validate", "validate a YAML schema map against a PDF"),
    ("7", "guide", "print schema specification and authoring tips"),
    ("8", "open", "open active PDF templates directory in OS file manager"),
    ("9", "output-dir", "view or set default directory for filled PDF outputs"),
]

ReadLineFn = Optional[Callable[[str], Optional[str]]]


def _apply_active_theme() -> None:
    palette = active_theme()
    global TABLE_STYLE, ID_STYLE, BORDER_STYLE, MENU_STYLE, ERROR_STYLE, ERROR_DIM_STYLE
    TABLE_STYLE = palette.heading_style
    ID_STYLE = palette.id_style
    BORDER_STYLE = palette.border_style
    MENU_STYLE = palette.menu_style
    ERROR_STYLE = f"bold {palette.error_color}"
    ERROR_DIM_STYLE = f"dim {palette.error_color}"


def _read_line(prompt: str, input_fn: ReadLineFn = None) -> Optional[str]:
    if input_fn is not None:
        return input_fn(prompt)
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return None


def _parse_nav(raw: Optional[str]) -> Tuple[str, Optional[str]]:
    if raw is None:
        return "", _NAV_EXIT
    text = raw.strip()
    if not text:
        return "", None
    lowered = text.lower()
    if lowered in {"0", "q", "quit", "exit"}:
        return "", _NAV_EXIT
    if lowered in {"b", "back"}:
        return "", _NAV_BACK
    return text, None


def _print_missing_fitz(console: Console, exc: PyMuPDFMissingError) -> int:
    console.print(Text(str(exc), style=ERROR_STYLE))
    return 1


def cmd_pdf_init(
    custom_dir: Optional[str] = None,
    *,
    output_dir: Optional[str] = None,
    console: Optional[Console] = None,
) -> int:
    """Initialize the user or project PDF templates directory (and optional output dir)."""
    _apply_active_theme()
    console = console or Console()
    try:
        created_dir, project_cfg = init_templates_dir(
            custom_dir=custom_dir, output_dir=output_dir
        )
    except Exception as exc:
        console.print(
            Text(
                f"Failed to initialize PDF templates directory: {exc}",
                style=ERROR_STYLE,
            )
        )
        return 1

    console.print(Text("PDF templates directory initialized.", style=TABLE_STYLE))
    console.print(f"  templates directory: {created_dir}", style=MENU_STYLE)
    if output_dir:
        out_tier, out_resolved = resolve_output_dir()
        console.print(
            f"  output directory ({out_tier}): {out_resolved}", style=MENU_STYLE
        )
    if project_cfg is not None:
        console.print(f"  project config updated: {project_cfg}", style="dim")
    else:
        console.print("  tier: user default", style="dim")
    return 0


def cmd_pdf_output_dir(
    output_dir: Optional[str] = None,
    *,
    global_scope: bool = False,
    console: Optional[Console] = None,
) -> int:
    """View or configure the default output directory for filled PDFs."""
    _apply_active_theme()
    console = console or Console()
    if not output_dir:
        tier, resolved = resolve_output_dir()
        console.print(Text("PDF output directory", style=TABLE_STYLE))
        if resolved is not None:
            exists_label = (
                "present" if resolved.is_dir() else "will auto-create on fill"
            )
            console.print(
                f"  active ({tier}): {resolved} ({exists_label})", style=MENU_STYLE
            )
        else:
            console.print(
                "  active (default): current working directory (or alongside ad-hoc PDF)",
                style=MENU_STYLE,
            )
            console.print(
                "  Tip: set a persistent folder via `skillware pdf output-dir ./filled_forms` "
                "(or `--global`), or set PDF_OUTPUT_DIR.",
                style="dim",
            )
        return 0

    try:
        created_dir, cfg_path = save_pdf_output_dir(
            output_dir, global_scope=global_scope
        )
    except Exception as exc:
        console.print(
            Text(f"Failed to configure PDF output directory: {exc}", style=ERROR_STYLE)
        )
        return 1

    scope_label = "global config" if global_scope else "project config"
    console.print(Text("PDF output directory configured.", style=TABLE_STYLE))
    console.print(f"  output directory: {created_dir}", style=MENU_STYLE)
    console.print(f"  {scope_label} updated: {cfg_path}", style="dim")
    return 0


def cmd_pdf_import(
    source: str,
    *,
    link: bool = False,
    auto_map: bool = False,
    console: Optional[Console] = None,
) -> int:
    """Batch-import PDF forms from a folder (or single file) into the active template dir."""
    _apply_active_theme()
    console = console or Console()
    try:
        dest_dir, results = import_pdf_forms(
            Path(source),
            symlink=link,
            auto_map=auto_map,
        )
    except PyMuPDFMissingError as exc:
        return _print_missing_fitz(console, exc)
    except FileNotFoundError as exc:
        console.print(Text(str(exc), style=ERROR_STYLE))
        return 1
    except Exception as exc:
        console.print(Text(f"Import failed: {exc}", style=ERROR_STYLE))
        return 1

    if not results:
        console.print(f"No PDF files found in {source}.", style="dim")
        return 0

    table = Table(
        title=f"PDF Import -> {dest_dir}",
        box=box.SIMPLE_HEAVY,
        header_style=TABLE_STYLE,
        border_style=BORDER_STYLE,
    )
    table.add_column("File", style=ID_STYLE)
    table.add_column("Status")
    table.add_column("Map")
    table.add_column("Details", style="dim")

    imported_count = 0
    xfa_count = 0
    invalid_count = 0

    for item in results:
        if item.status == "imported":
            imported_count += 1
            st_text = Text("IMPORTED", style="green")
        elif item.status == "xfa":
            xfa_count += 1
            st_text = Text("XFA [!]", style="yellow")
        else:
            invalid_count += 1
            st_text = Text("INVALID", style=ERROR_STYLE)

        map_col = item.map_status or "-"
        table.add_row(item.source_path.name, st_text, map_col, item.message)

    console.print(table)
    console.print(
        f"Summary: {imported_count} imported, {xfa_count} XFA warning(s), {invalid_count} invalid.",
        style=MENU_STYLE,
    )
    return 0 if invalid_count == 0 else 1


def cmd_pdf_status(
    *,
    as_json: bool = False,
    console: Optional[Console] = None,
) -> int:
    """Audit all configured and bundled PDF templates, paths, and XFA/schema readiness."""
    _apply_active_theme()
    console = console or Console()
    try:
        entries = audit_templates()
    except PyMuPDFMissingError as exc:
        return _print_missing_fitz(console, exc)

    tier, active_dir = resolve_active_templates_dir()
    out_tier, out_dir = resolve_output_dir()
    roots = get_template_roots(include_bundled=True)

    valid_count = sum(1 for e in entries if e.map_status == "[MAPPED - VALID]")
    unmapped_count = sum(1 for e in entries if e.map_status == "[UNMAPPED]")
    xfa_count = sum(1 for e in entries if e.map_status == "[UNSUPPORTED]")
    invalid_count = len(entries) - valid_count - unmapped_count - xfa_count

    if as_json:
        payload = {
            "command": "pdf status",
            "active_templates_dir": {
                "tier": tier,
                "path": str(active_dir),
                "exists": active_dir.is_dir(),
            },
            "output_dir": {
                "tier": out_tier,
                "path": str(out_dir) if out_dir is not None else None,
                "exists": out_dir.is_dir() if out_dir is not None else None,
            },
            "roots": [
                {
                    "tier": r.tier,
                    "path": str(r.path),
                    "exists": r.path.is_dir(),
                }
                for r in roots
            ],
            "templates": [
                {
                    "template_id": e.template_id,
                    "source": e.source,
                    "pdf_type": e.pdf_type,
                    "map_status": e.map_status,
                    "fields": e.fields,
                    "path": str(e.path),
                    "schema_path": str(e.schema_path) if e.schema_path else None,
                    "errors": list(e.errors),
                }
                for e in entries
            ],
            "summary": {
                "valid": valid_count,
                "unmapped": unmapped_count,
                "invalid": invalid_count,
                "xfa": xfa_count,
                "total": len(entries),
            },
        }
        console.print(
            json.dumps(payload, indent=2),
            markup=False,
            highlight=False,
            soft_wrap=True,
        )
        return 0

    console.print(
        Text("PDF Template Search Paths (precedence order)", style=TABLE_STYLE)
    )
    for r in roots:
        marker = "present" if r.path.is_dir() else "missing"
        active_tag = " [active]" if r.path == active_dir else ""
        console.print(
            Text(
                f"  {r.tier:<8} {r.path} ({marker}){active_tag}",
                style=MENU_STYLE if r.path.is_dir() else "dim",
            )
        )
    if out_dir is not None:
        out_state = "present" if out_dir.is_dir() else "will auto-create on fill"
        console.print(
            Text(
                f"  output   ({out_tier}): {out_dir} ({out_state})",
                style=MENU_STYLE,
            )
        )
    else:
        console.print(
            Text(
                "  output   (default): current working directory",
                style="dim",
            )
        )

    if not entries:
        console.print("No PDF form templates found.", style="dim")
        return 0

    table = Table(
        box=box.SIMPLE_HEAVY,
        header_style=TABLE_STYLE,
        border_style=BORDER_STYLE,
    )
    table.add_column("Template ID", style=ID_STYLE)
    table.add_column("Source")
    table.add_column("PDF Type")
    table.add_column("Map Status")
    table.add_column("Fields", justify="right")
    table.add_column("Path", style="dim")

    for entry in entries:
        if entry.map_status == "[MAPPED - VALID]":
            status_cell = Text(entry.map_status, style="green")
        elif entry.map_status == "[UNMAPPED]":
            status_cell = Text(entry.map_status, style="yellow")
        elif entry.map_status == "[UNSUPPORTED]":
            status_cell = Text(entry.map_status, style="red")
        else:
            status_cell = Text(entry.map_status, style=ERROR_STYLE)

        pdf_type_cell = (
            Text(entry.pdf_type, style="red")
            if "XFA" in entry.pdf_type
            else Text(entry.pdf_type)
        )
        fields_str = "-" if entry.fields is None else str(entry.fields)
        table.add_row(
            entry.template_id,
            entry.source,
            pdf_type_cell,
            status_cell,
            fields_str,
            str(entry.path),
        )

    console.print(table)

    invalid_entries = [
        e for e in entries if e.map_status == "[MAP INVALID]" and e.errors
    ]
    if invalid_entries:
        console.print(Text("Validation Errors:", style=ERROR_STYLE))
        for inv in invalid_entries:
            console.print(f"  {inv.template_id} ({inv.source}):", style=ERROR_STYLE)
            for err in inv.errors[:5]:
                console.print(f"    - {err}", style=ERROR_DIM_STYLE)
            if len(inv.errors) > 5:
                console.print(
                    f"    ... and {len(inv.errors) - 5} more error(s).",
                    style=ERROR_DIM_STYLE,
                )

    console.print(
        f"Summary: {valid_count} valid template(s), {unmapped_count} unmapped form(s), "
        f"{invalid_count} invalid map(s), {xfa_count} unsupported dynamic XFA form(s).",
        style=MENU_STYLE,
    )
    if unmapped_count > 0:
        console.print(
            "Hint: Run `skillware pdf map-generate --missing` to scaffold schema maps for unmapped forms.",
            style="dim",
        )
    return 0


def cmd_pdf_templates_list(
    *, as_json: bool = False, console: Optional[Console] = None
) -> int:
    """List bundled and user PDF form templates."""
    return cmd_pdf_status(as_json=as_json, console=console)


def cmd_pdf_inspect(
    pdf_path: str,
    *,
    as_json: bool = False,
    console: Optional[Console] = None,
) -> int:
    """Inspect a single PDF's AcroForm widgets, XFA status, and radio groups."""
    _apply_active_theme()
    console = console or Console()
    try:
        info = inspect_pdf(Path(pdf_path))
    except PyMuPDFMissingError as exc:
        return _print_missing_fitz(console, exc)
    except FileNotFoundError as exc:
        console.print(Text(str(exc), style=ERROR_STYLE))
        return 1
    except Exception as exc:
        console.print(Text(f"Inspection failed: {exc}", style=ERROR_STYLE))
        return 1

    if as_json:
        console.print(
            json.dumps(info, indent=2),
            markup=False,
            highlight=False,
            soft_wrap=True,
        )
        return 0

    console.print(Text(f"PDF Inspection: {info['pdf_path']}", style=TABLE_STYLE))
    console.print(
        f"  type: {info['pdf_type']} | pages: {info['pages']} | widgets: {info['widget_count']}",
        style=MENU_STYLE,
    )
    if info["is_xfa"]:
        console.print(
            Text(
                "  WARNING: Dynamic XFA form detected. Static AcroForm PDF is required.",
                style=ERROR_STYLE,
            )
        )

    if info["widgets"]:
        table = Table(
            box=box.SIMPLE_HEAVY,
            header_style=TABLE_STYLE,
            border_style=BORDER_STYLE,
        )
        table.add_column("Page", justify="right")
        table.add_column("Native Name", style=ID_STYLE)
        table.add_column("Type")
        table.add_column("Options / States")
        table.add_column("Nearby Label", style="dim")

        for w in info["widgets"]:
            opts = w.get("button_states") or w.get("choice_values") or []
            opts_str = ", ".join(str(x) for x in opts) if opts else "-"
            label = str(w.get("label_context") or "")
            if len(label) > 60:
                label = label[:57] + "..."
            table.add_row(
                str(w["page"]),
                str(w["native_name"]),
                str(w["field_type"]),
                opts_str,
                label,
            )
        console.print(table)

    if info["radio_groups"]:
        console.print(Text("Radio Groups:", style=TABLE_STYLE))
        for grp in info["radio_groups"]:
            states = (
                ", ".join(grp["export_values"]) if grp["export_values"] else "(none)"
            )
            console.print(
                f"  - {grp['native_name']} (page {grp['page']}): {states}",
                style=MENU_STYLE,
            )

    return 0


def cmd_pdf_map_generate(
    pdf_path: Optional[str] = None,
    *,
    out_path: Optional[str] = None,
    missing: bool = False,
    force: bool = False,
    console: Optional[Console] = None,
) -> int:
    """Auto-generate boilerplate YAML schema map(s) without overwriting existing maps."""
    _apply_active_theme()
    console = console or Console()

    if missing:
        try:
            outcomes = generate_missing_maps()
        except PyMuPDFMissingError as exc:
            return _print_missing_fitz(console, exc)

        if not outcomes:
            console.print(
                "No PDF files found in the active templates directory.", style="dim"
            )
            return 0

        generated = 0
        for pdf_file, map_file, status in outcomes:
            if status == "generated":
                generated += 1
                console.print(
                    Text(f"  [GENERATED] {pdf_file.name} -> {map_file}", style="green")
                )
            else:
                console.print(f"  [SKIPPED]   {pdf_file.name}: {status}", style="dim")
        console.print(f"Generated {generated} schema map(s).", style=MENU_STYLE)
        return 0

    if not pdf_path:
        console.print(
            Text(
                "Provide a PDF path or pass --missing to batch-generate maps.",
                style=ERROR_STYLE,
            )
        )
        return 1

    try:
        target_map, schema = generate_schema_map(
            Path(pdf_path),
            out_path=Path(out_path) if out_path else None,
            force=force,
        )
    except PyMuPDFMissingError as exc:
        return _print_missing_fitz(console, exc)
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        console.print(Text(str(exc), style=ERROR_STYLE))
        return 1
    except Exception as exc:
        console.print(Text(f"Map generation failed: {exc}", style=ERROR_STYLE))
        return 1

    total_fields = sum(
        len(sec.get("fields") or []) for sec in schema.get("sections") or []
    )
    console.print(
        Text(
            f"Generated schema map: {target_map} ({total_fields} field(s))",
            style="green",
        )
    )
    return 0


def cmd_pdf_map_validate(
    pdf_path: str,
    schema_path: str,
    *,
    console: Optional[Console] = None,
) -> int:
    """Validate a YAML schema map against physical AcroForm widgets in a PDF."""
    _apply_active_theme()
    console = console or Console()
    try:
        result = validate_schema_map(Path(pdf_path), Path(schema_path))
    except PyMuPDFMissingError as exc:
        return _print_missing_fitz(console, exc)

    if result.valid:
        console.print(
            Text(
                f"VALID: {result.schema_path} matches {result.pdf_path} "
                f"({result.field_count} field(s) verified).",
                style="green",
            )
        )
        return 0

    console.print(
        Text(
            f"INVALID: {len(result.errors)} error(s) found validating {result.schema_path}:",
            style=ERROR_STYLE,
        )
    )
    for err in result.errors:
        console.print(Text(f"  - {err}", style=ERROR_STYLE))
    return 1


def cmd_pdf_guide(*, console: Optional[Console] = None) -> int:
    """Print quick-reference terminal documentation for authoring PDF schema maps."""
    _apply_active_theme()
    console = console or Console()
    console.print(Text("Skillware PDF Form Schema Authoring Guide", style=TABLE_STYLE))
    console.print(
        """
1. Required and Optional Top-Level Fields (*.yaml)
   - form_id      (required): unique snake_case identifier (e.g. "vendor_nda_2026")
   - template_id  (optional): template stem used by office/pdf_form_filler
   - title        (required): human-readable form title
   - source_pdf   (required): relative path to the PDF inside the template root
   - pages        (optional): total page count
   - category     (optional): e.g. "tax", "hr", "legal"
   - jurisdiction (optional): e.g. "US", "EU"
   - sections     (required): list of section objects with id, title, and fields[]

2. Field Entry Specification
   - id             (required): clean snake_case semantic field ID
   - pdf_field_name (required): exact AcroForm widget name from the PDF
   - field_type     (required): text | checkbox | combobox | radio | date | signature
   - page           (required): 0-indexed page number containing the widget
   - label          (required): human-readable prompt label
   - required       (optional): true | false (default false)
   - sensitive      (optional): true for PII (SSN, TIN, EIN, date of birth)
   - export_value   (optional): checkbox/radio export state name
   - options        (optional): allowed values for radio or combobox fields

3. Handling Radio Groups and Export Values
   - Radio buttons share a parent pdf_field_name across multiple widgets.
   - Run `skillware pdf inspect path/to/form.pdf` to list exact widget names,
     radio group export states (widget.button_states()), and dropdown choices.

4. Workflow Commands
   - skillware pdf init [--dir ./my_forms]
   - skillware pdf import /path/to/forms/ --auto-map
   - skillware pdf status
   - skillware pdf map-generate --missing
   - skillware pdf map-validate path/to/form.pdf map.yaml

5. Full Documentation
   See: docs/skills/office/pdf_form_filler.md#authoring-custom-maps
""".strip(),
        style=MENU_STYLE,
    )
    return 0


def cmd_pdf_open(*, console: Optional[Console] = None) -> int:
    """Open the active PDF templates directory in the OS file manager."""
    _apply_active_theme()
    console = console or Console()
    tier, active_dir = resolve_active_templates_dir()
    if not active_dir.is_dir():
        console.print(
            f"PDF templates directory ({tier}) does not exist yet: {active_dir}",
            style=ERROR_DIM_STYLE,
        )
        console.print("  Run: skillware pdf init", style="dim")
        return 1
    try:
        open_path_in_os(active_dir)
    except Exception as exc:
        console.print(Text(f"Could not open {active_dir}: {exc}", style=ERROR_STYLE))
        return 1
    console.print(f"Opened {active_dir}", style=MENU_STYLE)
    return 0


def cmd_pdf_submenu(
    console: Optional[Console] = None,
    input_fn: ReadLineFn = None,
) -> Optional[str]:
    """Interactive PDF templates submenu under ``skillware`` -> ``config`` -> ``pdf``."""
    console = console or Console()
    while True:
        _apply_active_theme()
        console.print(Text("PDF Form Templates", style=TABLE_STYLE))
        for key, label, desc in _PDF_SUBMENU:
            console.print(f"    [{key}] {label:<16}— {desc}", style=MENU_STYLE)
        console.print(
            "    [b] back             [0/q] exit",
            style="dim",
        )
        choice, nav = _parse_nav(_read_line("  pdf> ", input_fn=input_fn))
        if nav == _NAV_EXIT:
            return _NAV_EXIT
        if nav == _NAV_BACK:
            return None
        if not choice:
            continue

        lowered = choice.lower()
        if lowered in {"1", "status", "templates", "list"}:
            cmd_pdf_status(console=console)
        elif lowered in {"2", "init"}:
            custom = _read_line(
                "  Custom project dir (Enter for user default): ", input_fn=input_fn
            )
            if custom is None:
                return _NAV_EXIT
            cmd_pdf_init(custom_dir=custom.strip() or None, console=console)
        elif lowered in {"3", "import"}:
            src = _read_line("  Source folder or PDF path: ", input_fn=input_fn)
            if src is None:
                return _NAV_EXIT
            if src.strip():
                auto_ans = _read_line(
                    "  Auto-generate missing maps? [y/N]: ", input_fn=input_fn
                )
                if auto_ans is None:
                    return _NAV_EXIT
                cmd_pdf_import(
                    src.strip(),
                    auto_map=auto_ans.strip().lower() in {"y", "yes"},
                    console=console,
                )
        elif lowered in {"4", "map-generate"}:
            target = _read_line(
                "  PDF path (or Enter for --missing batch mode): ", input_fn=input_fn
            )
            if target is None:
                return _NAV_EXIT
            if target.strip():
                cmd_pdf_map_generate(pdf_path=target.strip(), console=console)
            else:
                cmd_pdf_map_generate(missing=True, console=console)
        elif lowered in {"5", "inspect"}:
            pdf_p = _read_line("  PDF path to inspect: ", input_fn=input_fn)
            if pdf_p is None:
                return _NAV_EXIT
            if pdf_p.strip():
                cmd_pdf_inspect(pdf_p.strip(), console=console)
        elif lowered in {"6", "map-validate"}:
            pdf_p = _read_line("  PDF path: ", input_fn=input_fn)
            if pdf_p is None:
                return _NAV_EXIT
            yml_p = _read_line("  YAML schema path: ", input_fn=input_fn)
            if yml_p is None:
                return _NAV_EXIT
            if pdf_p.strip() and yml_p.strip():
                cmd_pdf_map_validate(pdf_p.strip(), yml_p.strip(), console=console)
        elif lowered in {"7", "guide"}:
            cmd_pdf_guide(console=console)
        elif lowered in {"8", "open"}:
            cmd_pdf_open(console=console)
        elif lowered in {"9", "output-dir", "output"}:
            out_val = _read_line(
                "  Output folder (Enter to view current): ", input_fn=input_fn
            )
            if out_val is None:
                return _NAV_EXIT
            cmd_pdf_output_dir(output_dir=out_val.strip() or None, console=console)
        else:
            console.print(f"  Unknown choice: {choice}", style=ERROR_DIM_STYLE)
        console.print()


def cmd_pdf_dispatch(
    area: Optional[str],
    action: Optional[str] = None,
    *,
    console: Optional[Console] = None,
    **kwargs: Any,
) -> int:
    """Dispatch `skillware pdf <subcommand>` invocations."""
    if not area or area == "status":
        return cmd_pdf_status(
            as_json=bool(kwargs.get("as_json", False)),
            console=console,
        )
    if area == "init":
        return cmd_pdf_init(
            custom_dir=kwargs.get("dir"),
            output_dir=kwargs.get("output_dir"),
            console=console,
        )
    if area == "output-dir":
        return cmd_pdf_output_dir(
            output_dir=kwargs.get("output_dir"),
            global_scope=bool(kwargs.get("global_scope", False)),
            console=console,
        )
    if area == "import":
        return cmd_pdf_import(
            kwargs["source"],
            link=bool(kwargs.get("link", False)),
            auto_map=bool(kwargs.get("auto_map", False)),
            console=console,
        )
    if area == "templates":
        if action in (None, "list"):
            return cmd_pdf_templates_list(
                as_json=bool(kwargs.get("as_json", False)),
                console=console,
            )
    if area == "inspect":
        return cmd_pdf_inspect(
            kwargs["pdf_path"],
            as_json=bool(kwargs.get("as_json", False)),
            console=console,
        )
    if area == "map-generate":
        return cmd_pdf_map_generate(
            pdf_path=kwargs.get("pdf_path"),
            out_path=kwargs.get("out"),
            missing=bool(kwargs.get("missing", False)),
            force=bool(kwargs.get("force", False)),
            console=console,
        )
    if area == "map-validate":
        return cmd_pdf_map_validate(
            kwargs["pdf_path"],
            kwargs["schema_path"],
            console=console,
        )
    if area == "guide":
        return cmd_pdf_guide(console=console)
    if area == "open":
        return cmd_pdf_open(console=console)
    return 1

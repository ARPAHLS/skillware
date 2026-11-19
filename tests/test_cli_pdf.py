# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Tests for skillware.core.pdf_templates and skillware.cli_pdf (Issue #406)."""

from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import fitz
import pytest
import yaml
from rich.console import Console

from skillware.cli_pdf import (
    cmd_pdf_dispatch,
    cmd_pdf_guide,
    cmd_pdf_import,
    cmd_pdf_init,
    cmd_pdf_inspect,
    cmd_pdf_map_generate,
    cmd_pdf_map_validate,
    cmd_pdf_open,
    cmd_pdf_output_dir,
    cmd_pdf_status,
    cmd_pdf_submenu,
)
from skillware.core.pdf_templates import (
    ENV_PDF_OUTPUT_DIR,
    ENV_PDF_TEMPLATES_DIR,
    PYMUPDF_INSTALL_HINT,
    PyMuPDFMissingError,
    audit_templates,
    bundled_pdf_kb_dir,
    generate_schema_map,
    import_pdf_forms,
    init_templates_dir,
    inspect_pdf,
    resolve_active_templates_dir,
    resolve_output_dir,
    validate_schema_map,
)


def _create_acroform_pdf(path: Path, *, with_pii: bool = True) -> Path:
    """Create a synthetic static AcroForm PDF with text, checkbox, and combobox widgets."""
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    page.insert_text((50, 70), "Full Legal Name", fontsize=11)
    w_name = fitz.Widget()
    w_name.field_name = "full_name"
    w_name.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    w_name.rect = fitz.Rect(50, 75, 280, 95)
    page.add_widget(w_name)

    if with_pii:
        page.insert_text((50, 125), "Tax ID / SSN", fontsize=11)
        w_ssn = fitz.Widget()
        w_ssn.field_name = "tax_ssn"
        w_ssn.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        w_ssn.rect = fitz.Rect(50, 130, 220, 150)
        page.add_widget(w_ssn)

    page.insert_text((50, 185), "Agree to Terms", fontsize=11)
    w_cb = fitz.Widget()
    w_cb.field_name = "agree_terms"
    w_cb.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    w_cb.rect = fitz.Rect(50, 190, 70, 210)
    page.add_widget(w_cb)

    page.insert_text((50, 245), "Country Selection", fontsize=11)
    w_dd = fitz.Widget()
    w_dd.field_name = "country_choice"
    w_dd.field_type = fitz.PDF_WIDGET_TYPE_COMBOBOX
    w_dd.choice_values = ["US", "GR", "DE"]
    w_dd.rect = fitz.Rect(50, 250, 220, 270)
    page.add_widget(w_dd)

    doc.save(str(path))
    doc.close()
    return path


def _create_xfa_like_pdf(path: Path) -> Path:
    """Create a PDF with an AcroForm/XFA catalog entry to trigger XFA detection."""
    doc = fitz.open()
    doc.new_page(width=612, height=792)
    cat_xref = doc.pdf_catalog()
    xfa_xref = doc.get_new_xref()
    doc.update_object(xfa_xref, "<< /Length 0 >>")
    acro_xref = doc.get_new_xref()
    doc.update_object(acro_xref, f"<< /Fields [] /XFA {xfa_xref} 0 R >>")
    doc.xref_set_key(cat_xref, "AcroForm", f"{acro_xref} 0 R")
    doc.save(str(path))
    doc.close()
    return path


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    return Console(file=buf, force_terminal=False, width=120), buf


def test_init_and_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLWARE_CONFIG_DIR", str(tmp_path / "global_cfg"))
    monkeypatch.delenv(ENV_PDF_TEMPLATES_DIR, raising=False)
    monkeypatch.chdir(tmp_path)

    # 1. Default user dir
    user_dir, proj_cfg = init_templates_dir()
    assert user_dir.is_dir()
    assert proj_cfg is None
    tier, resolved = resolve_active_templates_dir()
    assert tier == "user"
    assert resolved == user_dir.resolve()

    # 2. Project dir recorded in .skillware.yaml without clobbering existing keys
    proj_yaml = tmp_path / ".skillware.yaml"
    proj_yaml.write_text("presentation:\n  theme: ocean\n", encoding="utf-8")

    custom_dir, cfg_written = init_templates_dir("./my_forms", start=tmp_path)
    assert custom_dir.is_dir()
    assert cfg_written == proj_yaml.resolve()
    data = yaml.safe_load(proj_yaml.read_text(encoding="utf-8"))
    assert data["presentation"]["theme"] == "ocean"
    assert data["pdf"]["templates_dir"] == "./my_forms"

    tier, resolved = resolve_active_templates_dir(start=tmp_path)
    assert tier == "project"
    assert resolved == custom_dir.resolve()

    # 3. Env var overrides project config
    env_dir = tmp_path / "env_forms"
    monkeypatch.setenv(ENV_PDF_TEMPLATES_DIR, str(env_dir))
    tier, resolved = resolve_active_templates_dir(start=tmp_path)
    assert tier == "env"
    assert resolved == env_dir.resolve()


def test_generate_schema_map_pii_and_safety_invariant(tmp_path: Path) -> None:
    pdf_path = _create_acroform_pdf(tmp_path / "vendor_nda.pdf", with_pii=True)
    map_path, schema = generate_schema_map(pdf_path)

    assert map_path == pdf_path.with_suffix(".yaml")
    assert map_path.is_file()
    assert schema["template_id"] == "vendor_nda"
    assert len(schema["sections"]) == 1
    fields = schema["sections"][0]["fields"]
    assert len(fields) == 4

    # PII detection on SSN / Tax ID field
    ssn_fields = [f for f in fields if f["pdf_field_name"] == "tax_ssn"]
    assert len(ssn_fields) == 1
    assert ssn_fields[0].get("sensitive") is True

    # Safety invariant: never overwrite without --force
    with pytest.raises(FileExistsError):
        generate_schema_map(pdf_path)

    # With force=True, overwrite succeeds
    map_path2, _ = generate_schema_map(pdf_path, force=True)
    assert map_path2 == map_path

    # Generated schema must pass validate_schema_map cleanly
    res = validate_schema_map(pdf_path, map_path)
    assert res.valid is True
    assert res.field_count == 4
    assert res.errors == []


def test_validate_schema_map_catches_errors(tmp_path: Path) -> None:
    pdf_path = _create_acroform_pdf(tmp_path / "form.pdf")
    bad_schema = tmp_path / "bad.yaml"
    bad_schema.write_text(
        yaml.safe_dump(
            {
                "form_id": "bad_form",
                "title": "Bad Form",
                "source_pdf": "form.pdf",
                "sections": [
                    {
                        "id": "page_1",
                        "title": "Page 1",
                        "fields": [
                            {
                                "id": "missing_widget",
                                "pdf_field_name": "does_not_exist",
                                "field_type": "text",
                                "page": 0,
                            },
                            {
                                "id": "wrong_page",
                                "pdf_field_name": "full_name",
                                "field_type": "text",
                                "page": 5,
                            },
                            {
                                "id": "wrong_type",
                                "pdf_field_name": "full_name",
                                "field_type": "checkbox",
                                "page": 0,
                            },
                            {
                                "id": "bad_choice",
                                "pdf_field_name": "country_choice",
                                "field_type": "combobox",
                                "page": 0,
                                "options": ["US", "MARS"],
                            },
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    res = validate_schema_map(pdf_path, bad_schema)
    assert res.valid is False
    assert len(res.errors) == 4
    assert any("not found on page 0" in e for e in res.errors)
    assert any("out of range" in e for e in res.errors)
    assert any("Type mismatch" in e for e in res.errors)
    assert any("MARS" in e for e in res.errors)


def test_xfa_detection_blocks_generate_and_validate(tmp_path: Path) -> None:
    xfa_pdf = _create_xfa_like_pdf(tmp_path / "irs_1040_raw.pdf")
    info = inspect_pdf(xfa_pdf)
    assert info["is_xfa"] is True
    assert info["pdf_type"] == "XFA"

    with pytest.raises(ValueError, match="XFA"):
        generate_schema_map(xfa_pdf)

    dummy_yaml = tmp_path / "dummy.yaml"
    dummy_yaml.write_text("form_id: x\nsections: []\n", encoding="utf-8")
    res = validate_schema_map(xfa_pdf, dummy_yaml)
    assert res.valid is False
    assert res.is_xfa is True


def test_batch_import_auto_map_and_audit_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dest_dir = tmp_path / "active_templates"
    monkeypatch.setenv(ENV_PDF_TEMPLATES_DIR, str(dest_dir))
    monkeypatch.setenv("SKILLWARE_CONFIG_DIR", str(tmp_path / "cfg"))

    src_folder = tmp_path / "incoming"
    src_folder.mkdir()
    _create_acroform_pdf(src_folder / "employee_intake.pdf")
    _create_xfa_like_pdf(src_folder / "dynamic_xfa.pdf")
    (src_folder / "corrupt.pdf").write_text("not a pdf", encoding="utf-8")

    # Pre-create a custom map in dest to verify --auto-map preserves it
    dest_dir.mkdir(parents=True)
    existing_map = dest_dir / "employee_intake.yaml"
    existing_map.write_text(
        "# custom preserved map\nform_id: custom\nsections: []\n", encoding="utf-8"
    )

    target, results = import_pdf_forms(src_folder, auto_map=True)
    assert target == dest_dir.resolve()
    statuses = {r.source_path.name: r.status for r in results}
    assert statuses["employee_intake.pdf"] == "imported"
    assert statuses["dynamic_xfa.pdf"] == "xfa"
    assert statuses["corrupt.pdf"] == "invalid"

    # Existing map must not be overwritten
    assert "# custom preserved map" in existing_map.read_text(encoding="utf-8")

    # Audit templates
    entries = audit_templates(include_bundled=False)
    by_id = {e.template_id: e for e in entries}
    assert by_id["employee_intake"].map_status == "[MAPPED - VALID]"
    assert by_id["dynamic_xfa"].pdf_type == "XFA [!]"
    assert by_id["dynamic_xfa"].map_status == "[UNSUPPORTED]"


def test_cli_commands_end_to_end(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    templates_dir = tmp_path / "templates"
    monkeypatch.setenv(ENV_PDF_TEMPLATES_DIR, str(templates_dir))
    monkeypatch.setenv("SKILLWARE_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.chdir(tmp_path)

    # init
    con, buf = _make_console()
    assert cmd_pdf_init(console=con) == 0
    assert "initialized" in buf.getvalue().lower()

    # import without auto-map
    src_dir = tmp_path / "src_forms"
    src_dir.mkdir()
    pdf_src = _create_acroform_pdf(src_dir / "nda.pdf")

    con, buf = _make_console()
    assert cmd_pdf_import(str(src_dir), auto_map=False, console=con) == 0
    assert "IMPORTED" in buf.getvalue()

    # status shows UNMAPPED
    con, buf = _make_console()
    assert cmd_pdf_status(console=con) == 0
    assert "[UNMAPPED]" in buf.getvalue()

    # map-generate --missing
    con, buf = _make_console()
    assert cmd_pdf_map_generate(missing=True, console=con) == 0
    assert "[GENERATED]" in buf.getvalue()

    # map-validate
    con, buf = _make_console()
    assert (
        cmd_pdf_map_validate(
            str(templates_dir / "nda.pdf"),
            str(templates_dir / "nda.yaml"),
            console=con,
        )
        == 0
    )
    assert "VALID" in buf.getvalue()

    # inspect --json
    con, buf = _make_console()
    assert cmd_pdf_inspect(str(pdf_src), as_json=True, console=con) == 0
    parsed = json.loads(buf.getvalue())
    assert parsed["is_xfa"] is False
    assert parsed["widget_count"] == 4

    # guide
    con, buf = _make_console()
    assert cmd_pdf_guide(console=con) == 0
    assert (
        "docs/skills/office/pdf_form_filler.md#authoring-custom-maps" in buf.getvalue()
    )

    # dispatch helper
    con, buf = _make_console()
    assert cmd_pdf_dispatch("templates", "list", console=con) == 0


def test_graceful_degradation_when_pymupdf_missing(tmp_path: Path) -> None:
    con, buf = _make_console()
    with patch(
        "skillware.core.pdf_templates._require_fitz",
        side_effect=PyMuPDFMissingError(PYMUPDF_INSTALL_HINT),
    ):
        rc = cmd_pdf_status(console=con)
    assert rc == 1
    assert 'pip install "skillware[office_pdf_form_filler]"' in buf.getvalue()


def test_user_templates_dir_end_to_end_with_skill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify user-tier templates dir (no PDF_TEMPLATES_DIR env var) works with PDFFormFillerSkill."""
    from skillware.core.loader import SkillLoader

    monkeypatch.setenv("SKILLWARE_CONFIG_DIR", str(tmp_path / "user_cfg"))
    monkeypatch.delenv(ENV_PDF_TEMPLATES_DIR, raising=False)
    monkeypatch.chdir(tmp_path)

    # 1. Initialize default user templates dir
    user_dir, proj_cfg = init_templates_dir()
    assert proj_cfg is None
    assert user_dir == (tmp_path / "user_cfg" / "pdf_templates")

    # 2. Import + auto-map a custom PDF into user templates dir
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    _create_acroform_pdf(incoming / "user_tier_nda.pdf")
    dest, results = import_pdf_forms(incoming, auto_map=True)
    assert dest == user_dir.resolve()
    assert results[0].status == "imported"
    assert results[0].map_status == "generated"

    # 3. PDFFormFillerSkill discovers and fills the user-tier template without env var
    skill = SkillLoader.load_skill("office/pdf_form_filler")["class"]()
    listed = skill.execute({"action": "list_templates"})
    assert listed["status"] == "ok"
    assert any(
        t["template_id"] == "user_tier_nda" and t["tier"] == "user"
        for t in listed["templates"]
    )

    filled = skill.execute(
        {
            "action": "fill",
            "template_id": "user_tier_nda",
            "edits": {"full_legal_name": "Nikos Kazantzakis"},
            "output_dir": str(tmp_path),
            "confirmed": True,
        }
    )
    assert filled["status"] == "success"
    doc = fitz.open(filled["output_path"])
    vals = {w.field_name: w.field_value for w in doc[0].widgets()}
    doc.close()
    assert vals["full_name"] == "Nikos Kazantzakis"


def test_project_config_walk_up_and_config_show(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify project .skillware.yaml pdf.templates_dir works from nested subdirectories and config show."""
    from skillware.cli import cmd_config_show
    from skillware.core.config import clear_config_cache, load_merged_config

    monkeypatch.setenv("SKILLWARE_CONFIG_DIR", str(tmp_path / "global_cfg"))
    monkeypatch.delenv(ENV_PDF_TEMPLATES_DIR, raising=False)
    clear_config_cache()

    proj_dir, cfg_path = init_templates_dir("./company_forms", start=tmp_path)
    assert cfg_path is not None

    nested = tmp_path / "sub" / "deep"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)
    clear_config_cache()

    tier, resolved = resolve_active_templates_dir()
    assert tier == "project"
    assert resolved == proj_dir.resolve()

    merged = load_merged_config(refresh=True)
    assert merged.pdf.templates_dir == "./company_forms"
    assert "pdf" not in merged.extra

    con, buf = _make_console()
    assert cmd_config_show(console=con) == 0
    out = buf.getvalue()
    assert "pdf (active)" in out
    assert "./company_forms" in out


def test_pdf_submenu_and_open_and_mixed_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify interactive pdf submenu, cmd_pdf_open, and mixed status table output."""
    tdir = tmp_path / "mixed_templates"
    monkeypatch.setenv(ENV_PDF_TEMPLATES_DIR, str(tdir))
    monkeypatch.setenv("SKILLWARE_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.chdir(tmp_path)

    # open before dir exists -> exit 1 with hint
    con, buf = _make_console()
    assert cmd_pdf_open(console=con) == 1
    assert "skillware pdf init" in buf.getvalue()

    tdir.mkdir()
    # 1 valid, 1 unmapped, 1 invalid map, 1 XFA
    valid_pdf = _create_acroform_pdf(tdir / "valid_form.pdf")
    generate_schema_map(valid_pdf)
    _create_acroform_pdf(tdir / "unmapped_form.pdf")
    _create_acroform_pdf(tdir / "invalid_form.pdf")
    (tdir / "invalid_form.yaml").write_text(
        yaml.safe_dump(
            {
                "form_id": "invalid_form",
                "sections": [
                    {
                        "id": "p1",
                        "fields": [
                            {
                                "id": "ghost",
                                "pdf_field_name": "nonexistent",
                                "field_type": "text",
                                "page": 0,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    _create_xfa_like_pdf(tdir / "xfa_form.pdf")

    con, buf = _make_console()
    assert cmd_pdf_status(console=con) == 0
    out = buf.getvalue()
    assert "[MAPPED - VALID]" in out
    assert "[UNMAPPED]" in out
    assert "[MAP INVALID]" in out
    assert "[UNSUPPORTED]" in out
    assert "skillware pdf map-generate --missing" in out

    # open when dir exists (mock OS launcher)
    with patch("skillware.cli_pdf.open_path_in_os", return_value=None):
        con, buf = _make_console()
        assert cmd_pdf_open(console=con) == 0
        assert "Opened" in buf.getvalue()

    # interactive submenu: 1 (status) -> 7 (guide) -> b (back)
    responses = iter(["1", "7", "b"])
    con, buf = _make_console()
    assert cmd_pdf_submenu(console=con, input_fn=lambda _: next(responses)) is None
    sub_out = buf.getvalue()
    assert "PDF Form Templates" in sub_out
    assert "Authoring Guide" in sub_out

    # interactive submenu: q (exit)
    con, buf = _make_console()
    assert cmd_pdf_submenu(console=con, input_fn=lambda _: "q") == "exit"


def test_map_generate_out_and_force_cli(tmp_path: Path) -> None:
    """Verify CLI map-generate --out and --force overwrite protection."""
    pdf_path = _create_acroform_pdf(tmp_path / "custom.pdf")
    out_yaml = tmp_path / "custom_out.yaml"

    con, buf = _make_console()
    assert (
        cmd_pdf_map_generate(
            pdf_path=str(pdf_path), out_path=str(out_yaml), console=con
        )
        == 0
    )
    assert out_yaml.is_file()

    # Second run without --force must refuse overwrite
    con, buf = _make_console()
    assert (
        cmd_pdf_map_generate(
            pdf_path=str(pdf_path), out_path=str(out_yaml), console=con
        )
        == 1
    )
    assert "--force" in buf.getvalue()

    # Third run with --force succeeds
    con, buf = _make_console()
    assert (
        cmd_pdf_map_generate(
            pdf_path=str(pdf_path), out_path=str(out_yaml), force=True, console=con
        )
        == 0
    )


def test_pdf_output_dir_precedence_autocreate_and_skill_routing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify pdf.output_dir / PDF_OUTPUT_DIR 4-tier precedence, auto-creation, and skill routing."""
    from skillware.core.config import clear_config_cache
    from skillware.core.loader import SkillLoader

    monkeypatch.setenv("SKILLWARE_CONFIG_DIR", str(tmp_path / "global_cfg"))
    monkeypatch.delenv(ENV_PDF_OUTPUT_DIR, raising=False)
    monkeypatch.delenv(ENV_PDF_TEMPLATES_DIR, raising=False)
    monkeypatch.chdir(tmp_path)
    clear_config_cache()

    # 1. Default -> None (fallback to CWD / alongside input)
    tier, out_dir = resolve_output_dir()
    assert tier == "default"
    assert out_dir is None

    con, buf = _make_console()
    assert cmd_pdf_output_dir(console=con) == 0
    assert "current working directory" in buf.getvalue()

    # 2. Global config output-dir auto-creates missing folder
    global_out = tmp_path / "global_filled" / "nested"
    assert not global_out.exists()
    con, buf = _make_console()
    assert cmd_pdf_output_dir(str(global_out), global_scope=True, console=con) == 0
    assert global_out.is_dir()
    tier, out_dir = resolve_output_dir()
    assert tier == "global"
    assert out_dir == global_out.resolve()

    # 3. Project config via init --dir --output-dir overrides global and auto-creates folder
    proj_forms = tmp_path / "proj_forms"
    proj_out = tmp_path / "proj_filled"
    assert not proj_out.exists()
    con, buf = _make_console()
    assert (
        cmd_pdf_init(
            custom_dir=str(proj_forms),
            output_dir=str(proj_out),
            console=con,
        )
        == 0
    )
    assert proj_forms.is_dir()
    assert proj_out.is_dir()
    tier, out_dir = resolve_output_dir()
    assert tier == "project"
    assert out_dir == proj_out.resolve()

    # 4. Skill fill routes output to configured project pdf.output_dir automatically
    skill = SkillLoader.load_skill("office/pdf_form_filler")["class"]()
    adhoc_pdf = _create_acroform_pdf(tmp_path / "adhoc.pdf")
    fill_res = skill.execute(
        {
            "action": "fill",
            "pdf_path": str(adhoc_pdf),
            "edits": {"full_name": "Ada Lovelace"},
            "confirmed": True,
        }
    )
    assert fill_res["status"] == "success"
    written_path = Path(fill_res["output_path"]).resolve()
    assert written_path.parent == proj_out.resolve()
    assert written_path.is_file()

    # 5. PDF_OUTPUT_DIR env var overrides project config and auto-creates non-existent folder
    env_out = tmp_path / "env_filled_autocreate"
    assert not env_out.exists()
    monkeypatch.setenv(ENV_PDF_OUTPUT_DIR, str(env_out))
    tier, out_dir = resolve_output_dir()
    assert tier == "env"
    assert out_dir == env_out.resolve()

    fill_env = skill.execute(
        {
            "action": "fill",
            "pdf_path": str(adhoc_pdf),
            "edits": {"full_name": "Grace Hopper"},
            "confirmed": True,
        }
    )
    assert fill_env["status"] == "success"
    env_written = Path(fill_env["output_path"]).resolve()
    assert env_written.parent == env_out.resolve()
    assert env_written.is_file()

    # 6. Explicit per-call output_dir overrides PDF_OUTPUT_DIR
    call_out = tmp_path / "call_override_dir"
    fill_call = skill.execute(
        {
            "action": "fill",
            "pdf_path": str(adhoc_pdf),
            "edits": {"full_name": "Alan Turing"},
            "output_dir": str(call_out),
            "confirmed": True,
        }
    )
    assert fill_call["status"] == "success"
    assert Path(fill_call["output_path"]).resolve().parent == call_out.resolve()


def test_multi_section_header_heuristic_synthetic_and_w8ben(tmp_path: Path) -> None:
    """Verify multi-section header chunking works cleanly on synthetic and real IRS W-8BEN PDFs."""
    # 1. Synthetic single-page form with 2 structural Part headings
    multi_pdf = tmp_path / "multi_part.pdf"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    page.insert_text((50, 50), "Part I: Applicant Information", fontsize=13)
    page.insert_text((50, 90), "Full Name", fontsize=10)
    w1 = fitz.Widget()
    w1.field_name = "applicant_name"
    w1.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    w1.rect = fitz.Rect(50, 95, 250, 115)
    page.add_widget(w1)

    page.insert_text((50, 220), "Part II: Tax Certification", fontsize=13)
    page.insert_text((50, 260), "Tax ID / TIN", fontsize=10)
    w2 = fitz.Widget()
    w2.field_name = "applicant_tin"
    w2.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    w2.rect = fitz.Rect(50, 265, 250, 285)
    page.add_widget(w2)

    doc.save(str(multi_pdf))
    doc.close()

    map_path, schema = generate_schema_map(multi_pdf)
    assert len(schema["sections"]) == 2
    assert "part_i" in schema["sections"][0]["id"]
    assert "part_ii" in schema["sections"][1]["id"]
    assert schema["sections"][0]["fields"][0]["pdf_field_name"] == "applicant_name"
    assert schema["sections"][1]["fields"][0]["pdf_field_name"] == "applicant_tin"
    assert schema["sections"][1]["fields"][0].get("sensitive") is True
    assert validate_schema_map(multi_pdf, map_path).valid is True

    # 2. Real bundled IRS W-8BEN auto-map splits into multiple sections and validates cleanly
    w8ben_pdf = bundled_pdf_kb_dir() / "templates" / "us_irs_w8ben.pdf"
    w8ben_out = tmp_path / "w8ben_auto.yaml"
    gen_path, w8_schema = generate_schema_map(w8ben_pdf, out_path=w8ben_out)
    assert len(w8_schema["sections"]) >= 2
    val_res = validate_schema_map(w8ben_pdf, gen_path)
    assert val_res.valid is True, f"W-8BEN auto-map validation errors: {val_res.errors}"


def test_pdf_status_json_and_cli_main_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Verify skillware pdf status --json and end-to-end argparse dispatch in cli.main()."""
    import sys
    from skillware.cli import main as cli_main

    tdir = tmp_path / "json_templates"
    tdir.mkdir()
    _create_acroform_pdf(tdir / "sample_unmapped.pdf")
    monkeypatch.setenv(ENV_PDF_TEMPLATES_DIR, str(tdir))
    monkeypatch.setenv("SKILLWARE_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv(ENV_PDF_OUTPUT_DIR, raising=False)
    monkeypatch.chdir(tmp_path)

    # Direct cmd_pdf_status(as_json=True)
    con, buf = _make_console()
    assert cmd_pdf_status(as_json=True, console=con) == 0
    payload = json.loads(buf.getvalue())
    assert payload["command"] == "pdf status"
    assert payload["active_templates_dir"]["tier"] == "env"
    assert len(payload["roots"]) >= 2
    assert payload["summary"]["unmapped"] == 1
    assert payload["summary"]["valid"] >= 4

    # Full argparse dispatch through cli.main()
    monkeypatch.setattr(sys, "argv", ["skillware", "pdf", "guide"])
    with pytest.raises(SystemExit) as exc:
        cli_main()
    assert exc.value.code == 0
    assert "Authoring Guide" in capsys.readouterr().out

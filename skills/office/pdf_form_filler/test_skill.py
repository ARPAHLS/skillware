# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

import os
import sys
import types

import fitz
import pytest
import yaml

from skillware.core.loader import SkillLoader
from .skill import PDFFormFillerSkill

HELPER_MODULE_BY_ROUTE = {
    "package": "skills.office.pdf_form_filler.utils",
    "file": "pdf_form_filler_utils",
}


@pytest.fixture
def skill():
    return PDFFormFillerSkill()


@pytest.fixture
def manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _create_sample_acroform(pdf_path: str):
    """Generate a multi-field AcroForm PDF with text, checkbox, dropdown, and radio group."""
    doc = fitz.open()
    page = doc.new_page()

    # 1. Text Field
    w_text = fitz.Widget()
    w_text.rect = fitz.Rect(50, 50, 250, 75)
    w_text.field_name = "full_name"
    w_text.field_type = fitz.PDF_WIDGET_TYPE_TEXT
    page.add_widget(w_text)

    # 2. Checkbox Field
    w_chk = fitz.Widget()
    w_chk.rect = fitz.Rect(50, 90, 70, 110)
    w_chk.field_name = "agree_terms"
    w_chk.field_type = fitz.PDF_WIDGET_TYPE_CHECKBOX
    page.add_widget(w_chk)

    # 3. Dropdown / Combobox Field
    w_drop = fitz.Widget()
    w_drop.rect = fitz.Rect(50, 130, 200, 155)
    w_drop.field_name = "country"
    w_drop.field_type = fitz.PDF_WIDGET_TYPE_COMBOBOX
    w_drop.choice_values = ["US", "CA", "UK", "GR"]
    page.add_widget(w_drop)

    # 4. Radio Button Group (2 options sharing field_name)
    w_r1 = fitz.Widget()
    w_r1.rect = fitz.Rect(50, 170, 70, 190)
    w_r1.field_name = "tax_class"
    w_r1.field_type = fitz.PDF_WIDGET_TYPE_RADIOBUTTON
    w_r1.field_value = "Off"
    page.add_widget(w_r1)

    w_r2 = fitz.Widget()
    w_r2.rect = fitz.Rect(50, 200, 70, 220)
    w_r2.field_name = "tax_class"
    w_r2.field_type = fitz.PDF_WIDGET_TYPE_RADIOBUTTON
    w_r2.field_value = "Off"
    page.add_widget(w_r2)

    b = doc.tobytes()
    doc.close()

    # Customize export values on radio widgets in the saved PDF
    doc2 = fitz.open(stream=b, filetype="pdf")
    radio_widgets = [
        w for w in doc2[0].widgets() if w.field_type == fitz.PDF_WIDGET_TYPE_RADIOBUTTON
    ]
    if len(radio_widgets) >= 2:
        doc2.xref_set_key(
            radio_widgets[0].xref, "AP/N", "<</Off 1 0 R /Individual 2 0 R>>"
        )
        doc2.xref_set_key(
            radio_widgets[1].xref, "AP/N", "<</Off 1 0 R /Corporation 3 0 R>>"
        )
    final_bytes = doc2.tobytes()
    doc2.close()

    with open(pdf_path, "wb") as f:
        f.write(final_bytes)


# --- Manifest & Metadata Tests ---


def test_skill_manifest_consistency(skill, manifest):
    skill_manifest = skill.manifest
    assert skill_manifest["name"] == manifest["name"]
    assert manifest["name"] == "office/pdf_form_filler"
    assert skill_manifest["version"] == "0.2.4"
    assert manifest["version"] == "0.2.4"
    assert "pymupdf" in manifest.get("requirements", [])
    assert "anthropic" not in manifest.get("requirements", [])


# --- Action: Inspect Tests ---


def test_inspect_blank_pdf(skill, tmp_path):
    pdf_path = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    res = skill.execute({"action": "inspect", "pdf_path": str(pdf_path)})
    assert res["status"] == "ok"
    assert res["page_count"] == 1
    assert res["field_count"] == 0
    assert res["is_xfa"] is False
    assert res["fields"] == []


def test_inspect_acroform_fields(skill, tmp_path):
    pdf_path = str(tmp_path / "sample_form.pdf")
    _create_sample_acroform(pdf_path)

    res = skill.execute({"action": "inspect", "pdf_path": pdf_path})
    assert res["status"] == "ok"
    assert res["is_xfa"] is False
    assert res["field_count"] >= 4

    types_found = {f["type"] for f in res["fields"]}
    assert "text" in types_found
    assert "checkbox" in types_found
    assert "dropdown" in types_found
    assert "radio" in types_found

    # Check radio button group aggregation
    radio_fields = [f for f in res["fields"] if f["type"] == "radio"]
    assert len(radio_fields) == 1
    rf = radio_fields[0]
    assert rf["native_name"] == "tax_class"
    assert isinstance(rf["options"], list)
    export_values = [opt["export_value"] for opt in rf["options"]]
    assert "Individual" in export_values or "Yes" in export_values


def test_inspect_xfa_guard(skill, tmp_path):
    pdf_path = str(tmp_path / "xfa_form.pdf")
    doc = fitz.open()
    doc.new_page()
    cat = doc.pdf_catalog()
    doc.xref_set_key(cat, "AcroForm", "<< /XFA (dummy_xfa_stream) >>")
    doc.save(pdf_path)
    doc.close()

    res = skill.execute({"action": "inspect", "pdf_path": pdf_path})
    assert res["status"] == "error"
    assert res["error_code"] == "unsupported_xfa_form"
    assert "Dynamic XFA" in res["message"]


# --- Action: Validate Tests ---


def test_validate_clean_edits(skill, tmp_path):
    pdf_path = str(tmp_path / "sample_form.pdf")
    _create_sample_acroform(pdf_path)

    edits = {
        "page0_full_name": "Jane Doe",
        "page0_agree_terms": True,
        "page0_country": "US",
        "page0_tax_class": "Individual",
    }
    res = skill.execute({"action": "validate", "pdf_path": pdf_path, "edits": edits})
    assert res["status"] == "ok"
    assert res["valid"] is True
    assert res["field_count"] == 4


def test_validate_invalid_field(skill, tmp_path):
    pdf_path = str(tmp_path / "sample_form.pdf")
    _create_sample_acroform(pdf_path)

    edits = {"page0_non_existent_field": "test"}
    res = skill.execute({"action": "validate", "pdf_path": pdf_path, "edits": edits})
    assert res["status"] == "error"
    assert res["valid"] is False
    assert len(res["errors"]) >= 1
    assert "page0_non_existent_field" in res["errors"][0]["field"]


def test_validate_invalid_radio_option(skill, tmp_path):
    pdf_path = str(tmp_path / "sample_form.pdf")
    _create_sample_acroform(pdf_path)

    edits = {"page0_tax_class": "InvalidExportValue123"}
    res = skill.execute({"action": "validate", "pdf_path": pdf_path, "edits": edits})
    assert res["status"] == "error"
    assert res["valid"] is False
    assert any("tax_class" in err["field"] for err in res["errors"])


def test_validate_invalid_checkbox(skill, tmp_path):
    pdf_path = str(tmp_path / "sample_form.pdf")
    _create_sample_acroform(pdf_path)

    edits = {"page0_agree_terms": "NotABooleanValue"}
    res = skill.execute({"action": "validate", "pdf_path": pdf_path, "edits": edits})
    assert res["status"] == "error"
    assert res["valid"] is False


# --- Action: Fill Tests ---


def test_fill_safety_confirmation_gate(skill, tmp_path):
    pdf_path = str(tmp_path / "sample_form.pdf")
    _create_sample_acroform(pdf_path)
    out_path = str(tmp_path / "out_unconfirmed.pdf")

    edits = {"page0_full_name": "Alice Wonderland"}
    res = skill.execute(
        {
            "action": "fill",
            "pdf_path": pdf_path,
            "edits": edits,
            "output_path": out_path,
            "confirmed": False,
        }
    )

    assert res["status"] == "needs_input"
    assert "Confirmation required" in res["message"]
    assert "preview" in res
    assert res["preview"]["proposed_edits"] == edits
    assert not os.path.exists(out_path)


def test_fill_success_with_values(skill, tmp_path):
    pdf_path = str(tmp_path / "sample_form.pdf")
    _create_sample_acroform(pdf_path)
    out_path = str(tmp_path / "out_filled.pdf")

    edits = {
        "page0_full_name": "Bob Builder",
        "page0_agree_terms": True,
        "page0_tax_class": "Individual",
    }
    res = skill.execute(
        {
            "action": "fill",
            "pdf_path": pdf_path,
            "edits": edits,
            "output_path": out_path,
            "confirmed": True,
        }
    )

    assert res["status"] == "success"
    assert os.path.exists(out_path)
    assert len(res["filled_fields"]) >= 2

    # Verify values inside the filled PDF
    doc_out = fitz.open(out_path)
    p_out = doc_out[0]
    vals = {w.field_name: w.field_value for w in p_out.widgets()}
    assert vals["full_name"] == "Bob Builder"
    assert bool(vals["agree_terms"]) is True
    doc_out.close()


def test_fill_flatten_guard(skill, tmp_path):
    pdf_path = str(tmp_path / "sample_form.pdf")
    _create_sample_acroform(pdf_path)
    out_path = str(tmp_path / "out_flattened.pdf")

    edits = {"page0_full_name": "Immutable Document"}
    res = skill.execute(
        {
            "action": "fill",
            "pdf_path": pdf_path,
            "edits": edits,
            "output_path": out_path,
            "confirmed": True,
            "flatten": True,
        }
    )

    assert res["status"] == "success"
    assert res["flattened"] is True

    # Output document must have all widgets baked into static graphics
    doc_out = fitz.open(out_path)
    p_out = doc_out[0]
    remaining_widgets = list(p_out.widgets())
    assert len(remaining_widgets) == 0
    doc_out.close()


def test_missing_pdf_returns_error(skill):
    result = skill.execute(
        {
            "action": "inspect",
            "pdf_path": "/nonexistent/form.pdf",
        }
    )
    assert result["status"] == "error"
    assert "PDF file not found" in result["message"]


def test_fill_default_action_when_edits_provided(skill, tmp_path):
    pdf_path = str(tmp_path / "sample_form.pdf")
    _create_sample_acroform(pdf_path)

    # Calling execute with edits but without explicit action should default to fill
    res = skill.execute(
        {
            "pdf_path": pdf_path,
            "edits": {"page0_full_name": "Auto Fill Action"},
            "confirmed": False,
        }
    )
    assert res["status"] == "needs_input"


# --- Loader Isolation & Import Route Tests ---


@pytest.fixture(params=sorted(HELPER_MODULE_BY_ROUTE))
def import_route(request, monkeypatch):
    monkeypatch.setattr(sys, "path", list(sys.path))
    if request.param == "file":
        monkeypatch.setitem(sys.modules, HELPER_MODULE_BY_ROUTE["package"], None)
    return request.param


def _load_via_skill_loader():
    bundle = SkillLoader.load_skill("office/pdf_form_filler")
    assert bundle["module"].__name__ == "skill_module"
    return bundle


def _blank_pdf(tmp_path):
    pdf_path = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_loader_execute_leaves_sys_path_unchanged(import_route):
    before = list(sys.path)
    skill = _load_via_skill_loader()["class"]()

    for _ in range(3):
        result = skill.execute(
            {"action": "inspect", "pdf_path": "/nonexistent/form.pdf"}
        )
        assert "PDF file not found" in result["message"]

    assert sys.path == before


def test_loader_execute_with_host_utils_module(import_route, monkeypatch, tmp_path):
    host_utils = types.ModuleType("utils")
    monkeypatch.setitem(sys.modules, "utils", host_utils)
    bundle = _load_via_skill_loader()

    result = bundle["class"]().execute(
        {"action": "inspect", "pdf_path": str(_blank_pdf(tmp_path))}
    )

    assert result["status"] == "ok"
    assert result["field_count"] == 0
    assert sys.modules["utils"] is host_utils
    assert (
        bundle["module"].detect_form_fields.__module__
        == HELPER_MODULE_BY_ROUTE[import_route]
    )


def test_loader_execute_does_not_register_top_level_utils(import_route, monkeypatch):
    monkeypatch.delitem(sys.modules, "utils", raising=False)
    skill = _load_via_skill_loader()["class"]()

    skill.execute({"action": "inspect", "pdf_path": "/nonexistent/form.pdf"})
    assert "utils" not in sys.modules


# --- Stress & Multi-Page Tests ---


def test_multi_page_form_handling(skill, tmp_path):
    pdf_path = str(tmp_path / "multipage_form.pdf")
    doc = fitz.open()

    for p_idx in range(3):
        page = doc.new_page()
        w = fitz.Widget()
        w.rect = fitz.Rect(50, 50, 200, 80)
        w.field_name = f"page_{p_idx}_field"
        w.field_type = fitz.PDF_WIDGET_TYPE_TEXT
        page.add_widget(w)

    doc.save(pdf_path)
    doc.close()

    res = skill.execute({"action": "inspect", "pdf_path": pdf_path})
    assert res["status"] == "ok"
    assert res["page_count"] == 3
    assert res["field_count"] == 3

    # Fill fields across pages
    edits = {
        "page0_page_0_field": "Page 1 Value",
        "page2_page_2_field": "Page 3 Value",
    }
    fill_res = skill.execute(
        {
            "action": "fill",
            "pdf_path": pdf_path,
            "edits": edits,
            "confirmed": True,
        }
    )
    assert fill_res["status"] == "success"
    assert len(fill_res["filled_fields"]) == 2


# ---------------------------------------------------------------------------
# v0.2.0 KB Templates, Section-Chunked Schemas, PII Redaction & W-8BEN Tests
# ---------------------------------------------------------------------------


def test_list_templates_discovers_w8ben(skill):
    res = skill.execute({"action": "list_templates"})
    assert res["status"] == "ok"
    assert res["count"] >= 1
    ids = [t["template_id"] for t in res["templates"]]
    assert "us_irs_w8ben" in ids

    w8 = next(t for t in res["templates"] if t["template_id"] == "us_irs_w8ben")
    assert w8["category"] == "tax"
    assert w8["jurisdiction"] == "US"
    assert w8["section_count"] == 3
    assert w8["field_count"] == 23
    assert w8["pdf_available"] is True

    filtered = skill.execute(
        {"action": "list_templates", "category": "tax", "jurisdiction": "US"}
    )
    assert filtered["count"] >= 1
    empty = skill.execute({"action": "list_templates", "jurisdiction": "JP"})
    assert empty["count"] == 0


def test_get_template_schema_section_chunking(skill):
    full = skill.execute(
        {"action": "get_template_schema", "template_id": "us_irs_w8ben"}
    )
    assert full["status"] == "ok"
    assert len(full["sections"]) == 3
    assert len(full["sections_index"]) == 3

    sec1 = skill.execute(
        {
            "action": "get_template_schema",
            "template_id": "us_irs_w8ben",
            "section": "part_1_identification",
        }
    )
    assert sec1["status"] == "ok"
    assert "sections" not in sec1
    assert sec1["section"]["id"] == "part_1_identification"
    field_ids = [f["id"] for f in sec1["fields"]]
    assert "beneficial_owner_name" in field_ids
    assert "foreign_tin" in field_ids
    assert "treaty_country" not in field_ids

    bad_sec = skill.execute(
        {
            "action": "get_template_schema",
            "template_id": "us_irs_w8ben",
            "section": "nonexistent_part",
        }
    )
    assert bad_sec["status"] == "error"

    bad_tpl = skill.execute(
        {"action": "get_template_schema", "template_id": "unknown_form"}
    )
    assert bad_tpl["status"] == "error"


def test_w8ben_validate_required_and_date_format(skill):
    missing = skill.execute(
        {
            "action": "validate",
            "template_id": "us_irs_w8ben",
            "edits": {"beneficial_owner_name": "Jane Doe"},
        }
    )
    assert missing["status"] == "error"
    assert missing["valid"] is False
    missing_fields = {e["field"] for e in missing["errors"]}
    assert "country_of_citizenship" in missing_fields
    assert "capacity_to_sign" in missing_fields

    bad_date = skill.execute(
        {
            "action": "validate",
            "template_id": "us_irs_w8ben",
            "edits": {
                "beneficial_owner_name": "Jane Doe",
                "country_of_citizenship": "Greece",
                "permanent_residence_street": "10 Ermou St",
                "permanent_residence_city_state_postal": "Athens 10563",
                "permanent_residence_country": "Greece",
                "date_of_birth": "1990-05-12",  # invalid: must be MM-DD-YYYY
                "capacity_to_sign": True,
                "signer_name": "Jane Doe",
            },
        }
    )
    assert bad_date["status"] == "error"
    assert any(e["field"] == "date_of_birth" for e in bad_date["errors"])


def test_w8ben_fill_pii_redaction_and_output_naming(skill, tmp_path):
    edits = {
        "beneficial_owner_name": "Elena Papadopoulou",
        "country_of_citizenship": "Greece",
        "permanent_residence_street": "24 Syntagma Sq",
        "permanent_residence_city_state_postal": "Athens 10563",
        "permanent_residence_country": "Greece",
        "foreign_tin": "EL-987654321",
        "date_of_birth": "04-15-1992",
        "treaty_country": "Greece",
        "treaty_article_and_paragraph": "Article 12(2)",
        "treaty_withholding_rate_pct": "5",
        "treaty_income_type": "Royalties",
        "capacity_to_sign": True,
        "signature": "Elena Papadopoulou",
        "signer_name": "Elena Papadopoulou",
    }

    # Preview (confirmed=False) must redact sensitive PII fields
    preview_res = skill.execute(
        {
            "action": "fill",
            "template_id": "us_irs_w8ben",
            "edits": edits,
            "output_dir": str(tmp_path),
            "confirmed": False,
        }
    )
    assert preview_res["status"] == "needs_input"
    prev = preview_res["preview"]
    assert prev["proposed_edits"]["foreign_tin"] == "***4321"
    assert prev["proposed_edits"]["date_of_birth"] == "***1992"
    assert prev["proposed_edits"]["beneficial_owner_name"] == "Elena Papadopoulou"
    assert "foreign_tin" in prev["redacted_fields"]
    assert "date_of_birth" in prev["redacted_fields"]
    assert "us_irs_w8ben_" in os.path.basename(prev["output_path"])
    assert prev["output_path"].endswith("_elena_papadopoulou.pdf")

    # Confirmed fill with flatten=True
    fill_res = skill.execute(
        {
            "action": "fill",
            "template_id": "us_irs_w8ben",
            "edits": edits,
            "output_dir": str(tmp_path),
            "confirmed": True,
            "flatten": True,
        }
    )
    assert fill_res["status"] == "success"
    assert fill_res["flattened"] is True
    out_file = fill_res["output_path"]
    assert os.path.isfile(out_file)

    # Verify filled text is present in the flattened output PDF
    doc = fitz.open(out_file)
    text = doc[0].get_text()
    doc.close()
    assert "Elena Papadopoulou" in text
    assert "EL-987654321" in text
    assert "Article 12(2)" in text


def test_w8ben_unflattened_widgets_roundtrip(skill, tmp_path):
    out_pdf = str(tmp_path / "w8ben_editable.pdf")
    edits = {
        "beneficial_owner_name": "Nikos Kazantzakis",
        "country_of_citizenship": "Greece",
        "permanent_residence_street": "12 Heraklion Ave",
        "permanent_residence_city_state_postal": "Heraklion 71201",
        "permanent_residence_country": "Greece",
        "ftin_not_legally_required": True,
        "capacity_to_sign": True,
        "signature_date": "11-18-2026",
        "signer_name": "Nikos Kazantzakis",
    }
    res = skill.execute(
        {
            "action": "fill",
            "template_id": "us_irs_w8ben",
            "edits": edits,
            "output_path": out_pdf,
            "confirmed": True,
            "flatten": False,
        }
    )
    assert res["status"] == "success"
    doc = fitz.open(out_pdf)
    widgets = {w.field_name: w.field_value for w in doc[0].widgets()}
    doc.close()
    assert widgets["topmostSubform[0].Page1[0].f_1[0]"] == "Nikos Kazantzakis"
    assert widgets["topmostSubform[0].Page1[0].Date[0]"] == "11-18-2026"
    assert widgets["topmostSubform[0].Page1[0].c1_01[0]"] in (True, "1", "Yes")
    assert widgets["topmostSubform[0].Page1[0].c1_02[0]"] in (True, "1", "Yes")


def test_operator_env_template_override_and_path_traversal_guard(
    skill, tmp_path, monkeypatch
):
    from skills.office.pdf_form_filler.kb.registry import resolve_template_pdf_path

    # Path traversal must be rejected
    with pytest.raises(ValueError, match="Unsafe source_pdf"):
        resolve_template_pdf_path(
            {"source_pdf": "../../../../etc/passwd", "_root_dir": str(tmp_path)}
        )

    # Custom template via PDF_TEMPLATES_DIR (with radio group schema)
    custom_root = tmp_path / "custom_kb"
    (custom_root / "schemas").mkdir(parents=True)
    (custom_root / "templates").mkdir(parents=True)

    # Create a minimal 1-page static PDF with a radio button group
    pdf_path = custom_root / "templates" / "custom_radio.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    (custom_root / "schemas" / "custom_tax.yaml").write_text(
        "form_id: custom_tax_v1\n"
        "title: Custom Radio Tax Form\n"
        "jurisdiction: EU\n"
        "category: tax\n"
        "source_pdf: templates/custom_radio.pdf\n"
        "sections:\n"
        "  - id: part_1\n"
        "    title: Part 1\n"
        "    fields:\n"
        "      - id: entity_type\n"
        "        pdf_field_name: entity_type_radio\n"
        "        field_type: radio\n"
        "        required: true\n"
        "        options:\n"
        "          - label: Individual\n"
        "            export_value: Choice1\n"
        "          - label: Corporation\n"
        "            export_value: Choice2\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("PDF_TEMPLATES_DIR", str(custom_root))
    listed = skill.execute({"action": "list_templates", "jurisdiction": "EU"})
    assert listed["count"] == 1
    assert listed["templates"][0]["template_id"] == "custom_tax"
    assert listed["templates"][0]["tier"] == "env"


def test_all_four_bundled_tax_templates_discoverable_and_fillable(skill, tmp_path):
    """Verify W-8BEN, W-9, W-8BEN-E, and 8966 FATCA are all discoverable, valid, and fillable."""
    listed = skill.execute({"action": "list_templates", "category": "tax"})
    assert listed["status"] == "ok"
    ids = {t["template_id"] for t in listed["templates"]}
    assert {"us_irs_w8ben", "us_irs_w9", "us_irs_w8bene", "us_irs_f8966_fatca"} <= ids

    # 1. W-9 fill + PII redaction
    w9_edits = {
        "legal_name": "Acme Robotics Inc",
        "tax_class_c_corp": True,
        "address_street": "500 Market St",
        "address_city_state_zip": "San Francisco, CA 94105",
        "ein_part1": "94",
        "ein_part2": "3456789",
    }
    w9_prev = skill.execute(
        {
            "action": "fill",
            "template_id": "us_irs_w9",
            "edits": w9_edits,
            "output_dir": str(tmp_path),
            "confirmed": False,
        }
    )
    assert w9_prev["status"] == "needs_input"
    assert w9_prev["preview"]["proposed_edits"]["ein_part2"] == "***6789"
    w9_fill = skill.execute(
        {
            "action": "fill",
            "template_id": "us_irs_w9",
            "edits": w9_edits,
            "output_dir": str(tmp_path),
            "confirmed": True,
            "flatten": True,
        }
    )
    assert w9_fill["status"] == "success"
    assert os.path.isfile(w9_fill["output_path"])

    # 2. W-8BEN-E fill
    w8bene_edits = {
        "organization_name": "Aegean Holdings Ltd",
        "country_of_incorporation": "Cyprus",
        "chapter3_corporation": True,
        "capacity_to_sign": True,
        "signature": "Nikos Georgiou",
        "signer_name": "Nikos Georgiou",
    }
    w8bene_fill = skill.execute(
        {
            "action": "fill",
            "template_id": "us_irs_w8bene",
            "edits": w8bene_edits,
            "output_dir": str(tmp_path),
            "confirmed": True,
            "flatten": True,
        }
    )
    assert w8bene_fill["status"] == "success"
    assert os.path.isfile(w8bene_fill["output_path"])

    # 3. Form 8966 FATCA fill + PII redaction
    f8966_edits = {
        "filer_id_number": "98-7654321",
        "filer_name": "Mediterranean Custody SA",
        "filer_address_street": "10 Kifisias Ave",
        "filer_city_town": "Athens",
        "filer_country": "Greece",
        "account_number": "ACCT-99887766",
        "account_balance": "250000.00",
    }
    f8966_prev = skill.execute(
        {
            "action": "fill",
            "template_id": "us_irs_f8966_fatca",
            "edits": f8966_edits,
            "output_dir": str(tmp_path),
            "confirmed": False,
        }
    )
    assert f8966_prev["status"] == "needs_input"
    assert f8966_prev["preview"]["proposed_edits"]["account_number"] == "***7766"
    f8966_fill = skill.execute(
        {
            "action": "fill",
            "template_id": "us_irs_f8966_fatca",
            "edits": f8966_edits,
            "output_dir": str(tmp_path),
            "confirmed": True,
            "flatten": True,
        }
    )
    assert f8966_fill["status"] == "success"
    assert os.path.isfile(f8966_fill["output_path"])


def test_session_state_machine_full_lifecycle(skill, tmp_path):
    """Test session_init -> session_update (values, skip, defer) -> session_preview -> session_finalize."""
    sdir = str(tmp_path / "sessions")

    # 1. Init
    init_res = skill.execute(
        {
            "action": "session_init",
            "template_id": "us_irs_w8ben",
            "session_dir": sdir,
        }
    )
    assert init_res["status"] == "ok"
    sid = init_res["session_id"]
    assert sid.startswith("sess_us_irs_w8ben_")
    assert init_res["progress"]["total_fields"] == 23

    # 2. Update: partial values + skip + defer
    upd1 = skill.execute(
        {
            "action": "session_update",
            "session_id": sid,
            "session_dir": sdir,
            "values": {
                "beneficial_owner_name": "Alice Smith",
                "country_of_citizenship": "Germany",
                "permanent_residence_street": "Musterstrasse 1",
                "permanent_residence_city_state_postal": "10115 Berlin",
                "permanent_residence_country": "Germany",
            },
            "skip_fields": ["us_tin"],
            "defer_fields": {"foreign_tin": "looking up tax certificate"},
        }
    )
    assert upd1["status"] == "needs_input"
    assert upd1["progress"]["filled_count"] == 5
    assert upd1["progress"]["skipped_count"] == 1
    assert upd1["progress"]["to_revise_count"] == 1
    assert upd1["pending_revisions"][0]["field_id"] == "foreign_tin"

    # 3. Update: resolve deferred field & certification
    upd2 = skill.execute(
        {
            "action": "session_update",
            "session_id": sid,
            "session_dir": sdir,
            "values": {
                "foreign_tin": "DE-123456789",
                "capacity_to_sign": True,
                "signature": "Alice Smith",
                "signer_name": "Alice Smith",
            },
        }
    )
    assert upd2["status"] == "ready"
    assert upd2["progress"]["to_revise_count"] == 0
    assert upd2["progress"]["remaining_required_count"] == 0

    # 4. Preview (masked by default, unmasked on request)
    prev_masked = skill.execute(
        {"action": "session_preview", "session_id": sid, "session_dir": sdir}
    )
    assert prev_masked["status"] == "preview"
    assert prev_masked["all_required_resolved"] is True
    assert (
        prev_masked["summary_table"]["6a. Foreign tax identifying number"] == "***6789"
    )
    assert (
        prev_masked["summary_table"][
            "5. U.S. taxpayer identification number (SSN or ITIN), if required"
        ]
        == "[SKIPPED]"
    )
    assert (
        "/s/ Alice Smith"
        in prev_masked["summary_table"][
            "Signature of beneficial owner (or authorized individual)"
        ]
    )

    prev_unmasked = skill.execute(
        {
            "action": "session_preview",
            "session_id": sid,
            "session_dir": sdir,
            "unmask": True,
        }
    )
    assert (
        prev_unmasked["summary_table"]["6a. Foreign tax identifying number"]
        == "DE-123456789"
    )

    # 5. Finalize: fails closed without confirmed=True
    unconfirmed = skill.execute(
        {
            "action": "session_finalize",
            "session_id": sid,
            "session_dir": sdir,
            "confirmed": False,
        }
    )
    assert unconfirmed["status"] == "needs_input"
    assert unconfirmed["error_code"] == "confirmation_required"

    # 6. Finalize: confirmed=True writes flattened PDF
    out_pdf = str(tmp_path / "alice_w8ben_final.pdf")
    finalized = skill.execute(
        {
            "action": "session_finalize",
            "session_id": sid,
            "session_dir": sdir,
            "output_path": out_pdf,
            "confirmed": True,
        }
    )
    assert finalized["status"] == "success"
    assert finalized["flattened"] is True
    assert os.path.isfile(out_pdf)
    doc = fitz.open(out_pdf)
    text = doc[0].get_text()
    doc.close()
    assert "Alice Smith" in text
    assert "/s/ Alice Smith" in text
    assert "DE-123456789" in text


def test_session_expiry_and_invalid_id_fail_closed(skill, tmp_path):
    sdir = tmp_path / "sessions"
    bad = skill.execute(
        {
            "action": "session_preview",
            "session_id": "../escape",
            "session_dir": str(sdir),
        }
    )
    assert bad["status"] == "error"
    assert bad["error_code"] == "invalid_session_id"

    # Expired session
    init_res = skill.execute(
        {
            "action": "session_init",
            "template_id": "us_irs_w8ben",
            "session_dir": str(sdir),
        }
    )
    sid = init_res["session_id"]
    sess_file = sdir / f"{sid}.json"
    import json

    data = json.loads(sess_file.read_text(encoding="utf-8"))
    data["expires_at"] = "2020-01-01T00:00:00Z"
    sess_file.write_text(json.dumps(data), encoding="utf-8")

    expired = skill.execute(
        {
            "action": "session_update",
            "session_id": sid,
            "session_dir": str(sdir),
            "values": {"signer_name": "X"},
        }
    )
    assert expired["status"] == "error"
    assert expired["error_code"] == "session_expired"


def test_legal_profile_self_and_entity_autofill_override_and_guards(skill, tmp_path):
    """Test #408: self-filing W-8BEN, client W-9/W-8BEN-E, override diff, ambiguity, mismatch."""
    ab_path = tmp_path / "addressbook.yaml"
    ab_data = {
        "contacts": {
            "me": {
                "display_name": "Nikos Papadopoulos",
                "is_self": True,
                "emails": ["nikos@example.com"],
                "legal_profile": {
                    "type": "individual",
                    "citizenship": "GR",
                    "date_of_birth": "1990-05-15",
                    "tax_residency": [
                        {"country": "GR", "tin": "094123456", "tin_type": "AFM"}
                    ],
                    "residence_address": {
                        "street": "10 Ermou St",
                        "city": "Athens",
                        "state_province": "Attica",
                        "postal_code": "10563",
                        "country": "GR",
                    },
                },
            },
            "acme_us": {
                "display_name": "Acme Ventures Inc",
                "org": "Acme Group",
                "emails": ["tax@acme.example"],
                "aliases": ["Acme"],
                "legal_profile": {
                    "type": "entity",
                    "tax_ids": {"US_EIN": "12-3456789"},
                    "company_registration": {
                        "jurisdiction": "US",
                        "entity_classification": "c_corp",
                    },
                    "authorized_signatory": {
                        "name": "Alice Director",
                        "title": "CFO",
                    },
                    "residence_address": {
                        "street": "100 Market St",
                        "city": "Wilmington",
                        "state_province": "DE",
                        "postal_code": "19801",
                        "country": "US",
                    },
                },
            },
            "acme_uk": {
                "display_name": "Acme UK Ltd",
                "emails": ["uk@acme.example"],
                "aliases": ["Acme"],
            },
        },
        "org_domains": {},
    }
    ab_path.write_text(yaml.safe_dump(ab_data, sort_keys=False), encoding="utf-8")
    sdir = tmp_path / "sessions"

    # 1. Self-filing W-8BEN: Greek AFM -> foreign_tin, GR -> Greece, ISO DOB -> MM-DD-YYYY
    init_w8 = skill.execute(
        {
            "action": "session_init",
            "template_id": "us_irs_w8ben",
            "use_profile": True,
            "addressbook_path": str(ab_path),
            "session_dir": str(sdir),
        }
    )
    assert init_w8["status"] == "ok"
    assert init_w8["contact_applied"] == "me (Nikos Papadopoulos)"
    assert "foreign_tin" in init_w8["autofilled_fields"]
    assert "date_of_birth" in init_w8["autofilled_fields"]

    # Preview masks sensitive foreign_tin and DOB
    prev = skill.execute(
        {
            "action": "session_preview",
            "session_id": init_w8["session_id"],
            "session_dir": str(sdir),
        }
    )
    assert prev["summary_table"]["6a. Foreign tax identifying number"] == "***3456"
    assert prev["summary_table"]["2. Country of citizenship"] == "Greece"

    # Override street address + add signer_name, then finalize -> profile_updates_suggested
    skill.execute(
        {
            "action": "session_update",
            "session_id": init_w8["session_id"],
            "session_dir": str(sdir),
            "values": {
                "permanent_residence_street": "22 Syntagma Sq",
                "signer_name": "Nikos Papadopoulos",
            },
        }
    )
    fin = skill.execute(
        {
            "action": "session_finalize",
            "session_id": init_w8["session_id"],
            "session_dir": str(sdir),
            "output_path": str(tmp_path / "w8_out.pdf"),
            "confirmed": True,
        }
    )
    assert fin["status"] == "success"
    assert fin["contact_applied"] == "me (Nikos Papadopoulos)"
    assert any(
        u["field_id"] == "permanent_residence_street"
        and u["old_value"] == "10 Ermou St"
        and u["new_value"] == "22 Syntagma Sq"
        for u in fin.get("profile_updates_suggested", [])
    )

    # 2. Client W-9 filing: segmented EIN + c_corp checkbox
    init_w9 = skill.execute(
        {
            "action": "session_init",
            "template_id": "us_irs_w9",
            "contact": "acme_us",
            "addressbook_path": str(ab_path),
            "session_dir": str(sdir),
        }
    )
    assert init_w9["status"] == "ok"
    assert {"legal_name", "ein_part1", "ein_part2", "tax_class_c_corp"}.issubset(
        set(init_w9["autofilled_fields"])
    )

    # 3. Client W-8BEN-E filing: authorized_signatory.name -> signer_name
    init_w8e = skill.execute(
        {
            "action": "session_init",
            "template_id": "us_irs_w8bene",
            "contact": "acme_us",
            "addressbook_path": str(ab_path),
            "session_dir": str(sdir),
        }
    )
    assert init_w8e["status"] == "ok"
    assert {"organization_name", "chapter3_corporation", "signer_name"}.issubset(
        set(init_w8e["autofilled_fields"])
    )

    # 4. Entity-type mismatch warning: individual 'me' on entity form 'us_irs_w8bene'
    mismatch = skill.execute(
        {
            "action": "session_init",
            "template_id": "us_irs_w8bene",
            "use_profile": True,
            "addressbook_path": str(ab_path),
            "session_dir": str(sdir),
        }
    )
    assert any("entity_type_mismatch" in w for w in mismatch.get("warnings", []))

    # 5. Fail-closed on ambiguous contact alias ("Acme" matches acme_us & acme_uk)
    ambig = skill.execute(
        {
            "action": "session_init",
            "template_id": "us_irs_w9",
            "contact": "Acme",
            "addressbook_path": str(ab_path),
            "session_dir": str(sdir),
        }
    )
    assert ambig["status"] == "needs_input"
    assert ambig["error_code"] == "ambiguous_contact"
    assert len(ambig["candidates"]) == 2


def test_filing_receipt_post_fill_readback_and_encrypted_corrupt_guards(
    skill, tmp_path
):
    """Test #407: SHA-256 filing_receipt, emit_receipt, post_fill_verification, encrypted/corrupt/Unicode."""
    import hashlib
    import json

    # 1. Corrupted PDF guard
    bad_pdf = tmp_path / "corrupt.pdf"
    bad_pdf.write_bytes(b"NOT_A_VALID_PDF_HEADER_12345")
    corrupt_res = skill.execute({"action": "inspect", "pdf_path": str(bad_pdf)})
    assert corrupt_res["status"] == "error"
    assert corrupt_res["error_code"] == "corrupted_pdf"

    # 2. Encrypted / password-protected PDF guard
    enc_pdf = tmp_path / "encrypted.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(
        str(enc_pdf),
        encryption=fitz.PDF_ENCRYPT_AES_256,
        user_pw="secret123",
        owner_pw="owner123",
    )
    doc.close()
    enc_res = skill.execute({"action": "inspect", "pdf_path": str(enc_pdf)})
    assert enc_res["status"] == "error"
    assert enc_res["error_code"] == "encrypted_pdf_unsupported"
    # Verify fill, validate, and session_init also fail closed on encrypted PDFs
    for act in ("validate", "fill", "session_init"):
        r = skill.execute({"action": act, "pdf_path": str(enc_pdf), "edits": {}})
        assert r["status"] == "error"
        assert r["error_code"] == "encrypted_pdf_unsupported"

    # 3. Fill with emit_receipt=True + Unicode entity name + flatten=True + SHA-256 verification
    out_flat = tmp_path / "w8_unicode_flat.pdf"
    fill_flat = skill.execute(
        {
            "action": "fill",
            "template_id": "us_irs_w8ben",
            "edits": {
                "beneficial_owner_name": "Müller & Söhne — Νίκος",
                "country_of_citizenship": "Germany",
                "permanent_residence_street": "Friedrichstraße 42",
                "permanent_residence_city_state_postal": "Berlin 10117",
                "permanent_residence_country": "Germany",
                "foreign_tin": "DE998877665",
                "capacity_to_sign": True,
                "signer_name": "Müller & Söhne",
            },
            "output_path": str(out_flat),
            "confirmed": True,
            "flatten": True,
            "emit_receipt": True,
        }
    )
    assert fill_flat["status"] == "success"
    assert fill_flat["post_fill_verification"]["pdf_valid"] is True
    assert fill_flat["post_fill_verification"]["flattened_verified"] is True
    assert fill_flat["post_fill_verification"]["remaining_widget_count"] == 0

    receipt = fill_flat["filing_receipt"]
    assert receipt["schema_version"] == "skillware-pdf-receipt/1"
    assert receipt["output_sha256"] == hashlib.sha256(out_flat.read_bytes()).hexdigest()
    assert len(receipt["template_sha256"]) == 64
    assert len(receipt["receipt_hash"]) == 64
    # Sensitive TIN must be masked in receipt and on disk
    assert "DE998877665" not in json.dumps(receipt)
    receipt_file = tmp_path / "w8_unicode_flat.pdf.receipt.json"
    assert receipt_file.is_file()
    assert fill_flat["receipt_path"] == str(receipt_file)
    assert "DE998877665" not in receipt_file.read_text(encoding="utf-8")

    # 4. Unflattened post_fill_verification verifies widget readback match
    out_unflat = tmp_path / "w8_unflat.pdf"
    fill_unflat = skill.execute(
        {
            "action": "fill",
            "template_id": "us_irs_w8ben",
            "edits": {
                "beneficial_owner_name": "Alice Smith",
                "country_of_citizenship": "Greece",
                "permanent_residence_street": "10 Ermou St",
                "permanent_residence_city_state_postal": "Athens 10563",
                "permanent_residence_country": "Greece",
                "capacity_to_sign": True,
                "signer_name": "Alice Smith",
            },
            "output_path": str(out_unflat),
            "confirmed": True,
            "flatten": False,
        }
    )
    assert fill_unflat["status"] == "success"
    assert fill_unflat["post_fill_verification"]["pdf_valid"] is True
    assert fill_unflat["post_fill_verification"]["remaining_widget_count"] > 0
    assert fill_unflat["post_fill_verification"]["readback_mismatches"] == []

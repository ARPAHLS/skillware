# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

import os
import sys
import types
from unittest.mock import MagicMock, patch

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
    assert skill_manifest["version"] == "0.1.2"
    assert manifest["version"] == "0.1.2"
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


# --- Backward Compatibility Shim Tests ---


def test_missing_pdf_returns_error(skill):
    result = skill.execute(
        {
            "pdf_path": "/nonexistent/form.pdf",
            "instructions": "Fill name with Alice",
        }
    )
    assert "error" in result
    assert "PDF file not found" in result["error"]


def test_missing_instructions_returns_error(skill, tmp_path):
    pdf_path = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    result = skill.execute({"pdf_path": str(pdf_path), "instructions": ""})
    assert "error" in result
    assert "No instructions provided" in result["error"]


@patch("skills.office.pdf_form_filler.skill.anthropic.Anthropic")
def test_execute_mocked(mock_anthropic_cls, tmp_path, monkeypatch):
    mock_client = mock_anthropic_cls.return_value
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text='{"page0_test_field": "Hello World"}')]
    mock_client.messages.create.return_value = mock_message
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")

    skill = PDFFormFillerSkill()

    pdf_path = tmp_path / "form.pdf"
    doc = fitz.open()
    page = doc.new_page()
    widget = fitz.Widget()
    widget.rect = fitz.Rect(10, 10, 100, 30)
    widget.field_name = "test_field"
    widget.field_type = 7
    page.add_widget(widget)
    doc.save(str(pdf_path))
    doc.close()

    result = skill.execute(
        {
            "pdf_path": str(pdf_path),
            "instructions": "Fill test field with Hello World",
        }
    )

    assert result["status"] == "success"
    assert "page0_test_field" in result["filled_fields"]
    assert os.path.exists(result["output_path"])


def test_legacy_mode_without_api_key_returns_guidance(skill, tmp_path, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    pdf_path = tmp_path / "blank.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(pdf_path))
    doc.close()

    res = skill.execute(
        {
            "pdf_path": str(pdf_path),
            "instructions": "Fill with Alice",
        }
    )
    assert "error" in res
    assert "ANTHROPIC_API_KEY" in res["error"]
    assert "inspect" in res.get("message", "")


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
            {"pdf_path": "/nonexistent/form.pdf", "instructions": "Fill name"}
        )
        assert "PDF file not found" in result["error"]

    assert sys.path == before


def test_loader_execute_with_host_utils_module(import_route, monkeypatch, tmp_path):
    host_utils = types.ModuleType("utils")
    monkeypatch.setitem(sys.modules, "utils", host_utils)
    bundle = _load_via_skill_loader()

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    result = bundle["class"]().execute(
        {"pdf_path": str(_blank_pdf(tmp_path)), "instructions": "Fill name"}
    )

    assert result == {
        "status": "warning",
        "message": "No fillable fields found in PDF.",
    }
    assert sys.modules["utils"] is host_utils
    assert (
        bundle["module"].detect_form_fields.__module__
        == HELPER_MODULE_BY_ROUTE[import_route]
    )


def test_loader_execute_does_not_register_top_level_utils(import_route, monkeypatch):
    monkeypatch.delitem(sys.modules, "utils", raising=False)
    skill = _load_via_skill_loader()["class"]()

    skill.execute({"pdf_path": "/nonexistent/form.pdf", "instructions": "Fill name"})
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

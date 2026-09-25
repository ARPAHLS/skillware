import os
from unittest.mock import MagicMock, patch

import fitz
import pytest
import yaml

from .skill import PDFFormFillerSkill


@pytest.fixture
def skill():
    return PDFFormFillerSkill()


@pytest.fixture
def manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_skill_manifest_consistency(skill, manifest):
    skill_manifest = skill.manifest
    assert skill_manifest["name"] == manifest["name"]
    assert manifest["name"] == "office/pdf_form_filler"
    assert skill_manifest["version"] == manifest["version"]


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

    if os.path.exists(result["output_path"]):
        os.remove(result["output_path"])

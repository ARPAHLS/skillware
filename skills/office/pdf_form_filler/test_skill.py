import os
import sys
import types
from unittest.mock import MagicMock, patch

import fitz
import pytest
import yaml

from skillware.core.loader import SkillLoader

from .skill import PDFFormFillerSkill

# Module that provides detect_form_fields for each helper import route in skill.py.
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


@pytest.fixture(params=sorted(HELPER_MODULE_BY_ROUTE))
def import_route(request, monkeypatch):
    """Helper import route taken when SkillLoader runs skill.py as ``skill_module``.

    ``package`` resolves the helpers through the installed ``skills`` package.
    ``file`` blocks that import so the sibling ``utils.py`` is loaded by path,
    as it would be for a bundle outside the package.
    """
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

import pytest
from unittest.mock import MagicMock, patch
import fitz
import os

# Import the skill class and utils
# We need to ensure the path is correct. conftest.py adds the root.
from skills.office.pdf_form_filler.skill import PDFFormFillerSkill
from skills.office.pdf_form_filler.utils import (
    detect_form_fields,
    apply_edits,
    FieldEdit,
)

from skillware.core.loader import SkillLoader


def test_pdf_form_filler_manifest():
    bundle = SkillLoader.load_skill("office/pdf_form_filler")
    skill = bundle["module"].PDFFormFillerSkill()
    manifest = bundle["manifest"]
    assert skill.manifest["name"] == manifest["name"]
    assert manifest["name"] == "office/pdf_form_filler"


# --- Utils Tests ---


def test_detect_form_fields_empty():
    """Test that detecting fields on a PDF with no fields returns empty list."""
    # Create a blank PDF in memory
    doc = fitz.open()
    doc.new_page()
    pdf_bytes = doc.tobytes()
    doc.close()

    fields = detect_form_fields(pdf_bytes)
    assert fields == []


def test_apply_edits_checkbox():
    """Test applying a boolean edit to a checkbox."""
    doc = fitz.open()
    page = doc.new_page()

    # Add a checkbox widget
    widget = fitz.Widget()
    widget.rect = fitz.Rect(10, 10, 50, 50)
    widget.field_name = "test_check"
    # 2 is CHECKBOX
    widget.field_type = 2
    page.add_widget(widget)
    pdf_bytes = doc.tobytes()
    doc.close()

    # Apply edit
    edits = [FieldEdit(field_id="page0_test_check", value=True)]
    new_pdf_bytes = apply_edits(pdf_bytes, edits)

    # Verify
    doc2 = fitz.open(stream=new_pdf_bytes, filetype="pdf")
    page2 = doc2[0]
    target_widget = None
    for w in page2.widgets():
        if w.field_name == "test_check":
            target_widget = w
            break

    assert target_widget is not None
    # PyMuPDF might return boolean or string depending on version.
    # Our utils sets it as bool.
    assert bool(target_widget.field_value) is True
    doc2.close()


# --- Skill Logic Tests ---


@patch("skills.office.pdf_form_filler.skill.anthropic.Anthropic")
def test_skill_execute_mocked(mock_anthropic_cls, tmp_path):
    """Test the full execution flow with mocked LLM."""
    # Setup Mock
    mock_client = mock_anthropic_cls.return_value
    mock_message = MagicMock()
    # Mock Claude returning a JSON mapping
    mock_message.content = [MagicMock(text='{"page0_test_field": "Hello World"}')]
    mock_client.messages.create.return_value = mock_message

    # Initialize Skill
    skill = PDFFormFillerSkill()

    # Create a dummy PDF with one text field
    doc = fitz.open()
    page = doc.new_page()
    widget = fitz.Widget()
    widget.rect = fitz.Rect(10, 10, 100, 30)
    widget.field_name = "test_field"
    # 7 is TEXT
    widget.field_type = 7
    page.add_widget(widget)
    temp_pdf_path = tmp_path / "temp_test_skill.pdf"
    doc.save(temp_pdf_path)
    doc.close()

    result = skill.execute(
        {
            "pdf_path": str(temp_pdf_path),
            "instructions": "Fill test field with Hello World",
        }
    )

    if "error" in result:
        pytest.fail(f"Skill execution returned error: {result['error']}")

    assert result["status"] == "success"
    assert "page0_test_field" in result["filled_fields"]
    assert os.path.exists(result["output_path"])

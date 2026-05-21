from skillware.cli import _discover_skills
import pytest


def test_discover_skills_returns_skills(tmp_path):
    # Create a fake skill directory structure
    skill_dir = tmp_path / "office" / "pdf_form_filler"
    skill_dir.mkdir(parents=True)

    manifest = skill_dir / "manifest.yaml"
    manifest.write_text(
        "name: pdf_form_filler\n"
        "version: 0.1.0\n"
        "description: Fills PDF forms.\n"
        "requirements:\n"
        "  - pymupdf\n"
    )

    skills = _discover_skills(tmp_path)

    assert len(skills) == 1
    assert skills[0]["id"] == "office/pdf_form_filler"
    assert skills[0]["version"] == "0.1.0"


def test_discover_skills_empty_directory(tmp_path):
    # No skills created, directory is empty
    skills = _discover_skills(tmp_path)

    assert skills == []


def test_discover_skills_nonexistent_path(tmp_path):
    fake_path = tmp_path / "nonexistent"

    with pytest.raises(FileNotFoundError):
        _discover_skills(fake_path)


def test_discover_skills_missing_optional_fields(tmp_path):
    # Manifest with only required fields, no version, description or requirements
    skill_dir = tmp_path / "office" / "minimal_skill"
    skill_dir.mkdir(parents=True)

    manifest = skill_dir / "manifest.yaml"
    manifest.write_text("name: minimal_skill\n")

    skills = _discover_skills(tmp_path)

    assert len(skills) == 1
    assert skills[0]["version"] == "?"
    assert skills[0]["description"] == ""
    assert skills[0]["requirements"] == ""


def test_discover_skills_ignores_deeply_nested_manifest(tmp_path):
    # manifest.yaml three levels deep should not be picked up
    skill_dir = tmp_path / "office" / "pdf_form_filler" / "extra"
    skill_dir.mkdir(parents=True)

    manifest = skill_dir / "manifest.yaml"
    manifest.write_text("name: should_not_appear\nversion: 0.1.0\n")

    skills = _discover_skills(tmp_path)

    assert skills == []

from pathlib import Path
import pytest
import yaml

from skillware.core.base_skill import BaseSkill, SkillwareParamValidationError
from skillware.core.loader import SkillLoader
from .skill import MyAwesomeSkill


@pytest.fixture
def skill():
    """Fixture to initialize the skill class."""
    return MyAwesomeSkill()


@pytest.fixture
def manifest():
    """Fixture to load manifest.yaml for validation."""
    manifest_path = Path(__file__).resolve().parent / "manifest.yaml"
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_skill_manifest_consistency(skill, manifest):
    """Verify internal manifest matches manifest.yaml basics."""
    skill_manifest = skill.manifest
    assert skill_manifest["name"] == manifest["name"]
    assert skill_manifest["version"] == manifest["version"]
    assert skill_manifest.get("category") == manifest.get("category")


def test_skill_execution(skill, manifest):
    """Test standard execution and validate output schema."""
    # 1. Prepare valid test inputs
    params = {"param1": "test-value"}

    # 2. Execute skill
    result = skill.execute(params)

    # 3. Validate result is a dictionary (JSON serializable)
    assert isinstance(result, dict), "Execution result must be a dictionary"
    assert result.get("status") == "success"

    # 4. Validate against 'outputs' defined in manifest.yaml
    expected_outputs = manifest.get("outputs", {})
    for key, spec in expected_outputs.items():
        assert key in result, f"Missing expected output key: '{key}'"

        expected_type = spec.get("type")
        if expected_type == "string":
            assert isinstance(result[key], str), f"Output '{key}' should be a string"
        elif expected_type == "integer":
            assert isinstance(result[key], int), f"Output '{key}' should be an integer"
        elif expected_type == "boolean":
            assert isinstance(result[key], bool), f"Output '{key}' should be a boolean"


def test_skill_param_validation_failure(skill):
    """Verify built-in schema validation rejects invalid input types."""
    with pytest.raises(SkillwareParamValidationError):
        skill.execute({"param1": 12345})  # param1 must be string per schema


def test_skill_loader_can_import():
    """Verify the skill bundle can be loaded dynamically via SkillLoader."""
    skill_dir = Path(__file__).resolve().parent
    bundle = SkillLoader.load_skill(str(skill_dir))
    assert bundle["manifest"]["name"] == "category/my_awesome_skill"
    assert bundle["class"].__name__ == "MyAwesomeSkill"
    assert issubclass(bundle["class"], BaseSkill)
    assert isinstance(bundle["instructions"], str)
    assert isinstance(bundle["card"], dict)

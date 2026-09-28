import pytest
import yaml
import os
from .skill import MyAwesomeSkill


@pytest.fixture
def skill():
    """Fixture to initialize the skill class."""
    return MyAwesomeSkill()


@pytest.fixture
def manifest():
    """Fixture to load the manifest.yaml for validation."""
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_skill_manifest_consistency(skill, manifest):
    """Verify the skill's internal manifest matches the manifest.yaml file basics."""
    skill_manifest = skill.manifest
    assert skill_manifest["name"] == manifest["name"]
    assert skill_manifest["version"] == manifest["version"]


def test_skill_execution(skill, manifest):
    """Test the skill execution and validate output schema."""
    # 1. Prepare placeholder input
    params = {"param1": "test-value"}

    # 2. Execute
    result = skill.execute(params)

    # 3. Validate result is a dictionary (JSON serializable)
    assert isinstance(result, dict), "Execution result must be a dictionary"

    # 4. Validate against 'outputs' defined in manifest.yaml
    expected_outputs = manifest.get("outputs", {})
    for key, spec in expected_outputs.items():
        assert key in result, f"Missing expected output key: '{key}'"

        # Optional: Basic type checking based on manifest
        expected_type = spec.get("type")
        if expected_type == "string":
            assert isinstance(result[key], str), f"Output '{key}' should be a string"
        elif expected_type == "integer":
            assert isinstance(result[key], int), f"Output '{key}' should be an integer"
        elif expected_type == "boolean":
            assert isinstance(result[key], bool), f"Output '{key}' should be a boolean"

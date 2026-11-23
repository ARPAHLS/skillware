import os

import pytest
import yaml

from .skill import SyntheticGeneratorSkill


@pytest.fixture
def skill():
    return SyntheticGeneratorSkill()


@pytest.fixture
def manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_skill_manifest_consistency(skill, manifest):
    skill_manifest = skill.manifest
    assert skill_manifest["name"] == manifest["name"]
    assert skill_manifest["version"] == manifest["version"]


def test_entropy_score(skill):
    low_entropy_text = "test " * 100
    score_low = skill._calculate_entropy_score(low_entropy_text)

    high_text = "The brown fox jumps over the dog. Programming is fun!"
    score_high = skill._calculate_entropy_score(high_text)

    assert score_high > score_low


def test_execute_success(mocker, skill):
    mock_json_response = """```json
[
  {"instruction": "x", "input": "y", "output": "z"}
]
```"""
    mocker.patch.object(skill, "_call_gemini", return_value=mock_json_response)

    result = skill.execute(
        {
            "domain": "test domain",
            "num_samples": 1,
            "diversity_prompt": "be diverse",
            "model_provider": "gemini",
        }
    )

    assert result["status"] == "success"
    assert result["provider_used"] == "gemini"
    assert result["samples_generated"] == 1
    assert "samples" in result
    assert result["samples"][0]["instruction"] == "x"


def test_anthropic_default_model_is_served(mocker, skill):
    # Anthropic retired claude-3-haiku-20240307 on 2026-04-20 (#510).
    call = mocker.patch.object(
        skill, "_call_anthropic", return_value='[{"instruction": "x"}]'
    )

    skill.execute(
        {
            "domain": "test domain",
            "num_samples": 1,
            "diversity_prompt": "be diverse",
            "model_provider": "anthropic",
        }
    )

    assert call.call_args.args[2] == "claude-haiku-5-5"

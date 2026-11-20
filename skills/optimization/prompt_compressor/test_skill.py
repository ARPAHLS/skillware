import os

import pytest
import yaml

from .skill import PromptCompressor


@pytest.fixture
def skill():
    return PromptCompressor()


@pytest.fixture
def manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_skill_manifest_consistency(skill, manifest):
    skill_manifest = skill.manifest
    assert skill_manifest["name"] == manifest["name"]
    assert skill_manifest["version"] == manifest["version"]


def test_compressor_execution_lossless(skill):
    result = skill.execute(
        {
            "raw_text": "This   is a    very\n\n\nspaced out  prompt.",
            "compression_aggression": "lossless",
        }
    )
    assert result["compressed_text"] == "This is a very spaced out prompt."
    assert result["original_tokens"] >= result["new_tokens"]


def test_compressor_execution_aggressive(skill):
    result = skill.execute(
        {
            "raw_text": "Please make sure to read this and analyze the data.",
            "compression_aggression": "aggressive",
        }
    )
    assert "Please" not in result["compressed_text"]
    assert "make sure to" not in result["compressed_text"]
    assert result["tokens_saved"] > 0
    assert "new_tokens" in result
    assert "original_tokens" in result


def test_empty_string_returns_error(skill):
    result = skill.execute({"raw_text": ""})
    assert "error" in result
    assert result["error"] == "raw_text cannot be empty."

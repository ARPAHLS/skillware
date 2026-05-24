import pytest
import yaml
import os
from .skill import NoveltyExtractor


@pytest.fixture
def skill():
    """Fixture to initialize the skill."""
    return NoveltyExtractor()


@pytest.fixture
def manifest():
    """Fixture to load manifest.yaml for validation."""
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_skill_manifest_consistency(skill, manifest):
    """Verify the skill manifest matches manifest.yaml."""
    skill_manifest = skill.manifest
    assert skill_manifest["name"] == manifest["name"]
    assert skill_manifest["version"] == manifest["version"]


def test_skill_returns_dict(skill):
    """Execution result must be a dictionary."""
    result = skill.execute(
        {
            "dataset_chunk": "Bitcoin is going to rise.\n\nThe sky is blue.",
            "novelty_threshold": 0.85,
        }
    )
    assert isinstance(result, dict)


def test_skill_output_keys(skill):
    """Result must contain the three expected output keys."""
    result = skill.execute(
        {
            "dataset_chunk": "Bitcoin is going to rise.\n\nThe sky is blue.",
            "novelty_threshold": 0.85,
        }
    )
    assert "distilled_content" in result
    assert "compression_ratio" in result
    assert "redundant_chunks_dropped" in result


def test_skill_filters_redundant_chunks(skill):
    """Semantically similar chunks should be filtered out."""
    result = skill.execute(
        {
            "dataset_chunk": (
                "Bitcoin is going to rise.\n\n"
                "Bitcoin will increase in value.\n\n"
                "The sky is blue."
            ),
            "novelty_threshold": 0.85,
        }
    )
    assert result["redundant_chunks_dropped"] >= 1
    assert "Bitcoin is going to rise." in result["distilled_content"]
    assert "The sky is blue." in result["distilled_content"]


def test_skill_empty_input(skill):
    """Empty input should return empty result without crashing."""
    result = skill.execute(
        {
            "dataset_chunk": "",
            "novelty_threshold": 0.85,
        }
    )
    assert result["distilled_content"] == ""
    assert result["redundant_chunks_dropped"] == 0


def test_skill_baseline_filters_seen_content(skill):
    """Chunks already in baseline should be filtered out."""
    baseline = "Bitcoin is going to rise.\n\nThe sky is blue."
    result = skill.execute(
        {
            "dataset_chunk": "Bitcoin is going to rise.\n\nPython is a programming language.",
            "novelty_threshold": 0.85,
            "baseline_chunks": baseline,
        }
    )
    assert "Python is a programming language." in result["distilled_content"]
    assert result["redundant_chunks_dropped"] >= 1


def test_skill_sentence_strategy(skill):
    """Sentence chunking strategy should work without crashing."""
    result = skill.execute(
        {
            "dataset_chunk": "Bitcoin is going to rise. The sky is blue. Python is great.",
            "novelty_threshold": 0.85,
            "chunk_strategy": "sentence",
        }
    )
    assert isinstance(result, dict)
    assert "distilled_content" in result

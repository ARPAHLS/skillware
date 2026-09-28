"""Assurance tests for optimization/context_optimizer."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import numpy as np
import pytest
import yaml

from .skill import ContextOptimizerSkill


def _mock_embed_vectors(texts):
    """Deterministic keyword vectors — no HuggingFace download in CI."""
    vectors = []
    for text in texts:
        t = text.lower()
        if "jurisdiction" in t or "data handling" in t or "gdpr" in t:
            vectors.append(np.array([1.0, 0.0, 0.0], dtype=float))
        elif "marketing" in t or "newsletter" in t:
            vectors.append(np.array([0.0, 1.0, 0.0], dtype=float))
        elif "support" in t or "retention" in t:
            vectors.append(np.array([0.0, 0.0, 1.0], dtype=float))
        elif "quantum" in t:
            vectors.append(np.array([0.01, 0.99, 0.01], dtype=float))
        else:
            vectors.append(np.array([0.2, 0.5, 0.1], dtype=float))
    return vectors


@pytest.fixture(autouse=True)
def mock_embedding_model(monkeypatch):
    ContextOptimizerSkill._model = None
    mock_model = MagicMock()
    mock_model.embed.side_effect = _mock_embed_vectors

    @classmethod
    def _fake_get_model(cls):
        if cls._model is None:
            cls._model = mock_model
        return cls._model

    monkeypatch.setattr(ContextOptimizerSkill, "_get_model", _fake_get_model)
    yield
    ContextOptimizerSkill._model = None


@pytest.fixture
def skill():
    return ContextOptimizerSkill()


@pytest.fixture
def manifest():
    path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture
def sample_document():
    path = os.path.join(os.path.dirname(__file__), "data", "sample_policy.txt")
    return path


def test_manifest_consistency(skill, manifest):
    assert skill.manifest["name"] == manifest["name"]
    assert skill.manifest["version"] == manifest["version"]


def test_selects_jurisdiction_section(skill, sample_document):
    document = open(sample_document, encoding="utf-8").read()
    result = skill.execute(
        {
            "document_text": document,
            "agent_goal": "Find jurisdiction clauses for data handling.",
            "max_tokens_return": 80,
            "min_score": 0.2,
        }
    )
    assert result["status"] == "ready"
    assert "GDPR" in result["optimized_context"]
    assert "newsletter" not in result["optimized_context"].lower()
    assert result["chunks_selected_count"] >= 1
    assert "%" in result["reduction_percentage"]


def test_small_document_passthrough(skill):
    text = "Short note about jurisdiction and GDPR only."
    result = skill.execute(
        {
            "document_text": text,
            "agent_goal": "jurisdiction",
            "max_tokens_return": 5000,
        }
    )
    assert result["status"] == "ready"
    assert result["optimized_context"] == text
    assert result["reduction_percentage"] == "0%"


def test_empty_result_when_min_score_too_high(skill, sample_document):
    document = open(sample_document, encoding="utf-8").read()
    result = skill.execute(
        {
            "document_text": document,
            "agent_goal": "quantum physics equations",
            "max_tokens_return": 80,
            "min_score": 1.0,
        }
    )
    assert result["status"] == "empty_result"
    assert result["optimized_context"] == ""
    assert result["chunks_selected_count"] == 0


def test_missing_document_error(skill):
    result = skill.execute({"document_text": "", "agent_goal": "find clauses"})
    assert result["status"] == "error"
    assert result["error"] == "missing_document"


def test_missing_goal_error(skill):
    result = skill.execute({"document_text": "hello", "agent_goal": ""})
    assert result["status"] == "error"
    assert result["error"] == "missing_goal"


def test_chunks_selected_traceability(skill, sample_document):
    document = open(sample_document, encoding="utf-8").read()
    result = skill.execute(
        {
            "document_text": document,
            "agent_goal": "data handling jurisdiction",
            "max_tokens_return": 800,
            "min_score": 0.2,
        }
    )
    row = result["chunks_selected"][0]
    assert "index" in row and "score" in row and "start_offset" in row
    assert "preview" in row


def test_fixed_chars_strategy(skill):
    document = (
        "Intro paragraph about billing.\n\n" + "Jurisdiction GDPR data handling.\n\n"
    ) * 12
    result = skill.execute(
        {
            "document_text": document,
            "agent_goal": "jurisdiction data handling GDPR",
            "max_tokens_return": 40,
            "chunk_strategy": "fixed_chars",
            "chunk_size_chars": 80,
            "chunk_overlap_chars": 10,
            "min_score": 0.2,
        }
    )
    assert result["status"] == "ready"
    assert result["chunk_strategy"] == "fixed_chars"

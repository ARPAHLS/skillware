"""Integration tests for optimization/context_optimizer via SkillLoader."""

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
from skillware.core.loader import SkillLoader

REPO_ROOT = Path(__file__).resolve().parents[3]
SAMPLE_POLICY = (
    REPO_ROOT
    / "skills"
    / "optimization"
    / "context_optimizer"
    / "data"
    / "sample_policy.txt"
)


def _mock_embed_vectors(texts):
    vectors = []
    for text in texts:
        if "jurisdiction" in text.lower():
            vectors.append(np.array([1.0, 0.0], dtype=float))
        else:
            vectors.append(np.array([0.1, 0.1], dtype=float))
    return vectors


def test_context_optimizer_loads_and_executes_with_mocked_embed(monkeypatch):
    bundle = SkillLoader.load_skill("optimization/context_optimizer")
    skill_cls = bundle["class"]
    skill_cls._model = None

    mock_model = MagicMock()
    mock_model.embed.side_effect = _mock_embed_vectors

    @classmethod
    def _fake_get_model(cls):
        if cls._model is None:
            cls._model = mock_model
        return cls._model

    monkeypatch.setattr(skill_cls, "_get_model", _fake_get_model)

    skill = skill_cls()
    document = SAMPLE_POLICY.read_text(encoding="utf-8")
    result = skill.execute(
        {
            "document_text": document,
            "agent_goal": "jurisdiction for data handling",
            "max_tokens_return": 80,
            "min_score": 0.2,
        }
    )
    assert result["status"] == "ready"
    assert "optimized_context" in result
    assert "GDPR" in result["optimized_context"]

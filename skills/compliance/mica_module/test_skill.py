import os

import pytest
import yaml

from .skill import MiCAModuleSkill


@pytest.fixture
def skill():
    return MiCAModuleSkill()


@pytest.fixture
def manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_skill_manifest_consistency(skill, manifest):
    skill_manifest = skill.manifest
    assert skill_manifest["name"] == manifest["name"]
    assert skill_manifest["version"] == manifest["version"]
    assert "informational reference" in skill_manifest["constitution"].lower()


def test_stateless_rag_execution(skill):
    result = skill.execute(
        {
            "user_prompt": (
                "I want to issue an asset-referenced token. "
                "What are the authorization rules?"
            ),
            "run_evaluator": False,
        }
    )
    assert result["statutory_snapshot"] == (
        "Regulation (EU) 2023/1114 (MiCA), OJ L 150/40, 9 June 2023"
    )
    assert result["policy_status"] == "CAUTION"
    assert "retrieved_sections" in result
    assert "final_context_for_agent" in result
    assert "Evaluator disabled" in result["gemini_evaluator_feedback"]["holes_found"]


def test_router_normalization(skill):
    mock_corpus = [
        {
            "title_num": "Title V",
            "article_num": "Article 59",
            "keywords": ["authorisation", "casp"],
            "content": "CASP Authorization rules...",
        }
    ]
    matched = skill._route_and_fetch("Authorization of a CASP", mock_corpus)
    assert len(matched) > 0
    assert matched[0]["article_num"] == "Article 59"


def test_router_deduplication(skill):
    mock_corpus = [
        {
            "title_num": "Title V",
            "article_num": "Article 59",
            "keywords": ["authorisation", "casp"],
            "content": "CASP Authorization rules...",
        }
    ]
    matched = skill._route_and_fetch("authorisation casp", mock_corpus)
    assert len(matched) == 1

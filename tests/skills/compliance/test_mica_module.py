import pytest
from skillware.core.loader import SkillLoader


# Fixture to load the skill module
@pytest.fixture
def mica_skill():
    skill_bundle = SkillLoader.load_skill("compliance/mica_module")
    MiCAModuleSkill = skill_bundle["module"].MiCAModuleSkill
    return MiCAModuleSkill()


def test_mica_module_manifest(mica_skill):
    manifest = mica_skill.manifest
    assert manifest["name"] == "compliance/mica_module"
    assert manifest["version"] == "0.1.0"


def test_mica_module_stateless_rag_execution(mica_skill):
    # Test that the module correctly pulls information without running the evaluator
    params = {
        "user_prompt": "I want to issue an asset-referenced token. What are the authorization rules?",
        "run_evaluator": False,
    }

    result = mica_skill.execute(params)

    # Since run_evaluator is False, policy_status should default to CAUTION
    assert result["policy_status"] == "CAUTION"

    # It should have either found some chunks or correctly reported no matches
    assert "retrieved_sections" in result
    assert "final_context_for_agent" in result

    feedback = result["gemini_evaluator_feedback"]
    assert "Evaluator disabled" in feedback["holes_found"]


def test_mica_module_router_normalization(mica_skill):
    # Verify that 'authorization' (US) matches 'authorisation' (UK)
    mock_corpus = [
        {
            "title_num": "Title V",
            "article_num": "Article 59",
            "keywords": ["authorisation", "casp"],
            "content": "CASP Authorization rules...",
        }
    ]
    matched = mica_skill._route_and_fetch("Authorization of a CASP", mock_corpus)
    assert len(matched) > 0
    assert matched[0]["article_num"] == "Article 59"


def test_mica_module_router_deduplication(mica_skill):
    # Verify that multiple keyword matches dont duplicate the same article
    mock_corpus = [
        {
            "title_num": "Title V",
            "article_num": "Article 59",
            "keywords": ["authorisation", "casp"],
            "content": "CASP Authorization rules...",
        }
    ]
    # 'authorisation' and 'casp' both match
    matched = mica_skill._route_and_fetch("authorisation casp", mock_corpus)
    assert len(matched) == 1

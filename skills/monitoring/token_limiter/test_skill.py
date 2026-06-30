import json
import os

import pytest
import yaml

from .skill import TokenLimiterSkill, SCHEMA_VERSION


@pytest.fixture
def skill():
    return TokenLimiterSkill()


@pytest.fixture
def manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture
def card():
    card_path = os.path.join(os.path.dirname(__file__), "card.json")
    with open(card_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def test_manifest_name(skill, manifest):
    assert skill.manifest["name"] == manifest["name"]
    assert manifest["name"] == "monitoring/token_limiter"


def test_manifest_version(skill, manifest):
    assert skill.manifest["version"] == manifest["version"]


def test_manifest_has_real_issuer(manifest):
    issuer = manifest.get("issuer", {})
    assert issuer.get("name")
    assert issuer.get("email")
    assert issuer["name"].lower() != "your name"
    assert issuer["email"].lower() != "you@example.com"


def test_card_issuer_matches_manifest(manifest, card):
    m_issuer = manifest.get("issuer", {})
    c_issuer = card.get("issuer", {})
    assert c_issuer.get("name") == m_issuer.get("name")
    assert c_issuer.get("email") == m_issuer.get("email")


def test_missing_task_id_returns_error(skill):
    result = skill.execute({"current_token_count": 10, "max_allowed_tokens": 100})
    assert result["status"] == "error"
    assert "task_id" in result["message"].lower()


def test_continue_under_soft_threshold(skill):
    result = skill.execute(
        {
            "task_id": "task-1",
            "current_token_count": 50_000,
            "max_allowed_tokens": 100_000,
        }
    )
    assert result["status"] == "ready"
    assert result["action"] == "CONTINUE"
    assert result["schema_version"] == SCHEMA_VERSION


def test_warn_at_soft_threshold(skill):
    result = skill.execute(
        {
            "task_id": "task-warn",
            "current_token_count": 80_000,
            "max_allowed_tokens": 100_000,
            "soft_threshold_pct": 80,
        }
    )
    assert result["action"] == "WARN"
    assert result["budget"]["utilization_pct"] == 80.0


def test_force_terminate_over_limit(skill):
    result = skill.execute(
        {
            "task_id": "scrape_amazon_listings_101",
            "current_token_count": 125_000,
            "max_allowed_tokens": 100_000,
            "model_id": "gpt-4o",
            "roi_value_usd": 2.50,
        }
    )
    assert result["action"] == "FORCE_TERMINATE"
    assert result["budget"]["tokens_over_budget"] == 25_000
    assert "25" in result["reason"]
    assert result["cost"]["incurred_usd"] is not None
    assert result["roi"]["status"] == "scaffold_only"
    assert result["roi"]["enabled"] is True


def test_roi_scaffold_does_not_terminate_below_limit(skill):
    result = skill.execute(
        {
            "task_id": "task-roi",
            "current_token_count": 10_000,
            "max_allowed_tokens": 100_000,
            "roi_value_usd": 1.0,
            "expected_outcome": "Deliver JSON summary of 10 listings",
            "outcome_delivered": False,
        }
    )
    assert result["action"] == "CONTINUE"
    assert result["roi"]["enabled"] is True
    assert result["roi"]["status"] == "scaffold_only"


def test_unknown_model_uses_fallback_pricing(skill):
    result = skill.execute(
        {
            "task_id": "task-unknown-model",
            "current_token_count": 1_000_000,
            "max_allowed_tokens": 2_000_000,
            "model_id": "unknown-model-9000",
        }
    )
    assert result["status"] == "ready"
    assert any("Unknown model_id" in w for w in result["metadata"]["warnings"])
    assert result["cost"]["incurred_usd"] == 5.0


def test_turn_id_cache_is_idempotent(skill):
    params = {
        "task_id": "task-cache",
        "turn_id": "turn-3",
        "current_token_count": 90_000,
        "max_allowed_tokens": 100_000,
    }
    first = skill.execute(params)
    second = skill.execute(params)
    assert first["action"] == second["action"]
    assert second["metadata"]["cache_hit"] is True


def test_reset_clears_turn_cache(skill):
    params = {
        "task_id": "task-reset",
        "turn_id": "turn-1",
        "current_token_count": 90_000,
        "max_allowed_tokens": 100_000,
    }
    skill.execute(params)
    reset = skill.execute({"action": "reset", "task_id": "task-reset"})
    assert reset["status"] == "ready"
    assert reset["action"] == "RESET"
    again = skill.execute(params)
    assert again["metadata"]["cache_hit"] is False


def test_invalid_action(skill):
    result = skill.execute({"action": "fly", "task_id": "x"})
    assert result["status"] == "error"


def test_result_is_json_serializable(skill):
    result = skill.execute(
        {
            "task_id": "json-task",
            "current_token_count": 1,
            "max_allowed_tokens": 100,
        }
    )
    json.dumps(result)

import json
import unittest.mock as mock
import os

import pytest
import yaml

from .skill import IssueResolverSkill


@pytest.fixture
def skill():
    """Initialise the skill with no config (mirrors production load)."""
    return IssueResolverSkill()


@pytest.fixture
def manifest():
    """Load manifest.yaml for schema validation."""
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def card():
    """Load card.json for issuer consistency checks."""
    card_path = os.path.join(os.path.dirname(__file__), "card.json")
    with open(card_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Manifest integrity
# ---------------------------------------------------------------------------


def test_manifest_name(skill, manifest):
    """Skill internal manifest name must match manifest.yaml."""
    assert skill.manifest["name"] == manifest["name"]


def test_manifest_version(skill, manifest):
    """Skill internal manifest version must match manifest.yaml."""
    assert skill.manifest["version"] == manifest["version"]


def test_manifest_has_real_issuer(manifest):
    """manifest.yaml issuer must have non-placeholder name and email."""
    issuer = manifest.get("issuer", {})
    assert issuer.get("name"), "issuer.name is required"
    assert issuer.get("email"), "issuer.email is required"
    assert issuer["name"].lower() != "your name"
    assert issuer["email"].lower() != "you@example.com"


def test_card_issuer_matches_manifest(manifest, card):
    """card.json issuer name and email must match manifest.yaml."""
    m_issuer = manifest.get("issuer", {})
    c_issuer = card.get("issuer", {})
    assert c_issuer.get("name", "").strip() == m_issuer.get("name", "").strip()
    assert c_issuer.get("email", "").strip() == m_issuer.get("email", "").strip()


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_missing_issue_url_returns_error(skill):
    """execute() must return a structured error when issue_url is absent."""
    result = skill.execute({})
    assert result["status"] == "error"
    assert "issue_url" in result["message"].lower()


def test_empty_issue_url_returns_error(skill):
    """execute() must return a structured error when issue_url is empty string."""
    result = skill.execute({"issue_url": "  "})
    assert result["status"] == "error"


def test_malformed_url_returns_error(skill):
    """A URL that is not a GitHub issue URL must produce a structured error."""
    result = skill.execute({"issue_url": "https://example.com/not-an-issue"})
    assert result["status"] == "error"
    assert "issue_url" in result["message"].lower()


def test_non_issue_github_url_returns_error(skill):
    """A GitHub URL pointing to a PR or repo root must be rejected."""
    result = skill.execute({"issue_url": "https://github.com/owner/repo/pull/42"})
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Happy-path execution
# ---------------------------------------------------------------------------


VALID_URL = "https://github.com/ARPAHLS/skillware/issues/56"


def test_valid_url_returns_ready(skill):
    """A well-formed GitHub issue URL must produce status: ready."""
    result = skill.execute({"issue_url": VALID_URL})
    assert result["status"] == "ready"


def test_result_contains_issue_fields(skill):
    """Ready result must include all issue sub-fields."""
    result = skill.execute({"issue_url": VALID_URL})
    issue = result["issue"]
    assert issue["owner"] == "ARPAHLS"
    assert issue["repo"] == "skillware"
    assert issue["number"] == "56"
    assert issue["api_url"].startswith(
        "https://api.github.com/repos/ARPAHLS/skillware/issues/56"
    )
    assert issue["url"] == VALID_URL


def test_result_contains_repository_fields(skill):
    """Ready result must include pre-computed repository URL fields."""
    result = skill.execute({"issue_url": VALID_URL})
    repo = result["repository"]
    assert repo["html_url"] == "https://github.com/ARPAHLS/skillware"
    assert repo["api_url"].startswith("https://api.github.com/repos/ARPAHLS/skillware")
    assert repo["readme_url"].startswith(
        "https://raw.githubusercontent.com/ARPAHLS/skillware"
    )
    assert repo["readme_url"].endswith("README.md")
    assert repo["tree_api_url"].startswith(
        "https://api.github.com/repos/ARPAHLS/skillware"
    )
    assert "trees" in repo["tree_api_url"]


def test_no_token_auth_note(skill):
    """When no token is provided, auth.token_provided must be False."""
    env_without_token = {k: v for k, v in os.environ.items() if k != "GITHUB_TOKEN"}
    with mock.patch.dict(os.environ, env_without_token, clear=True):
        skill.config = {}
        result = skill.execute({"issue_url": VALID_URL})
    assert result["auth"]["token_provided"] is False
    assert "rate limit" in result["auth"]["note"].lower()


def test_runtime_token_takes_precedence(skill):
    """A token passed in params must be recognised over env vars."""
    result = skill.execute({"issue_url": VALID_URL, "github_token": "ghp_test_token"})
    assert result["auth"]["token_provided"] is True
    assert "Authorization" in result["auth"]["note"]


def test_extra_instructions_propagated(skill):
    """extra_instructions must be present in the payload when provided."""
    result = skill.execute(
        {
            "issue_url": VALID_URL,
            "extra_instructions": "Focus only on test coverage gaps.",
        }
    )
    assert result["extra_instructions"] == "Focus only on test coverage gaps."


def test_no_extra_instructions_is_none(skill):
    """extra_instructions must be None in the payload when not provided."""
    result = skill.execute({"issue_url": VALID_URL})
    assert result["extra_instructions"] is None


def test_result_is_json_serializable(skill):
    """execute() output must be fully JSON-serializable."""
    result = skill.execute({"issue_url": VALID_URL})
    serialized = json.dumps(result)
    assert isinstance(serialized, str)


def test_next_step_present(skill):
    """Ready result must include a next_step hint for the calling agent."""
    result = skill.execute({"issue_url": VALID_URL})
    assert "next_step" in result
    assert isinstance(result["next_step"], str)
    assert len(result["next_step"]) > 0

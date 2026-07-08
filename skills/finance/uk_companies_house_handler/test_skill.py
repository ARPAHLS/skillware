import os
from unittest.mock import MagicMock, patch

import pytest
import yaml

from .skill import UkCompaniesHouseHandlerSkill

# --- Fixtures ---


@pytest.fixture
def skill():
    """Initialize skill with a dummy API key."""
    return UkCompaniesHouseHandlerSkill(
        config={"COMPANIES_HOUSE_API_KEY": "test_key_123"}
    )


@pytest.fixture
def manifest():
    """Load manifest.yaml for validation."""
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# --- Manifest and Init Tests ---


def test_manifest_consistency(skill, manifest):
    """Verify skill manifest matches manifest.yaml."""
    skill_manifest = skill.manifest
    assert skill_manifest["name"] == manifest["name"]
    assert skill_manifest["version"] == manifest["version"]


def test_missing_api_key():
    """Constructor raises ValueError without API key."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError, match="COMPANIES_HOUSE_API_KEY"):
            UkCompaniesHouseHandlerSkill(config={})


def test_data_files_loaded(skill):
    """Verify api_index and terminology_map load at init."""
    assert isinstance(skill.api_index, dict)
    assert "endpoints" in skill.api_index
    assert isinstance(skill.terminology_map, dict)
    assert "role_mappings" in skill.terminology_map


# --- Action Validation Tests ---


def test_missing_action(skill):
    """Missing action returns error status."""
    result = skill.execute({})
    assert result["status"] == "error"
    assert result["error_code"] == "missing_action"
    assert "fetched_at" in result


def test_invalid_action(skill):
    """Unknown action returns error status."""
    result = skill.execute({"action": "nonexistent"})
    assert result["status"] == "error"
    assert result["error_code"] == "invalid_action"
    assert "fetched_at" in result


def test_missing_company_number(skill):
    """Actions requiring company_number fail without it."""
    for action in [
        "get_company_profile",
        "get_officers",
        "get_pscs",
        "get_filing_history",
    ]:
        result = skill.execute({"action": action})
        assert result["status"] == "error"
        assert result["error_code"] == "missing_company_number"
        assert "resolve_company" in result.get("next_actions", [])


# --- resolve_company Tests ---


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_resolve_company_multiple_matches(mock_request, skill):
    """Multiple search results return needs_input status."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "company_number": "00102498",
                "title": "BP P.L.C.",
                "company_status": "active",
                "company_type": "plc",
                "address_snippet": "London",
                "date_of_creation": "1909-04-14",
            },
            {
                "company_number": "01234567",
                "title": "BP ALTERNATIVE LTD",
                "company_status": "active",
                "company_type": "ltd",
                "address_snippet": "Manchester",
                "date_of_creation": "2015-01-01",
            },
            {
                "company_number": "07654321",
                "title": "BP SERVICES LTD",
                "company_status": "dissolved",
                "company_type": "ltd",
                "address_snippet": "Birmingham",
                "date_of_creation": "2010-06-15",
            },
            {
                "company_number": "09999999",
                "title": "BP CONSULTING LTD",
                "company_status": "active",
                "company_type": "ltd",
                "address_snippet": "Leeds",
                "date_of_creation": "2020-03-01",
            },
        ]
    }
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    result = skill.execute({"action": "resolve_company", "query": "BP"})

    assert result["status"] == "needs_input"
    assert result["reason"] == "multiple_matches"
    assert len(result["candidates"]) == 4
    assert result["candidates"][0]["company_number"] == "00102498"
    assert "agent_hint" in result
    assert "fetched_at" in result


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_resolve_company_single_active_match(mock_request, skill):
    """Single active match returns ready status."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "company_number": "00102498",
                "title": "BP P.L.C.",
                "company_status": "active",
                "company_type": "plc",
                "address_snippet": "London",
                "date_of_creation": "1909-04-14",
            },
        ]
    }
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    result = skill.execute({"action": "resolve_company", "query": "BP PLC"})

    assert result["status"] == "ready"
    assert result["company_number"] == "00102498"
    assert result["company_name"] == "BP P.L.C."
    assert "next_actions" in result
    assert "fetched_at" in result


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_resolve_company_no_results(mock_request, skill):
    """No results returns error status."""
    mock_response = MagicMock()
    mock_response.json.return_value = {"items": []}
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    result = skill.execute({"action": "resolve_company", "query": "xyznonexistent"})

    assert result["status"] == "error"
    assert result["error_code"] == "no_results"


def test_resolve_company_missing_query(skill):
    """resolve_company without query returns error."""
    result = skill.execute({"action": "resolve_company"})
    assert result["status"] == "error"
    assert result["error_code"] == "missing_query"


# --- get_company_profile Tests ---


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_company_profile(mock_request, skill):
    """Profile action returns structured company data."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "company_name": "BP P.L.C.",
        "company_status": "active",
        "type": "plc",
        "date_of_creation": "1909-04-14",
        "registered_office_address": {
            "address_line_1": "1 St James Square",
            "locality": "London",
            "postal_code": "SW1Y 4PD",
        },
        "sic_codes": ["06100"],
        "has_charges": True,
        "jurisdiction": "england-wales",
    }
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    result = skill.execute(
        {
            "action": "get_company_profile",
            "company_number": "00102498",
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00102498"
    assert result["company_name"] == "BP P.L.C."
    assert result["company_status"] == "active"
    assert result["sic_codes"] == ["06100"]
    assert "next_actions" in result
    assert "fetched_at" in result


# --- get_officers Tests ---


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_officers(mock_request, skill):
    """Officers action returns structured officer list."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "name": "SMITH, John",
                "officer_role": "director",
                "appointed_on": "2020-03-01",
                "nationality": "British",
            },
            {
                "name": "DOE, Jane",
                "officer_role": "secretary",
                "appointed_on": "2019-06-15",
                "resigned_on": "2023-01-01",
            },
        ],
        "total_results": 2,
        "active_count": 1,
    }
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    result = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
        }
    )

    assert result["status"] == "ready"
    assert len(result["officers"]) == 2
    assert result["officers"][0]["name"] == "SMITH, John"
    assert result["officers"][0]["officer_role"] == "director"
    assert "terminology_note" in result
    assert "fetched_at" in result


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_officers_active_only(mock_request, skill):
    """active_only flag filters resigned officers."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "name": "SMITH, John",
                "officer_role": "director",
                "appointed_on": "2020-03-01",
            },
            {
                "name": "DOE, Jane",
                "officer_role": "secretary",
                "appointed_on": "2019-06-15",
                "resigned_on": "2023-01-01",
            },
        ],
        "total_results": 2,
        "active_count": 1,
    }
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    result = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
            "active_only": True,
        }
    )

    assert result["status"] == "ready"
    assert len(result["officers"]) == 1
    assert result["officers"][0]["name"] == "SMITH, John"


# --- get_pscs Tests ---


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_pscs(mock_request, skill):
    """PSC action returns structured PSC list."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "name": "SMITH, John",
                "kind": "individual-person-with-significant-control",
                "notified_on": "2016-04-06",
                "natures_of_control": ["ownership-of-shares-75-to-100-percent"],
                "nationality": "British",
            }
        ],
        "total_results": 1,
    }
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    result = skill.execute(
        {
            "action": "get_pscs",
            "company_number": "00102498",
        }
    )

    assert result["status"] == "ready"
    assert len(result["pscs"]) == 1
    assert result["pscs"][0]["name"] == "SMITH, John"
    assert "terminology_note" in result
    assert "fetched_at" in result


# --- get_filing_history Tests ---


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_filing_history(mock_request, skill):
    """Filing history action returns structured filings list."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "date": "2024-12-15",
                "category": "accounts",
                "type": "AA",
                "description": "accounts-with-accounts-type-full",
                "barcode": "ABC123",
                "transaction_id": "TXN456",
                "links": {"document_metadata": "/document/abc123"},
            },
            {
                "date": "2024-06-01",
                "category": "confirmation-statement",
                "type": "CS01",
                "description": "confirmation-statement",
            },
        ],
        "total_count": 2,
        "filing_history_status": "filing-history-available",
    }
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    result = skill.execute(
        {
            "action": "get_filing_history",
            "company_number": "00102498",
        }
    )

    assert result["status"] == "ready"
    assert len(result["filings"]) == 2
    assert result["filings"][0]["category"] == "accounts"
    assert "document_metadata_url" in result["filings"][0]
    assert "document_metadata_url" not in result["filings"][1]
    assert "fetched_at" in result


# --- map_intent Tests ---


def test_map_intent_ceo_query(skill):
    """map_intent translates CEO to director and suggests pipeline."""
    result = skill.execute(
        {
            "action": "map_intent",
            "intent_keywords": ["ceo", "bp", "director"],
            "entities": {"company_query": "BP"},
        }
    )

    assert result["status"] == "ready"
    assert "suggested_pipeline" in result
    assert result["terminology_map"]["ceo"] == "director"

    # Pipeline should start with resolve_company
    pipeline = result["suggested_pipeline"]
    assert pipeline[0]["action"] == "resolve_company"
    assert pipeline[0]["params"]["query"] == "BP"

    # Should include get_officers for "director" keyword
    action_names = [step["action"] for step in pipeline]
    assert "get_officers" in action_names
    assert "fetched_at" in result


def test_map_intent_owner_query(skill):
    """map_intent translates owner to PSC."""
    result = skill.execute(
        {
            "action": "map_intent",
            "intent_keywords": ["owner", "shareholders"],
            "entities": {"company_query": "Tesco"},
        }
    )

    assert result["status"] == "ready"
    assert result["terminology_map"]["owner"] == "person_with_significant_control"
    action_names = [step["action"] for step in result["suggested_pipeline"]]
    assert "resolve_company" in action_names
    assert "get_pscs" in action_names


def test_map_intent_missing_input(skill):
    """map_intent without keywords or entities returns error."""
    result = skill.execute({"action": "map_intent"})
    assert result["status"] == "error"
    assert result["error_code"] == "missing_intent"


# --- HTTP Error Handling Tests ---


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_http_404_error(mock_request, skill):
    """404 response returns not_found error."""
    import requests as req

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = req.exceptions.HTTPError(
        response=mock_response
    )
    mock_request.return_value = mock_response

    result = skill.execute(
        {
            "action": "get_company_profile",
            "company_number": "99999999",
        }
    )

    assert result["status"] == "error"
    assert result["error_code"] == "not_found"
    assert "fetched_at" in result


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_http_429_rate_limit(mock_request, skill):
    """429 response returns rate_limited error."""
    import requests as req

    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.raise_for_status.side_effect = req.exceptions.HTTPError(
        response=mock_response
    )
    mock_request.return_value = mock_response

    result = skill.execute(
        {
            "action": "get_company_profile",
            "company_number": "00102498",
        }
    )

    assert result["status"] == "error"
    assert result["error_code"] == "rate_limited"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_http_timeout(mock_request, skill):
    """Timeout returns timeout error."""
    import requests as req

    mock_request.side_effect = req.exceptions.Timeout()

    result = skill.execute(
        {
            "action": "get_company_profile",
            "company_number": "00102498",
        }
    )

    assert result["status"] == "error"
    assert result["error_code"] == "timeout"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_connection_error(mock_request, skill):
    """Connection error returns connection_error."""
    import requests as req

    mock_request.side_effect = req.exceptions.ConnectionError()

    result = skill.execute(
        {
            "action": "get_company_profile",
            "company_number": "00102498",
        }
    )

    assert result["status"] == "error"
    assert result["error_code"] == "connection_error"

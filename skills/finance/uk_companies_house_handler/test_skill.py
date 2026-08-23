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
    assert "context" in skill_manifest["parameters"]["properties"]


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
    # Default active_only=True filters out resigned officer Jane Doe
    assert len(result["officers"]) == 1
    assert result["officers"][0]["name"] == "SMITH, John"
    assert result["officers"][0]["officer_role"] == "director"
    assert "terminology_note" in result
    assert "fetched_at" in result


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_officers_include_resigned(mock_request, skill):
    """active_only=False returns resigned officers as well."""
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
            "active_only": False,
        }
    )

    assert result["status"] == "ready"
    assert len(result["officers"]) == 2
    assert result["officers"][0]["name"] == "SMITH, John"
    assert result["officers"][1]["name"] == "DOE, Jane"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_officers_context_only_company_number(mock_request, skill):
    """get_officers works with company_number provided only via context."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "name": "SMITH, John",
                "officer_role": "director",
                "appointed_on": "2020-03-01",
                "nationality": "British",
            }
        ],
        "total_results": 1,
        "active_count": 1,
    }
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    result = skill.execute(
        {
            "action": "get_officers",
            "context": {"company_number": "00102498"},
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00102498"
    assert len(result["officers"]) == 1
    assert result["officers"][0]["name"] == "SMITH, John"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_officers_company_name_fallback_via_profile(mock_request, skill):
    """Officers action falls back to profile fetch if company_name is missing."""
    mock_officers_response = MagicMock()
    mock_officers_response.json.return_value = {
        "items": [
            {
                "name": "SMITH, John",
                "officer_role": "director",
                "appointed_on": "2020-03-01",
            }
        ],
        "total_results": 1,
        "active_count": 1,
    }
    mock_officers_response.raise_for_status = MagicMock()

    mock_profile_response = MagicMock()
    mock_profile_response.json.return_value = {
        "company_name": "PROFILE FALLBACK LTD",
        "company_status": "active",
        "type": "ltd",
    }
    mock_profile_response.raise_for_status = MagicMock()

    mock_request.side_effect = [mock_officers_response, mock_profile_response]

    result = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
        }
    )

    assert result["status"] == "ready"
    assert result["company_name"] == "PROFILE FALLBACK LTD"
    assert mock_request.call_count == 2


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


def test_map_intent_officer_and_filings(skill):
    """map_intent maps officer and filings to resolve, officers, and filings."""
    result = skill.execute(
        {
            "action": "map_intent",
            "intent_keywords": "officer, filings",
            "entities": {"company_query": "BP"},
        }
    )

    assert result["status"] == "ready"
    pipeline = result["suggested_pipeline"]
    action_names = [step["action"] for step in pipeline]
    assert action_names == [
        "resolve_company",
        "get_officers",
        "get_filing_history",
    ]


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


# --- v2a Enhancements Tests ---


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_context_propagation(mock_request, skill):
    """Context should carry forward and supply missing parameters."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "company_name": "TEST COMPANY LTD",
        "company_status": "active",
        "type": "ltd",
    }
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    result = skill.execute(
        {
            "action": "get_company_profile",
            "context": {
                "company_number": "12345678",
                "officer_filter": "Smith",
            },
        }
    )

    assert result["status"] == "ready"
    assert "context" in result
    ctx = result["context"]
    assert ctx["last_action"] == "get_company_profile"
    assert ctx["company_number"] == "12345678"
    assert ctx["company_name"] == "TEST COMPANY LTD"
    assert ctx["officer_filter"] == "Smith"


def test_partial_response(skill):
    """_partial_response should build the correct envelope."""
    result = skill._partial_response(
        data={"some_key": "some_val"},
        next_actions=["do_something_else"],
        context={"state": 1},
        pipeline={"completed_steps": 1, "total_steps": 2},
    )
    assert result["status"] == "partial"
    assert result["some_key"] == "some_val"
    assert result["next_actions"] == ["do_something_else"]
    assert result["context"] == {"state": 1}
    assert result["pipeline"] == {"completed_steps": 1, "total_steps": 2}
    assert "fetched_at" in result


# --- v2b Pipeline and Composite Actions Tests ---


def test_run_pipeline_missing_steps(skill):
    """run_pipeline without steps returns error."""
    result = skill.execute({"action": "run_pipeline"})
    assert result["status"] == "error"
    assert result["error_code"] == "missing_steps"


def test_run_pipeline_invalid_step(skill):
    """run_pipeline with invalid step returns error."""
    result = skill.execute({"action": "run_pipeline", "steps": ["invalid"]})
    assert result["status"] == "error"
    assert result["error_code"] == "invalid_step"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_run_pipeline_success_multi_step(mock_request, skill):
    """run_pipeline executes ordered steps and merges context."""
    mock_search = MagicMock()
    mock_search.json.return_value = {
        "items": [
            {
                "company_number": "00102498",
                "title": "BP P.L.C.",
                "company_status": "active",
                "company_type": "plc",
                "address_snippet": "London",
                "date_of_creation": "1909-04-14",
            }
        ]
    }
    mock_search.raise_for_status = MagicMock()

    mock_officers = MagicMock()
    mock_officers.json.return_value = {
        "items": [
            {
                "name": "SMITH, John",
                "officer_role": "director",
                "appointed_on": "2020-03-01",
            }
        ],
        "total_results": 1,
        "active_count": 1,
        "company_name": "BP P.L.C.",
    }
    mock_officers.raise_for_status = MagicMock()

    mock_request.side_effect = [mock_search, mock_officers]

    result = skill.execute(
        {
            "action": "run_pipeline",
            "steps": [
                {
                    "action": "resolve_company",
                    "params": {"query": "BP PLC"},
                },
                {
                    "action": "get_officers",
                    "params": {"active_only": True},
                },
            ],
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00102498"
    assert len(result["officers"]) == 1
    assert result["officers"][0]["name"] == "SMITH, John"
    assert result["pipeline"] == {"completed_steps": 2, "total_steps": 2}
    assert result["context"]["company_number"] == "00102498"
    assert result["context"]["last_action"] == "run_pipeline"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_run_pipeline_merges_multiple_data_steps(mock_request, skill):
    """run_pipeline retains data from all steps (both officers and filings)."""
    mock_officers = MagicMock()
    mock_officers.json.return_value = {
        "items": [
            {
                "name": "SMITH, John",
                "officer_role": "director",
                "appointed_on": "2020-03-01",
            }
        ],
        "total_results": 1,
        "active_count": 1,
        "company_name": "BP P.L.C.",
    }
    mock_officers.raise_for_status = MagicMock()

    mock_filings = MagicMock()
    mock_filings.json.return_value = {
        "items": [
            {
                "date": "2026-08-19",
                "category": "officers",
                "type": "AP03",
                "description": "appoint-person-secretary",
            }
        ],
        "total_count": 1,
        "filing_history_status": "filing-history-available",
    }
    mock_filings.raise_for_status = MagicMock()

    mock_request.side_effect = [mock_officers, mock_filings]

    result = skill.execute(
        {
            "action": "run_pipeline",
            "steps": [
                {
                    "action": "get_officers",
                    "params": {"company_number": "00102498"},
                },
                {
                    "action": "get_filing_history",
                    "params": {"company_number": "00102498"},
                },
            ],
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00102498"
    assert "officers" in result
    assert len(result["officers"]) == 1
    assert result["officers"][0]["name"] == "SMITH, John"
    assert "filings" in result
    assert len(result["filings"]) == 1
    assert result["filings"][0]["category"] == "officers"
    assert "terminology_note" in result
    assert result["pipeline"] == {"completed_steps": 2, "total_steps": 2}


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_run_pipeline_resumed_progress_tracking(mock_request, skill):
    """run_pipeline preserves multi-turn progress when incoming pipeline state is passed."""
    mock_officers = MagicMock()
    mock_officers.json.return_value = {
        "items": [
            {
                "name": "SMITH, John",
                "officer_role": "director",
                "appointed_on": "2020-03-01",
            }
        ],
        "total_results": 1,
        "active_count": 1,
        "company_name": "BP P.L.C.",
    }
    mock_officers.raise_for_status = MagicMock()

    mock_filings = MagicMock()
    mock_filings.json.return_value = {
        "items": [
            {
                "date": "2026-08-19",
                "category": "officers",
                "type": "AP03",
                "description": "appoint-person-secretary",
            }
        ],
        "total_count": 1,
        "filing_history_status": "filing-history-available",
    }
    mock_filings.raise_for_status = MagicMock()

    mock_request.side_effect = [mock_officers, mock_filings]

    result = skill.execute(
        {
            "action": "run_pipeline",
            "steps": [
                {
                    "action": "get_officers",
                    "params": {"company_number": "00102498"},
                },
                {
                    "action": "get_filing_history",
                    "params": {"company_number": "00102498"},
                },
            ],
            "pipeline": {
                "completed_steps": 1,
                "total_steps": 3,
            },
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00102498"
    assert "officers" in result
    assert "filings" in result
    # Progress should reflect 1 prior completed + 2 current = 3 total out of 3
    assert result["pipeline"] == {"completed_steps": 3, "total_steps": 3}


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_run_pipeline_full_resubmission_skips_completed_and_substitutes_placeholder(
    mock_request, skill
):
    """When caller passes full 3-step pipeline on resume, step 0 is skipped and placeholder substituted."""
    mock_officers = MagicMock()
    mock_officers.json.return_value = {
        "items": [
            {
                "name": "SMITH, John",
                "officer_role": "director",
                "appointed_on": "2020-03-01",
            }
        ],
        "total_results": 1,
        "active_count": 1,
        "company_name": "BP P.L.C.",
    }
    mock_officers.raise_for_status = MagicMock()

    mock_filings = MagicMock()
    mock_filings.json.return_value = {
        "items": [
            {
                "date": "2026-08-19",
                "category": "officers",
                "type": "AP03",
                "description": "appoint-person-secretary",
            }
        ],
        "total_count": 1,
        "filing_history_status": "filing-history-available",
    }
    mock_filings.raise_for_status = MagicMock()

    mock_request.side_effect = [mock_officers, mock_filings]

    result = skill.execute(
        {
            "action": "run_pipeline",
            "steps": [
                {
                    "action": "resolve_company",
                    "params": {"query": "bp"},
                },
                {
                    "action": "get_officers",
                    "params": {"company_number": "<from_resolve>"},
                },
                {
                    "action": "get_filing_history",
                    "params": {"company_number": "<from_resolve>"},
                },
            ],
            "company_number": "00102498",
            "pipeline": {
                "completed_steps": 1,
                "total_steps": 3,
            },
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00102498"
    assert "officers" in result
    assert "filings" in result
    assert result["pipeline"] == {"completed_steps": 3, "total_steps": 3}


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_officers_partial_status(mock_request, skill):
    """get_officers returns status=partial when active_count exceeds returned limit."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "name": f"DIRECTOR_{i}",
                "officer_role": "director",
                "appointed_on": "2020-01-01",
            }
            for i in range(15)
        ],
        "total_results": 20,
        "active_count": 15,
    }
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    result = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
            "limit": 10,
        }
    )

    assert result["status"] == "partial"
    assert len(result["officers"]) == 10
    assert result["active_count"] == 15
    assert "agent_hint" in result
    assert "Showing 10 active officers" in result["agent_hint"]


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_filings_partial_status(mock_request, skill):
    """get_filing_history returns status=partial when total filings exceed limit."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "date": "2026-08-19",
                "category": "officers",
                "type": "AP03",
                "description": "appoint-person-secretary",
            }
            for _ in range(10)
        ],
        "total_count": 15549,
        "filing_history_status": "filing-history-available",
    }
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    result = skill.execute(
        {
            "action": "get_filing_history",
            "company_number": "00102498",
            "limit": 10,
        }
    )

    assert result["status"] == "partial"
    assert len(result["filings"]) == 10
    assert result["total_results"] == 15549
    assert "agent_hint" in result
    assert "Showing 10 filings out of 15549" in result["agent_hint"]


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_officers_terminology_note_contextual(mock_request, skill):
    """get_officers provides CEO note only when CEO or US role is queried."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [
            {
                "name": "SMITH, John",
                "officer_role": "director",
                "appointed_on": "2020-03-01",
            }
        ],
        "total_results": 1,
        "active_count": 1,
    }
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    # Standard query without CEO
    result_std = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
        }
    )
    assert "CEO" not in result_std["terminology_note"]
    assert "directors and secretaries" in result_std["terminology_note"]

    # Query with CEO role_hint
    result_ceo = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
            "role_hint": "ceo",
        }
    )
    assert "CEO" in result_ceo["terminology_note"]


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_run_pipeline_stops_on_needs_input(mock_request, skill):
    """run_pipeline stops on disambiguation and sets next_actions."""
    mock_search = MagicMock()
    mock_search.json.return_value = {
        "items": [
            {
                "company_number": "00102498",
                "title": "BP P.L.C.",
                "company_status": "active",
            },
            {
                "company_number": "01234567",
                "title": "BP ALTERNATIVE LTD",
                "company_status": "active",
            },
            {
                "company_number": "09999999",
                "title": "BP SERVICES LTD",
                "company_status": "active",
            },
            {
                "company_number": "08888888",
                "title": "BP CONSULTING LTD",
                "company_status": "active",
            },
        ]
    }
    mock_search.raise_for_status = MagicMock()
    mock_request.return_value = mock_search

    result = skill.execute(
        {
            "action": "run_pipeline",
            "steps": [
                {
                    "action": "resolve_company",
                    "params": {"query": "BP"},
                },
                {
                    "action": "get_officers",
                    "params": {"active_only": True},
                },
            ],
        }
    )

    assert result["status"] == "needs_input"
    assert result["reason"] == "multiple_matches"
    assert len(result["candidates"]) == 4
    assert result["pipeline"] == {"completed_steps": 1, "total_steps": 2}
    assert result["next_actions"] == ["get_officers"]


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_run_pipeline_stops_on_error(mock_request, skill):
    """run_pipeline stops on error with pipeline state."""
    import requests as req

    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.raise_for_status.side_effect = req.exceptions.HTTPError(
        response=mock_response
    )
    mock_request.return_value = mock_response

    result = skill.execute(
        {
            "action": "run_pipeline",
            "steps": [
                {
                    "action": "get_company_profile",
                    "params": {"company_number": "99999999"},
                },
                {
                    "action": "get_officers",
                },
            ],
        }
    )

    assert result["status"] == "error"
    assert result["error_code"] == "not_found"
    assert result["pipeline"] == {"completed_steps": 1, "total_steps": 2}
    assert result["next_actions"] == ["get_officers"]


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_resolve_and_get_officers_single_match(mock_request, skill):
    """resolve_and_get_officers composite resolves and fetches officers."""
    mock_search = MagicMock()
    mock_search.json.return_value = {
        "items": [
            {
                "company_number": "00102498",
                "title": "BP P.L.C.",
                "company_status": "active",
                "company_type": "plc",
            }
        ]
    }
    mock_search.raise_for_status = MagicMock()

    mock_officers = MagicMock()
    mock_officers.json.return_value = {
        "items": [
            {
                "name": "SMITH, John",
                "officer_role": "director",
                "appointed_on": "2020-03-01",
            }
        ],
        "total_results": 1,
        "active_count": 1,
        "company_name": "BP P.L.C.",
    }
    mock_officers.raise_for_status = MagicMock()

    mock_request.side_effect = [mock_search, mock_officers]

    result = skill.execute(
        {
            "action": "resolve_and_get_officers",
            "query": "BP PLC",
            "active_only": True,
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00102498"
    assert len(result["officers"]) == 1
    assert result["pipeline"] == {"completed_steps": 2, "total_steps": 2}


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_resolve_and_get_officers_multiple_matches(mock_request, skill):
    """resolve_and_get_officers halts on multiple matches."""
    mock_search = MagicMock()
    mock_search.json.return_value = {
        "items": [
            {
                "company_number": "00102498",
                "title": "BP P.L.C.",
                "company_status": "active",
            },
            {
                "company_number": "01234567",
                "title": "BP ALTERNATIVE LTD",
                "company_status": "active",
            },
            {
                "company_number": "09999999",
                "title": "BP SERVICES LTD",
                "company_status": "active",
            },
            {
                "company_number": "08888888",
                "title": "BP CONSULTING LTD",
                "company_status": "active",
            },
        ]
    }
    mock_search.raise_for_status = MagicMock()
    mock_request.return_value = mock_search

    result = skill.execute(
        {
            "action": "resolve_and_get_officers",
            "company_query": "BP",
        }
    )

    assert result["status"] == "needs_input"
    assert result["reason"] == "multiple_matches"
    assert result["pipeline"] == {"completed_steps": 1, "total_steps": 2}
    assert result["next_actions"] == ["get_officers"]


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_resolve_and_get_officers_with_company_number(mock_request, skill):
    """resolve_and_get_officers with company_number bypasses search."""
    mock_officers = MagicMock()
    mock_officers.json.return_value = {
        "items": [
            {
                "name": "SMITH, John",
                "officer_role": "director",
                "appointed_on": "2020-03-01",
            }
        ],
        "total_results": 1,
        "active_count": 1,
        "company_name": "BP P.L.C.",
    }
    mock_officers.raise_for_status = MagicMock()
    mock_request.return_value = mock_officers

    result = skill.execute(
        {
            "action": "resolve_and_get_officers",
            "company_number": "00102498",
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00102498"
    assert len(result["officers"]) == 1
    assert mock_request.call_count == 1


def test_resolve_and_get_officers_missing_query(skill):
    """resolve_and_get_officers without query or company_number returns error."""
    result = skill.execute({"action": "resolve_and_get_officers"})
    assert result["status"] == "error"
    assert result["error_code"] == "missing_query"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_resolve_and_get_filings_single_match(mock_request, skill):
    """resolve_and_get_filings composite resolves and fetches filings."""
    mock_search = MagicMock()
    mock_search.json.return_value = {
        "items": [
            {
                "company_number": "00102498",
                "title": "BP P.L.C.",
                "company_status": "active",
                "company_type": "plc",
            }
        ]
    }
    mock_search.raise_for_status = MagicMock()

    mock_filings = MagicMock()
    mock_filings.json.return_value = {
        "items": [
            {
                "date": "2024-12-15",
                "category": "accounts",
                "type": "AA",
                "description": "accounts-with-accounts-type-full",
            }
        ],
        "total_count": 1,
        "filing_history_status": "filing-history-available",
    }
    mock_filings.raise_for_status = MagicMock()

    mock_request.side_effect = [mock_search, mock_filings]

    result = skill.execute(
        {
            "action": "resolve_and_get_filings",
            "query": "BP PLC",
            "category": "accounts",
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00102498"
    assert len(result["filings"]) == 1
    assert result["pipeline"] == {"completed_steps": 2, "total_steps": 2}


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_resolve_and_get_filings_multiple_matches(mock_request, skill):
    """resolve_and_get_filings halts on multiple matches."""
    mock_search = MagicMock()
    mock_search.json.return_value = {
        "items": [
            {
                "company_number": "00102498",
                "title": "BP P.L.C.",
                "company_status": "active",
            },
            {
                "company_number": "01234567",
                "title": "BP ALTERNATIVE LTD",
                "company_status": "active",
            },
            {
                "company_number": "09999999",
                "title": "BP SERVICES LTD",
                "company_status": "active",
            },
            {
                "company_number": "08888888",
                "title": "BP CONSULTING LTD",
                "company_status": "active",
            },
        ]
    }
    mock_search.raise_for_status = MagicMock()
    mock_request.return_value = mock_search

    result = skill.execute(
        {
            "action": "resolve_and_get_filings",
            "query": "BP",
        }
    )

    assert result["status"] == "needs_input"
    assert result["reason"] == "multiple_matches"
    assert result["pipeline"] == {"completed_steps": 1, "total_steps": 2}
    assert result["next_actions"] == ["get_filing_history"]


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_resolve_and_get_filings_with_company_number(mock_request, skill):
    """resolve_and_get_filings with company_number bypasses search."""
    mock_filings = MagicMock()
    mock_filings.json.return_value = {
        "items": [
            {
                "date": "2024-12-15",
                "category": "accounts",
                "type": "AA",
                "description": "accounts-with-accounts-type-full",
            }
        ],
        "total_count": 1,
        "filing_history_status": "filing-history-available",
    }
    mock_filings.raise_for_status = MagicMock()
    mock_request.return_value = mock_filings

    result = skill.execute(
        {
            "action": "resolve_and_get_filings",
            "company_number": "00102498",
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00102498"
    assert len(result["filings"]) == 1
    assert mock_request.call_count == 1


def test_resolve_and_get_filings_missing_query(skill):
    """resolve_and_get_filings without query or company_number returns error."""
    result = skill.execute({"action": "resolve_and_get_filings"})
    assert result["status"] == "error"
    assert result["error_code"] == "missing_query"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_run_pipeline_resumes_from_context_next_actions_when_steps_omitted(
    mock_request, skill
):
    """run_pipeline automatically falls back to context next_actions when steps is omitted."""
    mock_officers = MagicMock()
    mock_officers.json.return_value = {
        "items": [
            {
                "name": "MURPHY, Ken",
                "officer_role": "director",
                "appointed_on": "2020-10-01",
            }
        ],
        "total_results": 1,
        "active_count": 1,
        "company_name": "TESCO PLC",
    }
    mock_officers.raise_for_status = MagicMock()
    mock_request.return_value = mock_officers

    result = skill.execute(
        {
            "action": "run_pipeline",
            "company_number": "00445790",
            "context": {
                "last_action": "resolve_and_get_officers",
                "next_actions": ["get_officers"],
                "role_hint": "ceo",
            },
            "pipeline": {
                "completed_steps": 1,
                "total_steps": 2,
            },
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00445790"
    assert len(result["officers"]) == 1
    assert "CEO" in result["terminology_note"]
    assert result["pipeline"] == {"completed_steps": 2, "total_steps": 2}


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_resolve_and_get_officers_extracts_ceo_from_natural_query(mock_request, skill):
    """resolve_and_get_officers extracts 'ceo' from natural query and passes to get_officers."""
    mock_search = MagicMock()
    mock_search.json.return_value = {
        "items": [
            {
                "company_number": "00445790",
                "title": "TESCO PLC",
                "company_status": "active",
            }
        ]
    }
    mock_search.raise_for_status = MagicMock()

    mock_officers = MagicMock()
    mock_officers.json.return_value = {
        "items": [
            {
                "name": "MURPHY, Ken",
                "officer_role": "director",
                "appointed_on": "2020-10-01",
            }
        ],
        "total_results": 1,
        "active_count": 1,
        "company_name": "TESCO PLC",
    }
    mock_officers.raise_for_status = MagicMock()
    mock_request.side_effect = [mock_search, mock_officers]

    result = skill.execute(
        {
            "action": "resolve_and_get_officers",
            "query": "who is the ceo of tesco",
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00445790"
    assert "CEO" in result["terminology_note"]
    assert result["context"]["role_hint"] == "ceo"

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
    assert "agent_hint" in result


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
def test_get_officers_empty_list_agent_hint(mock_request, skill):
    """Empty officers[] on success includes agent_hint for the host."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [],
        "total_results": 0,
        "active_count": 0,
    }
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    result = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00061707",
        }
    )

    assert result["status"] == "ready"
    assert result["officers"] == []
    assert "agent_hint" in result
    assert "empty" in result["agent_hint"].lower()


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_filing_history_empty_list_agent_hint(mock_request, skill):
    """Empty filings[] on success includes agent_hint for the host."""
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "items": [],
        "total_count": 0,
        "filing_history_status": "filing-history-available",
    }
    mock_response.raise_for_status = MagicMock()
    mock_request.return_value = mock_response

    result = skill.execute(
        {
            "action": "get_filing_history",
            "company_number": "00061707",
            "category": "accounts",
        }
    )

    assert result["status"] == "ready"
    assert result["filings"] == []
    assert "agent_hint" in result
    assert "empty" in result["agent_hint"].lower()


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


# --- run_pipeline Tests ---


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_resolve_company_strips_trailing_punctuation(mock_request, skill):
    """resolve_company normalizes trailing punctuation in search queries."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "items": [
            {
                "company_number": "01026167",
                "title": "BARCLAYS BANK PLC",
                "company_status": "active",
            }
        ]
    }
    mock_resp.raise_for_status = MagicMock()
    mock_request.return_value = mock_resp

    result = skill.execute({"action": "resolve_company", "query": "Barclays?"})

    assert result["status"] == "ready"
    assert mock_request.call_args.kwargs["params"]["q"] == "Barclays"


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
            },
        }
    )

    assert result["status"] == "ready"
    assert "context" in result
    ctx = result["context"]
    assert ctx["last_action"] == "get_company_profile"
    assert ctx["company_number"] == "12345678"
    assert ctx["company_name"] == "TEST COMPANY LTD"


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
    """run_pipeline executes ordered steps one at a time via stack pop."""
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

    # Step 1: resolve_company
    step1_res = skill.execute(
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

    assert step1_res["status"] == "partial"
    assert step1_res["company_number"] == "00102498"
    assert step1_res["pipeline"]["completed_steps"] == 1
    assert step1_res["pipeline"]["total_steps"] == 2
    assert len(step1_res["steps"]) == 1
    assert step1_res["steps"][0]["action"] == "get_officers"
    assert step1_res["steps"][0]["params"]["company_number"] == "00102498"

    # Step 2: get_officers
    step2_res = skill.execute(
        {
            "action": "run_pipeline",
            "steps": step1_res["steps"],
            "pipeline": step1_res["pipeline"],
            "context": step1_res["context"],
        }
    )

    assert step2_res["status"] == "ready"
    assert step2_res["company_number"] == "00102498"
    assert len(step2_res["officers"]) == 1
    assert step2_res["officers"][0]["name"] == "SMITH, John"
    assert step2_res["pipeline"]["completed_steps"] == 2
    assert step2_res["pipeline"]["total_steps"] == 2


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_run_pipeline_multi_step_sequential_loop(mock_request, skill):
    """run_pipeline executes multiple steps turn-by-turn with clean step data."""
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

    mock_profile = MagicMock()
    mock_profile.json.return_value = {
        "company_name": "BP P.L.C.",
        "company_status": "active",
    }
    mock_profile.raise_for_status = MagicMock()

    mock_request.side_effect = [mock_officers, mock_profile, mock_filings]

    # Turn 1
    res1 = skill.execute(
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

    assert res1["status"] == "partial"
    assert "officers" in res1
    assert "filings" not in res1
    assert res1["pipeline"]["completed_steps"] == 1
    assert res1["pipeline"]["total_steps"] == 2

    # Turn 2
    res2 = skill.execute(
        {
            "action": "run_pipeline",
            "steps": res1["steps"],
            "pipeline": res1["pipeline"],
            "context": res1["context"],
        }
    )

    assert res2["status"] == "ready"
    assert "filings" in res2
    assert res2["pipeline"]["completed_steps"] == 2
    assert res2["pipeline"]["total_steps"] == 2


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_run_pipeline_resumed_progress_tracking(mock_request, skill):
    """run_pipeline preserves multi-turn progress when incoming pipeline state is passed."""
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
    mock_request.return_value = mock_filings

    result = skill.execute(
        {
            "action": "run_pipeline",
            "steps": [
                {
                    "action": "get_filing_history",
                    "params": {"company_number": "00102498"},
                },
            ],
            "pipeline": {
                "completed_steps": 2,
                "total_steps": 3,
            },
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00102498"
    assert "filings" in result
    assert result["pipeline"]["completed_steps"] == 3
    assert result["pipeline"]["total_steps"] == 3


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_run_pipeline_resume_skips_done_steps(mock_request, skill):
    """Resume substitutes <from_resolve> placeholders in remaining steps."""
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
            "action": "run_pipeline",
            "steps": [
                {
                    "action": "get_officers",
                    "params": {"company_number": "<from_resolve>"},
                },
            ],
            "company_number": "00102498",
            "pipeline": {
                "completed_steps": 1,
                "total_steps": 2,
            },
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00102498"
    assert "officers" in result
    assert result["pipeline"]["completed_steps"] == 2
    assert result["pipeline"]["total_steps"] == 2


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_officers_partial_status(mock_request, skill):
    """get_officers returns status=ready even when active_count exceeds preview limit."""
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
        "company_name": "BP P.L.C.",
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

    assert result["status"] == "ready"
    assert len(result["officers"]) == 10
    assert result["active_count"] == 15
    assert result["total_results"] == 20


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_filings_partial_status(mock_request, skill):
    """get_filing_history returns status=ready even when total filings exceed limit."""
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
        "company_name": "BP P.L.C.",
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

    assert result["status"] == "ready"
    assert len(result["filings"]) == 10
    assert result["total_results"] == 15549


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
    """run_pipeline stops on disambiguation when multiple matches are found."""
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
    assert result["pipeline"]["completed_steps"] == 1
    assert result["pipeline"]["total_steps"] == 2
    assert result["steps"] == [
        {"action": "get_officers", "params": {"active_only": True}}
    ]


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
    assert result["pipeline"]["completed_steps"] == 1
    assert result["pipeline"]["total_steps"] == 2
    assert result["steps"] == [{"action": "get_officers"}]


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
    assert "pipeline" not in result


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
    assert "pipeline" not in result


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
    }
    mock_officers.raise_for_status = MagicMock()

    mock_profile = MagicMock()
    mock_profile.json.return_value = {
        "company_name": "BP P.L.C.",
        "company_status": "active",
    }
    mock_profile.raise_for_status = MagicMock()
    mock_request.side_effect = [mock_officers, mock_profile]

    result = skill.execute(
        {
            "action": "resolve_and_get_officers",
            "company_number": "00102498",
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00102498"
    assert result["company_name"] == "BP P.L.C."
    assert len(result["officers"]) == 1
    assert mock_request.call_count == 2


def test_resolve_and_get_officers_missing_query(skill):
    """resolve_and_get_officers without query or company_number returns error."""
    result = skill.execute({"action": "resolve_and_get_officers"})
    assert result["status"] == "error"
    assert result["error_code"] == "missing_company"


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
    assert "pipeline" not in result


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
    assert "pipeline" not in result


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

    mock_profile = MagicMock()
    mock_profile.json.return_value = {
        "company_name": "BP P.L.C.",
        "company_status": "active",
    }
    mock_profile.raise_for_status = MagicMock()
    mock_request.side_effect = [mock_filings, mock_profile]

    result = skill.execute(
        {
            "action": "resolve_and_get_filings",
            "company_number": "00102498",
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00102498"
    assert result["company_name"] == "BP P.L.C."
    assert len(result["filings"]) == 1
    assert mock_request.call_count == 2


def test_resolve_and_get_filings_missing_query(skill):
    """resolve_and_get_filings without query or company_number returns error."""
    result = skill.execute({"action": "resolve_and_get_filings"})
    assert result["status"] == "error"
    assert result["error_code"] == "missing_company"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_resolve_and_get_officers_with_role_hint(mock_request, skill):
    """resolve_and_get_officers uses clean query and explicit role_hint."""
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
    }
    mock_officers.raise_for_status = MagicMock()
    mock_request.side_effect = [mock_search, mock_officers]

    result = skill.execute(
        {
            "action": "resolve_and_get_officers",
            "query": "Tesco",
            "role_hint": "ceo",
        }
    )

    assert result["status"] == "ready"
    assert result["company_number"] == "00445790"
    assert result["company_name"] == "TESCO PLC"
    assert "CEO" in result["terminology_note"]
    assert "role_hint" not in result["context"]
    search_params = mock_request.call_args_list[0].kwargs["params"]
    assert search_params["q"] == "Tesco"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_run_pipeline_multi_turn_with_step_substitution(mock_request, skill):
    """run_pipeline executes turn-by-turn with <from_resolve> substitution across steps."""
    mock_search = MagicMock()
    mock_search.json.return_value = {
        "items": [
            {
                "company_number": "00102498",
                "title": "BP P.L.C.",
                "company_status": "active",
            }
        ]
    }
    mock_search.raise_for_status = MagicMock()

    mock_officers = MagicMock()
    mock_officers.json.return_value = {
        "items": [
            {
                "name": "LOONEY, Bernard",
                "officer_role": "director",
                "resigned_on": None,
            }
        ],
        "total_results": 1,
        "active_count": 1,
    }
    mock_officers.raise_for_status = MagicMock()

    mock_filings = MagicMock()
    mock_filings.json.return_value = {
        "items": [
            {
                "transaction_id": "tx_123",
                "category": "accounts",
                "date": "2026-03-01",
                "description": "Group accounts",
            }
        ],
        "total_count": 1,
    }
    mock_filings.raise_for_status = MagicMock()

    mock_request.side_effect = [mock_search, mock_officers, mock_filings]

    steps = [
        {"action": "resolve_company", "params": {"query": "BP"}},
        {
            "action": "get_officers",
            "params": {"company_number": "<from_resolve>", "officer_name": "Looney"},
        },
        {
            "action": "get_filing_history",
            "params": {
                "company_number": "<from_resolve>",
                "latest_only": True,
                "category": "accounts",
            },
        },
    ]

    # Turn 1: execute step 1 (resolve_company)
    turn1 = skill.execute({"action": "run_pipeline", "steps": steps})
    assert turn1["status"] == "partial"
    assert turn1["company_number"] == "00102498"
    assert turn1["pipeline"]["completed_steps"] == 1
    assert turn1["pipeline"]["total_steps"] == 3
    # Verify remaining steps had <from_resolve> substituted with resolved company number
    rem_steps = turn1["steps"]
    assert len(rem_steps) == 2
    assert rem_steps[0]["params"]["company_number"] == "00102498"
    assert rem_steps[1]["params"]["company_number"] == "00102498"

    # Turn 2: execute step 2 (get_officers)
    turn2 = skill.execute(
        {
            "action": "run_pipeline",
            "steps": rem_steps,
            "context": turn1["context"],
            "pipeline": turn1["pipeline"],
        }
    )
    assert turn2["status"] == "partial"
    assert turn2["pipeline"]["completed_steps"] == 2
    assert len(turn2["officers"]) == 1
    assert turn2["officers"][0]["name"] == "LOONEY, Bernard"
    rem_steps2 = turn2["steps"]
    assert len(rem_steps2) == 1

    # Turn 3: execute step 3 (get_filing_history)
    turn3 = skill.execute(
        {
            "action": "run_pipeline",
            "steps": rem_steps2,
            "context": turn2["context"],
            "pipeline": turn2["pipeline"],
        }
    )
    assert turn3["status"] == "ready"
    assert turn3["pipeline"]["completed_steps"] == 3
    assert "steps" not in turn3
    assert len(turn3["filings"]) == 1
    assert turn3["filings"][0]["category"] == "accounts"


# --- Phase v2c Tests ---


def test_match_officer_role_categories(skill):
    """Test deterministic role matching across canonical categories and aliases."""
    # Category: directors
    assert skill._match_officer_role("director", "director") is True
    assert skill._match_officer_role("corporate-director", "director") is True
    assert skill._match_officer_role("nominee-director", "directors") is True
    assert skill._match_officer_role("corporate-nominee-director", "director") is True
    assert skill._match_officer_role("secretary", "director") is False

    # Category: secretaries
    assert skill._match_officer_role("secretary", "secretary") is True
    assert skill._match_officer_role("corporate-secretary", "secretaries") is True
    assert skill._match_officer_role("nominee-secretary", "secretary") is True
    assert skill._match_officer_role("director", "secretary") is False

    # Category: corporate
    assert skill._match_officer_role("corporate-director", "corporate") is True
    assert skill._match_officer_role("corporate-secretary", "corporate") is True
    assert skill._match_officer_role("corporate-llp-member", "corporate") is True
    assert skill._match_officer_role("director", "corporate") is False

    # Alias / US term mapping
    assert skill._match_officer_role("director", "ceo") is True
    assert skill._match_officer_role("corporate-director", "cfo") is True
    assert skill._match_officer_role("secretary", "company_secretary") is True

    # Exact statutory role
    assert skill._match_officer_role("cic-manager", "cic-manager") is True
    assert (
        skill._match_officer_role("llp-designated-member", "llp-designated-member")
        is True
    )
    assert skill._match_officer_role("director", "cic-manager") is False


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_officer_role_and_name_filter(mock_request, skill):
    """Deterministic filtering by role and case-insensitive name substring."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "items": [
            {"name": "SMITH, John", "officer_role": "director"},
            {"name": "DOE, Jane", "officer_role": "director"},
            {"name": "SMITH, Alice", "officer_role": "secretary"},
            {"name": "CORPORATE AGENT LTD", "officer_role": "corporate-director"},
        ],
        "total_results": 4,
        "active_count": 4,
    }
    mock_resp.raise_for_status = MagicMock()
    mock_request.return_value = mock_resp

    # Filter by officer_name only
    res = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
            "officer_name": "Smith",
        }
    )
    assert res["status"] == "ready"
    assert len(res["officers"]) == 2
    assert res["matched_count"] == 2
    assert {o["name"] for o in res["officers"]} == {"SMITH, John", "SMITH, Alice"}

    # Filter by officer_role only
    res2 = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
            "officer_role": "secretary",
        }
    )
    assert res2["status"] == "ready"
    assert len(res2["officers"]) == 1
    assert res2["officers"][0]["name"] == "SMITH, Alice"

    # Filter by both officer_role (director category) and officer_name
    res3 = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
            "officer_role": "director",
            "officer_name": "Smith",
        }
    )
    assert res3["status"] == "ready"
    assert len(res3["officers"]) == 1
    assert res3["officers"][0]["name"] == "SMITH, John"

    # Natural name order (Firstname Lastname matching inverted SURNAME, Firstname)
    res_natural = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
            "officer_name": "John Smith",
        }
    )
    assert res_natural["status"] == "ready"
    assert len(res_natural["officers"]) == 1
    assert res_natural["officers"][0]["name"] == "SMITH, John"

    # Inverted with comma
    res_comma = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
            "officer_name": "Smith, Alice",
        }
    )
    assert res_comma["status"] == "ready"
    assert len(res_comma["officers"]) == 1
    assert res_comma["officers"][0]["name"] == "SMITH, Alice"

    # Non-matching name with common surname
    res_nonmatch = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
            "officer_name": "Bob Smith",
        }
    )
    assert res_nonmatch["status"] == "ready"
    assert len(res_nonmatch["officers"]) == 0


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_officer_multi_page_scanning(mock_request, skill):
    """Multi-page scanning when filtering: scans across pages up to limit."""
    # Page 1: 100 directors named Brown
    page1 = MagicMock()
    page1.json.return_value = {
        "items": [
            {"name": f"BROWN, Person {i}", "officer_role": "director"}
            for i in range(100)
        ],
        "total_results": 105,
        "active_count": 105,
    }
    page1.raise_for_status = MagicMock()

    # Page 2: 5 directors including one target
    page2 = MagicMock()
    page2.json.return_value = {
        "items": [
            {"name": "TARGET, Wanted", "officer_role": "director"},
            {"name": "OTHER, Person", "officer_role": "director"},
        ],
        "total_results": 105,
        "active_count": 105,
    }
    page2.raise_for_status = MagicMock()

    mock_request.side_effect = [page1, page2]

    res = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
            "officer_name": "Target",
            "context": {"company_name": "BP P.L.C."},
        }
    )

    assert res["status"] == "ready"
    assert len(res["officers"]) == 1
    assert res["officers"][0]["name"] == "TARGET, Wanted"
    assert res["matched_count"] == 1
    assert mock_request.call_count == 2
    # Verify pagination offsets
    assert mock_request.call_args_list[0].kwargs["params"]["start_index"] == 0
    assert mock_request.call_args_list[1].kwargs["params"]["start_index"] == 100


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_officer_active_vs_resigned_disclaimer(mock_request, skill):
    """Transparency on active_only: false with explicit terminology_note disclaimer."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "items": [
            {"name": "ACTIVE, Alice", "officer_role": "director", "resigned_on": None},
            {
                "name": "RESIGNED, Bob",
                "officer_role": "director",
                "resigned_on": "2021-01-01",
            },
        ],
        "total_results": 2,
        "active_count": 1,
    }
    mock_resp.raise_for_status = MagicMock()
    mock_request.return_value = mock_resp

    # With active_only: true (default)
    res_active = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
        }
    )
    assert len(res_active["officers"]) == 1
    assert res_active["officers"][0]["name"] == "ACTIVE, Alice"
    assert res_active["active_only"] is True

    # With active_only: false
    res_all = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
            "active_only": False,
        }
    )
    assert len(res_all["officers"]) == 2
    assert res_all["active_only"] is False
    assert (
        "Includes both active and resigned officers on record."
        in res_all["terminology_note"]
    )


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_filing_history_deterministic_date_sort(mock_request, skill):
    """Filing history is deterministically sorted newest-first by date."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "items": [
            {
                "date": "2021-05-10",
                "category": "accounts",
                "description": "old accounts",
            },
            {
                "date": "2024-03-15",
                "category": "accounts",
                "description": "new accounts",
            },
            {
                "date": "2022-11-20",
                "category": "confirmation-statement",
                "description": "mid statement",
            },
        ],
        "total_count": 3,
        "filing_history_status": "filing-history-available",
    }
    mock_resp.raise_for_status = MagicMock()
    mock_request.return_value = mock_resp

    res = skill.execute(
        {
            "action": "get_filing_history",
            "company_number": "00102498",
        }
    )

    assert res["status"] == "ready"
    assert [f["date"] for f in res["filings"]] == [
        "2024-03-15",
        "2022-11-20",
        "2021-05-10",
    ]


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_filing_helper_latest_only(mock_request, skill):
    """latest_only: true returns only the single most recent filing."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "items": [
            {"date": "2021-05-10", "category": "accounts"},
            {"date": "2024-03-15", "category": "accounts"},
            {"date": "2023-01-01", "category": "confirmation-statement"},
        ],
        "total_count": 3,
    }
    mock_resp.raise_for_status = MagicMock()
    mock_request.return_value = mock_resp

    res = skill.execute(
        {
            "action": "get_filing_history",
            "company_number": "00102498",
            "latest_only": True,
        }
    )

    assert res["status"] == "ready"
    assert res["latest_only"] is True
    assert len(res["filings"]) == 1
    assert res["filings"][0]["date"] == "2024-03-15"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_filing_helper_latest_per_category(mock_request, skill):
    """latest_per_category: true deduplicates to latest filing per distinct category."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "items": [
            {
                "date": "2024-01-01",
                "category": "accounts",
                "description": "accounts-2024",
            },
            {
                "date": "2023-01-01",
                "category": "accounts",
                "description": "accounts-2023",
            },
            {
                "date": "2024-06-01",
                "category": "confirmation-statement",
                "description": "cs-2024",
            },
            {
                "date": "2022-06-01",
                "category": "confirmation-statement",
                "description": "cs-2022",
            },
            {
                "date": "2020-01-01",
                "category": "incorporation",
                "description": "inc-2020",
            },
        ],
        "total_count": 5,
    }
    mock_resp.raise_for_status = MagicMock()
    mock_request.return_value = mock_resp

    res = skill.execute(
        {
            "action": "get_filing_history",
            "company_number": "00102498",
            "latest_per_category": True,
        }
    )

    assert res["status"] == "ready"
    assert res["latest_per_category"] is True
    assert len(res["filings"]) == 3
    # Check each category is represented once, with the newest date
    cat_dates = {f["category"]: f["date"] for f in res["filings"]}
    assert cat_dates["accounts"] == "2024-01-01"
    assert cat_dates["confirmation-statement"] == "2024-06-01"
    assert cat_dates["incorporation"] == "2020-01-01"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_composite_resolve_company_officer_direct_company_number(mock_request, skill):
    """resolve_company_officer bypasses search if company_number is already known."""
    mock_officers = MagicMock()
    mock_officers.json.return_value = {
        "items": [
            {"name": "MURPHY, Ken", "officer_role": "director"},
            {"name": "SMITH, Jane", "officer_role": "secretary"},
        ],
        "total_results": 2,
        "active_count": 2,
    }
    mock_officers.raise_for_status = MagicMock()
    mock_request.return_value = mock_officers

    res = skill.execute(
        {
            "action": "resolve_company_officer",
            "company_number": "00445790",
            "officer_role": "director",
            "officer_name": "Murphy",
            "context": {"company_name": "TESCO PLC"},
        }
    )

    assert res["status"] == "ready"
    assert len(res["officers"]) == 1
    assert res["officers"][0]["name"] == "MURPHY, Ken"
    assert mock_request.call_count == 1  # only get_officers, no resolve_company


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_composite_resolve_company_officer_full_flow(mock_request, skill):
    """resolve_company_officer resolves company and filters matching officers."""
    mock_search = MagicMock()
    mock_search.json.return_value = {
        "items": [
            {
                "company_number": "00102498",
                "title": "BP P.L.C.",
                "company_status": "active",
            }
        ]
    }
    mock_search.raise_for_status = MagicMock()

    mock_officers = MagicMock()
    mock_officers.json.return_value = {
        "items": [
            {"name": "LOONEY, Bernard", "officer_role": "director"},
            {"name": "SHERIDAN, Kerry", "officer_role": "secretary"},
        ],
        "total_results": 2,
        "active_count": 2,
    }
    mock_officers.raise_for_status = MagicMock()
    mock_request.side_effect = [mock_search, mock_officers]

    res = skill.execute(
        {
            "action": "resolve_company_officer",
            "query": "BP",
            "officer_role": "director",
            "officer_name": "Looney",
        }
    )

    assert res["status"] == "ready"
    assert res["company_number"] == "00102498"
    assert res["company_name"] == "BP P.L.C."
    assert len(res["officers"]) == 1
    assert res["officers"][0]["name"] == "LOONEY, Bernard"
    assert res["context"]["last_action"] == "resolve_company_officer"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_composite_resolve_company_officer_needs_input(mock_request, skill):
    """resolve_company_officer halts on needs_input when query is ambiguous."""
    mock_search = MagicMock()
    mock_search.json.return_value = {
        "items": [
            {
                "company_number": "01026167",
                "title": "BARCLAYS BANK PLC",
                "company_status": "active",
            },
            {
                "company_number": "02223073",
                "title": "BARCLAYS ALDERSGATE",
                "company_status": "active",
            },
        ]
    }
    mock_search.raise_for_status = MagicMock()
    mock_request.return_value = mock_search

    res = skill.execute(
        {
            "action": "resolve_company_officer",
            "query": "Barclays",
            "officer_name": "John",
        }
    )

    assert res["status"] == "needs_input"
    assert res["reason"] == "multiple_matches"
    assert len(res["candidates"]) == 2
    assert mock_request.call_count == 1  # halted before get_officers


def test_composite_resolve_company_officer_missing_company(skill):
    """resolve_company_officer without query or company_number returns error."""
    res = skill.execute({"action": "resolve_company_officer"})
    assert res["status"] == "error"
    assert res["error_code"] == "missing_company"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_context_isolation_no_sticky_filters(mock_request, skill):
    """Context remains strictly lean and does not leak volatile filter parameters."""
    mock_officers = MagicMock()
    mock_officers.json.return_value = {
        "items": [
            {"name": "SMITH, John", "officer_role": "director"},
            {"name": "DOE, Jane", "officer_role": "secretary"},
        ],
        "total_results": 2,
        "active_count": 2,
    }
    mock_officers.raise_for_status = MagicMock()
    mock_request.return_value = mock_officers

    # Turn 1: Call with volatile filters
    turn1 = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
            "officer_name": "Smith",
            "officer_role": "director",
            "role_hint": "ceo",
        }
    )

    ctx = turn1["context"]
    assert "officer_name" not in ctx
    assert "officer_filter" not in ctx
    assert "officer_role" not in ctx
    assert "role_hint" not in ctx
    assert "latest_only" not in ctx
    assert set(ctx.keys()) == {
        "company_number",
        "company_name",
        "selected_transaction_id",
        "last_action",
    }


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_run_pipeline_pauses_on_ambiguous_company(mock_request, skill):
    """run_pipeline halts with needs_input when resolve_company returns ambiguous candidates."""
    mock_search = MagicMock()
    mock_search.json.return_value = {
        "items": [
            {
                "company_number": "00048839",
                "title": "BARCLAYS PLC",
                "company_status": "active",
            },
            {
                "company_number": "01026167",
                "title": "BARCLAYS BANK PLC",
                "company_status": "active",
            },
        ]
    }
    mock_search.raise_for_status = MagicMock()
    mock_request.return_value = mock_search

    steps = [
        {"action": "resolve_company", "params": {"query": "Barclays"}},
        {"action": "get_officers", "params": {"company_number": "<from_resolve>"}},
    ]

    res = skill.execute({"action": "run_pipeline", "steps": steps})
    assert res["status"] == "needs_input"
    assert res["reason"] == "multiple_matches"
    assert len(res["candidates"]) == 2
    assert "resume run_pipeline" in res["agent_hint"]
    assert len(res["steps"]) == 1


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_run_pipeline_multi_company_resolve_boundary(mock_request, skill):
    """run_pipeline stops substituting <from_resolve> when encountering a subsequent resolve_company step."""
    mock_search_tesco = MagicMock()
    mock_search_tesco.json.return_value = {
        "items": [
            {
                "company_number": "00445790",
                "title": "TESCO PLC",
                "company_status": "active",
            }
        ]
    }
    mock_search_tesco.raise_for_status = MagicMock()

    mock_filings = MagicMock()
    mock_filings.json.return_value = {
        "items": [
            {
                "category": "accounts",
                "date": "2026-07-25",
                "description": "accounts-group",
            }
        ],
        "total_count": 1,
    }
    mock_filings.raise_for_status = MagicMock()

    mock_request.side_effect = [mock_search_tesco, mock_filings]

    steps = [
        {"action": "resolve_company", "params": {"query": "Tesco"}},
        {
            "action": "get_filing_history",
            "params": {"company_number": "<from_resolve>"},
        },
        {"action": "resolve_company", "params": {"query": "Barclays"}},
        {
            "action": "get_officers",
            "params": {
                "company_number": "<from_resolve>",
                "officer_name": "John McFarlane",
            },
        },
    ]

    # Turn 1: resolve Tesco
    turn1 = skill.execute({"action": "run_pipeline", "steps": steps})
    assert turn1["status"] == "partial"
    assert turn1["company_number"] == "00445790"

    rem_steps = turn1["steps"]
    assert len(rem_steps) == 3
    # Tesco filings step got Tesco's number
    assert rem_steps[0]["params"]["company_number"] == "00445790"
    # Barclays resolve step
    assert rem_steps[1]["action"] == "resolve_company"
    # Barclays officers step MUST NOT be overwritten by Tesco's number!
    assert rem_steps[2]["params"]["company_number"] == "<from_resolve>"

    # Turn 2: get Tesco filings
    turn2 = skill.execute(
        {
            "action": "run_pipeline",
            "steps": rem_steps,
            "context": turn1["context"],
            "pipeline": turn1["pipeline"],
        }
    )
    assert turn2["status"] == "partial"
    rem_steps2 = turn2["steps"]
    assert len(rem_steps2) == 2
    assert rem_steps2[0]["action"] == "resolve_company"
    # Barclays officers step MUST STILL remain <from_resolve>!
    assert rem_steps2[1]["params"]["company_number"] == "<from_resolve>"

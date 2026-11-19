import os
from unittest.mock import MagicMock, patch

import pytest
import requests
import yaml

from .skill import UkCompaniesHouseHandlerSkill

# --- Fixtures ---


@pytest.fixture
def skill():
    """Initialize skill with a placeholder API key."""
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
        "get_company_charges",
        "get_insolvency",
        "get_filing_item",
    ]:
        result = skill.execute({"action": action})
        assert result["status"] == "error"
        assert result["error_code"] == "missing_company_number"


def test_list_downloadable_documents_needs_company_number(skill):
    """list_downloadable_documents returns needs_input without company_number."""
    result = skill.execute({"action": "list_downloadable_documents"})
    assert result["status"] == "needs_input"
    assert result["reason"] == "missing_company_number"


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


# --- Document API Tests (v1.4.0 / #421) ---

_MOCK_FILINGS_WITH_DOCS = {
    "total_count": 3,
    "filing_history_status": "filing-history-available",
    "items": [
        {
            "date": "2024-03-15",
            "category": "accounts",
            "type": "AA",
            "description": "accounts-with-accounts-type-full",
            "transaction_id": "tx-accounts-001",
            "barcode": "B1",
            "links": {
                "document_metadata": (
                    "https://document-api.company-information.service.gov.uk/document/doc-accounts-001"
                )
            },
        },
        {
            "date": "2024-01-10",
            "category": "confirmation-statement",
            "type": "CS01",
            "description": "confirmation-statement",
            "transaction_id": "tx-cs-001",
            "barcode": "B2",
            "links": {
                "document_metadata": (
                    "https://document-api.company-information.service.gov.uk/document/doc-cs-001"
                )
            },
        },
        {
            "date": "2023-06-01",
            "category": "officers",
            "type": "AP01",
            "description": "appointment",
            "transaction_id": "tx-no-doc",
            "barcode": "B3",
            "links": {},
        },
    ],
}

_MOCK_DOC_METADATA = {
    "id": "doc-accounts-001",
    "created_at": "2024-03-16T10:00:00Z",
    "pages": 42,
    "resources": {
        "application/pdf": {
            "content_length": 1024,
            "created_at": "2024-03-16T10:00:00Z",
        },
        "application/xhtml+xml": {
            "content_length": 2048,
            "created_at": "2024-03-16T10:00:00Z",
        },
    },
    "links": {
        "self": (
            "https://document-api.company-information.service.gov.uk/document/doc-accounts-001"
        ),
        "document": (
            "https://document-api.company-information.service.gov.uk/document/doc-accounts-001/content"
        ),
    },
}


def _mock_response(json_data=None, status=200, headers=None, content=b"", raw=None):
    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    if json_data is not None:
        resp.json.return_value = json_data
    resp.content = content
    resp.raise_for_status = MagicMock()
    if status >= 400:
        http_err = requests.exceptions.HTTPError(f"HTTP {status}", response=resp)
        resp.raise_for_status.side_effect = http_err

    def iter_content(chunk_size=8192):
        data = raw if raw is not None else content
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]

    resp.iter_content = iter_content
    resp.close = MagicMock()
    return resp


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_list_downloadable_documents(mock_request, skill):
    """list_downloadable_documents filters filings with metadata links."""
    mock_request.return_value = _mock_response(_MOCK_FILINGS_WITH_DOCS)

    result = skill.execute(
        {
            "action": "list_downloadable_documents",
            "company_number": "00102498",
            "limit": 10,
        }
    )

    assert result["status"] == "ready"
    assert len(result["documents"]) == 2
    assert result["documents"][0]["transaction_id"] == "tx-accounts-001"
    assert result["documents"][0]["downloadable"] is True
    assert "document-api.company-information" in result["documents"][0]["metadata_url"]
    assert "tx-no-doc" not in [d["transaction_id"] for d in result["documents"]]
    assert "document_candidates" in result["context"]
    assert "tx-accounts-001" in result["context"]["document_candidates"]


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_list_downloadable_documents_latest_only(mock_request, skill):
    mock_request.return_value = _mock_response(_MOCK_FILINGS_WITH_DOCS)
    result = skill.execute(
        {
            "action": "list_downloadable_documents",
            "company_number": "00102498",
            "latest_only": True,
        }
    )
    assert result["status"] == "ready"
    assert len(result["documents"]) == 1
    assert result["documents"][0]["transaction_id"] == "tx-accounts-001"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_list_downloadable_documents_category_filter(mock_request, skill):
    mock_request.return_value = _mock_response(_MOCK_FILINGS_WITH_DOCS)
    result = skill.execute(
        {
            "action": "list_downloadable_documents",
            "company_number": "00102498",
            "category": "accounts",
        }
    )
    assert result["status"] == "ready"
    # Mock ignores category server-side; client still returns downloadable only
    assert all(d["downloadable"] for d in result["documents"])
    filing_call = mock_request.call_args_list[0]
    assert filing_call[1]["params"]["category"] == "accounts"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_document_metadata(mock_request, skill):
    mock_request.return_value = _mock_response(_MOCK_DOC_METADATA)
    result = skill.execute(
        {
            "action": "get_document_metadata",
            "metadata_url": (
                "https://document-api.company-information.service.gov.uk/document/doc-accounts-001"
            ),
            "transaction_id": "tx-accounts-001",
        }
    )
    assert result["status"] == "ready"
    assert result["source"] == "companies_house_document_api"
    assert "application/pdf" in result["mime_types"]
    assert result["total_pages"] == 42
    assert result["content_length"] == 1024
    assert result["context"]["selected_transaction_id"] == "tx-accounts-001"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_document_metadata_404(mock_request, skill):
    mock_request.return_value = _mock_response(status=404)
    result = skill.execute(
        {
            "action": "get_document_metadata",
            "metadata_url": (
                "https://document-api.company-information.service.gov.uk/document/missing"
            ),
        }
    )
    assert result["status"] == "error"
    assert result["error_code"] == "not_found"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_document_metadata_410(mock_request, skill):
    resp = _mock_response(status=410)
    mock_request.return_value = resp
    result = skill.execute(
        {
            "action": "get_document_metadata",
            "metadata_url": (
                "https://document-api.company-information.service.gov.uk/document/gone"
            ),
        }
    )
    assert result["status"] == "error"
    assert result["error_code"] == "api_error"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_document_api_429_includes_retry_after(mock_request, skill):
    resp = _mock_response(status=429, headers={"Retry-After": "12"})
    mock_request.return_value = resp
    result = skill.execute(
        {
            "action": "get_document_metadata",
            "metadata_url": (
                "https://document-api.company-information.service.gov.uk/document/doc-accounts-001"
            ),
        }
    )
    assert result["status"] == "error"
    assert result["error_code"] == "rate_limited"
    assert result["retry_after"] == "12"
    assert "Retry-After: 12" in result["agent_hint"]


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_fetch_document_with_redirect_drops_auth(mock_request, skill):
    """Auth on Document API only; redirect to storage has no Authorization."""
    pdf_bytes = b"%PDF-1.4 mock document content"

    def side_effect(method, url, **kwargs):
        if url.endswith("/document/doc-accounts-001") and not url.endswith("/content"):
            return _mock_response(_MOCK_DOC_METADATA)
        if url.endswith("/document/doc-accounts-001/content"):
            assert kwargs.get("auth") is not None
            assert kwargs.get("allow_redirects") is False
            return _mock_response(
                status=302,
                headers={
                    "Location": "https://s3.example.com/presigned/doc.pdf?X-Amz=1"
                },
            )
        if url.startswith("https://s3.example.com/"):
            assert kwargs.get("auth") is None
            assert "Authorization" not in (kwargs.get("headers") or {})
            return _mock_response(status=200, content=pdf_bytes, raw=pdf_bytes)
        raise AssertionError(f"Unexpected URL: {url}")

    mock_request.side_effect = side_effect

    result = skill.execute(
        {
            "action": "fetch_document",
            "metadata_url": (
                "https://document-api.company-information.service.gov.uk/document/doc-accounts-001"
            ),
            "transaction_id": "tx-accounts-001",
            "company_number": "00102498",
            "context": {
                "company_number": "00102498",
                "document_candidates": {
                    "tx-accounts-001": {
                        "metadata_url": (
                            "https://document-api.company-information.service.gov.uk/document/doc-accounts-001"
                        ),
                        "date": "2024-03-15",
                        "category": "accounts",
                    }
                },
            },
        }
    )

    assert result["status"] == "ready"
    assert result["size_bytes"] == len(pdf_bytes)
    assert result["content_type"] == "application/pdf"
    import base64

    assert base64.b64decode(result["content_base64"]) == pdf_bytes
    assert result["context"]["selected_transaction_id"] == "tx-accounts-001"
    assert "00102498" in result["filename"]
    # Ensure no disk write artifacts from skill
    assert not any(key.endswith("_path") or key == "saved_to" for key in result)


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_fetch_document_oversize_from_metadata(mock_request, skill):
    big_meta = dict(_MOCK_DOC_METADATA)
    big_meta["resources"] = {
        "application/pdf": {
            "content_length": 12_582_912,
            "created_at": "2024-03-16T10:00:00Z",
        }
    }
    mock_request.return_value = _mock_response(big_meta)
    result = skill.execute(
        {
            "action": "fetch_document",
            "metadata_url": (
                "https://document-api.company-information.service.gov.uk/document/doc-accounts-001"
            ),
            "max_bytes": 5_242_880,
        }
    )
    assert result["status"] == "error"
    assert result["error_code"] == "document_too_large"
    assert result["reason"] == "document_too_large"
    assert result["size_bytes"] == 12_582_912
    assert result["max_bytes"] == 5_242_880
    assert mock_request.call_count == 1  # metadata only; no content fetch


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_fetch_document_oversize_during_stream(mock_request, skill):
    oversized = b"x" * 3000

    def side_effect(method, url, **kwargs):
        if url.endswith("/document/doc-accounts-001") and not url.endswith("/content"):
            meta = dict(_MOCK_DOC_METADATA)
            # Declare small so we enter stream path
            meta["resources"] = {
                "application/pdf": {
                    "content_length": 100,
                    "created_at": "2024-03-16T10:00:00Z",
                }
            }
            return _mock_response(meta)
        if url.endswith("/content"):
            return _mock_response(
                status=302,
                headers={"Location": "https://s3.example.com/big.pdf"},
            )
        if url.startswith("https://s3.example.com/"):
            return _mock_response(status=200, content=oversized, raw=oversized)
        raise AssertionError(url)

    mock_request.side_effect = side_effect
    result = skill.execute(
        {
            "action": "fetch_document",
            "metadata_url": (
                "https://document-api.company-information.service.gov.uk/document/doc-accounts-001"
            ),
            "max_bytes": 2048,
        }
    )
    assert result["status"] == "error"
    assert result["error_code"] == "document_too_large"
    assert result["max_bytes"] == 2048
    assert result["size_bytes"] > 2048


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_fetch_document_include_content_false(mock_request, skill):
    mock_request.return_value = _mock_response(_MOCK_DOC_METADATA)
    result = skill.execute(
        {
            "action": "fetch_document",
            "metadata_url": (
                "https://document-api.company-information.service.gov.uk/document/doc-accounts-001"
            ),
            "include_content": False,
        }
    )
    assert result["status"] == "ready"
    assert result["content_base64"] is None
    assert result["download_url"].endswith("/content")
    assert mock_request.call_count == 1


def test_fetch_document_missing_target(skill):
    result = skill.execute({"action": "fetch_document"})
    assert result["status"] == "error"
    assert result["error_code"] == "missing_document_target"


def test_invalid_metadata_url(skill):
    result = skill.execute(
        {
            "action": "get_document_metadata",
            "metadata_url": "https://evil.example.com/document/x",
        }
    )
    assert result["status"] == "error"
    assert result["error_code"] == "invalid_metadata_url"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_run_pipeline_document_flow(mock_request, skill):
    """resolve -> list_downloadable_documents via run_pipeline."""
    call_n = {"i": 0}

    def side_effect(method, url, **kwargs):
        idx = call_n["i"]
        call_n["i"] += 1
        if "/search/companies" in url:
            return _mock_response(
                {
                    "items": [
                        {
                            "company_number": "00102498",
                            "title": "BP P.L.C.",
                            "company_status": "active",
                            "company_type": "plc",
                            "address_snippet": "London",
                            "date_of_creation": "1909-04-14",
                            "snippet": "",
                        }
                    ]
                }
            )
        if "/filing-history" in url:
            return _mock_response(_MOCK_FILINGS_WITH_DOCS)
        raise AssertionError(f"unexpected {url} call={idx}")

    mock_request.side_effect = side_effect

    first = skill.execute(
        {
            "action": "run_pipeline",
            "steps": [
                {"action": "resolve_company", "params": {"query": "BP"}},
                {
                    "action": "list_downloadable_documents",
                    "params": {
                        "company_number": "<from_resolve>",
                        "category": "accounts",
                        "latest_only": True,
                    },
                },
            ],
        }
    )
    assert first["status"] == "partial"
    assert first["company_number"] == "00102498"

    second = skill.execute(
        {
            "action": "run_pipeline",
            "steps": first["steps"],
            "context": first["context"],
            "pipeline": first["pipeline"],
        }
    )
    assert second["status"] == "ready"
    assert len(second["documents"]) == 1
    assert second["documents"][0]["category"] == "accounts"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_fetch_document_404_on_content(mock_request, skill):
    def side_effect(method, url, **kwargs):
        if url.endswith("/document/doc-accounts-001") and not url.endswith("/content"):
            return _mock_response(_MOCK_DOC_METADATA)
        if url.endswith("/content"):
            return _mock_response(status=404)
        raise AssertionError(url)

    mock_request.side_effect = side_effect
    result = skill.execute(
        {
            "action": "fetch_document",
            "metadata_url": (
                "https://document-api.company-information.service.gov.uk/document/doc-accounts-001"
            ),
        }
    )
    assert result["status"] == "error"
    assert result["error_code"] == "not_found"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_fetch_document_410_on_content(mock_request, skill):
    def side_effect(method, url, **kwargs):
        if url.endswith("/document/doc-accounts-001") and not url.endswith("/content"):
            return _mock_response(_MOCK_DOC_METADATA)
        if url.endswith("/content"):
            return _mock_response(status=410)
        raise AssertionError(url)

    mock_request.side_effect = side_effect
    result = skill.execute(
        {
            "action": "fetch_document",
            "metadata_url": (
                "https://document-api.company-information.service.gov.uk/document/doc-accounts-001"
            ),
        }
    )
    assert result["status"] == "error"
    assert result["error_code"] == "api_error"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_fetch_document_429_on_content(mock_request, skill):
    def side_effect(method, url, **kwargs):
        if url.endswith("/document/doc-accounts-001") and not url.endswith("/content"):
            return _mock_response(_MOCK_DOC_METADATA)
        if url.endswith("/content"):
            return _mock_response(status=429, headers={"Retry-After": "30"})
        raise AssertionError(url)

    mock_request.side_effect = side_effect
    result = skill.execute(
        {
            "action": "fetch_document",
            "metadata_url": (
                "https://document-api.company-information.service.gov.uk/document/doc-accounts-001"
            ),
        }
    )
    assert result["status"] == "error"
    assert result["error_code"] == "rate_limited"
    assert result["retry_after"] == "30"


def test_manifest_version_200(manifest):
    assert manifest["version"] == "2.0.0"
    actions = manifest["parameters"]["properties"]["action"]["enum"]
    assert "list_downloadable_documents" in actions
    assert "get_document_metadata" in actions
    assert "fetch_document" in actions


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_run_pipeline_keeps_document_candidates_in_context(mock_request, skill):
    """Candidates from a pipeline list step survive the outer context merge."""
    mock_request.return_value = _mock_response(_MOCK_FILINGS_WITH_DOCS)
    result = skill.execute(
        {
            "action": "run_pipeline",
            "company_number": "00102498",
            "context": {"company_number": "00102498", "company_name": "BP P.L.C."},
            "steps": [
                {
                    "action": "list_downloadable_documents",
                    "params": {"company_number": "<from_resolve>"},
                }
            ],
        }
    )
    assert result["status"] == "ready"
    assert "tx-accounts-001" in result["context"]["document_candidates"]


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_fetch_document_resolves_unknown_transaction_via_filing_item(
    mock_request, skill
):
    """A transaction_id outside candidates is resolved via filing-history item."""
    pdf = b"%PDF-1.7 tiny"
    seen = []

    def side_effect(method, url, **kwargs):
        seen.append(url)
        if url.endswith("/company/00102498/filing-history/tx-accounts-001"):
            return _mock_response(_MOCK_FILINGS_WITH_DOCS["items"][0])
        if url.endswith("/document/doc-accounts-001"):
            return _mock_response(_MOCK_DOC_METADATA)
        if url.endswith("/content"):
            return _mock_response(
                status=302, headers={"Location": "https://s3.example.com/x.pdf"}
            )
        if url.startswith("https://s3.example.com/"):
            return _mock_response(status=200, raw=pdf)
        raise AssertionError(url)

    mock_request.side_effect = side_effect
    result = skill.execute(
        {
            "action": "fetch_document",
            "transaction_id": "tx-accounts-001",
            "context": {"company_number": "00102498", "company_name": "BP P.L.C."},
        }
    )
    assert result["status"] == "ready"
    assert result["filename"] == "00102498_accounts_2024-03-15.pdf"
    assert not any("/document/tx-accounts-001" in u for u in seen)


def test_fetch_document_unknown_transaction_without_company(skill):
    result = skill.execute({"action": "fetch_document", "transaction_id": "tx-x"})
    assert result["status"] == "error"
    assert result["error_code"] == "unknown_transaction_id"


# --- v2e Tests: Charges, Insolvency, Filing Item, Officer Search & Appointments ---


def _mock_http_error(status_code: int) -> requests.exceptions.HTTPError:
    resp = MagicMock()
    resp.status_code = status_code
    err = requests.exceptions.HTTPError(f"HTTP {status_code}", response=resp)
    return err


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_officers_extracts_officer_id(mock_request, skill):
    """get_officers extracts officer_id from links.officer.appointments."""
    mock_request.return_value = _mock_response(
        {
            "total_results": 1,
            "active_count": 1,
            "items": [
                {
                    "name": "AUCHINCLOSS, Murray",
                    "officer_role": "director",
                    "appointed_on": "2020-07-01",
                    "links": {
                        "officer": {
                            "appointments": "/officers/off-murray-123/appointments"
                        }
                    },
                }
            ],
        }
    )
    res = skill.execute(
        {
            "action": "get_officers",
            "company_number": "00102498",
            "context": {"company_number": "00102498", "company_name": "BP P.L.C."},
        }
    )
    assert res["status"] == "ready"
    assert res["officers"][0]["officer_id"] == "off-murray-123"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_company_charges_collection_and_status_filter(mock_request, skill):
    """get_company_charges returns formatted charges and applies status_filter."""
    mock_request.return_value = _mock_response(
        {
            "total_count": 2,
            "satisfied_count": 1,
            "part_satisfied_count": 0,
            "items": [
                {
                    "charge_code": "094462310001",
                    "charge_number": 1,
                    "status": "outstanding",
                    "created_on": "2021-05-10",
                    "delivered_on": "2021-05-12",
                    "classification": {"description": "A registered charge"},
                    "particulars": {"description": "Fixed and floating debenture"},
                    "persons_entitled": [{"name": "Barclays Bank PLC"}],
                    "links": {"self": "/company/09446231/charges/chg-001"},
                },
                {
                    "charge_code": "094462310002",
                    "charge_number": 2,
                    "status": "fully-satisfied",
                    "created_on": "2019-01-10",
                    "delivered_on": "2019-01-11",
                    "satisfied_on": "2022-03-01",
                    "persons_entitled": [{"name": "HSBC UK Bank PLC"}],
                    "links": {"self": "/company/09446231/charges/chg-002"},
                },
            ],
        }
    )
    res = skill.execute(
        {
            "action": "get_company_charges",
            "company_number": "09446231",
            "status_filter": "outstanding",
            "context": {
                "company_number": "09446231",
                "company_name": "MONZO BANK LIMITED",
            },
        }
    )
    assert res["status"] == "ready"
    assert len(res["charges"]) == 1
    assert res["charges"][0]["charge_id"] == "chg-001"
    assert res["charges"][0]["persons_entitled"] == ["Barclays Bank PLC"]
    assert res["total_count"] == 2
    assert res["satisfied_count"] == 1


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_company_charges_single_and_404(mock_request, skill):
    """get_company_charges handles single charge_id lookup and 404 charge_not_found."""
    mock_request.return_value = _mock_response(
        {
            "charge_code": "094462310001",
            "status": "outstanding",
            "persons_entitled": [{"name": "Barclays Bank PLC"}],
            "links": {"self": "/company/09446231/charges/chg-001"},
        }
    )
    res = skill.execute(
        {
            "action": "get_company_charges",
            "company_number": "09446231",
            "charge_id": "/company/09446231/charges/chg-001",
            "context": {
                "company_number": "09446231",
                "company_name": "MONZO BANK LIMITED",
            },
        }
    )
    assert res["status"] == "ready"
    assert res["charge_id"] == "chg-001"
    assert res["charge"]["charge_id"] == "chg-001"

    mock_request.side_effect = _mock_http_error(404)
    err_res = skill.execute(
        {
            "action": "get_company_charges",
            "company_number": "09446231",
            "charge_id": "chg-missing",
            "context": {
                "company_number": "09446231",
                "company_name": "MONZO BANK LIMITED",
            },
        }
    )
    assert err_res["status"] == "error"
    assert err_res["error_code"] == "charge_not_found"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_company_charges_404_normalization(mock_request, skill):
    """404 on charges collection verifies existence unless context already cached."""
    # Context bypass: 1 HTTP call (charges -> 404), no profile probe
    mock_request.side_effect = [_mock_http_error(404)]
    res = skill.execute(
        {
            "action": "get_company_charges",
            "company_number": "00102498",
            "context": {"company_number": "00102498", "company_name": "BP P.L.C."},
        }
    )
    assert res["status"] == "ready"
    assert res["charges"] == []
    assert res["total_count"] == 0
    assert mock_request.call_count == 1

    # Unverified context: charges 404 -> profile 404 -> company_not_found
    mock_request.reset_mock()
    mock_request.side_effect = [_mock_http_error(404), _mock_http_error(404)]
    err_res = skill.execute(
        {
            "action": "get_company_charges",
            "company_number": "99999999",
        }
    )
    assert err_res["status"] == "error"
    assert err_res["error_code"] == "company_not_found"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_insolvency_cases_and_404_normalization(mock_request, skill):
    """get_insolvency parses active cases and normalizes 404s with existence check."""
    mock_request.return_value = _mock_response(
        {
            "status": ["liquidation"],
            "cases": [
                {
                    "type": "compulsory-liquidation",
                    "number": "1",
                    "dates": [{"type": "wound-up-on", "date": "2023-06-15"}],
                    "practitioners": [
                        {"name": "Jane Insolvency", "role": "final-liquidator"}
                    ],
                }
            ],
        }
    )
    res = skill.execute(
        {
            "action": "get_insolvency",
            "company_number": "11112222",
            "context": {"company_number": "11112222", "company_name": "ACME LTD"},
        }
    )
    assert res["status"] == "ready"
    assert res["has_insolvency_history"] is True
    assert len(res["cases"]) == 1
    assert res["cases"][0]["practitioners"][0]["name"] == "Jane Insolvency"

    # Context bypass on 404
    mock_request.reset_mock()
    mock_request.side_effect = [_mock_http_error(404)]
    clean_res = skill.execute(
        {
            "action": "get_insolvency",
            "company_number": "00102498",
            "context": {"company_number": "00102498", "company_name": "BP P.L.C."},
        }
    )
    assert clean_res["status"] == "ready"
    assert clean_res["has_insolvency_history"] is False
    assert clean_res["cases"] == []

    # Unverified context: insolvency 404 -> profile 200 -> clean
    mock_request.reset_mock()
    mock_request.side_effect = [
        _mock_http_error(404),
        _mock_response({"company_name": "BP P.L.C."}),
    ]
    probe_ok = skill.execute(
        {
            "action": "get_insolvency",
            "company_number": "00102498",
        }
    )
    assert probe_ok["status"] == "ready"
    assert probe_ok["has_insolvency_history"] is False
    assert probe_ok["company_name"] == "BP P.L.C."

    # Unverified context: insolvency 404 -> profile 404 -> company_not_found
    mock_request.reset_mock()
    mock_request.side_effect = [_mock_http_error(404), _mock_http_error(404)]
    probe_404 = skill.execute(
        {
            "action": "get_insolvency",
            "company_number": "99999999",
        }
    )
    assert probe_404["status"] == "error"
    assert probe_404["error_code"] == "company_not_found"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_filing_item(mock_request, skill):
    """get_filing_item validates transaction_id, sanitizes path, and sets downloadable."""
    missing = skill.execute({"action": "get_filing_item", "company_number": "00102498"})
    assert missing["status"] == "error"
    assert missing["error_code"] == "missing_transaction_id"

    mock_request.return_value = _mock_response(
        {
            "transaction_id": "MzM1",
            "date": "2024-03-15",
            "category": "accounts",
            "type": "AA",
            "description": "accounts-with-accounts-type-full",
            "links": {
                "self": "/company/00102498/filing-history/MzM1",
                "document_metadata": "https://document-api.company-information.service.gov.uk/document/doc-123",
            },
        }
    )
    res = skill.execute(
        {
            "action": "get_filing_item",
            "company_number": "00102498",
            "transaction_id": "/company/00102498/filing-history/MzM1",
            "context": {"company_number": "00102498", "company_name": "BP P.L.C."},
        }
    )
    assert res["status"] == "ready"
    assert res["transaction_id"] == "MzM1"
    assert res["downloadable"] is True
    assert res["filing"]["category"] == "accounts"

    mock_request.side_effect = _mock_http_error(404)
    not_found = skill.execute(
        {
            "action": "get_filing_item",
            "company_number": "00102498",
            "transaction_id": "missing-tx",
            "context": {"company_number": "00102498", "company_name": "BP P.L.C."},
        }
    )
    assert not_found["status"] == "error"
    assert not_found["error_code"] == "filing_not_found"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_search_officers_disambiguation_and_context_isolation(mock_request, skill):
    """search_officers handles multi-match, single-match, zero-match without inheriting company_number."""
    missing = skill.execute({"action": "search_officers"})
    assert missing["status"] == "error"
    assert missing["error_code"] == "missing_query"

    # Multi-match -> needs_input
    mock_request.return_value = _mock_response(
        {
            "total_results": 2,
            "items": [
                {
                    "title": "John MCFARLANE",
                    "appointment_count": 5,
                    "date_of_birth": {"month": 6, "year": 1947},
                    "address_snippet": "1 Churchill Place, London",
                    "links": {"self": "/officers/off-111/appointments"},
                },
                {
                    "title": "John MCFARLANE",
                    "appointment_count": 2,
                    "date_of_birth": {"month": 1, "year": 1965},
                    "address_snippet": "10 George Street, Edinburgh",
                    "links": {"self": "/officers/off-222/appointments"},
                },
            ],
        }
    )
    multi = skill.execute(
        {
            "action": "search_officers",
            "query": "John McFarlane",
            "context": {"company_number": "00102498", "company_name": "BP P.L.C."},
        }
    )
    assert multi["status"] == "needs_input"
    assert multi["reason"] == "multiple_matches"
    assert len(multi["candidates"]) == 2
    assert multi["candidates"][0]["officer_id"] == "off-111"
    assert "officer_id" not in multi["context"]
    assert mock_request.call_count == 1  # No extra profile fetch

    # Single match -> ready
    mock_request.reset_mock()
    mock_request.return_value = _mock_response(
        {
            "total_results": 1,
            "items": [
                {
                    "title": "Murray AUCHINCLOSS",
                    "appointment_count": 3,
                    "links": {"self": "/officers/off-333/appointments"},
                }
            ],
        }
    )
    single = skill.execute({"action": "search_officers", "query": "Murray Auchincloss"})
    assert single["status"] == "ready"
    assert single["officer_id"] == "off-333"
    assert "officer_id" not in single["context"]

    # Zero match -> ready empty
    mock_request.return_value = _mock_response({"total_results": 0, "items": []})
    empty = skill.execute({"action": "search_officers", "query": "Nobody XYZ"})
    assert empty["status"] == "ready"
    assert empty["officers"] == []
    assert empty["total_results"] == 0


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_get_officer_appointments_filter_and_404(mock_request, skill):
    """get_officer_appointments passes filter=active by default, sanitizes id, and handles 404."""
    missing = skill.execute({"action": "get_officer_appointments"})
    assert missing["status"] == "error"
    assert missing["error_code"] == "missing_officer_id"

    mock_request.return_value = _mock_response(
        {
            "name": "AUCHINCLOSS, Murray",
            "total_results": 1,
            "active_count": 1,
            "items": [
                {
                    "appointed_to": {
                        "company_name": "BP P.L.C.",
                        "company_number": "00102498",
                        "company_status": "active",
                    },
                    "officer_role": "director",
                    "appointed_on": "2020-07-01",
                }
            ],
        }
    )
    res = skill.execute(
        {
            "action": "get_officer_appointments",
            "officer_id": "/officers/off-333/appointments",
            "context": {
                "company_number": "09446231",
                "company_name": "MONZO BANK LIMITED",
            },
        }
    )
    assert res["status"] == "ready"
    assert res["officer_id"] == "off-333"
    assert res["appointments"][0]["company_number"] == "00102498"
    assert res["appointments"][0]["is_active"] is True
    assert "officer_id" not in res["context"]
    assert "company_number" not in res or res.get("company_number") != "09446231"
    # Verify filter=active was sent
    _, kwargs = mock_request.call_args
    assert kwargs["params"]["filter"] == "active"

    # active_only=False omits filter param
    mock_request.reset_mock()
    skill.execute(
        {
            "action": "get_officer_appointments",
            "officer_id": "off-333",
            "active_only": False,
        }
    )
    _, kwargs = mock_request.call_args
    assert "filter" not in kwargs["params"]

    # 404 -> officer_not_found
    mock_request.side_effect = _mock_http_error(404)
    err = skill.execute(
        {
            "action": "get_officer_appointments",
            "officer_id": "off-missing",
        }
    )
    assert err["status"] == "error"
    assert err["error_code"] == "officer_not_found"


@patch("skills.finance.uk_companies_house_handler.skill.requests.request")
def test_run_pipeline_chains_charges_and_insolvency(mock_request, skill):
    """run_pipeline auto-binds company_number across charges and insolvency steps."""
    mock_request.side_effect = [
        _mock_response(
            {
                "items": [
                    {
                        "company_number": "09446231",
                        "title": "MONZO BANK LIMITED",
                        "company_status": "active",
                    }
                ]
            }
        ),
        _mock_response(
            {
                "company_name": "MONZO BANK LIMITED",
                "company_number": "09446231",
                "company_status": "active",
            }
        ),
        _mock_response({"total_count": 0, "items": []}),
        _mock_http_error(404),
    ]
    step1 = skill.execute(
        {
            "action": "run_pipeline",
            "steps": [
                {"action": "resolve_company", "params": {"query": "Monzo Bank"}},
                {
                    "action": "get_company_profile",
                    "params": {"company_number": "<from_resolve>"},
                },
                {
                    "action": "get_company_charges",
                    "params": {"company_number": "<from_resolve>"},
                },
                {
                    "action": "get_insolvency",
                    "params": {"company_number": "<from_resolve>"},
                },
            ],
        }
    )
    assert step1["status"] == "partial"
    assert step1["steps"][0]["params"]["company_number"] == "09446231"
    assert step1["steps"][1]["params"]["company_number"] == "09446231"
    assert step1["steps"][2]["params"]["company_number"] == "09446231"

    step2 = skill.execute(
        {
            "action": "run_pipeline",
            "steps": step1["steps"],
            "context": step1["context"],
            "pipeline": step1["pipeline"],
        }
    )
    assert step2["status"] == "partial"

    step3 = skill.execute(
        {
            "action": "run_pipeline",
            "steps": step2["steps"],
            "context": step2["context"],
            "pipeline": step2["pipeline"],
        }
    )
    assert step3["status"] == "partial"
    assert step3["charges"] == []

    step4 = skill.execute(
        {
            "action": "run_pipeline",
            "steps": step3["steps"],
            "context": step3["context"],
            "pipeline": step3["pipeline"],
        }
    )
    assert step4["status"] == "ready"
    assert step4["has_insolvency_history"] is False

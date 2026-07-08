"""
Shared helpers for uk_companies_house_handler examples.

Set UK_COMPANIES_HOUSE_EXAMPLE_DEMO=1 to run a scripted flow with mocked
HTTP responses (no live API key required).
"""

from __future__ import annotations

import json
from typing import Any, Dict

SKILL_ID = "finance/uk_companies_house_handler"


# --- Mock Data ---

MOCK_SEARCH_RESPONSE = {
    "items": [
        {
            "company_number": "00102498",
            "title": "BP P.L.C.",
            "company_status": "active",
            "company_type": "plc",
            "address_snippet": "1 St James's Square, London, SW1Y 4PD",
            "date_of_creation": "1909-04-14",
        },
        {
            "company_number": "04284740",
            "title": "BP OIL UK LIMITED",
            "company_status": "active",
            "company_type": "ltd",
            "address_snippet": "Chertsey Road, Sunbury On Thames, TW16 7BP",
            "date_of_creation": "2001-10-01",
        },
    ]
}

MOCK_PROFILE_RESPONSE = {
    "company_name": "BP P.L.C.",
    "company_status": "active",
    "type": "plc",
    "date_of_creation": "1909-04-14",
    "registered_office_address": {
        "address_line_1": "1 St James's Square",
        "locality": "London",
        "postal_code": "SW1Y 4PD",
        "country": "United Kingdom",
    },
    "sic_codes": ["06100", "19200"],
    "has_charges": True,
    "has_insolvency_history": False,
    "jurisdiction": "england-wales",
    "accounts": {
        "next_due": "2025-12-31",
        "last_accounts": {"made_up_to": "2024-12-31"},
    },
}

MOCK_OFFICERS_RESPONSE = {
    "items": [
        {
            "name": "LOONEY, Bernard",
            "officer_role": "director",
            "appointed_on": "2020-04-02",
            "nationality": "Irish",
            "occupation": "Company Director",
            "country_of_residence": "England",
        },
        {
            "name": "SHERIDAN, Kerry",
            "officer_role": "secretary",
            "appointed_on": "2019-01-15",
            "nationality": "British",
            "occupation": "Company Secretary",
        },
        {
            "name": "CONNELLY, Brian",
            "officer_role": "director",
            "appointed_on": "2015-03-01",
            "resigned_on": "2022-06-30",
            "nationality": "American",
            "occupation": "Executive",
        },
    ],
    "total_results": 3,
    "active_count": 2,
}

MOCK_PSC_RESPONSE = {
    "items": [
        {
            "name": "Example Holding Company Ltd",
            "kind": "corporate-entity-person-with-significant-control",
            "notified_on": "2016-04-06",
            "natures_of_control": [
                "ownership-of-shares-75-to-100-percent",
                "voting-rights-75-to-100-percent",
            ],
        }
    ],
    "total_results": 1,
}

MOCK_FILING_RESPONSE = {
    "items": [
        {
            "date": "2024-12-15",
            "category": "accounts",
            "type": "AA",
            "description": "accounts-with-accounts-type-full",
            "barcode": "XA1B2C3D",
            "transaction_id": "MzM1MjExOTY3OWFkaXF6a2N4",
            "links": {"document_metadata": "/document/abc123def"},
        },
        {
            "date": "2024-06-01",
            "category": "confirmation-statement",
            "type": "CS01",
            "description": "confirmation-statement",
            "barcode": "YB2C3D4E",
            "transaction_id": "NjQ2NjIyOTY3OWFkaXF6a2N4",
        },
    ],
    "total_count": 2,
    "filing_history_status": "filing-history-available",
}


def run_scripted_flow(skill: Any) -> None:
    """Deterministic agent-style sequence: map_intent, resolve, profile, officers, PSC, filings."""
    print("=== uk_companies_house_handler scripted flow ===\n")
    print("User Query: Who is the CEO of BP?")

    # Step 0: Map intent
    intent_result = skill.execute(
        {
            "action": "map_intent",
            "intent_keywords": "CEO",
            "entities": {"company_query": "BP"},
        }
    )
    print(json.dumps(intent_result, indent=2))

    # Step 1: Resolve company
    resolve_result = skill.execute(
        {"action": "resolve_company", "query": "BP", "limit": 5}
    )
    print(json.dumps(resolve_result, indent=2))

    # Pick the first candidate
    if resolve_result["status"] == "needs_input":
        company_number = resolve_result["candidates"][0]["company_number"]
        company_name = resolve_result["candidates"][0]["title"]
        print(f"\nUser selects: {company_name} ({company_number})\n")
    elif resolve_result["status"] == "ready":
        company_number = resolve_result["company_number"]
        company_name = resolve_result.get("company_name", "")
        print(f"\nSingle match: {company_name} ({company_number})\n")
    else:
        print(f"\nError: {resolve_result.get('message', 'unknown')}")
        return

    # Step 2: Get company profile
    profile_result = skill.execute(
        {"action": "get_company_profile", "company_number": company_number}
    )
    print(json.dumps(profile_result, indent=2))

    # Step 3: Get officers (active only)
    officers_result = skill.execute(
        {
            "action": "get_officers",
            "company_number": company_number,
            "active_only": True,
        }
    )
    print(json.dumps(officers_result, indent=2))

    # Step 4: Get PSCs
    psc_result = skill.execute({"action": "get_pscs", "company_number": company_number})
    print(json.dumps(psc_result, indent=2))

    # Step 5: Get filing history
    filing_result = skill.execute(
        {"action": "get_filing_history", "company_number": company_number}
    )
    print(json.dumps(filing_result, indent=2))

    print("\n=== flow complete ===")


def handle_tool_call(skill: Any, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a single uk_companies_house_handler tool call payload."""
    return skill.execute(tool_input)

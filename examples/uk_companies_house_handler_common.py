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

MOCK_BARCLAYS_SEARCH_RESPONSE = {
    "items": [
        {
            "company_number": "01026167",
            "title": "BARCLAYS BANK PLC",
            "company_status": "active",
            "company_type": "plc",
            "address_snippet": "1 Churchill Place, London, E14 5HP",
            "date_of_creation": "1896-07-20",
        },
        {
            "company_number": "01026167",
            "title": "BARCLAYS EXECUTIVE NOMINEES LIMITED",
            "company_status": "active",
            "company_type": "ltd",
            "address_snippet": "1 Churchill Place, London, E14 5HP",
            "date_of_creation": "1985-03-12",
        },
    ]
}

MOCK_BP_SINGLE_SEARCH_RESPONSE = {
    "items": [
        {
            "company_number": "00102498",
            "title": "BP P.L.C.",
            "company_status": "active",
            "company_type": "plc",
            "address_snippet": "1 St James's Square, London, SW1Y 4PD",
            "date_of_creation": "1909-04-14",
        }
    ]
}

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

MOCK_OFFICERS_PARTIAL_RESPONSE = {
    "items": [
        {
            "name": f"DIRECTOR-{idx}, Example",
            "officer_role": "director",
            "appointed_on": "2020-01-01",
        }
        for idx in range(15)
    ],
    "total_results": 15,
    "active_count": 15,
    "company_name": "BP P.L.C.",
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
    """Deterministic v2b flows: composite, pipeline, partial preview, disambiguation."""
    print("=== uk_companies_house_handler v2b scripted flows ===\n")

    print(
        "--- Flow A: composite resolve_and_get_officers (clean query + role_hint) ---"
    )
    print('User: "Who is the CEO of BP?" -> agent passes query="BP", role_hint="ceo"\n')
    composite = skill.execute(
        {
            "action": "resolve_and_get_officers",
            "query": "BP",
            "role_hint": "ceo",
        }
    )
    print(json.dumps(composite, indent=2))
    context = composite.get("context", {})

    print("\n--- Flow B: map_intent + run_pipeline (officers and filings) ---")
    intent = skill.execute(
        {
            "action": "map_intent",
            "intent_keywords": "officers, filings",
            "entities": {"company_query": "BP"},
        }
    )
    print(json.dumps(intent, indent=2))
    pipeline = skill.execute(
        {
            "action": "run_pipeline",
            "steps": intent["suggested_pipeline"],
            "context": context,
        }
    )
    print(json.dumps(pipeline, indent=2))
    context = pipeline.get("context", context)

    print("\n--- Flow C: disambiguation resume (Barclays-style needs_input) ---")
    disambig = skill.execute({"action": "resolve_company", "query": "Barclays"})
    print(json.dumps(disambig, indent=2))
    if disambig["status"] == "needs_input":
        picked = disambig["candidates"][0]
        context["company_number"] = picked["company_number"]
        context["company_name"] = picked["title"]
        print(f"\nUser selects: {picked['title']} ({picked['company_number']})\n")
        resumed = skill.execute(
            {
                "action": "get_officers",
                "role_hint": "ceo",
                "context": context,
            }
        )
        print(json.dumps(resumed, indent=2))

    print("\n--- Flow D: partial officers preview (limit 10 of many) ---")
    partial = skill.execute(
        {
            "action": "get_officers",
            "company_number": context.get("company_number", "00102498"),
            "limit": 10,
        }
    )
    print(json.dumps(partial, indent=2))

    print("\n=== flow complete ===")


def handle_tool_call(skill: Any, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Dispatch a single uk_companies_house_handler tool call payload."""
    return skill.execute(tool_input)

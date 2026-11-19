"""
Mocked due diligence demo script for finance/uk_companies_house_handler (v2.0.0).

Demonstrates an end-to-end v2.0.0 corporate due diligence flow with mocked HTTP:
  1. run_pipeline: resolve_company -> get_company_profile -> get_company_charges -> get_insolvency
  2. search_officers -> get_officer_appointments (1-hop cross-entity tracing)
  3. get_filing_item (single filing transaction inspection)

No live API key required.

Usage:
  python examples/uk_companies_house_due_diligence_demo.py
"""

from __future__ import annotations

import json
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import MagicMock, patch

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

from uk_companies_house_handler_common import (  # noqa: E402
    MOCK_BP_SINGLE_SEARCH_RESPONSE,
    MOCK_CHARGES_RESPONSE,
    MOCK_FILING_ITEM_RESPONSE,
    MOCK_OFFICER_APPOINTMENTS_RESPONSE,
    MOCK_PROFILE_RESPONSE,
    MOCK_SEARCH_OFFICERS_RESPONSE,
    SKILL_ID,
)
from skillware.core.loader import SkillLoader  # noqa: E402


@contextmanager
def demo_skill() -> Iterator[Any]:
    """Yield a skill instance with mocked URL-routed HTTP responses."""
    bundle = SkillLoader.load_skill(SKILL_ID)
    skill = bundle["module"].UkCompaniesHouseHandlerSkill(
        config={"COMPANIES_HOUSE_API_KEY": "demo_key"}
    )

    def mock_request(method: str, url: str, **kwargs: Any) -> MagicMock:
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()

        if url.endswith("/search/companies"):
            mock_resp.json.return_value = MOCK_BP_SINGLE_SEARCH_RESPONSE
        elif url.endswith("/search/officers"):
            mock_resp.json.return_value = MOCK_SEARCH_OFFICERS_RESPONSE
        elif url.endswith("/appointments"):
            mock_resp.json.return_value = MOCK_OFFICER_APPOINTMENTS_RESPONSE
        elif url.endswith("/charges"):
            mock_resp.json.return_value = MOCK_CHARGES_RESPONSE
        elif url.endswith("/insolvency"):
            err_resp = MagicMock()
            err_resp.status_code = 404
            mock_resp.status_code = 404
            mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError(
                "404 Not Found", response=err_resp
            )
        elif "/filing-history/" in url:
            mock_resp.json.return_value = MOCK_FILING_ITEM_RESPONSE
        elif url.endswith("/company/00102498"):
            mock_resp.json.return_value = MOCK_PROFILE_RESPONSE
        else:
            raise AssertionError(f"Unexpected mocked URL: {url}")

        return mock_resp

    with patch(
        "skills.finance.uk_companies_house_handler.skill.requests.request",
        side_effect=mock_request,
    ):
        yield skill


def main() -> None:
    print("DEMO MODE: mocked HTTP — no live API key required.\n")
    with demo_skill() as skill:
        print("--- Step 1: Due Diligence Pipeline (Profile + Charges + Insolvency) ---")
        context: dict[str, Any] = {}
        pipeline_state = None
        steps = [
            {"action": "resolve_company", "params": {"query": "BP"}},
            {
                "action": "get_company_profile",
                "params": {"company_number": "<from_resolve>"},
            },
            {
                "action": "get_company_charges",
                "params": {
                    "company_number": "<from_resolve>",
                    "status_filter": "outstanding",
                },
            },
            {
                "action": "get_insolvency",
                "params": {"company_number": "<from_resolve>"},
            },
        ]
        while steps:
            res = skill.execute(
                {
                    "action": "run_pipeline",
                    "steps": steps,
                    "context": context,
                    "pipeline": pipeline_state,
                }
            )
            print(json.dumps(res, indent=2))
            context = res.get("context", context)
            pipeline_state = res.get("pipeline")
            steps = res.get("steps", [])
            if res.get("status") in ("needs_input", "error"):
                break

        print("\n--- Step 2: 1-Hop Officer Search & Appointments ---")
        search_res = skill.execute(
            {"action": "search_officers", "query": "Bernard Looney"}
        )
        print(json.dumps(search_res, indent=2))
        officer_id = search_res.get("officer_id")
        if officer_id:
            appt_res = skill.execute(
                {
                    "action": "get_officer_appointments",
                    "officer_id": officer_id,
                    "active_only": True,
                }
            )
            print(json.dumps(appt_res, indent=2))

        print("\n--- Step 3: Single Filing Item Inspection ---")
        filing_res = skill.execute(
            {
                "action": "get_filing_item",
                "company_number": "00102498",
                "transaction_id": "MzM1",
                "context": context,
            }
        )
        print(json.dumps(filing_res, indent=2))

    print("\n=== due diligence demo complete ===")


if __name__ == "__main__":
    main()

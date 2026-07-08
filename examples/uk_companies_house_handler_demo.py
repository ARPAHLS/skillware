"""
Mocked demo script for finance/uk_companies_house_handler.

Runs a scripted sequence (map_intent -> resolve_company -> get_company_profile
-> get_officers -> get_pscs -> get_filing_history) using mocked HTTP responses.
No live API key is required.

Usage:
  python examples/uk_companies_house_handler_demo.py
"""

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from uk_companies_house_handler_common import (  # noqa: E402
    MOCK_FILING_RESPONSE,
    MOCK_OFFICERS_RESPONSE,
    MOCK_PROFILE_RESPONSE,
    MOCK_PSC_RESPONSE,
    MOCK_SEARCH_RESPONSE,
    SKILL_ID,
    run_scripted_flow,
)
from skillware.core.loader import SkillLoader  # noqa: E402


@contextmanager
def demo_skill() -> Iterator[Any]:
    """Yield a skill instance with mocked HTTP for demo mode."""
    bundle = SkillLoader.load_skill(SKILL_ID)
    skill = bundle["module"].UkCompaniesHouseHandlerSkill(
        config={"COMPANIES_HOUSE_API_KEY": "demo_key"}
    )

    call_counter = {"n": 0}
    ordered_responses = [
        MOCK_SEARCH_RESPONSE,
        MOCK_PROFILE_RESPONSE,
        MOCK_OFFICERS_RESPONSE,
        MOCK_PSC_RESPONSE,
        MOCK_FILING_RESPONSE,
    ]

    def mock_request(method, url, **kwargs):
        mock_resp = MagicMock()
        idx = min(call_counter["n"], len(ordered_responses) - 1)
        mock_resp.json.return_value = ordered_responses[idx]
        mock_resp.raise_for_status = MagicMock()
        call_counter["n"] += 1
        return mock_resp

    with patch(
        "skills.finance.uk_companies_house_handler.skill.requests.request",
        side_effect=mock_request,
    ):
        yield skill


def main() -> None:
    print("DEMO MODE: mocked HTTP — no live API key required.\n")
    with demo_skill() as skill:
        run_scripted_flow(skill)


if __name__ == "__main__":
    main()

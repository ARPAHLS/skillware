"""Offline demo for defi/token_security_scanner v0.2.

Shows a bundled GoPlus fixture, policy_action, and a token-slug scan.
No network. Set TOKEN_SCAN_LIVE=1 to also call GoPlus for the Base DEGEN token.

    python examples/token_security_scanner_demo.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skillware.core.loader import SkillLoader  # noqa: E402

DEGEN = "0x4ed4e862860bed51a9570b96d89af5e1b0efefed"
FIXTURE = (
    REPO_ROOT
    / "skills"
    / "defi"
    / "token_security_scanner"
    / "fixtures"
    / "goplus_clean_base.json"
)


def _mock_get(payload: dict):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = payload
    return response


def run_offline() -> None:
    print("=== defi/token_security_scanner demo (offline) ===")
    skill = SkillLoader.load_skill("defi/token_security_scanner")["class"]()
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    skill._session.get = lambda *args, **kwargs: _mock_get(payload)

    chains = skill.execute({"action": "supported_chains"})
    base = next(row for row in chains["chains"] if row["slug"] == "base")
    print(
        f"base goplus_supported={base['goplus_supported']} chain_id={base['chain_id']}"
    )

    report = skill.execute({"action": "scan", "chain": "base", "token": "degen"})
    print(
        f"token=degen contract={report['contract']} "
        f"tier={report['risk_tier']} policy_action={report['policy_action']} "
        f"profile={report['policy_profile']}"
    )
    print("Demo completed successfully.")


def run_live() -> None:
    print("=== live GoPlus scan (TOKEN_SCAN_LIVE=1) ===")
    skill = SkillLoader.load_skill("defi/token_security_scanner")["class"]()
    report = skill.execute({"action": "scan", "chain": "base", "contract": DEGEN})
    print(report.get("status"), report.get("risk_tier"), report.get("policy_action"))
    if report.get("status") != "ok":
        print(report.get("error_code"), report.get("message"))


if __name__ == "__main__":
    run_offline()
    if os.environ.get("TOKEN_SCAN_LIVE") == "1":
        run_live()

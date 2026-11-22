# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ARPA Hellenic Logical Systems

"""Host-loop simulations for finance/ephemeral_wallet (#41 v0.2)."""

from __future__ import annotations

import pytest
from eth_account import Account

from skills.finance.ephemeral_wallet.providers import HttpX402Provider
from skills.finance.ephemeral_wallet.signers import Eip3009ExactSigner
from skills.finance.ephemeral_wallet.skill import (
    EphemeralWalletSkill,
    _reset_sessions_for_tests,
)
from skills.finance.ephemeral_wallet.x402_client import (
    ScriptedHttp,
    build_mock_402_pair,
)


@pytest.fixture(autouse=True)
def _clean():
    _reset_sessions_for_tests()
    yield
    _reset_sessions_for_tests()


def test_simulation_quote_then_pay_then_revoke():
    skill = EphemeralWalletSkill()
    created = skill.execute(
        {
            "action": "create_session",
            "spend_cap_usd": 3.0,
            "network": "eip155:84532",
            "allowed_domains": ["api.example.com"],
        }
    )
    sid = created["session_id"]
    url = "https://api.example.com/premium"

    quoted = skill.execute({"action": "quote", "session_id": sid, "url": url})
    assert quoted["status"] == "quoted"
    assert quoted["within_cap"] is True

    paid = skill.execute(
        {
            "action": "pay",
            "session_id": sid,
            "url": url,
            "amount_usd": quoted["quote"]["amount_usd"],
            "idempotency_key": "sim-1",
        }
    )
    assert paid["status"] == "confirmed"
    assert paid["remaining_usd"] < 3.0

    blocked_ssrf = skill.execute(
        {"action": "pay", "session_id": sid, "url": "http://169.254.169.254/"}
    )
    assert blocked_ssrf["status"] == "ssrf_blocked"

    skill.execute({"action": "revoke", "session_id": sid})
    after = skill.execute(
        {"action": "pay", "session_id": sid, "url": url, "amount_usd": 0.1}
    )
    assert after["status"] == "revoked"


def test_simulation_live_signer_over_scripted_http():
    """Live EIP-3009 signer + scripted 402/200 (no outbound network)."""
    acct = Account.create()
    url = "https://api.example.com/item"
    caip2 = "eip155:84532"
    challenge, success = build_mock_402_pair(
        url=url, amount_atomic="250000", network_caip2=caip2
    )
    http = ScriptedHttp([challenge, success])
    provider = HttpX402Provider(
        signer=Eip3009ExactSigner(acct.key.hex()), http_get=http.get
    )
    skill = EphemeralWalletSkill(provider=provider)
    created = skill.execute(
        {"action": "create_session", "spend_cap_usd": 2.0, "network": "base-sepolia"}
    )
    # Force mock session but injected provider still uses live signer.
    paid = skill.execute(
        {
            "action": "pay",
            "session_id": created["session_id"],
            "url": url,
            "amount_usd": 1.0,
        }
    )
    assert paid["status"] == "confirmed"
    assert paid["payment"]["signing"] == "eip3009"
    assert paid["payment"]["nonce"]
    assert len(http.calls) == 2
    headers = {str(k).lower(): v for k, v in http.calls[1]["headers"].items()}
    assert "payment-signature" in headers

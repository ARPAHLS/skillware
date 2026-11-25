# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ARPA Hellenic Logical Systems

"""Tests for finance/ephemeral_wallet (#41 / #475 / #516)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from skillware.core.config import GLOBAL_CONFIG_DIR_ENV, clear_config_cache
from skillware.core.evm_config import clear_evm_config_cache
from skills.finance.ephemeral_wallet.networks import normalize_network
from skills.finance.ephemeral_wallet.providers import (
    HttpX402Provider,
    MockX402Provider,
)
from skills.finance.ephemeral_wallet.skill import (
    EphemeralWalletSkill,
    _reset_sessions_for_tests,
)
from skills.finance.ephemeral_wallet.x402_client import (
    HEADER_PAYMENT_SIGNATURE,
    MockExactSigner,
    ScriptedHttp,
    X402Error,
    build_mock_402_pair,
    settle_x402,
)


@pytest.fixture(autouse=True)
def _clean_sessions():
    _reset_sessions_for_tests()
    yield
    _reset_sessions_for_tests()


@pytest.fixture
def skill(monkeypatch):
    monkeypatch.delenv("EPHEMERAL_WALLET_SESSION_DIR", raising=False)
    monkeypatch.delenv("EPHEMERAL_WALLET_MOCK", raising=False)
    for key in ("CDP_API_KEY_ID", "CDP_API_KEY_SECRET", "CDP_WALLET_SECRET"):
        monkeypatch.delenv(key, raising=False)
    return EphemeralWalletSkill()


def test_manifest_contract():
    skill = EphemeralWalletSkill()
    manifest_path = Path(__file__).with_name("manifest.yaml")
    with manifest_path.open(encoding="utf-8") as handle:
        manifest = yaml.safe_load(handle)
    assert skill.manifest["name"] == manifest["name"] == "finance/ephemeral_wallet"
    assert skill.manifest["version"] == "0.2.1"
    assert "requests" in skill.manifest["requirements"]
    assert "eth_account" in skill.manifest["requirements"]
    assert "quote" in skill.manifest["parameters"]["properties"]["action"]["enum"]
    assert "constitution" in skill.manifest


def test_network_caip2_aliases():
    alias, caip2 = normalize_network("base-sepolia")
    assert alias == "base-sepolia"
    assert caip2 == "eip155:84532"
    alias2, caip22 = normalize_network("eip155:84532")
    assert caip22 == "eip155:84532"
    assert alias2 == "base-sepolia"


def test_network_resolves_custom_evm_yaml_chain(tmp_path, monkeypatch):
    clear_config_cache()
    clear_evm_config_cache()
    config_dir = tmp_path / "cfg"
    config_dir.mkdir()
    monkeypatch.setenv(GLOBAL_CONFIG_DIR_ENV, str(config_dir))
    (config_dir / "evm.yaml").write_text(
        """
version: 1
chains:
  custom_pay_l2:
    enabled: false
    chain_id: 424242
    rpc_env: CUSTOM_PAY_L2_RPC_URL
    native_symbol: eth
    native_decimals: 18
""",
        encoding="utf-8",
    )
    clear_evm_config_cache()
    alias, caip2 = normalize_network("custom_pay_l2")
    assert alias == "custom_pay_l2"
    assert caip2 == "eip155:424242"
    alias2, caip22 = normalize_network("eip155:424242")
    assert caip22 == "eip155:424242"
    assert alias2 == "custom_pay_l2"
    clear_config_cache()
    clear_evm_config_cache()


def test_network_bundled_evm_alias_via_resolve_chain():
    """Bundled defaults (e.g. arbitrum) map even when not in the x402 builtin table."""
    alias, caip2 = normalize_network("arbitrum")
    assert alias == "arbitrum"
    assert caip2 == "eip155:42161"


def test_create_status_pay_revoke_happy_path(skill):
    created = skill.execute(
        {
            "action": "create_session",
            "spend_cap_usd": 5.0,
            "ttl_seconds": 3600,
            "network": "base-sepolia",
        }
    )
    assert created["status"] == "ready"
    assert created["session_id"].startswith("ews_")
    assert created["network_caip2"] == "eip155:84532"
    assert "private_key" not in created

    sid = created["session_id"]
    paid = skill.execute(
        {
            "action": "pay",
            "session_id": sid,
            "url": "https://api.example.com/v1/resource",
            "amount_usd": 1.25,
        }
    )
    assert paid["status"] == "confirmed"
    assert paid["remaining_usd"] == pytest.approx(3.75)
    assert paid["payment"]["tx_ref"]
    assert paid["payment"]["nonce"]
    assert paid["payment"]["network"] == "eip155:84532"
    assert "cvv" not in paid["payment"]

    revoked = skill.execute({"action": "revoke", "session_id": sid})
    assert revoked["status"] == "revoked"
    blocked = skill.execute(
        {
            "action": "pay",
            "session_id": sid,
            "url": "https://api.example.com/v1/resource",
            "amount_usd": 0.5,
        }
    )
    assert blocked["status"] == "revoked"


def test_x402_handshake_scripted_http():
    url = "https://api.example.com/premium"
    caip2 = "eip155:84532"
    challenge, success = build_mock_402_pair(
        url=url, amount_atomic="1000000", network_caip2=caip2
    )
    http = ScriptedHttp([challenge, success])
    used: set[str] = set()
    result = settle_x402(
        url=url,
        session_caip2=caip2,
        remaining_usd=5.0,
        max_amount_usd=2.0,
        signer=MockExactSigner(),
        http_get=http.get,
        used_nonces=used,
    )
    assert result.amount_usd == pytest.approx(1.0)
    assert result.nonce
    assert HEADER_PAYMENT_SIGNATURE in http.calls[1]["headers"]
    # Replay same nonce blocked
    used.add(result.nonce)
    challenge2, success2 = build_mock_402_pair(
        url=url, amount_atomic="1000000", network_caip2=caip2
    )
    http2 = ScriptedHttp([challenge2, success2])

    class FixedNonceSigner(MockExactSigner):
        def sign_exact(self, **kwargs):
            payload = super().sign_exact(**kwargs)
            payload["authorization"]["nonce"] = result.nonce
            return payload

    with pytest.raises(X402Error) as exc:
        settle_x402(
            url=url,
            session_caip2=caip2,
            remaining_usd=5.0,
            max_amount_usd=2.0,
            signer=FixedNonceSigner(),
            http_get=http2.get,
            used_nonces=used,
        )
    assert exc.value.code == "replay"


def test_http_provider_with_scripted_transport():
    url = "https://api.example.com/item"
    caip2 = "eip155:84532"
    challenge, success = build_mock_402_pair(
        url=url, amount_atomic="500000", network_caip2=caip2
    )
    http = ScriptedHttp([challenge, success])
    provider = HttpX402Provider(http_get=http.get)
    used: set[str] = set()
    receipt = provider.pay(
        session_id="ews_test",
        url=url,
        amount_usd=1.0,
        network_caip2=caip2,
        remaining_usd=5.0,
        used_nonces=used,
        idempotency_key="k1",
    )
    assert receipt["provider"] == "http_x402"
    assert receipt["amount_usd"] == pytest.approx(0.5)
    assert receipt["nonce"] in used


def test_ssrf_blocks_loopback(skill):
    created = skill.execute({"action": "create_session", "spend_cap_usd": 2.0})
    out = skill.execute(
        {
            "action": "pay",
            "session_id": created["session_id"],
            "url": "http://127.0.0.1/secret",
            "amount_usd": 0.1,
        }
    )
    assert out["status"] == "ssrf_blocked"


def test_allowed_domains_enforced(skill):
    created = skill.execute(
        {
            "action": "create_session",
            "spend_cap_usd": 2.0,
            "allowed_domains": ["api.example.com"],
        }
    )
    denied = skill.execute(
        {
            "action": "pay",
            "session_id": created["session_id"],
            "url": "https://evil.example.net/x",
            "amount_usd": 0.1,
        }
    )
    assert denied["status"] == "ssrf_blocked"
    ok = skill.execute(
        {
            "action": "pay",
            "session_id": created["session_id"],
            "url": "https://api.example.com/ok",
            "amount_usd": 0.1,
        }
    )
    assert ok["status"] == "confirmed"


def test_idempotency_key_replays_prior_payment(skill):
    created = skill.execute({"action": "create_session", "spend_cap_usd": 5.0})
    sid = created["session_id"]
    first = skill.execute(
        {
            "action": "pay",
            "session_id": sid,
            "url": "https://api.example.com/v1/resource",
            "amount_usd": 1.0,
            "idempotency_key": "order-9",
        }
    )
    second = skill.execute(
        {
            "action": "pay",
            "session_id": sid,
            "url": "https://api.example.com/v1/resource",
            "amount_usd": 1.0,
            "idempotency_key": "order-9",
        }
    )
    assert first["status"] == second["status"] == "confirmed"
    assert second.get("idempotent_replay") is True
    assert second["remaining_usd"] == first["remaining_usd"]
    assert second["payment"]["tx_ref"] == first["payment"]["tx_ref"]


def test_over_cap_from_server_amount(skill):
    created = skill.execute({"action": "create_session", "spend_cap_usd": 0.25})
    out = skill.execute(
        {
            "action": "pay",
            "session_id": created["session_id"],
            "url": "https://api.example.com/v1/resource",
            "amount_usd": 1.0,
        }
    )
    assert out["status"] == "over_cap"


def test_expired_fail_closed(skill):
    created = skill.execute(
        {"action": "create_session", "spend_cap_usd": 2.0, "ttl_seconds": 60}
    )
    sid = created["session_id"]
    from skills.finance.ephemeral_wallet import skill as skill_mod

    past = (
        (datetime.now(timezone.utc) - timedelta(seconds=5))
        .isoformat()
        .replace("+00:00", "Z")
    )
    skill_mod._SESSIONS[sid]["expires_at"] = past
    out = skill.execute(
        {
            "action": "pay",
            "session_id": sid,
            "url": "https://api.example.com/x",
            "amount_usd": 0.1,
        }
    )
    assert out["status"] == "expired"


def test_missing_config_when_live_without_cdp(skill, monkeypatch):
    out = skill.execute(
        {"action": "create_session", "spend_cap_usd": 1.0, "live": True}
    )
    assert out["status"] == "missing_config"


def test_live_with_cdp_creates_http_session(skill, monkeypatch):
    from eth_account import Account

    acct = Account.create()
    monkeypatch.setenv("CDP_API_KEY_ID", "id")
    monkeypatch.setenv("CDP_API_KEY_SECRET", "secret")
    monkeypatch.setenv("CDP_WALLET_SECRET", acct.key.hex())
    out = skill.execute(
        {"action": "create_session", "spend_cap_usd": 1.0, "live": True}
    )
    assert out["status"] == "ready"
    assert out["settlement"] == "http_x402"
    assert out["signing"] == "eip3009"
    assert out["wallet_address"] == acct.address


def test_quote_dry_run_no_spend(skill):
    created = skill.execute({"action": "create_session", "spend_cap_usd": 5.0})
    sid = created["session_id"]
    quoted = skill.execute(
        {
            "action": "quote",
            "session_id": sid,
            "url": "https://api.example.com/v1/resource",
        }
    )
    assert quoted["status"] == "quoted"
    assert quoted["within_cap"] is True
    assert quoted["quote"]["amount_usd"] == pytest.approx(0.5)
    assert quoted["quote"]["network"] == "eip155:84532"
    # quote must not debit
    st = skill.execute({"action": "status", "session_id": sid})
    assert st["remaining_usd"] == pytest.approx(5.0)
    assert st["payments_count"] == 0


def test_eip3009_signer_produces_recoverable_signature():
    from eth_account import Account
    from eth_account.messages import encode_typed_data

    from skills.finance.ephemeral_wallet.signers import Eip3009ExactSigner

    acct = Account.create()
    signer = Eip3009ExactSigner(acct.key.hex())
    accepted = {
        "scheme": "exact",
        "network": "eip155:84532",
        "amount": "10000",
        "asset": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
        "payTo": "0x209693Bc6afc0C5328bA36FaF03C514EF312287C",
        "maxTimeoutSeconds": 60,
        "extra": {"name": "USDC", "version": "2"},
    }
    payload = signer.sign_exact(
        accepted=accepted, resource={"url": "https://api.example.com/x"}, extensions={}
    )
    auth = payload["authorization"]
    typed = {
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "TransferWithAuthorization": [
                {"name": "from", "type": "address"},
                {"name": "to", "type": "address"},
                {"name": "value", "type": "uint256"},
                {"name": "validAfter", "type": "uint256"},
                {"name": "validBefore", "type": "uint256"},
                {"name": "nonce", "type": "bytes32"},
            ],
        },
        "primaryType": "TransferWithAuthorization",
        "domain": {
            "name": "USDC",
            "version": "2",
            "chainId": 84532,
            "verifyingContract": accepted["asset"],
        },
        "message": {
            "from": auth["from"],
            "to": auth["to"],
            "value": int(auth["value"]),
            "validAfter": int(auth["validAfter"]),
            "validBefore": int(auth["validBefore"]),
            "nonce": bytes.fromhex(auth["nonce"][2:]),
        },
    }
    recovered = Account.recover_message(
        encode_typed_data(full_message=typed), signature=payload["signature"]
    )
    assert recovered == acct.address


def test_provider_injection_sanitizes_secrets():
    class LeakyProvider(MockX402Provider):
        def pay(self, **kwargs: Any) -> Dict[str, Any]:
            receipt = super().pay(**kwargs)
            receipt["private_key"] = "0xDEAD"
            receipt["cvv"] = "999"
            return receipt

    store: dict = {}
    skill = EphemeralWalletSkill(provider=LeakyProvider(), sessions=store)
    created = skill.execute({"action": "create_session", "spend_cap_usd": 2.0})
    paid = skill.execute(
        {
            "action": "pay",
            "session_id": created["session_id"],
            "url": "https://api.example.com/p",
            "amount_usd": 0.25,
        }
    )
    assert paid["status"] == "confirmed"
    assert "private_key" not in paid["payment"]
    assert "cvv" not in paid["payment"]


def test_session_dir_jsonl(skill, tmp_path, monkeypatch):
    monkeypatch.setenv("EPHEMERAL_WALLET_SESSION_DIR", str(tmp_path))
    created = skill.execute(
        {"action": "create_session", "spend_cap_usd": 3.0, "ttl_seconds": 120}
    )
    sid = created["session_id"]
    skill.execute(
        {
            "action": "pay",
            "session_id": sid,
            "url": "https://api.example.com/item",
            "amount_usd": 0.5,
        }
    )
    sessions_log = (
        (tmp_path / "sessions.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    payments_log = (
        (tmp_path / "payments.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    assert len(sessions_log) >= 1
    assert len(payments_log) == 1
    assert json.loads(payments_log[0])["amount_usd"] == 0.5

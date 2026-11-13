# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ARPA Hellenic Logical Systems

"""Mocked tests for finance/ephemeral_wallet (#41 PR1)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from skills.finance.ephemeral_wallet.providers import MockX402Provider
from skills.finance.ephemeral_wallet.skill import (
    EphemeralWalletSkill,
    _reset_sessions_for_tests,
)


@pytest.fixture(autouse=True)
def _clean_sessions():
    _reset_sessions_for_tests()
    yield
    _reset_sessions_for_tests()


@pytest.fixture
def skill(tmp_path, monkeypatch):
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
    assert skill.manifest["version"] == "0.1.0"
    assert (
        "create_session" in skill.manifest["parameters"]["properties"]["action"]["enum"]
    )
    assert "constitution" in skill.manifest
    assert "CDP_WALLET_SECRET" in skill.manifest["env_vars"]


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
    assert created["spend_cap_usd"] == 5.0
    assert created["remaining_usd"] == 5.0
    assert created["wallet_address"].startswith("0x")
    assert "private_key" not in created
    assert "CDP_WALLET_SECRET" not in json.dumps(created)
    assert "card_number" not in created
    assert "cvv" not in created

    sid = created["session_id"]
    st = skill.execute({"action": "status", "session_id": sid})
    assert st["status"] == "ready"
    assert st["payments_count"] == 0
    assert st["revoked"] is False

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
    assert paid["payment"]["tx_ref"].startswith("mock_tx_")
    assert paid["payment"]["url"] == "https://api.example.com/v1/resource"
    assert "cvv" not in paid["payment"]
    assert "pan" not in paid["payment"]

    st2 = skill.execute({"action": "status", "session_id": sid})
    assert st2["payments_count"] == 1
    assert st2["last_payment"]["amount_usd"] == 1.25

    revoked = skill.execute({"action": "revoke", "session_id": sid})
    assert revoked["status"] == "revoked"
    assert revoked["revoked_at"]

    blocked = skill.execute(
        {
            "action": "pay",
            "session_id": sid,
            "url": "https://api.example.com/v1/resource",
            "amount_usd": 0.5,
        }
    )
    assert blocked["status"] == "revoked"


def test_over_cap_fail_closed(skill):
    created = skill.execute(
        {"action": "create_session", "spend_cap_usd": 1.0, "ttl_seconds": 600}
    )
    sid = created["session_id"]
    out = skill.execute(
        {
            "action": "pay",
            "session_id": sid,
            "url": "https://pay.example/x",
            "amount_usd": 1.01,
        }
    )
    assert out["status"] == "over_cap"
    assert out["remaining_usd"] == pytest.approx(1.0)


def test_expired_fail_closed(skill):
    created = skill.execute(
        {"action": "create_session", "spend_cap_usd": 2.0, "ttl_seconds": 60}
    )
    sid = created["session_id"]
    # Force expiry in the process store.
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
            "url": "https://pay.example/x",
            "amount_usd": 0.1,
        }
    )
    assert out["status"] == "expired"

    st = skill.execute({"action": "status", "session_id": sid})
    assert st["status"] == "expired"


def test_unknown_session_fail_closed(skill):
    out = skill.execute({"action": "status", "session_id": "ews_missing"})
    assert out["status"] == "error"
    assert "Unknown session_id" in out["error"]


def test_missing_config_when_live_without_cdp(skill, monkeypatch):
    monkeypatch.delenv("CDP_API_KEY_ID", raising=False)
    monkeypatch.delenv("CDP_API_KEY_SECRET", raising=False)
    monkeypatch.delenv("CDP_WALLET_SECRET", raising=False)
    out = skill.execute(
        {"action": "create_session", "spend_cap_usd": 1.0, "live": True}
    )
    assert out["status"] == "missing_config"
    assert "setup" in out
    assert "CDP_API_KEY_ID" in out["error"]


def test_missing_config_when_mock_env_disabled(skill, monkeypatch):
    monkeypatch.setenv("EPHEMERAL_WALLET_MOCK", "0")
    out = skill.execute({"action": "create_session", "spend_cap_usd": 1.0})
    assert out["status"] == "missing_config"


def test_live_with_cdp_still_refuses_in_pr1(skill, monkeypatch):
    monkeypatch.setenv("CDP_API_KEY_ID", "id")
    monkeypatch.setenv("CDP_API_KEY_SECRET", "secret")
    monkeypatch.setenv("CDP_WALLET_SECRET", "wallet")
    out = skill.execute(
        {"action": "create_session", "spend_cap_usd": 1.0, "live": True}
    )
    assert out["status"] == "error"
    assert "not wired" in out["error"].lower() or "mock only" in out["error"].lower()


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
    skill.execute({"action": "revoke", "session_id": sid})

    sessions_log = (
        (tmp_path / "sessions.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    payments_log = (
        (tmp_path / "payments.jsonl").read_text(encoding="utf-8").strip().splitlines()
    )
    assert len(sessions_log) == 2  # create + revoke
    assert len(payments_log) == 1
    create_row = json.loads(sessions_log[0])
    assert create_row["event"] == "create"
    assert create_row["session_id"] == sid
    pay_row = json.loads(payments_log[0])
    assert pay_row["amount_usd"] == 0.5
    assert "private_key" not in pay_row


def test_session_dir_unwritable_fail_closed(skill, tmp_path, monkeypatch):
    bad = tmp_path / "not_a_dir"
    bad.write_text("file", encoding="utf-8")
    monkeypatch.setenv("EPHEMERAL_WALLET_SESSION_DIR", str(bad))
    out = skill.execute({"action": "create_session", "spend_cap_usd": 1.0})
    assert out["status"] == "error"
    assert "SESSION_DIR" in out["error"] or "writable" in out["error"].lower()


def test_provider_injection_sanitizes_secrets():
    class LeakyProvider(MockX402Provider):
        def pay(self, **kwargs):
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
            "url": "https://x.example/p",
            "amount_usd": 0.25,
        }
    )
    assert paid["status"] == "confirmed"
    assert "private_key" not in paid["payment"]
    assert "cvv" not in paid["payment"]


def test_unsupported_action(skill):
    out = skill.execute({"action": "mint_card"})
    assert out["status"] == "error"

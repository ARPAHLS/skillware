"""Offline tests for defi/token_security_scanner."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest
import requests
import yaml

from skillware.core.loader import SkillLoader

from .skill import TokenSecurityScannerSkill

_DIR = os.path.dirname(os.path.abspath(__file__))
_FIXTURES = os.path.join(_DIR, "fixtures")


def _load_fixture(name: str) -> dict:
    with open(os.path.join(_FIXTURES, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture
def skill(monkeypatch):
    monkeypatch.setattr(
        TokenSecurityScannerSkill,
        "_operator_policy_file",
        lambda self: None,
    )
    monkeypatch.setattr(TokenSecurityScannerSkill, "_backoff", lambda self: None)
    return TokenSecurityScannerSkill()


@pytest.fixture
def manifest():
    path = os.path.join(_DIR, "manifest.yaml")
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_manifest_consistency(skill, manifest):
    assert skill.manifest["name"] == manifest["name"] == "defi/token_security_scanner"
    assert skill.manifest["version"] == manifest["version"] == "0.2.0"
    assert set(manifest["parameters"]["properties"]["action"]["enum"]) == {
        "scan",
        "scan_batch",
        "supported_chains",
    }
    assert "GOPLUS_APP_KEY" in manifest["env_vars"]


def test_skill_loader_can_import():
    bundle = SkillLoader.load_skill("defi/token_security_scanner")
    assert bundle["manifest"]["name"] == "defi/token_security_scanner"
    assert hasattr(bundle["module"], "TokenSecurityScannerSkill")
    instance = bundle["class"]()
    result = instance.execute({"action": "supported_chains"})
    assert result["status"] == "ok"
    assert any(row["slug"] == "base" for row in result["chains"])


def test_supported_chains(skill):
    result = skill.execute({"action": "supported_chains"})
    assert result["status"] == "ok"
    slugs = {row["slug"] for row in result["chains"]}
    assert "ethereum" in slugs
    assert "base" in slugs
    base = next(row for row in result["chains"] if row["slug"] == "base")
    assert base["chain_id"] == "8453"
    assert base["goplus_supported"] is True


def test_missing_and_invalid_action(skill):
    missing = skill.execute({})
    assert missing["status"] == "error"
    assert missing["error_code"] == "missing_action"

    invalid = skill.execute({"action": "audit_pdf"})
    assert invalid["status"] == "error"
    assert invalid["error_code"] == "invalid_action"


def test_scan_validation_errors(skill):
    assert (
        skill.execute({"action": "scan", "contract": "0x" + "a" * 40})["error_code"]
        == "missing_chain"
    )
    assert (
        skill.execute(
            {"action": "scan", "chain": "base", "contract": "not-an-address"}
        )["error_code"]
        == "invalid_contract"
    )
    assert (
        skill.execute(
            {
                "action": "scan",
                "chain": "solana",
                "contract": "0x4ed4e862860bed51a9570b96d89af5e1b0efefed",
            }
        )["error_code"]
        == "unsupported_chain"
    )


@patch("skills.defi.token_security_scanner.skill.requests.Session.get")
def test_scan_clean_token(mock_get, skill):
    fixture = _load_fixture("goplus_clean_base.json")
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = fixture
    mock_get.return_value = response

    contract = "0x4ed4e862860bed51a9570b96d89af5e1b0efefed"
    result = skill.execute({"action": "scan", "chain": "base", "contract": contract})

    assert result["status"] == "ok"
    assert result["chain"] == "base"
    assert result["contract"] == contract.lower()
    assert result["risk_tier"] == "low"
    assert result["signals"]["is_honeypot"] is False
    assert result["signals"]["owner_renounced"] is True
    assert result["signals"]["buy_tax_pct"] == 0.0
    assert result["signals"]["sell_tax_pct"] == 0.0
    assert result["token"]["symbol"] == "DEGEN"
    assert result["sources"][0]["provider"] == "goplus"
    assert result["contract_errors"] == []
    assert result["policy_action"] == "allow"
    assert result["policy_profile"] == "enterprise_default"
    assert result["report_schema_version"] == "0.2"
    assert result["report_id"].startswith("tsr_")
    assert "API coverage varies by chain" in result["warnings"]

    mock_get.assert_called_once()
    args, kwargs = mock_get.call_args
    assert args[0].endswith("/8453")
    assert kwargs["params"]["contract_addresses"] == contract.lower()


@patch("skills.defi.token_security_scanner.skill.requests.Session.get")
def test_scan_honeypot_critical(mock_get, skill):
    fixture = _load_fixture("goplus_honeypot.json")
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = fixture
    mock_get.return_value = response

    result = skill.execute(
        {
            "action": "scan",
            "chain": "ethereum",
            "contract": "0xDeadBeefDeadBeefDeadBeefDeadBeefDeadBeef",
        }
    )
    assert result["status"] == "ok"
    assert result["risk_tier"] == "critical"
    assert result["signals"]["is_honeypot"] is True
    assert "is_honeypot" in result["contract_errors"]
    assert result["signals"]["buy_tax_pct"] == 12.0
    assert result["signals"]["sell_tax_pct"] == 25.0
    assert result["policy_action"] == "block"


@patch("skills.defi.token_security_scanner.skill.requests.Session.get")
def test_scan_medium_proxy_mint(mock_get, skill):
    fixture = _load_fixture("goplus_medium.json")
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = fixture
    mock_get.return_value = response

    result = skill.execute(
        {
            "action": "scan",
            "chain": "ethereum",
            "contract": "0xcafebabecafebabecafebabecafebabecafebabe",
        }
    )
    assert result["status"] == "ok"
    assert result["risk_tier"] == "medium"
    assert result["policy_action"] == "flag"
    assert result["signals"]["is_proxy"] is True
    assert result["signals"]["can_mint"] is True
    assert "is_proxy" in result["contract_errors"]
    assert any("Proxy contract" in w for w in result["warnings"])


@patch("skills.defi.token_security_scanner.skill.requests.Session.get")
def test_rate_limited(mock_get, skill):
    response = MagicMock()
    response.status_code = 429
    response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        response=response
    )
    mock_get.return_value = response

    result = skill.execute(
        {
            "action": "scan",
            "chain": "base",
            "contract": "0x4ed4e862860bed51a9570b96d89af5e1b0efefed",
        }
    )
    assert result["status"] == "error"
    assert result["error_code"] == "rate_limited"


@patch("skills.defi.token_security_scanner.skill.requests.Session.get")
def test_goplus_app_key_sent_as_bearer(mock_get, skill):
    fixture = _load_fixture("goplus_clean_base.json")
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = fixture
    mock_get.return_value = response

    keyed = TokenSecurityScannerSkill(config={"GOPLUS_APP_KEY": "test-token"})
    keyed.execute(
        {
            "action": "scan",
            "chain": "base",
            "contract": "0x4ed4e862860bed51a9570b96d89af5e1b0efefed",
        }
    )
    headers = mock_get.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer test-token"


@patch("skills.defi.token_security_scanner.skill.requests.Session.get")
def test_scan_closed_source_unknown_honeypot_high(mock_get, skill):
    fixture = _load_fixture("goplus_closed_source_unknown.json")
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = fixture
    mock_get.return_value = response

    result = skill.execute(
        {
            "action": "scan",
            "chain": "base",
            "contract": "0x1111111111111111111111111111111111111111",
        }
    )
    assert result["status"] == "ok"
    assert result["risk_tier"] == "high"
    assert "closed_source_unknown_honeypot" in result["contract_errors"]
    assert result["signals"]["is_honeypot"] is None


@patch("skills.defi.token_security_scanner.skill.requests.Session.get")
def test_scan_empty_goplus_result_unknown(mock_get, skill):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"code": 1, "message": "OK", "result": {}}
    mock_get.return_value = response

    result = skill.execute(
        {
            "action": "scan",
            "chain": "base",
            "contract": "0x4ed4e862860bed51a9570b96d89af5e1b0efefed",
        }
    )
    assert result["status"] == "ok"
    assert result["risk_tier"] == "unknown"
    assert "goplus_empty_result" in result["contract_errors"]


def test_as_bool_and_pct_helpers():
    assert TokenSecurityScannerSkill._as_bool("1") is True
    assert TokenSecurityScannerSkill._as_bool("0") is False
    assert TokenSecurityScannerSkill._as_bool(None) is None
    # Avoid Hermes-style bool("0") == True bug
    assert TokenSecurityScannerSkill._as_bool("0") is not True
    assert TokenSecurityScannerSkill._as_pct("0.05") == 5.0
    assert TokenSecurityScannerSkill._as_pct("5") == 5.0
    assert TokenSecurityScannerSkill._as_pct(None) is None


def _goplus_body(contract: str, **fields) -> dict:
    row = {
        "token_name": "Fixture",
        "token_symbol": "FIX",
        "decimals": "18",
        "owner_address": "0x0000000000000000000000000000000000000000",
        "is_open_source": "1",
        "is_proxy": "0",
        "is_mintable": "0",
        "is_honeypot": "0",
        "buy_tax": "0",
        "sell_tax": "0",
        "tax_modifiable": "0",
        "cannot_sell_all": "0",
        "owner_change_balance": "0",
        "hidden_owner": "0",
        "external_call": "0",
        "transfer_pausable": "0",
        "trading_cooldown": "0",
        "is_blacklisted": "0",
        "holder_count": "1000",
    }
    row.update(fields)
    return {"code": 1, "message": "OK", "result": {contract.lower(): row}}


def _mock_response(payload, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=response
        )
    return response


def test_supported_chains_marks_non_goplus_chain(skill, monkeypatch):
    from skills.defi.token_security_scanner import skill as skill_mod

    original = skill_mod.list_configured_chains

    def fake_chains(enabled_only=True):
        rows = list(original(enabled_only=enabled_only))
        rows.append(("custom_l2", {"chain_id": 999999, "label": "Custom"}))
        return rows

    monkeypatch.setattr(skill_mod, "list_configured_chains", fake_chains)
    result = skill.execute({"action": "supported_chains"})
    custom = next(row for row in result["chains"] if row["slug"] == "custom_l2")
    assert custom["goplus_supported"] is False


def test_scan_rejects_chain_outside_goplus_map(skill):
    result = skill.execute(
        {
            "action": "scan",
            "chain": "sepolia",
            "contract": "0x4ed4e862860bed51a9570b96d89af5e1b0efefed",
        }
    )
    assert result["error_code"] == "goplus_unsupported_chain"


@patch("skills.defi.token_security_scanner.skill.requests.Session.get")
def test_scan_token_slug_resolves_degen(mock_get, skill):
    contract = "0x4ed4e862860bed51a9570b96d89af5e1b0efefed"
    mock_get.return_value = _mock_response(_load_fixture("goplus_clean_base.json"))
    result = skill.execute({"action": "scan", "chain": "base", "token": "degen"})
    assert result["status"] == "ok"
    assert result["contract"] == contract
    assert result["token_slug"] == "degen"
    assert result["policy_action"] == "allow"
    assert mock_get.call_args.kwargs["params"]["contract_addresses"] == contract


def test_unknown_token_fails_closed(skill):
    result = skill.execute({"action": "scan", "chain": "base", "token": "not-a-token"})
    assert result["status"] == "error"
    assert result["error_code"] == "unknown_token"


@patch("skills.defi.token_security_scanner.skill.requests.Session.get")
def test_operator_policy_lowers_tax_threshold(mock_get, skill, tmp_path):
    contract = "0x2222222222222222222222222222222222222222"
    mock_get.return_value = _mock_response(
        _goplus_body(contract, buy_tax="0.06", sell_tax="0")
    )
    default = skill.execute({"action": "scan", "chain": "base", "contract": contract})
    assert default["risk_tier"] == "medium"
    assert default["policy_action"] == "flag"

    policy = tmp_path / "token_scan_policy.yaml"
    policy.write_text(
        "profile: desk\nhigh_tax_pct: 5\nmedium_tax_above_pct: 0\n",
        encoding="utf-8",
    )
    overridden = skill.execute(
        {
            "action": "scan",
            "chain": "base",
            "contract": contract,
            "policy_path": str(policy),
        }
    )
    assert overridden["risk_tier"] == "high"
    assert overridden["policy_action"] == "block"
    assert overridden["policy_profile"] == "desk"
    assert "buy_tax_high" in overridden["contract_errors"]


@patch("skills.defi.token_security_scanner.skill.requests.Session.get")
def test_min_holder_count_flags_thin_token(mock_get, skill, tmp_path):
    contract = "0x3333333333333333333333333333333333333333"
    mock_get.return_value = _mock_response(_goplus_body(contract, holder_count="12"))
    policy = tmp_path / "holders.yaml"
    policy.write_text("profile: desk\nmin_holder_count: 50\n", encoding="utf-8")
    result = skill.execute(
        {
            "action": "scan",
            "chain": "ethereum",
            "contract": contract,
            "policy_path": str(policy),
        }
    )
    assert result["risk_tier"] == "medium"
    assert "low_liquidity_holders" in result["contract_errors"]
    assert result["policy_action"] == "flag"


@patch("skills.defi.token_security_scanner.skill.requests.Session.get")
def test_richer_goplus_signals(mock_get, skill):
    contract = "0x4444444444444444444444444444444444444444"
    mock_get.return_value = _mock_response(
        _goplus_body(
            contract,
            creator_percent="0.02",
            owner_percent="0",
            is_in_dex="1",
            lp_total_supply="1000",
            holders=[{"percent": "0.4"}],
            dex=[{"name": "uniswap"}, {"name": "sushi"}],
        )
    )
    result = skill.execute(
        {"action": "scan", "chain": "ethereum", "contract": contract}
    )
    signals = result["signals"]
    assert signals["top_holder_pct"] == 40.0
    assert signals["creator_percent"] == 2.0
    assert signals["is_in_dex"] is True
    assert signals["dex_count"] == 2
    assert signals["lp_total_supply"] == "1000"
    assert result["risk_tier"] == "low"


@patch("skills.defi.token_security_scanner.skill.requests.Session.get")
def test_scan_batch_worst_tier(mock_get, skill):
    clean = "0x4ed4e862860bed51a9570b96d89af5e1b0efefed"
    honey = "0xdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    medium = "0xcafebabecafebabecafebabecafebabecafebabe"
    mock_get.side_effect = [
        _mock_response(_load_fixture("goplus_clean_base.json")),
        _mock_response(_load_fixture("goplus_honeypot.json")),
        _mock_response(_load_fixture("goplus_medium.json")),
    ]
    result = skill.execute(
        {
            "action": "scan_batch",
            "items": [
                {"chain": "base", "contract": clean},
                {"chain": "ethereum", "contract": honey},
                {"chain": "ethereum", "contract": medium},
            ],
        }
    )
    assert result["status"] == "ok"
    assert len(result["reports"]) == 3
    assert [row["policy_action"] for row in result["reports"]] == [
        "allow",
        "block",
        "flag",
    ]
    assert result["worst_risk_tier"] == "critical"
    assert mock_get.call_count == 3


def test_scan_batch_rejects_more_than_five(skill):
    items = [
        {
            "chain": "base",
            "contract": "0x4ed4e862860bed51a9570b96d89af5e1b0efefed",
        }
        for _ in range(6)
    ]
    result = skill.execute({"action": "scan_batch", "items": items})
    assert result["error_code"] == "batch_too_large"


@patch("skills.defi.token_security_scanner.skill.requests.Session.get")
def test_retries_once_on_429_then_succeeds(mock_get, skill):
    contract = "0x4ed4e862860bed51a9570b96d89af5e1b0efefed"
    mock_get.side_effect = [
        _mock_response({}, status_code=429),
        _mock_response(_load_fixture("goplus_clean_base.json")),
    ]
    result = skill.execute({"action": "scan", "chain": "base", "contract": contract})
    assert result["status"] == "ok"
    assert result["policy_action"] == "allow"
    assert mock_get.call_count == 2


@patch("skills.defi.token_security_scanner.skill.requests.Session.get")
def test_persistent_429_still_fails_closed(mock_get, skill):
    mock_get.return_value = _mock_response({}, status_code=429)
    result = skill.execute(
        {
            "action": "scan",
            "chain": "base",
            "contract": "0x4ed4e862860bed51a9570b96d89af5e1b0efefed",
        }
    )
    assert result["error_code"] == "rate_limited"
    assert mock_get.call_count == 2

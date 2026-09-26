"""Offline tests for defi/token_security_scanner."""

from __future__ import annotations

import json
import os
from unittest.mock import MagicMock, patch

import pytest
import yaml

from skillware.core.loader import SkillLoader

from .skill import TokenSecurityScannerSkill

_DIR = os.path.dirname(os.path.abspath(__file__))
_FIXTURES = os.path.join(_DIR, "fixtures")


def _load_fixture(name: str) -> dict:
    with open(os.path.join(_FIXTURES, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture
def skill():
    return TokenSecurityScannerSkill()


@pytest.fixture
def manifest():
    path = os.path.join(_DIR, "manifest.yaml")
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def test_manifest_consistency(skill, manifest):
    assert skill.manifest["name"] == manifest["name"] == "defi/token_security_scanner"
    assert skill.manifest["version"] == manifest["version"] == "0.1.0"
    assert set(manifest["parameters"]["properties"]["action"]["enum"]) == {
        "scan",
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
    assert result["signals"]["is_proxy"] is True
    assert result["signals"]["can_mint"] is True
    assert "is_proxy" in result["contract_errors"]
    assert any("Proxy contract" in w for w in result["warnings"])


@patch("skills.defi.token_security_scanner.skill.requests.Session.get")
def test_rate_limited(mock_get, skill):
    response = MagicMock()
    response.status_code = 429
    response.raise_for_status.side_effect = __import__("requests").exceptions.HTTPError(
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

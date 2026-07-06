import os
from unittest.mock import MagicMock, patch

import pytest
import yaml

from .skill import WalletScreeningSkill


@pytest.fixture
def skill():
    return WalletScreeningSkill()


@pytest.fixture
def manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_skill_manifest_consistency(skill, manifest):
    skill_manifest = skill.manifest
    assert skill_manifest["name"] == manifest["name"]
    assert skill_manifest["version"] == manifest["version"]


def test_invalid_address(skill):
    result = skill.execute({"address": "invalid_addr"})
    assert "error" in result
    assert "Invalid Ethereum address" in result["error"]


def test_missing_api_key(skill):
    skill.etherscan_api_key = None
    result = skill.execute({"address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"})
    assert "error" in result
    assert "Missing ETHERSCAN_API_KEY" in result["error"]


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_execute_success(mock_get, skill):
    skill.etherscan_api_key = "dummy_key"

    mock_eth_balance = MagicMock()
    mock_eth_balance.json.return_value = {
        "status": "1",
        "result": "1000000000000000000",
    }

    mock_txs = MagicMock()
    mock_txs.json.return_value = {
        "status": "1",
        "result": [
            {
                "from": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045".lower(),
                "to": "0x123",
                "value": "500000000000000000",
                "isError": "0",
                "gasUsed": "21000",
                "gasPrice": "1000000000",
            }
        ],
    }

    mock_price = MagicMock()
    mock_price.json.return_value = {"ethereum": {"usd": 2000.0, "eur": 1800.0}}

    def get_side_effect(url, **kwargs):
        params = kwargs.get("params") or {}
        if params.get("action") == "balance":
            return mock_eth_balance
        if params.get("action") == "txlist":
            return mock_txs
        return mock_price

    mock_get.side_effect = get_side_effect

    result = skill.execute({"address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"})

    assert "error" not in result
    assert "summary" in result
    assert result["summary"]["balance_eth"] == 1.0
    assert result["summary"]["balance_usd"] == 2000.0


def _sample_tx(index: int = 0) -> dict:
    return {
        "from": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045".lower(),
        "to": "0x123",
        "value": "500000000000000000",
        "isError": "0",
        "gasUsed": "21000",
        "gasPrice": "1000000000",
        "hash": f"0x{'a' * 62}{index:02x}",
    }


def _mock_price_and_balance_side_effect():
    mock_eth_balance = MagicMock()
    mock_eth_balance.json.return_value = {
        "status": "1",
        "result": "1000000000000000000",
    }
    mock_price = MagicMock()
    mock_price.json.return_value = {"ethereum": {"usd": 2000.0, "eur": 1800.0}}

    def side_effect(url, **kwargs):
        params = kwargs.get("params") or {}
        if params.get("action") == "balance":
            return mock_eth_balance
        return mock_price

    return side_effect


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_txlist_pagination_merges_pages(mock_get, skill, monkeypatch):
    skill.etherscan_api_key = "dummy_key"
    monkeypatch.setattr(skill, "ETHERSCAN_TX_PAGE_OFFSET", 2)
    monkeypatch.setattr(skill, "ETHERSCAN_TX_MAX_PAGES", 5)

    get_side_effect = _mock_price_and_balance_side_effect()

    def tx_side_effect(url, **kwargs):
        params = kwargs.get("params") or {}
        if params.get("action") == "txlist":
            page = int(params.get("page", 1))
            if page == 1:
                return MagicMock(
                    json=lambda: {
                        "status": "1",
                        "result": [_sample_tx(1), _sample_tx(2)],
                    }
                )
            if page == 2:
                return MagicMock(
                    json=lambda: {"status": "1", "result": [_sample_tx(3)]}
                )
            raise AssertionError(f"unexpected page {page}")
        return get_side_effect(url, **kwargs)

    mock_get.side_effect = tx_side_effect

    result = skill.execute({"address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"})

    assert "error" not in result
    assert result["summary"]["total_transactions"] == 3
    assert "warnings" not in result["metadata"]


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_txlist_truncation_warning(mock_get, skill, monkeypatch):
    skill.etherscan_api_key = "dummy_key"
    monkeypatch.setattr(skill, "ETHERSCAN_TX_PAGE_OFFSET", 1)
    monkeypatch.setattr(skill, "ETHERSCAN_TX_MAX_PAGES", 2)

    get_side_effect = _mock_price_and_balance_side_effect()

    def tx_side_effect(url, **kwargs):
        params = kwargs.get("params") or {}
        if params.get("action") == "txlist":
            return MagicMock(json=lambda: {"status": "1", "result": [_sample_tx()]})
        return get_side_effect(url, **kwargs)

    mock_get.side_effect = tx_side_effect

    result = skill.execute({"address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"})

    assert result["metadata"]["warnings"] == ["etherscan_txlist_truncated"]
    assert result["summary"]["total_transactions"] == 2


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_txlist_unavailable_warning(mock_get, skill):
    skill.etherscan_api_key = "dummy_key"

    get_side_effect = _mock_price_and_balance_side_effect()

    def tx_side_effect(url, **kwargs):
        params = kwargs.get("params") or {}
        if params.get("action") == "txlist":
            return MagicMock(
                json=lambda: {"status": "0", "message": "NOTOK", "result": []}
            )
        return get_side_effect(url, **kwargs)

    mock_get.side_effect = tx_side_effect

    result = skill.execute({"address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"})

    assert result["metadata"]["warnings"] == ["etherscan_txlist_unavailable"]
    assert result["summary"]["total_transactions"] == 0


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_txlist_no_transactions_no_warning(mock_get, skill):
    skill.etherscan_api_key = "dummy_key"

    get_side_effect = _mock_price_and_balance_side_effect()

    def tx_side_effect(url, **kwargs):
        params = kwargs.get("params") or {}
        if params.get("action") == "txlist":
            return MagicMock(
                json=lambda: {
                    "status": "0",
                    "message": "No transactions found",
                    "result": [],
                }
            )
        return get_side_effect(url, **kwargs)

    mock_get.side_effect = tx_side_effect

    result = skill.execute({"address": "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"})

    assert "warnings" not in result["metadata"]
    assert result["summary"]["total_transactions"] == 0

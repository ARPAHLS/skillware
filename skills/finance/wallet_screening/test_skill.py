import os
from unittest.mock import MagicMock, patch

import pytest
import yaml

from .skill import WalletScreeningSkill

WALLET = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
WALLET_L = WALLET.lower()
TORNADO = "0x910cbd523d972eb0a6f4cae4618ad62622b39dbf"
USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"


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
    assert skill_manifest["version"] == manifest["version"] == "1.1.0"


def test_invalid_address(skill):
    result = skill.execute({"address": "invalid_addr"})
    assert "error" in result
    assert "Invalid Ethereum address" in result["error"]


def test_missing_api_key(skill):
    skill.etherscan_api_key = None
    result = skill.execute({"address": WALLET})
    assert "error" in result
    assert "Missing ETHERSCAN_API_KEY" in result["error"]


def test_major_tokens_come_from_evm_config(skill):
    assert "usdt" in skill._major_tokens
    assert "usdc" in skill._major_tokens
    assert "dai" in skill._major_tokens
    assert "weth" in skill._major_tokens
    assert skill._major_tokens["usdt"]["address"] == USDT


def _sample_tx(index: int = 0) -> dict:
    return {
        "from": WALLET_L,
        "to": "0x1234567890123456789012345678901234567890",
        "value": "500000000000000000",
        "isError": "0",
        "gasUsed": "21000",
        "gasPrice": "1000000000",
        "hash": f"0x{'a' * 62}{index:02x}",
    }


def _empty_list_response():
    return MagicMock(json=lambda: {"status": "1", "result": []})


def _no_tx_response():
    return MagicMock(
        json=lambda: {
            "status": "0",
            "message": "No transactions found",
            "result": [],
        }
    )


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
        action = params.get("action")
        if action == "balance":
            return mock_eth_balance
        if action in {"txlist", "tokentx", "txlistinternal"}:
            return _empty_list_response()
        return mock_price

    return side_effect


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_execute_success(mock_get, skill):
    skill.etherscan_api_key = "placeholder_key"

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
                "from": WALLET_L,
                "to": "0x1234567890123456789012345678901234567890",
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
        action = params.get("action")
        if action == "balance":
            return mock_eth_balance
        if action == "txlist":
            return mock_txs
        if action in {"tokentx", "txlistinternal"}:
            return _empty_list_response()
        return mock_price

    mock_get.side_effect = get_side_effect

    result = skill.execute({"address": WALLET})

    assert "error" not in result
    assert "summary" in result
    assert result["summary"]["balance_eth"] == 1.0
    assert result["summary"]["balance_usd"] == 2000.0
    assert result["summary"]["total_token_txs"] == 0
    assert result["summary"]["total_internal_txs"] == 0


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_txlist_pagination_merges_pages(mock_get, skill, monkeypatch):
    skill.etherscan_api_key = "placeholder_key"
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

    result = skill.execute({"address": WALLET})

    assert "error" not in result
    assert result["summary"]["total_transactions"] == 3
    assert "warnings" not in result["metadata"]


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_txlist_truncation_warning(mock_get, skill, monkeypatch):
    skill.etherscan_api_key = "placeholder_key"
    monkeypatch.setattr(skill, "ETHERSCAN_TX_PAGE_OFFSET", 1)
    monkeypatch.setattr(skill, "ETHERSCAN_TX_MAX_PAGES", 2)

    get_side_effect = _mock_price_and_balance_side_effect()

    def tx_side_effect(url, **kwargs):
        params = kwargs.get("params") or {}
        if params.get("action") == "txlist":
            return MagicMock(json=lambda: {"status": "1", "result": [_sample_tx()]})
        return get_side_effect(url, **kwargs)

    mock_get.side_effect = tx_side_effect

    result = skill.execute({"address": WALLET})

    assert result["metadata"]["warnings"] == ["etherscan_txlist_truncated"]
    assert result["summary"]["total_transactions"] == 2


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_txlist_unavailable_warning(mock_get, skill):
    skill.etherscan_api_key = "placeholder_key"

    get_side_effect = _mock_price_and_balance_side_effect()

    def tx_side_effect(url, **kwargs):
        params = kwargs.get("params") or {}
        if params.get("action") == "txlist":
            return MagicMock(
                json=lambda: {"status": "0", "message": "NOTOK", "result": []}
            )
        return get_side_effect(url, **kwargs)

    mock_get.side_effect = tx_side_effect

    result = skill.execute({"address": WALLET})

    assert result["metadata"]["warnings"] == ["etherscan_txlist_unavailable"]
    assert result["summary"]["total_transactions"] == 0


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_txlist_no_transactions_no_warning(mock_get, skill):
    skill.etherscan_api_key = "placeholder_key"

    get_side_effect = _mock_price_and_balance_side_effect()

    def tx_side_effect(url, **kwargs):
        params = kwargs.get("params") or {}
        action = params.get("action")
        if action == "txlist":
            return _no_tx_response()
        if action in {"tokentx", "txlistinternal"}:
            return _no_tx_response()
        return get_side_effect(url, **kwargs)

    mock_get.side_effect = tx_side_effect

    result = skill.execute({"address": WALLET})

    assert "warnings" not in result["metadata"]
    assert result["summary"]["total_transactions"] == 0


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_tokentx_usdt_to_tornado_is_flagged(mock_get, skill):
    skill.etherscan_api_key = "placeholder_key"
    base = _mock_price_and_balance_side_effect()

    token_row = {
        "from": WALLET_L,
        "to": TORNADO,
        "contractAddress": USDT,
        "tokenSymbol": "USDT",
        "tokenDecimal": "6",
        "value": "2500000000",  # 2500 USDT
        "hash": "0x" + "b" * 64,
    }

    def side_effect(url, **kwargs):
        params = kwargs.get("params") or {}
        action = params.get("action")
        if action == "tokentx":
            return MagicMock(json=lambda: {"status": "1", "result": [token_row]})
        if action in {"txlist", "txlistinternal"}:
            return _empty_list_response()
        return base(url, **kwargs)

    mock_get.side_effect = side_effect
    result = skill.execute({"address": WALLET})

    assert result["summary"]["total_token_txs"] == 1
    assert result["summary"]["risk_flag"] is True
    assert result["summary"]["malicious_interaction_count"] == 1
    hit = result["risk_details"]["malicious_interactions"][0]
    assert hit["transfer_kind"] == "erc20"
    assert hit["other_party"] == TORNADO
    assert hit["token_symbol"] == "USDT"
    assert hit["token_amount"] == 2500.0
    assert result["financial_analysis"]["token_flow"]["usdt_volume"] == 2500.0


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_internal_tx_to_tornado_is_flagged(mock_get, skill):
    skill.etherscan_api_key = "placeholder_key"
    base = _mock_price_and_balance_side_effect()

    internal_row = {
        "from": WALLET_L,
        "to": TORNADO,
        "value": "1000000000000000000",
        "isError": "0",
        "hash": "0x" + "c" * 64,
    }

    def side_effect(url, **kwargs):
        params = kwargs.get("params") or {}
        action = params.get("action")
        if action == "txlistinternal":
            return MagicMock(json=lambda: {"status": "1", "result": [internal_row]})
        if action in {"txlist", "tokentx"}:
            return _empty_list_response()
        return base(url, **kwargs)

    mock_get.side_effect = side_effect
    result = skill.execute({"address": WALLET})

    assert result["summary"]["total_internal_txs"] == 1
    assert result["summary"]["risk_flag"] is True
    hit = result["risk_details"]["malicious_interactions"][0]
    assert hit["transfer_kind"] == "internal"
    assert hit["other_party"] == TORNADO
    assert hit["value_eth"] == 1.0


@patch("skills.finance.wallet_screening.skill.requests.get")
def test_tokentx_truncation_warning(mock_get, skill, monkeypatch):
    skill.etherscan_api_key = "placeholder_key"
    monkeypatch.setattr(skill, "ETHERSCAN_TX_PAGE_OFFSET", 1)
    monkeypatch.setattr(skill, "ETHERSCAN_TX_MAX_PAGES", 2)
    base = _mock_price_and_balance_side_effect()

    def side_effect(url, **kwargs):
        params = kwargs.get("params") or {}
        action = params.get("action")
        if action == "tokentx":
            return MagicMock(
                json=lambda: {
                    "status": "1",
                    "result": [
                        {
                            "from": WALLET_L,
                            "to": "0x1234567890123456789012345678901234567890",
                            "contractAddress": USDT,
                            "tokenSymbol": "USDT",
                            "tokenDecimal": "6",
                            "value": "1000000",
                            "hash": "0x" + "d" * 64,
                        }
                    ],
                }
            )
        if action in {"txlist", "txlistinternal"}:
            return _empty_list_response()
        return base(url, **kwargs)

    mock_get.side_effect = side_effect
    result = skill.execute({"address": WALLET})
    assert "etherscan_tokentx_truncated" in result["metadata"]["warnings"]
    assert result["summary"]["total_token_txs"] == 2

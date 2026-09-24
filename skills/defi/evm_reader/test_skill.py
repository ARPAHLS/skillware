"""Tests for defi/evm_reader — all RPC calls are mocked."""

import os
import sys
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import yaml

from skillware.core.loader import SkillLoader

_SKILL_DIR = os.path.dirname(__file__)
if _SKILL_DIR not in sys.path:
    sys.path.insert(0, _SKILL_DIR)

from .skill import EvmReaderSkill  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USDC_ADDRESS = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
HOLDER_ADDRESS = "0x742d35Cc6634C0532925a3b844Bc9e7595f0aBe0"
SPENDER_ADDRESS = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
NFT_ADDRESS = "0xBC4CA0EdA7647A8aB7C2061c2E118A18a936f13D"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_web3_erc20(
    *,
    name="USD Coin",
    symbol="USDC",
    decimals=6,
    total_supply=1_000_000_000_000_000,
    balance=1_500_000_000,
    allowance=500_000_000,
):
    """Create a mock Web3 instance with ERC-20 contract methods."""
    w3 = MagicMock()

    contract = MagicMock()
    contract.functions.name.return_value.call.return_value = name
    contract.functions.symbol.return_value.call.return_value = symbol
    contract.functions.decimals.return_value.call.return_value = decimals
    contract.functions.totalSupply.return_value.call.return_value = total_supply

    def _balance_of(addr):
        fn = MagicMock()
        fn.call.return_value = balance
        return fn

    def _allowance_fn(owner, spender):
        fn = MagicMock()
        fn.call.return_value = allowance
        return fn

    contract.functions.balanceOf.side_effect = _balance_of
    contract.functions.allowance.side_effect = _allowance_fn

    w3.eth.contract.return_value = contract
    return w3


def _mock_web3_erc721(
    *,
    name="BoredApeYachtClub",
    symbol="BAYC",
    total_supply=10000,
    balance=3,
    owner="0x742d35Cc6634C0532925a3b844Bc9e7595f0aBe0",
):
    """Create a mock Web3 instance with ERC-721 contract methods."""
    w3 = MagicMock()

    contract = MagicMock()
    contract.functions.name.return_value.call.return_value = name
    contract.functions.symbol.return_value.call.return_value = symbol
    contract.functions.totalSupply.return_value.call.return_value = total_supply

    def _balance_of(addr):
        fn = MagicMock()
        fn.call.return_value = balance
        return fn

    def _owner_of(token_id):
        fn = MagicMock()
        fn.call.return_value = owner
        return fn

    contract.functions.balanceOf.side_effect = _balance_of
    contract.functions.ownerOf.side_effect = _owner_of

    w3.eth.contract.return_value = contract
    return w3


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def skill(monkeypatch):
    monkeypatch.setenv("ETHEREUM_RPC_URL", "http://localhost:8545")
    monkeypatch.setenv("BASE_RPC_URL", "http://localhost:8546")
    return EvmReaderSkill()


@pytest.fixture
def manifest():
    path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Manifest & loader tests
# ---------------------------------------------------------------------------


def test_manifest_consistency(skill, manifest):
    assert skill.manifest["name"] == manifest["name"]
    assert manifest["name"] == "defi/evm_reader"
    assert manifest["version"] == "0.1.0"


def test_manifest_has_required_fields(manifest):
    assert "constitution" in manifest
    assert "env_vars" in manifest
    assert "parameters" in manifest
    actions = manifest["parameters"]["properties"]["action"]["enum"]
    assert "erc20_metadata" in actions
    assert "multicall" in actions


def test_loader_discovers_skill(monkeypatch):
    monkeypatch.setenv("ETHEREUM_RPC_URL", "http://localhost:8545")
    bundle = SkillLoader.load_skill("defi/evm_reader")
    assert bundle["manifest"]["name"] == "defi/evm_reader"
    cls = bundle["module"].EvmReaderSkill
    assert cls is not None


# ---------------------------------------------------------------------------
# Unknown / missing action
# ---------------------------------------------------------------------------


def test_unknown_action(skill):
    result = skill.execute({"action": "sign_tx", "chain": "ethereum"})
    assert result["status"] == "error"
    assert "Unknown action" in result["error"]


def test_missing_action(skill):
    result = skill.execute({})
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# ERC-20 tests
# ---------------------------------------------------------------------------


@patch("skills.defi.evm_reader.skill.get_web3")
def test_erc20_metadata(mock_get_web3, skill):
    mock_get_web3.return_value = _mock_web3_erc20()
    result = skill.execute(
        {"action": "erc20_metadata", "chain": "ethereum", "token": USDC_ADDRESS}
    )
    assert result["status"] == "ok"
    assert result["name"] == "USD Coin"
    assert result["symbol"] == "USDC"
    assert result["decimals"] == 6
    assert result["total_supply_raw"] == "1000000000000000"
    assert "." in result["total_supply"]


@patch("skills.defi.evm_reader.skill.get_web3")
def test_erc20_balance(mock_get_web3, skill):
    mock_get_web3.return_value = _mock_web3_erc20(balance=1_500_000_000)
    result = skill.execute(
        {
            "action": "erc20_balance",
            "chain": "ethereum",
            "token": USDC_ADDRESS,
            "holder": HOLDER_ADDRESS,
        }
    )
    assert result["status"] == "ok"
    assert result["balance_raw"] == "1500000000"
    assert result["balance"] == "1500.000000"
    assert result["decimals"] == 6


@patch("skills.defi.evm_reader.skill.get_web3")
def test_erc20_balance_missing_holder(mock_get_web3, skill):
    mock_get_web3.return_value = _mock_web3_erc20()
    result = skill.execute(
        {"action": "erc20_balance", "chain": "ethereum", "token": USDC_ADDRESS}
    )
    assert result["status"] == "error"
    assert "holder" in result["error"].lower()


@patch("skills.defi.evm_reader.skill.get_web3")
def test_erc20_allowance(mock_get_web3, skill):
    mock_get_web3.return_value = _mock_web3_erc20(allowance=500_000_000)
    result = skill.execute(
        {
            "action": "erc20_allowance",
            "chain": "ethereum",
            "token": USDC_ADDRESS,
            "holder": HOLDER_ADDRESS,
            "spender": SPENDER_ADDRESS,
        }
    )
    assert result["status"] == "ok"
    assert result["allowance_raw"] == "500000000"
    assert result["allowance"] == "500.000000"


# ---------------------------------------------------------------------------
# ERC-721 tests
# ---------------------------------------------------------------------------


@patch("skills.defi.evm_reader.skill.get_web3")
def test_erc721_metadata(mock_get_web3, skill):
    mock_get_web3.return_value = _mock_web3_erc721()
    result = skill.execute(
        {"action": "erc721_metadata", "chain": "ethereum", "token": NFT_ADDRESS}
    )
    assert result["status"] == "ok"
    assert result["name"] == "BoredApeYachtClub"
    assert result["symbol"] == "BAYC"
    assert result["total_supply"] == 10000


@patch("skills.defi.evm_reader.skill.get_web3")
def test_erc721_balance(mock_get_web3, skill):
    mock_get_web3.return_value = _mock_web3_erc721(balance=3)
    result = skill.execute(
        {
            "action": "erc721_balance",
            "chain": "ethereum",
            "token": NFT_ADDRESS,
            "holder": HOLDER_ADDRESS,
        }
    )
    assert result["status"] == "ok"
    assert result["balance"] == 3


@patch("skills.defi.evm_reader.skill.get_web3")
def test_erc721_owner_of(mock_get_web3, skill):
    mock_get_web3.return_value = _mock_web3_erc721(
        owner="0x742d35Cc6634C0532925a3b844Bc9e7595f0aBe0"
    )
    result = skill.execute(
        {
            "action": "erc721_owner_of",
            "chain": "ethereum",
            "token": NFT_ADDRESS,
            "token_id": 1234,
        }
    )
    assert result["status"] == "ok"
    assert result["token_id"] == 1234
    assert result["owner"].startswith("0x")


def test_erc721_owner_of_missing_token_id(skill):
    result = skill.execute(
        {"action": "erc721_owner_of", "chain": "ethereum", "token": NFT_ADDRESS}
    )
    assert result["status"] == "error"
    assert "token_id" in result["error"]


# ---------------------------------------------------------------------------
# call_view tests
# ---------------------------------------------------------------------------


@patch("skills.defi.evm_reader.skill.get_web3")
def test_call_view_erc20_decimals(mock_get_web3, skill):
    w3 = MagicMock()
    contract = MagicMock()
    contract.functions.decimals.return_value.call.return_value = 6
    w3.eth.contract.return_value = contract
    mock_get_web3.return_value = w3

    result = skill.execute(
        {
            "action": "call_view",
            "chain": "ethereum",
            "target": USDC_ADDRESS,
            "abi_name": "erc20",
            "function": "decimals",
            "args": [],
        }
    )
    assert result["status"] == "ok"
    assert result["result"] == 6


def test_call_view_unknown_abi(skill):
    result = skill.execute(
        {
            "action": "call_view",
            "chain": "ethereum",
            "target": USDC_ADDRESS,
            "abi_name": "custom_exploit",
            "function": "steal",
            "args": [],
        }
    )
    assert result["status"] == "error"
    assert "Allowlisted" in result["error"]


@patch("skills.defi.evm_reader.skill.get_web3")
def test_call_view_non_view_function_rejected(mock_get_web3, skill):
    """Calling a non-view function (e.g. approve) should fail even if
    it appears in the erc20 ABI — the skill only permits view/pure."""
    mock_get_web3.return_value = MagicMock()
    result = skill.execute(
        {
            "action": "call_view",
            "chain": "ethereum",
            "target": USDC_ADDRESS,
            "abi_name": "erc20",
            "function": "approve",  # not view
            "args": [SPENDER_ADDRESS, 100],
        }
    )
    # The evm_reader ABIs only contain view functions, so approve is not found.
    assert result["status"] == "error"
    assert "not found" in result["error"] or "not view" in result["error"]


# ---------------------------------------------------------------------------
# Address validation
# ---------------------------------------------------------------------------


def test_invalid_address_rejected(skill):
    result = skill.execute(
        {"action": "erc20_metadata", "chain": "ethereum", "token": "0xINVALID"}
    )
    assert result["status"] == "error"
    assert "address" in result["error"].lower() or "hex" in result["error"].lower()


def test_short_address_rejected(skill):
    result = skill.execute(
        {"action": "erc20_metadata", "chain": "ethereum", "token": "0x1234"}
    )
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Multicall tests
# ---------------------------------------------------------------------------


def test_multicall_batch_size_cap(skill):
    # 51 calls should exceed the cap of 50.
    calls = [
        {
            "target": USDC_ADDRESS,
            "abi_name": "erc20",
            "function": "decimals",
            "args": [],
        }
    ] * 51
    result = skill.execute({"action": "multicall", "chain": "ethereum", "calls": calls})
    assert result["status"] == "error"
    assert "50" in result["error"]


def test_multicall_empty_calls(skill):
    result = skill.execute({"action": "multicall", "chain": "ethereum", "calls": []})
    assert result["status"] == "error"


def test_multicall_invalid_calls_type(skill):
    result = skill.execute(
        {"action": "multicall", "chain": "ethereum", "calls": "not_a_list"}
    )
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# Balance formatting
# ---------------------------------------------------------------------------


def test_format_balance_six_decimals():
    assert EvmReaderSkill._format_balance(1_500_000_000, 6) == "1500.000000"


def test_format_balance_eighteen_decimals():
    result = EvmReaderSkill._format_balance(10**18, 18)
    assert result == "1.000000000000000000"


def test_format_balance_zero_decimals():
    assert EvmReaderSkill._format_balance(42, 0) == "42"


def test_format_balance_zero_amount():
    assert EvmReaderSkill._format_balance(0, 6) == "0.000000"


# ---------------------------------------------------------------------------
# Normalize result helper
# ---------------------------------------------------------------------------


def test_normalize_result_bytes():
    assert EvmReaderSkill._normalize_result(b"\xde\xad") == "0xdead"


def test_normalize_result_int():
    assert EvmReaderSkill._normalize_result(42) == 42


def test_normalize_result_nested():
    result = EvmReaderSkill._normalize_result([1, b"\xab", [2, 3]])
    assert result == [1, "0xab", [2, 3]]

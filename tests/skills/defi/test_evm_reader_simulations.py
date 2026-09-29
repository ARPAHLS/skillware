"""Simulation and edge-case stress tests for defi/evm_reader."""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from skills.defi.evm_reader.skill import EVMReaderSkill
from skillware.core.evm_config import load_merged_evm_config

ADDRESS_ALICE = "0x1111111111111111111111111111111111111111"
ADDRESS_BOB = "0x2222222222222222222222222222222222222222"
ADDRESS_USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
ADDRESS_MULTICALL = "0xcA11bde05977b3631167028862bE2a173976CA11"


@pytest.fixture
def mock_w3_factory():
    w3 = MagicMock()
    ct = MagicMock()
    w3.eth.contract.return_value = ct
    return lambda _chain: w3, ct


@pytest.fixture
def complex_addressbook(tmp_path: Path) -> Path:
    p = tmp_path / "addressbook.yaml"
    p.write_text(
        """version: 1
contacts:
  treasury_eth:
    display_name: "DAO Treasury"
    public_0x: "0x1111111111111111111111111111111111111111"
    aliases: ["treasury", "safe"]
  treasury_base:
    display_name: "Base Safe"
    public_0x: "0x2222222222222222222222222222222222222222"
    aliases: ["treasury", "base_safe"]
  single_dev:
    display_name: "Core Developer"
    public_0x: "0x3333333333333333333333333333333333333333"
    aliases: ["lead_dev"]
""",
        encoding="utf-8",
    )
    return p


def test_chain_matrix_resolution():
    """Verify all 10 chains in evm_defaults can be resolved."""
    cfg = load_merged_evm_config()
    expected_chains = [
        "ethereum",
        "base",
        "arbitrum",
        "optimism",
        "polygon",
        "bsc",
        "sepolia",
        "megaeth",
        "arc",
        "anvil_local",
    ]
    for c in expected_chains:
        assert c in cfg.chains

    skill = EVMReaderSkill()
    # Active chains should resolve contract or token without unknown-chain error
    addr = skill._resolve_contract_address("megaeth", ADDRESS_ALICE)
    assert addr == ADDRESS_ALICE

    addr_arc = skill._resolve_contract_address("arc", ADDRESS_BOB)
    assert addr_arc == ADDRESS_BOB


def test_address_normalization_stress():
    skill = EVMReaderSkill()

    # Valid lowercase -> checksummed
    raw_lower = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    assert skill._resolve_contract_address("ethereum", raw_lower) == ADDRESS_USDC

    # Valid uppercase -> checksummed
    raw_upper = "0xA0B86991C6218B36C1D19D4A2E9EB0CE3606EB48"
    assert skill._resolve_contract_address("ethereum", raw_upper) == ADDRESS_USDC

    # Valid 40-char hex without 0x prefix -> checksummed
    raw_no_prefix = "a0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
    assert skill._resolve_contract_address("ethereum", raw_no_prefix) == ADDRESS_USDC

    # Invalid lengths
    for bad in ["0x123", "0x" + "a" * 39, "0x" + "a" * 41, "not_an_address", ""]:
        with pytest.raises(ValueError):
            skill._resolve_contract_address("ethereum", bad)


def test_holder_disambiguation_multi_turn(complex_addressbook: Path):
    """Test ambiguous query triggers needs_input, then resolved with specific alias."""
    skill = EVMReaderSkill(addressbook_path=complex_addressbook)

    # 1. Ambiguous query "treasury" matches both treasury_eth and treasury_base
    amb_res = skill.execute("resolve_holder", holder="treasury")
    assert amb_res["status"] == "needs_input"
    assert amb_res["error_code"] == "ambiguous_recipient"
    assert "ambiguous_recipient" in amb_res
    candidates = amb_res["ambiguous_recipient"]["candidates"]
    assert len(candidates) == 2

    # 2. Re-query with specific alias "safe"
    res_safe = skill.execute("resolve_holder", holder="safe")
    assert res_safe["status"] == "ok"
    assert res_safe["holder"] == ADDRESS_ALICE
    assert "treasury_eth" in res_safe["holder_source"]

    # 3. Query single match "lead_dev"
    res_dev = skill.execute("resolve_holder", holder="lead_dev")
    assert res_dev["status"] == "ok"
    assert res_dev["holder"] == "0x3333333333333333333333333333333333333333"


def test_erc4626_vault_view(mock_w3_factory):
    factory, ct = mock_w3_factory
    func_assets = MagicMock()
    func_assets.return_value.call.return_value = 5000000000000000000
    setattr(ct.functions, "totalAssets", func_assets)

    skill = EVMReaderSkill(web3_factory=factory)
    out = skill.execute(
        "call_view",
        chain="ethereum",
        contract=ADDRESS_ALICE,
        method="totalAssets",
        abi_preset="erc4626",
    )
    assert out["status"] == "ok"
    assert out["result"] == 5000000000000000000


def test_chainlink_feed_view(mock_w3_factory):
    factory, ct = mock_w3_factory
    round_data = (
        18446744073709551617,
        300050000000,
        1600000000,
        1600000000,
        18446744073709551617,
    )
    func_round = MagicMock()
    func_round.return_value.call.return_value = round_data
    setattr(ct.functions, "latestRoundData", func_round)

    skill = EVMReaderSkill(web3_factory=factory)
    out = skill.execute(
        "call_view",
        chain="ethereum",
        contract=ADDRESS_ALICE,
        method="latestRoundData",
        abi_preset="chainlink_feed",
    )
    assert out["status"] == "ok"
    assert len(out["result"]) == 5
    assert out["result"][1] == 300050000000


def test_multicall_partial_failure(mock_w3_factory):
    """Test tryAggregate returning success=True for call 1 and False for call 2."""
    factory, ct = mock_w3_factory
    ct.encodeABI.return_value = "0x1234"
    ct.decode_function_output.return_value = 42

    # Call 1 succeeds, Call 2 fails
    ct.functions.tryAggregate.return_value.call.return_value = [
        (
            True,
            bytes.fromhex(
                "000000000000000000000000000000000000000000000000000000000000002a"
            ),
        ),
        (False, b""),
    ]

    skill = EVMReaderSkill(web3_factory=factory)
    calls = [
        {"target": ADDRESS_USDC, "method": "decimals", "abi_preset": "erc20"},
        {
            "target": ADDRESS_USDC,
            "method": "balanceOf",
            "abi_preset": "erc20",
            "args": [ADDRESS_ALICE],
        },
    ]
    out = skill.execute("multicall", chain="ethereum", calls=calls)

    assert out["status"] == "ok"
    assert out["total_calls"] == 2
    assert out["results"][0]["success"] is True
    assert out["results"][0]["result"] == 42
    assert out["results"][1]["success"] is False
    assert out["results"][1]["result"] is None

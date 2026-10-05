"""Simulation and edge-case stress tests for defi/permit2_helper."""

from unittest.mock import MagicMock
from eth_account import Account
from eth_account.messages import encode_typed_data

from skills.defi.permit2_helper.constants import (
    CANONICAL_PERMIT2_ADDRESS,
    MAX_UINT160,
    MAX_UINT256,
)
from skills.defi.permit2_helper.skill import Permit2HelperSkill
from skillware.core.evm_config import load_merged_evm_config

ADDRESS_USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
ADDRESS_SPENDER = "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45"
ADDRESS_ALICE = "0x1111111111111111111111111111111111111111"


def test_permit2_chain_matrix_resolution():
    """Verify domain and verifying contract resolution across all 10 EVM chains."""
    cfg = load_merged_evm_config()
    skill = Permit2HelperSkill()

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
    for chain_name in expected_chains:
        assert chain_name in cfg.chains
        res = skill.execute(
            action="build_permit2",
            chain=chain_name,
            token=ADDRESS_USDC,
            spender=ADDRESS_SPENDER,
            amount=5000000,
            nonce=0,
        )
        assert res["status"] == "ok"
        assert res["chain_id"] == cfg.chains[chain_name]["chain_id"]
        assert (
            res["typed_data"]["domain"]["verifyingContract"].lower()
            == (
                cfg.chains[chain_name].get("permit2") or CANONICAL_PERMIT2_ADDRESS
            ).lower()
        )


def test_permit2_address_normalization_and_symbols_stress():
    """Verify lowercase, uppercase, raw 40-hex, symbols, and router aliases."""
    skill = Permit2HelperSkill()

    # 1. Lowercase token address
    res_lower = skill.execute(
        action="build_permit2",
        chain="ethereum",
        token="0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48",
        spender=ADDRESS_SPENDER,
        amount=1000,
    )
    assert res_lower["status"] == "ok"
    assert res_lower["preview"]["token"] == ADDRESS_USDC

    # 2. Token symbol resolution for configured tokens (e.g. usdc)
    res_symbol = skill.execute(
        action="build_permit2",
        chain="ethereum",
        token="usdc",
        spender=ADDRESS_SPENDER,
        amount=1000,
    )
    assert res_symbol["status"] == "ok"
    assert res_symbol["preview"]["token"] == ADDRESS_USDC

    # 3. Spender alias "router_v2" resolution to configured router and label
    res_alias = skill.execute(
        action="build_permit2",
        chain="ethereum",
        token="usdc",
        spender="router_v2",
        amount=1000,
    )
    assert res_alias["status"] == "ok"
    assert res_alias["preview"]["spender_label"] == "Uniswap V2 Router"

    # 4. Spender alias case-insensitive
    res_alias_upper = skill.execute(
        action="build_permit2",
        chain="ethereum",
        token="usdc",
        spender="ROUTER_V2",
        amount=1000,
    )
    assert res_alias_upper["status"] == "ok"
    assert res_alias_upper["preview"]["spender_label"] == "Uniswap V2 Router"

    # 5. Invalid addresses fail cleanly
    res_bad = skill.execute(
        action="build_permit2",
        chain="ethereum",
        token="0xnot_a_valid_token_address",
        spender=ADDRESS_SPENDER,
        amount=1000,
    )
    assert res_bad["status"] == "error"
    assert res_bad["error_code"] == "invalid_token_address"


def test_permit2_cryptographic_verification_simulations():
    """Verify cryptographic signature round-trip across different accounts and message formats."""
    skill = Permit2HelperSkill()

    for permit_type in ["PermitSingle", "PermitTransferFrom"]:
        account = Account.create()
        build_res = skill.execute(
            action="build_permit2",
            chain="ethereum",
            token="usdc",
            spender="router_v2",
            amount=2500000,
            permit_type=permit_type,
            nonce=7,
            deadline=1750000000,
        )
        assert build_res["status"] == "ok"
        typed_data = build_res["typed_data"]
        digest_hex = build_res["digest"]

        # Sign using eth_account
        signable = encode_typed_data(full_message=typed_data)
        signed = account.sign_message(signable)

        # Recover from digest
        digest_bytes = bytes.fromhex(digest_hex[2:])
        recovered = Account._recover_hash(digest_bytes, signature=signed.signature)
        assert recovered.lower() == account.address.lower()


def test_permit2_unlimited_protections_edge_cases():
    """Verify boundaries and fail-closed protections for unlimited allowances and transfers."""
    skill = Permit2HelperSkill()

    # 1. Exact boundary uint160 max on PermitSingle fails without allow_unlimited
    res_160_block = skill.execute(
        action="build_permit2",
        chain="ethereum",
        token="usdc",
        spender="router_v2",
        amount=MAX_UINT160,
    )
    assert res_160_block["status"] == "error"
    assert res_160_block["error_code"] == "unlimited_amount_forbidden"

    # 2. PermitSingle with allow_unlimited=True succeeds
    res_160_pass = skill.execute(
        action="build_permit2",
        chain="ethereum",
        token="usdc",
        spender="router_v2",
        amount=MAX_UINT160,
        allow_unlimited=True,
    )
    assert res_160_pass["status"] == "ok"
    assert res_160_pass["typed_data"]["message"]["details"]["amount"] == MAX_UINT160

    # 3. uint160 max - 1 succeeds without allow_unlimited
    res_160_below = skill.execute(
        action="build_permit2",
        chain="ethereum",
        token="usdc",
        spender="router_v2",
        amount=MAX_UINT160 - 1,
    )
    assert res_160_below["status"] == "ok"

    # 4. uint256 max on PermitTransferFrom fails without allow_unlimited
    res_256_block = skill.execute(
        action="build_permit2",
        chain="ethereum",
        token="usdc",
        spender="router_v2",
        permit_type="PermitTransferFrom",
        amount=MAX_UINT256,
    )
    assert res_256_block["status"] == "error"
    assert res_256_block["error_code"] == "unlimited_amount_forbidden"

    # 5. String 'max' resolves to MAX_UINT256 on PermitTransferFrom when allowed
    res_256_max_str = skill.execute(
        action="build_permit2",
        chain="ethereum",
        token="usdc",
        spender="router_v2",
        permit_type="PermitTransferFrom",
        amount="max",
        allow_unlimited=True,
    )
    assert res_256_max_str["status"] == "ok"
    assert (
        res_256_max_str["typed_data"]["message"]["permitted"]["amount"] == MAX_UINT256
    )

    # 6. String 'max' resolves to MAX_UINT160 on PermitSingle when allowed
    res_160_max_str = skill.execute(
        action="build_permit2",
        chain="ethereum",
        token="usdc",
        spender="router_v2",
        permit_type="PermitSingle",
        amount="max",
        allow_unlimited=True,
    )
    assert res_160_max_str["status"] == "ok"
    assert res_160_max_str["typed_data"]["message"]["details"]["amount"] == MAX_UINT160


def test_permit2_float_decimal_rejections():
    """Verify float inputs with non-zero fractional decimals are strictly rejected."""
    skill = Permit2HelperSkill()

    bad_amounts = [1.5, 0.001, 100.25, "10.5", "0.000000000000000001"]
    for amt in bad_amounts:
        res = skill.execute(
            action="build_permit2",
            chain="ethereum",
            token="usdc",
            spender="router_v2",
            amount=amt,
        )
        assert res["status"] == "error"
        assert res["error_code"] == "invalid_amount"
        assert "fractional decimals" in res["message"]

    # Whole floats (e.g. 10.0) should be parsed cleanly as integer
    res_whole = skill.execute(
        action="build_permit2",
        chain="ethereum",
        token="usdc",
        spender="router_v2",
        amount=10.0,
    )
    assert res_whole["status"] == "ok"
    assert res_whole["preview"]["amount"] == "10"


def test_permit2_read_nonce_simulation():
    """Verify read_nonce simulation with mocked RPC contract."""
    mock_contract = MagicMock()
    mock_contract.functions.allowance.return_value.call.return_value = (
        125000000,  # allowance
        1800000000,  # expiration
        5,  # nonce
    )
    mock_w3 = MagicMock()
    mock_w3.eth.contract.return_value = mock_contract

    skill = Permit2HelperSkill(web3_factory=lambda _: mock_w3)
    res = skill.execute(
        action="read_nonce",
        chain="ethereum",
        owner=ADDRESS_ALICE,
        token="usdc",
        spender="router_v2",
    )
    assert res["status"] == "ok"
    assert res["nonce"] == 5
    assert res["current_allowance"] == "125000000"
    assert res["expiration"] == 1800000000
    assert res["owner"] == ADDRESS_ALICE
    assert res["token"] == ADDRESS_USDC


def test_permit2_typed_data_tampering_detection():
    """Verify validate_typed_data catches tampered domain, chainId, and spenders."""
    skill = Permit2HelperSkill()
    built = skill.execute(
        action="build_permit2",
        chain="ethereum",
        token="usdc",
        spender=ADDRESS_SPENDER,
        amount=1000,
        deadline=2500000000,
    )
    assert built["status"] == "ok"
    typed_data = built["typed_data"]

    # 1. Valid validation
    val_ok = skill.execute(
        action="validate_typed_data",
        typed_data=typed_data,
        expected_chain="ethereum",
        expected_spender=ADDRESS_SPENDER,
    )
    assert val_ok["status"] == "ok"
    assert val_ok["is_valid"] is True

    # 2. Tampered chainId
    tampered_chain = dict(typed_data)
    tampered_chain["domain"] = dict(typed_data["domain"])
    tampered_chain["domain"]["chainId"] = 8453  # base instead of ethereum
    val_bad_chain = skill.execute(
        action="validate_typed_data",
        typed_data=tampered_chain,
        expected_chain="ethereum",
    )
    assert val_bad_chain["status"] == "error"
    assert val_bad_chain["is_valid"] is False
    assert any(
        "does not match expected chain" in err for err in val_bad_chain["errors"]
    )

    # 3. Tampered spender in message
    tampered_spender = dict(typed_data)
    tampered_spender["message"] = dict(typed_data["message"])
    tampered_spender["message"]["spender"] = ADDRESS_ALICE
    val_bad_spender = skill.execute(
        action="validate_typed_data",
        typed_data=tampered_spender,
        expected_spender=ADDRESS_SPENDER,
    )
    assert val_bad_spender["status"] == "error"
    assert val_bad_spender["is_valid"] is False
    assert any(
        "does not match expected_spender" in err for err in val_bad_spender["errors"]
    )

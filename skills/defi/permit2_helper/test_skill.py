"""Unit tests for defi/permit2_helper skill."""

import os
from unittest.mock import MagicMock, patch
from eth_account import Account
from eth_account.messages import encode_typed_data
import pytest
import yaml

from skills.defi.permit2_helper import Permit2HelperSkill
from skills.defi.permit2_helper.constants import (
    CANONICAL_PERMIT2_ADDRESS,
    MAX_UINT160,
    MAX_UINT256,
)
from skillware.core.evm_config import load_merged_evm_config


@pytest.fixture
def skill():
    return Permit2HelperSkill()


@pytest.fixture
def manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_skill_manifest_consistency(skill, manifest):
    skill_manifest = skill.manifest
    assert skill_manifest["name"] == manifest["name"]
    assert skill_manifest["version"] == manifest["version"]


def test_missing_and_invalid_action(skill):
    res1 = skill.execute({})
    assert res1["status"] == "error"
    assert res1["error_code"] == "missing_action"

    res2 = skill.execute({"action": "unknown_action"})
    assert res2["status"] == "error"
    assert res2["error_code"] == "invalid_action"


def test_build_permit2_single_success(skill):
    token = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48"
    spender = "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD"
    res = skill.execute(
        {
            "action": "build_permit2",
            "chain": "ethereum",
            "token": token,
            "spender": spender,
            "amount": "1000000",
            "nonce": 0,
            "deadline": 1735689600,
        }
    )

    assert res["status"] == "ok"
    assert res["chain"] == "ethereum"
    assert res["chain_id"] == 1
    assert res["primary_type"] == "PermitSingle"
    assert res["verifying_contract"].lower() == CANONICAL_PERMIT2_ADDRESS.lower()
    assert res["digest"].startswith("0x")
    assert len(res["digest"]) == 66  # 32 bytes hex + 0x

    typed_data = res["typed_data"]
    assert typed_data["primaryType"] == "PermitSingle"
    assert typed_data["domain"]["name"] == "Permit2"
    assert typed_data["domain"]["chainId"] == 1
    assert typed_data["message"]["details"]["amount"] == 1000000
    assert typed_data["message"]["details"]["nonce"] == 0
    assert typed_data["message"]["spender"].lower() == spender.lower()

    # Spender preview check
    assert "Uniswap Universal Router" in res["preview"]["spender_label"]


def test_build_permit2_transfer_from_success(skill):
    token = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48"
    spender = "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45"
    res = skill.execute(
        {
            "action": "build_permit2",
            "chain": "base",
            "permit_type": "PermitTransferFrom",
            "token": token,
            "spender": spender,
            "amount": 5000000,
            "nonce": 12,
            "deadline": 1735689600,
        }
    )

    assert res["status"] == "ok"
    assert res["chain"] == "base"
    assert res["chain_id"] == 8453
    assert res["primary_type"] == "PermitTransferFrom"
    assert res["typed_data"]["message"]["permitted"]["amount"] == 5000000
    assert res["typed_data"]["message"]["nonce"] == 12


def test_build_permit2_transfer_from_unlimited(skill):
    token = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48"
    spender = "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45"
    res = skill.execute(
        {
            "action": "build_permit2",
            "chain": "base",
            "permit_type": "PermitTransferFrom",
            "token": token,
            "spender": spender,
            "amount": MAX_UINT256,
        }
    )
    assert res["status"] == "error"
    assert res["error_code"] == "unlimited_amount_forbidden"

    res_ok = skill.execute(
        {
            "action": "build_permit2",
            "chain": "base",
            "permit_type": "PermitTransferFrom",
            "token": token,
            "spender": spender,
            "amount": MAX_UINT256,
            "allow_unlimited": True,
        }
    )
    assert res_ok["status"] == "ok"
    assert res_ok["typed_data"]["message"]["permitted"]["amount"] == MAX_UINT256

    # Test "max" and "unlimited" string values resolve to MAX_UINT256 for PermitTransferFrom
    for max_str in ["max", "unlimited"]:
        res_str_block = skill.execute(
            {
                "action": "build_permit2",
                "chain": "base",
                "permit_type": "PermitTransferFrom",
                "token": token,
                "spender": spender,
                "amount": max_str,
            }
        )
        assert res_str_block["status"] == "error"
        assert res_str_block["error_code"] == "unlimited_amount_forbidden"

        res_str_ok = skill.execute(
            {
                "action": "build_permit2",
                "chain": "base",
                "permit_type": "PermitTransferFrom",
                "token": token,
                "spender": spender,
                "amount": max_str,
                "allow_unlimited": True,
            }
        )
        assert res_str_ok["status"] == "ok"
        assert res_str_ok["typed_data"]["message"]["permitted"]["amount"] == MAX_UINT256


def test_build_permit2_router_alias(skill):
    token = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48"
    res = skill.execute(
        {
            "action": "build_permit2",
            "chain": "ethereum",
            "token": token,
            "spender": "router_v2",
            "amount": "1000",
        }
    )

    assert res["status"] == "ok"
    assert (
        res["preview"]["spender"].lower()
        == "0x7a250d5630b4cf539739df2c5da4bf9c15291ece"
    )


def test_build_permit2_unlimited_fails_closed(skill):
    token = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48"
    spender = "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD"

    # Testing uint160 max without allow_unlimited
    res = skill.execute(
        {
            "action": "build_permit2",
            "chain": "ethereum",
            "token": token,
            "spender": spender,
            "amount": MAX_UINT160,
        }
    )

    assert res["status"] == "error"
    assert res["error_code"] == "unlimited_amount_forbidden"

    # With allow_unlimited: true it succeeds
    res_allowed = skill.execute(
        {
            "action": "build_permit2",
            "chain": "ethereum",
            "token": token,
            "spender": spender,
            "amount": MAX_UINT160,
            "allow_unlimited": True,
        }
    )
    assert res_allowed["status"] == "ok"
    assert res_allowed["typed_data"]["message"]["details"]["amount"] == MAX_UINT160


def test_validate_typed_data_valid(skill):
    # First build
    build_res = skill.execute(
        {
            "action": "build_permit2",
            "chain": "ethereum",
            "token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48",
            "spender": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
            "amount": 1000,
            "deadline": 2500000000,  # far future
        }
    )
    assert build_res["status"] == "ok"
    typed_data = build_res["typed_data"]

    # Now validate
    val_res = skill.execute(
        {
            "action": "validate_typed_data",
            "typed_data": typed_data,
            "expected_chain": "ethereum",
            "expected_spender": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
        }
    )

    assert val_res["status"] == "ok"
    assert val_res["is_valid"] is True
    assert val_res["errors"] == []
    assert val_res["digest"] == build_res["digest"]


def test_validate_typed_data_mismatches(skill):
    build_res = skill.execute(
        {
            "action": "build_permit2",
            "chain": "ethereum",
            "token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48",
            "spender": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
            "amount": 1000,
            "deadline": 1000000000,  # expired timestamp
        }
    )
    typed_data = build_res["typed_data"]

    # Check mismatched chain and expired deadline
    val_res = skill.execute(
        {
            "action": "validate_typed_data",
            "typed_data": typed_data,
            "expected_chain": "base",  # chainId mismatch (1 vs 8453)
            "expected_spender": "0x1111111254eeb25477b68fb85ed929f73a960582",  # spender mismatch
        }
    )

    assert val_res["status"] == "error"
    assert val_res["is_valid"] is False
    assert any("does not match expected chain" in err for err in val_res["errors"])
    assert any("does not match expected_spender" in err for err in val_res["errors"])
    assert any("expired" in warn.lower() for warn in val_res["warnings"])


def test_hash_typed_data_success(skill):
    build_res = skill.execute(
        {
            "action": "build_permit2",
            "chain": "ethereum",
            "token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48",
            "spender": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
            "amount": 2500000,
            "deadline": 1735689600,
        }
    )
    typed_data = build_res["typed_data"]

    hash_res = skill.execute(
        {
            "action": "hash_typed_data",
            "typed_data": typed_data,
        }
    )

    assert hash_res["status"] == "ok"
    assert hash_res["digest"] == build_res["digest"]


def test_read_nonce_without_rpc(skill, monkeypatch):
    monkeypatch.delenv("ETHEREUM_RPC_URL", raising=False)
    res = skill.execute(
        {
            "action": "read_nonce",
            "chain": "ethereum",
            "owner": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0",
            "token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48",
            "spender": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
        }
    )
    assert res["status"] == "error"
    assert res["error_code"] == "rpc_not_configured"


def test_read_nonce_with_mocked_rpc(skill):
    mock_contract = MagicMock()
    mock_contract.functions.allowance.return_value.call.return_value = (
        5000000,
        1735689600,
        3,
    )

    mock_w3 = MagicMock()
    mock_w3.eth.contract.return_value = mock_contract

    with (
        patch("skills.defi.permit2_helper.skill.is_rpc_configured", return_value=True),
        patch("skills.defi.permit2_helper.skill.get_web3", return_value=mock_w3),
    ):
        res = skill.execute(
            {
                "action": "read_nonce",
                "chain": "ethereum",
                "owner": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0",
                "token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48",
                "spender": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
            }
        )

        assert res["status"] == "ok"
        assert res["nonce"] == 3
        assert res["current_allowance"] == "5000000"
        assert res["expiration"] == 1735689600


def test_invalid_parameters_fail_safely(skill):
    # Invalid chain
    res = skill.execute(
        {
            "action": "build_permit2",
            "chain": "unknown_chain_xyz",
            "token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48",
            "spender": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
            "amount": 100,
        }
    )
    assert res["status"] == "error"
    assert res["error_code"] == "invalid_chain"

    # Invalid token address
    res = skill.execute(
        {
            "action": "build_permit2",
            "chain": "ethereum",
            "token": "0xNotAnAddress",
            "spender": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
            "amount": 100,
        }
    )
    assert res["status"] == "error"
    assert res["error_code"] == "invalid_token_address"


def test_cryptographic_roundtrip_signing_and_recovery(skill):
    account = Account.create()
    build_res = skill.execute(
        {
            "action": "build_permit2",
            "chain": "ethereum",
            "token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48",
            "spender": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
            "amount": 1000000,
            "nonce": 0,
            "deadline": 1735689600,
        }
    )
    assert build_res["status"] == "ok"
    typed_data = build_res["typed_data"]
    digest_hex = build_res["digest"]

    # Sign using eth_account
    signable = encode_typed_data(full_message=typed_data)
    signed_msg = account.sign_message(signable)

    # Recover signer from the computed 32-byte digest
    digest_bytes = bytes.fromhex(digest_hex[2:])
    recovered = Account._recover_hash(digest_bytes, signature=signed_msg.signature)
    assert recovered.lower() == account.address.lower()


def test_all_10_chains_domain_and_verifying_contract_resolution(skill):
    cfg = load_merged_evm_config()
    for chain_name in cfg.chains:
        res = skill.execute(
            {
                "action": "build_permit2",
                "chain": chain_name,
                "token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48",
                "spender": "0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
                "amount": 1000,
            }
        )
        assert res["status"] == "ok", f"failed on chain {chain_name}: {res}"
        expected_chain_id = cfg.chains[chain_name]["chain_id"]
        assert res["chain_id"] == expected_chain_id
        assert res["typed_data"]["domain"]["chainId"] == expected_chain_id

        expected_permit2 = (
            cfg.chains[chain_name].get("permit2") or CANONICAL_PERMIT2_ADDRESS
        )
        assert (
            res["typed_data"]["domain"]["verifyingContract"].lower()
            == expected_permit2.lower()
        )


def test_token_symbol_and_spender_alias_resolution(skill):
    res = skill.execute(
        {
            "action": "build_permit2",
            "chain": "ethereum",
            "token": "usdc",
            "spender": "router_v2",
            "amount": 500000,
        }
    )
    assert res["status"] == "ok"
    assert (
        res["preview"]["token"].lower()
        == "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48".lower()
    )
    assert res["preview"]["spender_label"] == "Uniswap V2 Router"


def test_read_nonce_supports_symbol_and_alias():
    mock_contract = MagicMock()
    mock_contract.functions.allowance.return_value.call.return_value = (
        1000000,
        1735689600,
        1,
    )
    mock_w3 = MagicMock()
    mock_w3.eth.contract.return_value = mock_contract

    skill = Permit2HelperSkill(web3_factory=lambda _: mock_w3)
    res = skill.execute(
        {
            "action": "read_nonce",
            "chain": "ethereum",
            "owner": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0",
            "token": "usdc",
            "spender": "router_v2",
        }
    )
    assert res["status"] == "ok"
    assert res["token"].lower() == "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48".lower()
    assert res["nonce"] == 1


def test_decimal_float_rejection(skill):
    res = skill.execute(
        {
            "action": "build_permit2",
            "chain": "ethereum",
            "token": "usdc",
            "spender": "router_v2",
            "amount": 10.5,
        }
    )
    assert res["status"] == "error"
    assert res["error_code"] == "invalid_amount"
    assert "fractional decimals" in res["message"]

    res_str = skill.execute(
        {
            "action": "build_permit2",
            "chain": "ethereum",
            "token": "usdc",
            "spender": "router_v2",
            "amount": "10.5",
        }
    )
    assert res_str["status"] == "error"
    assert res_str["error_code"] == "invalid_amount"
    assert "fractional decimals" in res_str["message"]


@pytest.mark.asyncio
async def test_async_execute_parity(skill):
    params = {
        "action": "build_permit2",
        "chain": "ethereum",
        "token": "usdc",
        "spender": "router_v2",
        "amount": 1000000,
    }
    sync_res = skill.execute(params)
    async_res = await skill.aexecute(params)
    assert sync_res["status"] == "ok"
    assert async_res["status"] == "ok"
    assert sync_res["digest"] == async_res["digest"]


def test_validate_params(skill):
    valid = skill.validate_params(
        {
            "action": "build_permit2",
            "chain": "ethereum",
            "token": "usdc",
            "spender": "router_v2",
            "amount": 100,
        }
    )
    assert valid is True

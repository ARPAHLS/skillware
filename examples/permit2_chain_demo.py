"""Cross-skill orchestration demo with SkillContext and Permit2.

Demonstrates:
1. Initialize SkillContext with 'defi' category
2. defi/evm_reader: Check ERC-20 token balance & existing Permit2 allowance
3. defi/permit2_helper: Build & validate EIP-712 PermitSingle typed data
4. Host signing: Sign the 32-byte digest with ephemeral eth_account
5. Verification: Recover and verify signer identity

Run offline:
    python examples/permit2_chain_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock
from eth_account import Account
from eth_account.messages import encode_typed_data

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skillware import SkillContext  # noqa: E402


def run_demo() -> None:
    print("=== Permit2 Cross-Skill Chaining Demo ===")
    account = Account.create()
    owner_addr = account.address
    print(f"1. Host signer initialized: {owner_addr}")

    # Set up SkillContext with mock web3 factory for offline execution
    mock_w3 = MagicMock()
    mock_contract = MagicMock()
    mock_w3.eth.contract.return_value = mock_contract
    # Mock ERC-20 balance & allowance
    mock_contract.functions.balanceOf.return_value.call.return_value = (
        5000000000  # 5000 USDC
    )
    mock_contract.functions.allowance.return_value.call.return_value = (
        0,
        0,
        0,
    )  # no permit2 allowance

    ctx = SkillContext(categories=["defi"])
    prep_reader = ctx.prepare("defi/evm_reader")
    reader_instance = ctx._get_instance(prep_reader)
    reader_instance._web3_factory = lambda _: mock_w3

    prep_permit2 = ctx.prepare("defi/permit2_helper")
    permit2_instance = ctx._get_instance(prep_permit2)
    permit2_instance._web3_factory = lambda _: mock_w3

    # Step 1: Query balance & allowance via defi/evm_reader
    print("\n2. Step 1: Querying balance and existing allowance via defi/evm_reader...")
    bal_res = ctx.execute(
        "defi/evm_reader",
        {
            "action": "erc20_balance",
            "chain": "ethereum",
            "contract": "usdc",
            "holder": owner_addr,
        },
    )
    print(f"   Balance raw: {bal_res.get('balance_raw')}")

    # Step 2: Build PermitSingle typed data via defi/permit2_helper
    print(
        "\n3. Step 2: Building EIP-712 PermitSingle payload via defi/permit2_helper..."
    )
    permit_res = ctx.execute(
        "defi/permit2_helper",
        {
            "action": "build_permit2",
            "chain": "ethereum",
            "token": "usdc",
            "spender": "router_v2",
            "amount": 100000000,  # 100 USDC
            "nonce": 0,
            "deadline": 1750000000,
        },
    )
    print(f"   Permit status: {permit_res['status']}")
    print(f"   Digest to sign: {permit_res['digest']}")

    # Step 3: Validate the generated typed data
    print("\n4. Step 3: Validating payload integrity before host signing...")
    val_res = ctx.execute(
        "defi/permit2_helper",
        {
            "action": "validate_typed_data",
            "typed_data": permit_res["typed_data"],
            "expected_chain": "ethereum",
        },
    )
    print(f"   Payload valid: {val_res['is_valid']}")

    # Step 4: Host wallet signs typed data
    print("\n5. Step 4: Host agent signs typed data with ephemeral private key...")
    signable = encode_typed_data(full_message=permit_res["typed_data"])
    signed = account.sign_message(signable)
    print(f"   Signature acquired: {signed.signature.hex()[:32]}...")

    # Step 5: Cryptographic recovery verification
    print("\n6. Step 5: Verifying signature against 32-byte EIP-712 digest...")
    digest_bytes = bytes.fromhex(permit_res["digest"][2:])
    recovered = Account._recover_hash(digest_bytes, signature=signed.signature)
    print(f"   Recovered signer: {recovered}")
    assert recovered.lower() == owner_addr.lower()
    print("   Signer verification matches host address perfectly!")

    print("\nPermit2 cross-skill chaining demo completed successfully.")


if __name__ == "__main__":
    run_demo()

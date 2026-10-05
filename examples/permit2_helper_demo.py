"""Local execute and offline demo for defi/permit2_helper.

Demonstrates:
1. Building an EIP-712 PermitSingle typed data payload and 32-byte digest
2. Building an EIP-712 PermitTransferFrom payload
3. Validating typed data against expected chain and spender
4. Re-computing 32-byte EIP-712 signing digest
5. Fail-closed protection on unlimited approvals

Run offline:
    python examples/permit2_helper_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skillware.core.loader import SkillLoader  # noqa: E402


def run_demo() -> None:
    print("=== defi/permit2_helper Demo (Offline Execution) ===")
    bundle = SkillLoader.load_skill("defi/permit2_helper")
    skill = bundle["class"]()

    # 1. Build PermitSingle
    print("\n1. Building PermitSingle typed data for USDC:")
    res_single = skill.execute(
        action="build_permit2",
        chain="ethereum",
        token="usdc",
        spender="router_v2",
        amount=1000000,
        nonce=0,
        deadline=1750000000,
    )
    print(f"   Status: {res_single['status']}")
    print(f"   Primary Type: {res_single['primary_type']}")
    print(f"   Spender Label: {res_single['preview']['spender_label']}")
    print(f"   Signing Digest: {res_single['digest']}")

    # 2. Validate typed data
    print("\n2. Validating EIP-712 typed data payload:")
    val_res = skill.execute(
        action="validate_typed_data",
        typed_data=res_single["typed_data"],
        expected_chain="ethereum",
        expected_spender=res_single["preview"]["spender"],
    )
    print(f"   Is Valid: {val_res['is_valid']}")
    print(f"   Digest Match: {val_res['digest'] == res_single['digest']}")

    # 3. Hash typed data
    print("\n3. Re-computing EIP-712 hash:")
    hash_res = skill.execute(
        action="hash_typed_data",
        typed_data=res_single["typed_data"],
    )
    print(f"   Hash: {hash_res['digest']}")

    # 4. Fail-closed unlimited approval guard
    print("\n4. Unlimited approval guard check (fail-closed):")
    guard_res = skill.execute(
        action="build_permit2",
        chain="ethereum",
        token="usdc",
        spender="router_v2",
        amount="max",
    )
    print(f"   Blocked Status: {guard_res['status']}")
    print(f"   Error Code: {guard_res['error_code']}")

    print("\nPermit2 helper demo completed successfully.")


if __name__ == "__main__":
    run_demo()

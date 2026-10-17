"""Local execute and live demo for defi/evm_reader.

Demonstrates read-only EVM queries:
1. Addressbook holder resolution
2. ERC-20 metadata & formatted balances
3. Pair reserves view calls
4. Multicall3 batch queries

Run offline (mocked):
    python examples/evm_reader_demo.py

Run live (when RPC URLs configured in .env):
    ETHEREUM_RPC_URL="https://..." python examples/evm_reader_demo.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skillware.core.env import load_env_file  # noqa: E402
from skillware.core.loader import SkillLoader  # noqa: E402

ADDRESS_USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
ADDRESS_ALICE = "0x1111111111111111111111111111111111111111"


def run_mock_demo() -> None:
    print("=== defi/evm_reader Demo (Offline / Mock Mode) ===")
    bundle = SkillLoader.load_skill("defi/evm_reader")

    mock_w3 = MagicMock()
    mock_ct = MagicMock()
    mock_w3.eth.contract.return_value = mock_ct

    # Mock contract return values
    mock_ct.functions.name.return_value.call.return_value = "USD Coin"
    mock_ct.functions.symbol.return_value.call.return_value = "USDC"
    mock_ct.functions.decimals.return_value.call.return_value = 6
    mock_ct.functions.totalSupply.return_value.call.return_value = 25000000000000
    mock_ct.functions.balanceOf.return_value.call.return_value = 1500500000
    mock_ct.functions.allowance.return_value.call.return_value = 500000000

    skill = bundle["class"](web3_factory=lambda _: mock_w3)

    # 1. ERC-20 Metadata
    print("\n1. Querying ERC-20 Metadata:")
    meta = skill.execute("erc20_metadata", chain="ethereum", contract=ADDRESS_USDC)
    print(f"   Token: {meta['name']} ({meta['symbol']})")
    print(f"   Decimals: {meta['decimals']} | Total Supply: {meta['total_supply']}")

    # 2. ERC-20 Balance
    print("\n2. Querying ERC-20 Balance:")
    bal = skill.execute(
        "erc20_balance", chain="ethereum", contract=ADDRESS_USDC, holder=ADDRESS_ALICE
    )
    print(f"   Holder: {bal['holder']}")
    print(f"   Balance Raw: {bal['balance_raw']}")
    print(f"   Balance Formatted: {bal['balance']} {meta['symbol']}")

    # 3. View Call (Uni V2 Pair Reserves)
    func_reserves = MagicMock()
    func_reserves.return_value.call.return_value = (
        50000000000,
        15000000000000000000,
        1720000000,
    )
    setattr(mock_ct.functions, "getReserves", func_reserves)

    print("\n3. Calling View Function (getReserves on Uni V2 Pair):")
    reserves = skill.execute(
        "call_view",
        chain="ethereum",
        contract="0xB4e16d0168e52d35CaCD2c6185b44281Ec28C9Dc",
        method="getReserves",
        abi_preset="univ2_pair",
    )
    print(f"   Reserves Result: {reserves['result']}")

    # 4. Multicall3 Batch Query
    mock_ct.encodeABI.return_value = "0x1234"
    mock_ct.decode_function_output.return_value = 6
    mock_ct.functions.tryAggregate.return_value.call.return_value = [
        (
            True,
            bytes.fromhex(
                "0000000000000000000000000000000000000000000000000000000000000006"
            ),
        )
    ]

    print("\n4. Executing Multicall3 Batch Read:")
    calls = [{"target": ADDRESS_USDC, "method": "decimals", "abi_preset": "erc20"}]
    mc = skill.execute("multicall", chain="ethereum", calls=calls)
    print(f"   Total Batched Calls: {mc['total_calls']}")
    print(
        f"   Call 0 Success: {mc['results'][0]['success']} | Decoded: {mc['results'][0]['result']}"
    )

    print("\nDemo completed successfully.")


def run_live_demo(chain: str) -> None:
    print(f"=== defi/evm_reader Demo (Live Mode on {chain}) ===")
    bundle = SkillLoader.load_skill("defi/evm_reader")
    skill = bundle["class"]()

    print(f"\n1. Fetching Live USDC Metadata on {chain}:")
    meta = skill.execute("erc20_metadata", chain=chain, contract="usdc")
    if meta.get("status") == "ok":
        print(f"   Token: {meta.get('name')} ({meta.get('symbol')})")
        print(
            f"   Decimals: {meta.get('decimals')} | Total Supply: {meta.get('total_supply')}"
        )
    else:
        print(f"   RPC query failed: {meta.get('message')}")


def main() -> None:
    load_env_file()
    force_live = os.environ.get("EVM_READER_LIVE", "").strip() in ("1", "true")
    force_demo = os.environ.get("EVM_READER_DEMO", "").strip() in ("1", "true")
    has_live_rpc = bool(
        os.environ.get("ETHEREUM_RPC_URL") or os.environ.get("BASE_RPC_URL")
    )

    if force_live and has_live_rpc and not force_demo:
        chain = "ethereum" if os.environ.get("ETHEREUM_RPC_URL") else "base"
        run_live_demo(chain)
    else:
        run_mock_demo()


if __name__ == "__main__":
    main()

"""Pre-flight chain demo: monitoring/rpc_health_probe gates defi/evm_reader.

Demonstrates the recommended pre-trade pattern:
1. Probe the operator RPC endpoint with monitoring/rpc_health_probe
   (action: probe) for chain ID, block height, latency and reference lag.
2. Run defi/evm_reader only when the probe reports all_healthy == True.
3. Abort cleanly when all_healthy == False (here, a wrong-chain endpoint).

Runs fully offline: JSON-RPC answers and the web3 client are mocked.

    python examples/rpc_health_chain_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skillware.core.loader import SkillLoader  # noqa: E402

CHAIN = "ethereum"
ADDRESS_USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
HEALTHY_RPC = "https://healthy-rpc.invalid"
WRONG_CHAIN_RPC = "https://wrong-chain-rpc.invalid"
REFERENCE_RPC = "https://reference-rpc.invalid"

MOCK_RPC_RESULTS: Dict[str, Dict[str, str]] = {
    HEALTHY_RPC: {"eth_chainId": "0x1", "eth_blockNumber": "0x1406f40"},
    REFERENCE_RPC: {"eth_chainId": "0x1", "eth_blockNumber": "0x1406f41"},
    WRONG_CHAIN_RPC: {"eth_chainId": "0x2105", "eth_blockNumber": "0x1406f40"},
}


class _MockResponse:
    status_code = 200

    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def json(self) -> Dict[str, Any]:
        return self._payload


def _mock_post(url: str, json: Dict[str, Any], timeout: float) -> _MockResponse:
    result = MOCK_RPC_RESULTS[url][json["method"]]
    return _MockResponse({"jsonrpc": "2.0", "id": json["id"], "result": result})


def _mock_web3() -> MagicMock:
    w3 = MagicMock()
    contract = w3.eth.contract.return_value
    contract.functions.name.return_value.call.return_value = "USD Coin"
    contract.functions.symbol.return_value.call.return_value = "USDC"
    contract.functions.decimals.return_value.call.return_value = 6
    contract.functions.totalSupply.return_value.call.return_value = 25000000000000
    return w3


def run_pipeline(label: str, rpc_url: str, probe: Any, reader_cls: Any) -> None:
    print(f"\n--- {label} ---")
    print("[Step 1] monitoring/rpc_health_probe (action: probe)")
    report = probe.execute(
        {
            "action": "probe",
            "endpoints": [
                {"chain": CHAIN, "url": rpc_url, "reference_url": REFERENCE_RPC}
            ],
        }
    )
    for row in report["results"]:
        print(
            f"  endpoint={row['endpoint']} status={row['status']} "
            f"chain_id={row['chain_id']} expected={row['expected_chain_id']} "
            f"lag={row['lag_status']} reasons={row['reasons']}"
        )
    print(f"  all_healthy={report['all_healthy']}")

    w3 = _mock_web3()
    reader = reader_cls(web3_factory=lambda _: w3)
    if not report["all_healthy"]:
        print("[Step 2] Gate closed: defi/evm_reader skipped.")
        print(f"  evm_reader contract calls: {w3.eth.contract.call_count}")
        return

    print("[Step 2] Gate open: defi/evm_reader erc20_metadata")
    meta = reader.execute("erc20_metadata", chain=CHAIN, contract=ADDRESS_USDC)
    print(f"  Token: {meta['name']} ({meta['symbol']}) decimals={meta['decimals']}")


def main() -> None:
    print("=== Pre-flight chain: monitoring/rpc_health_probe -> defi/evm_reader ===")
    probe = SkillLoader.load_skill("monitoring/rpc_health_probe")["class"]()
    reader_cls = SkillLoader.load_skill("defi/evm_reader")["class"]

    with patch.object(probe._session, "post", side_effect=_mock_post):
        run_pipeline("Case A: healthy endpoint", HEALTHY_RPC, probe, reader_cls)
        run_pipeline("Case B: wrong-chain endpoint", WRONG_CHAIN_RPC, probe, reader_cls)

    print("\nPre-flight chain demo complete.")


if __name__ == "__main__":
    main()

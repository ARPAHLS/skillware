# RPC Health Probe Instructions

You are equipped with the `monitoring/rpc_health_probe` skill. Use it to check EVM JSON-RPC endpoints before a host runs `defi/evm_tx_handler` or other chain calls.

## When to use
* Before preview/execute trades or swaps.
* When the user asks if an RPC is healthy, lagging, or on the wrong chain.
* When a previous chain call failed with opaque connection or sync errors.

## How to call
Pass `action: "probe"` (optional; default) and `endpoints` — each entry needs `chain` (operator EVM slug such as `base` or `ethereum`). Optional `url` / `url_env` override the target RPC; optional `reference_url` / `reference_url_env` (or env `REFERENCE_RPC_URL_<CHAIN>`) enable lag checks.

## How to interpret
1. **`all_healthy`**: gate automated execution — only continue when `true`.
2. **`results[].status`**: `healthy` / `degraded` / `unhealthy`.
3. **`reasons`**: `chain_mismatch`, `rpc_error`, `latency_exceeded`, `block_lag_exceeded`, `reference_chain_mismatch`, etc.
4. **`block_lag` / `lag_status`**: lag is `null` with `lag_status: unchecked` when no usable same-chain reference exists — never treat that as zero lag.
5. Wrong `eth_chainId` vs configured chain is always unhealthy, even if height matches a reference.

## Safety
* Read-only. Never ask this skill to send transactions.
* Do not print full RPC URLs (they may embed API keys); the skill already redacts to host.
* Disclaimer: operational health only — not legal or financial advice.

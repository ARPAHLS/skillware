# Wallet Screening Skill Instructions

You are equipped with the `finance/wallet_screening` skill. This tool allows you to perform due diligence on Ethereum addresses.

## When to use
Use this skill when the user:
*   Asks to check if a wallet is safe.
*   Asks for a background check on a crypto address.
*   Mentions "AML", "KYC", or "Sanctions" in the context of a crypto address.
*   Wants to know if a wallet has interacted with mixers (Tornado Cash) or scams.

## How to interpret the output
The tool returns a JSON object. You should summarize this for the user in a professional, "Compliance Officer" tone.

### Key Fields to Check:
1.  **`verdict.decision`** / **`summary.risk_level`**: Gate automated actions on these first (`ALLOW` / `REVIEW` / `DENY`).
2.  **`summary.sanctioned_entity_match` (Boolean)**: If `true`, this is CRITICAL. Report the `risk_details.sanctions_hits` (and any live provider hits) immediately.
3.  **`summary.malicious_interaction_count` (Integer)**: If > 0, the wallet has touched bad actors. List the `risk_details.malicious_interactions` (includes `transfer_kind`: `eth`, `erc20`, `internal`, or `direct`).
4.  **`summary.indirect_exposure_count`**: Hop-1 counterparties that match bundled sanctions lists.
5.  **`summary.total_token_txs` / `total_internal_txs`**: ERC-20 and internal transfer counts alongside `total_transactions` (normal ETH only). Absent or zero in offline-direct mode.
6.  **`financial_analysis.pnl_eth` / `pnl_usd`**: Profit and Loss on ETH (+ internal ETH). Check `financial_analysis.token_flow` for major ERC-20 volumes.
7.  **`network_analysis.top_10_counterparties`**: Who are they sending money to?
8.  **`metadata.mode`**: `full_forensics` when Etherscan ran; `offline_direct_only` when only bundled lists were checked (no tx history).
9.  **`metadata.warnings` (Array, optional)**: Incomplete history or live-provider codes (`etherscan_*`, `offline_direct_only_no_tx_history`, `chainalysis_*`, `trm_*`). Do not present PnL or interaction counts as exhaustive when warnings are set.

## Safety Protocol
*   If a wallet is **Sanctioned** or **`verdict.decision` is `DENY`**: severe warning. Halt automated execution.
*   If **`REVIEW`**: flag for a human; do not auto-trade.
*   If a wallet is **Clean** / **`ALLOW`**: "✅ Analysis complete. No direct links to sanctions or known malicious contracts were found."
*   **Disclaimer**: Always append: "This analysis is for informational purposes only and does not constitute legal or financial advice."

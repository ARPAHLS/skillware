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
1.  **`summary.sanctioned_entity_match` (Boolean)**: If `true`, this is CRITICAL. Report the `risk_details.sanctions_hits` immediately.
2.  **`summary.malicious_interaction_count` (Integer)**: If > 0, the wallet has touched bad actors. List the `risk_details.malicious_interactions` (includes `transfer_kind`: `eth`, `erc20`, or `internal`).
3.  **`summary.total_token_txs` / `total_internal_txs`**: ERC-20 and internal transfer counts alongside `total_transactions` (normal ETH only).
4.  **`financial_analysis.pnl_eth` / `pnl_usd`**: Profit and Loss on ETH (+ internal ETH). Check `financial_analysis.token_flow` for major ERC-20 volumes.
5.  **`network_analysis.top_10_counterparties`**: Who are they sending money to?
6.  **`metadata.warnings` (Array, optional)**: Incomplete history codes — `etherscan_txlist_*`, `etherscan_tokentx_*`, `etherscan_txlistinternal_*` (`truncated` / `unavailable` / `partial`). Do not present PnL or interaction counts as exhaustive when warnings are set.

## Safety Protocol
*   If a wallet is **Sanctioned**: severe warning. "⚠️ WARNING: This wallet appears on the following sanctions lists..."
*   If a wallet is **Clean**: "✅ Analysis complete. No direct links to sanctions or known malicious contracts were found."
*   **Disclaimer**: Always append: "This analysis is for informational purposes only and does not constitute legal or financial advice."

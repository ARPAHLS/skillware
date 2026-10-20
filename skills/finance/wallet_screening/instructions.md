# Wallet Screening Skill Instructions

You are equipped with the `finance/wallet_screening` skill. This tool allows you to perform due diligence on Ethereum addresses.

## When to use
Use this skill when the user:
*   Asks to check if a wallet is safe.
*   Asks for a background check on a crypto address.
*   Mentions "AML", "KYC", or "Sanctions" in the context of a crypto address.
*   Wants to know if a wallet has interacted with mixers (Tornado Cash) or scams.

## How to interpret the output
The tool returns a JSON object (`schema_version: "2.0"`). Summarize it for the user in a professional, "Compliance Officer" tone.

### Key Fields to Check:
1.  **`verdict.decision`** (`ALLOW` | `REVIEW` | `DENY`) and **`verdict.risk_level`** (`critical` | `high` | `medium` | `low`): host agents should gate on these first.
2.  **`verdict.reason_code`** / **`summary_statement`**: short machine and human explanations.
3.  **`summary.sanctioned_entity_match` (Boolean)**: If `true`, this is CRITICAL. Report the `risk_details.sanctions_hits` immediately.
4.  **`summary.malicious_interaction_count` (Integer)**: If > 0, the wallet has touched bad actors. List the `risk_details.malicious_interactions` (includes `transfer_kind`: `eth`, `erc20`, or `internal`).
5.  **`summary.indirect_exposure_count` / `risk_details.indirect_exposures`**: Hop-1 counterparties that match bundled sanctions lists.
6.  **`risk_factors[]`**: Structured evidence (`code`, `severity`, `evidence`) for audit trails.
7.  **`summary.risk_flag` (Boolean, v1 alias)**: `true` when `risk_level` is `critical`, `high`, or `medium`. Prefer `verdict` / `risk_level` for new hosts.
8.  **`summary.total_token_txs` / `total_internal_txs`**: ERC-20 and internal transfer counts alongside `total_transactions` (normal ETH only).
9.  **`financial_analysis.pnl_eth` / `pnl_usd`**: Profit and Loss on ETH (+ internal ETH). Check `financial_analysis.token_flow` for major ERC-20 volumes.
10. **`network_analysis.risky_counterparties`**: Sanctioned hop-1 peers; `top_10_counterparties` remains volume-ranked.
11. **`metadata.warnings` (Array, optional)**: Incomplete history codes — `etherscan_txlist_*`, `etherscan_tokentx_*`, `etherscan_txlistinternal_*` (`truncated` / `unavailable` / `partial`). Do not present PnL or interaction counts as exhaustive when warnings are set.

## Safety Protocol
*   If **`verdict.decision` is `DENY`** (especially `DIRECT_SANCTIONS_MATCH`): severe warning. Halt automated execution.
*   If **`REVIEW`**: flag for a human; do not auto-trade.
*   If **`ALLOW` / clean**: "✅ Analysis complete. No direct links to sanctions or known malicious contracts were found."
*   **Disclaimer**: Always append: "This analysis is for informational purposes only and does not constitute legal or financial advice."

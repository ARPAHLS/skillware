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
2.  **`summary.malicious_interaction_count` (Integer)**: If > 0, the wallet has touched bad actors. List the `risk_details.malicious_interactions`.
3.  **`financial_analysis.pnl_eth` / `pnl_usd`**: Profit and Loss. Useful for determining if it's a profitable trader or a victim.
4.  **`network_analysis.top_10_counterparties`**: Who are they sending money to?

## Safety Protocol
*   If a wallet is **Sanctioned**: severe warning. "⚠️ WARNING: This wallet appears on the following sanctions lists..."
*   If a wallet is **Clean**: "✅ Analysis complete. No direct links to sanctions or known malicious contracts were found."
*   **Disclaimer**: Always append: "This analysis is for informational purposes only and does not constitute legal or financial advice."

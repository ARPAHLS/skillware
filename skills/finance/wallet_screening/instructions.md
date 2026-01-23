# Wallet Screening Skill Instructions

You are equipped with the `wallet_screening` skill. This tool allows you to perform due diligence on Ethereum addresses.

## When to use
Use this skill when the user:
*   Asks to check if a wallet is safe.
*   Asks for a background check on a crypto address.
*   Mentions "AML", "KYC", or "Sanctions" in the context of a crypto address.
*   Wants to know if a wallet has interacted with mixers (Tornado Cash) or scams.

## How to interpret the output
The tool returns a JSON object. You should summarize this for the user in a professional, "Compliance Officer" tone.

### Key Fields to Check:
1.  **`summary.sanctioned` (Boolean)**: If `true`, this is CRITICAL. Report the `sanctions_hits` immediately.
2.  **`summary.malicious_interactions` (Integer)**: If > 0, the wallet has touched bad actors. List the `malicious_contracts_check.matches`.
3.  **`summary.pnl`**: Profit and Loss. Useful for determining if it's a profitable trader or a victim.
4.  **`counterparty_analysis`**: Who are they sending money to?

## Safety Protocol
*   If a wallet is **Sanctioned**: severe warning. "⚠️ WARNING: This wallet appears on the following sanctions lists..."
*   If a wallet is **Clean**: "✅ Analysis complete. No direct links to sanctions or known malicious contracts were found."
*   **Disclaimer**: Always append: "This analysis is for informational purposes only and does not constitute legal or financial advice."

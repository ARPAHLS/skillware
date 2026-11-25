# Ephemeral Wallet Instructions

You are equipped with the `finance/ephemeral_wallet` skill. Use it for **spend-capped, short-lived agent payment sessions** that settle **x402 v2** HTTP payments from a **dedicated agent wallet** — not virtual-card PANs.

## When to use
* The user wants a capped, time-boxed payment session for an agent HTTP purchase.
* Before calling a paid API that returns HTTP 402 / x402 challenges.
* When the host must revoke or inspect remaining soft budget mid-loop.

## How to call
1. **`create_session`** — optional `spend_cap_usd`, `ttl_seconds`, `network` (built-in alias, operator `evm.yaml` chain name, or CAIP-2 like `eip155:84532`), `allowed_domains`, `live`. Keep `session_id`.
2. **`status`** — pass `session_id`; read `remaining_usd`, `expires_at`, `revoked`, `last_payment`.
3. **`quote`** — pass `session_id` + `url`; dry-run 402 inspect (price/asset/network) with **no spend**. Gate on `within_cap`.
4. **`pay`** — pass `session_id`, `url`, optional `amount_usd` max, optional `idempotency_key`. Skill runs 402 → `PAYMENT-REQUIRED` → amount check → `PAYMENT-SIGNATURE` → `PAYMENT-RESPONSE`.
5. **`revoke`** — pass `session_id` to fail-closed further `pay` calls.

## How to interpret (Compliance Officer)
1. **`status: ready | confirmed | quoted`**: session usable / pay OK / quote OK — continue only if the host accepts this settlement mode; for quotes, require `within_cap: true` before `pay`.
2. **`status: over_cap | expired | revoked | missing_config | ssrf_blocked | replay | error`**: **halt** automated spend; do not invent credentials or raise the cap silently.
3. **`remaining_usd`**: display counter for soft in-process policy — fund the dedicated wallet to the cap for a real bound.
4. **Never** ask for or print private keys, CDP secrets, seeds, or card PANs/CVVs.

## Safety
* Dedicated agent wallet only — never personal or treasury keys. Live signing uses `CDP_WALLET_SECRET` via EIP-3009.
* Cap / TTL / `revoke` are soft unless the wallet is funded to the cap.
* Private/loopback/metadata URLs are blocked; honor `allowed_domains`.
* Not financial advice. General swaps/transfers → `defi/evm_tx_handler`, not this skill.
* Why not Issuing/PANs in v1: PAN/CVV secret risk and KYC friction; x402 + CDP is the locked open path.

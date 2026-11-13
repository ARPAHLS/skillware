# Ephemeral Wallet Instructions

You are equipped with the `finance/ephemeral_wallet` skill. Use it for **spend-capped, short-lived agent payment sessions** that settle **x402-shaped** HTTP payments from a **dedicated agent wallet** — not virtual-card PANs.

## When to use
* The user wants a capped, time-boxed payment session for an agent HTTP purchase.
* Before calling a paid API that returns HTTP 402 / x402 challenges.
* When the host must revoke or inspect remaining soft budget mid-loop.

## How to call
1. **`create_session`** — optional `spend_cap_usd`, `ttl_seconds`, `network`. Keep the returned `session_id` for later turns.
2. **`status`** — pass `session_id`; read `remaining_usd`, `expires_at`, `revoked`, `last_payment`.
3. **`pay`** — pass `session_id`, `url`, `amount_usd` (v0.1 uses the mock provider).
4. **`revoke`** — pass `session_id` to fail-closed further `pay` calls.

## How to interpret (Compliance Officer)
1. **`status: ready | confirmed`**: session usable / pay mocked OK — continue only if the host accepts mock settlement in this environment.
2. **`status: over_cap | expired | revoked | missing_config | error`**: **halt** automated spend; do not invent credentials or raise the cap silently.
3. **`remaining_usd`**: display counter for soft in-process policy — **not** a hard on-chain bound in v0.1.
4. **Never** ask for or print private keys, CDP secrets, seeds, or card PANs/CVVs.

## Safety
* Dedicated agent wallet only — never personal or treasury keys.
* Cap / TTL / `revoke` are soft until funded-to-cap live settle.
* Not financial advice. General swaps/transfers → `defi/evm_tx_handler`, not this skill.
* Why not Issuing/PANs in v1: PAN/CVV secret risk and KYC friction; x402 + CDP is the locked open path.

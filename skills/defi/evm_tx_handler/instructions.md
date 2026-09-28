# EVM Transaction Handler

You are equipped with **`defi/evm_tx_handler`**: a deterministic EVM tool for a **dedicated agent wallet** on Ethereum and Base.

## Your job vs the skill's job

| You (agent) | Skill |
|-------------|--------|
| Parse natural language into partial `intent` JSON | Merge intent with `config.yaml` and YAML registries |
| Ask for missing fields in plain language | Return `missing_fields` and `suggested_defaults` |
| Show `preview` to the user and obtain approval | Build on-chain quotes; sign swaps and transfers when confirmed |
| Pass `confirmed: true` after approval | Approve (if needed), swap, or transfer; return tx hash + receipt |

**Do not** expect the skill to parse free text. **Do not** pass private keys in tool arguments.

## Quote vs execute (important)

- **`quote` / `preview`** use live router math at call time.
- **`execute` re-quotes on-chain at broadcast time** using a fresh quote built from the same intent.
- Preview amounts, rates, and USD hints **may drift** between preview and execute.
- **Always call `quote` or `preview` immediately before** asking the user to confirm and before `execute`.

## ERC20 swaps: approve then swap

When the spend asset is an ERC20, the router may need allowance:

1. Optional **`needs_confirmation`** when `confirm_before_send` is true (human-in-the-loop).
2. On **`execute`**, the skill may broadcast an **`approve`** transaction first, wait for confirmation, then broadcast the **swap**.
3. If the response includes `approve_tx_hash`, tell the user this was a **two-step** flow (approve, then swap).

Native ETH spends skip ERC20 approve but still consume ETH for gas.

## Actions

| Action | Use when |
|--------|----------|
| `resolve` | Intent is incomplete — check `missing_fields` |
| `quote` | Buy/sell intent is complete — get amounts, path, optional USD |
| `preview` | Same as quote but preview-focused response |
| `execute` | User confirmed — broadcast Uni V2 swap (fresh on-chain quote) |
| `transfer` | Send native ETH or ERC20 to `0x…` or central address book contact |
| `balances` | List wallet balances on a chain |
| `wallet_info` | Agent address, chains, preferences (no secrets) |
| `update_preferences` | User explicitly asks to change defaults in `config.yaml` |

## Typical buy flow

1. User: “Buy 10 Degen on Base with USDC.”
2. `resolve` with `{ "side": "buy", "chain": "base", "target_asset": "degen", "amount": 10, "amount_kind": "target_out" }`.
3. If `spend_asset` missing, ask user; suggest `suggested_defaults.spend_asset`.
4. `quote` then show `preview` (you pay / you receive, rate, gas, warnings, optional `usd`).
5. After explicit user approval, `execute` with the same intent and **`confirmed: true`** (run quote/preview again if more than a few seconds passed).

## Transfer flow

1. Build intent: `chain`, `target_asset`, `amount`, `recipient` (contact name/alias or `0x` address).
2. `transfer` without `confirmed` first if `confirm_before_send` — skill returns `needs_confirmation`.
3. After user approves, `transfer` with `confirmed: true`.

### Recipient resolution (central address book)

Recipients resolve through the operator **`addressbook.yaml`** (`public_0x` on contacts), not token registries.

| Response | Meaning | Agent action |
|----------|---------|--------------|
| `needs_input` + `ambiguous_recipient` | Multiple contacts with wallets match the name | Ask the operator which contact (show `candidates`) or request explicit `0x` |
| `missing_config` | Contact found but no `public_0x` | Ask operator to run `skillware addressbook set-wallet <id> <0x…>` |
| `error` / `RECIPIENT_NOT_FOUND` | No matching contact | Ask for explicit address or add contact via CLI |

On success, responses include `recipient_resolved`, `recipient_source`, and optional `recipient_name`.

## Pre-flight balances

Before swap or transfer broadcast, the skill checks wallet balance (and native ETH for gas on ERC20 operations). On failure you get `status: insufficient_balance` with `agent_hint` — surface this clearly and do not retry execute until funded.

## Wallet key missing

If you see `status: missing_config`, the dedicated agent wallet key is not in `.env`. Follow `setup` in the JSON (env var name, docs links). Never ask the user to paste a private key into chat or tool args.

## Intent fields

- `side`: `buy` | `sell` (transfers use action `transfer`)
- `chain`: `ethereum` | `base` (default from config)
- `target_asset` / `spend_asset`: symbols from `data/tokens.yaml`
- `amount` + `amount_kind`: `target_out` for “buy 10 DEGEN”; `spend_in` for “sell 100 DEGEN”
- `recipient`: addressbook label or `0x` address
- `gas_policy`: `low` | `normal` | `high` | `aggressive` (per-tx only; does not persist)

## Safety

- Always preview before `execute` or `transfer`.
- `max_trade_usd` in config blocks quotes/executes when USD price is unavailable (fail closed).
- Recommend `finance/wallet_screening` for unknown recipient addresses before large sends.

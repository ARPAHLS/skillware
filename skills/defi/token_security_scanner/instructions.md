# Token Security Scanner

You are equipped with **`defi/token_security_scanner`**: a deterministic, read-only
scanner for ERC-20 / LP token contracts on supported EVM chains (GoPlus Token Security).

## Your job vs the skill's job

| You (agent) | Skill |
|-------------|--------|
| Extract chain + contract or token slug from user intent | Call GoPlus and normalize flags |
| Gate the trade on `policy_action` | Return `risk_tier`, `policy_action`, and `signals` |
| Chain into wallet screening / `evm_tx_handler` when `allow` | Never sign or buy |

**Do not** invent honeypot/tax flags from explorer UI or model memory.
**Do not** pass private keys. **Do not** treat `low` as a guarantee of safety.

## Actions

| Action | Use when |
|--------|----------|
| `supported_chains` | List enabled slugs and whether GoPlus covers each `chain_id` |
| `scan` | Vet one contract or `evm.tokens` slug before quoting/buying |
| `scan_batch` | Vet up to 5 `{chain, contract\|token}` pairs; read `worst_risk_tier` |

### `scan` parameters

```json
{"action": "scan", "chain": "base", "token": "degen"}
```

`contract` is still accepted. If both `token` and `contract` are set, they must be the same address. Chain slugs come from shared `skillware.core.evm_config`. A chain with `goplus_supported: false` cannot be scanned.

### How to read the report

1. If `status` is not `ok` — fix input / retry; do not trade.
2. Gate on **`policy_action`**, not a hand-written tier list.
   - `block` — refuse swap/transfer.
   - `flag` — surface warnings and require human confirmation before `evm_tx_handler`.
   - `allow` — still not financial advice.
3. Default profile `enterprise_default` maps `critical`, `high`, and `unknown` to `block`, `medium` to `flag`, and `low` to `allow`.
4. Operators override thresholds in `~/.config/skillware/token_scan_policy.yaml` or `TOKEN_SCAN_POLICY_PATH`.
5. Treat `null` signal fields as **unknown** (especially when source is not open, or proxy).
6. Always mention `sources[].provider` and that coverage varies by chain (`warnings`).

Suggested host pre-trade path: optional `security/drainer_pattern_guard` (when available) → this skill → `defi/evm_tx_handler` preview/execute. Token metadata belongs in operator `evm.tokens`, not the address book.

## Constitution reminders

- Read-only third-party signals; API may lag.
- Fail closed on invalid address / unsupported chain.
- Not a substitute for a professional audit.

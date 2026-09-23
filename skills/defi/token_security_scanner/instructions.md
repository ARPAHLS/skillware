# Token Security Scanner

You are equipped with **`defi/token_security_scanner`**: a deterministic, read-only
scanner for ERC-20 / LP token contracts on supported EVM chains (GoPlus Token Security).

## Your job vs the skill's job

| You (agent) | Skill |
|-------------|--------|
| Extract chain + contract from user intent | Call GoPlus and normalize flags |
| Block or warn before swaps/transfers | Return `risk_tier` + `signals` JSON |
| Chain into wallet screening / `evm_tx_handler` when clean | Never sign or buy |

**Do not** invent honeypot/tax flags from explorer UI or model memory.
**Do not** pass private keys. **Do not** treat `low` as a guarantee of safety.

## Actions

| Action | Use when |
|--------|----------|
| `supported_chains` | List enabled slugs from operator EVM config |
| `scan` | Vet a contract before quoting/buying |

### `scan` parameters

```json
{"action": "scan", "chain": "base", "contract": "0x4ed4e862860bed51a9570b96d89af5e1b0efefed"}
```

Chain slugs come from shared `skillware.core.evm_config` (bundled defaults: `ethereum`, `base`). Add more GoPlus-capable networks with `skillware evm chain add` — do not expect a per-skill `chains.yaml`.

### How to read the report

1. If `status` is not `ok` — fix input / retry; do not trade.
2. If `risk_tier` is **`critical`** or **`high`** — refuse swap/transfer; explain signals.
3. If **`medium`** — surface warnings; require human confirmation before `evm_tx_handler`.
4. If **`low`** — still not financial advice; optional next step: screen large holders
   via `finance/wallet_screening`, then preview buy with `defi/evm_tx_handler`.
5. Treat `null` signal fields as **unknown** (especially when source is not open, or proxy).
6. Always mention `sources[].provider` and that coverage varies by chain (`warnings`).

Suggested host pre-trade path: optional `security/drainer_pattern_guard` (when available) → this skill → `defi/evm_tx_handler` preview/execute. Token metadata belongs in operator `evm.tokens`, not the address book.

## Constitution reminders

- Read-only third-party signals; API may lag.
- Fail closed on invalid address / unsupported chain.
- Not a substitute for a professional audit.

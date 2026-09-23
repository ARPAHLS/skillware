# EVM operator config

Shared chain and RPC settings for **defi skills** that call JSON-RPC (`defi/evm_tx_handler`, future `defi/evm_reader`, token scanners, and similar). Operators configure networks once; skills resolve chains through `skillware.core.evm_config`.

**Not the same as:** [`skillware chain`](cli.md#skillware-chain) — that runs **multi-skill orchestration** pipelines from the top-level `chains:` key in YAML. EVM networks live under **`evm:`** / **`evm.yaml`**.

Vocabulary: [glossary — Operator configuration](../glossary.md#operator-configuration).

---

## Fresh install checklist

After `pip install skillware` (add `defi_evm_tx_handler` or `[all]` when using signing skills):

| Step | Required? | What you get |
| :--- | :--- | :--- |
| Bundled defaults in wheel | Automatic | `skillware/data/evm_defaults.yaml` (ethereum, base, …) — read-only |
| RPC URLs in `.env` | **Yes** (live RPC) | `ETHEREUM_RPC_URL`, `BASE_RPC_URL`, or env names referenced in `evm.yaml` |
| `skillware evm init` | **Recommended** | Writable `evm.yaml` under user config |
| `skillware evm chains list` | Optional | Confirm enabled chains and RPC readiness |
| Project `.skillware.yaml` | Optional | Inline `evm.chains` / `evm.tokens` or `evm.config_path` |

**Out of the box (no init):** skills fall back to bundled defaults plus env vars (same behavior as pre-#379 `evm_tx_handler` bundle `data/chains.yaml`). **Writable operator config** requires `evm init` (or manual `evm.yaml`).

### One-time operator setup (typical)

```bash
# 1) RPC secrets (.env — never commit)
#    ETHEREUM_RPC_URL=https://...
#    BASE_RPC_URL=https://...

# 2) Writable chain registry (persists across skillware upgrades)
skillware evm init
skillware evm chains list
skillware evm validate
```

For signing skills (`defi/evm_tx_handler`), also set `AGENT_WALLET_PRIVATE_KEY` in `.env` — see [API keys — EVM RPC](api_keys.md#evm-rpc-and-operator-config) and [EVM Transaction Handler](../skills/evm_tx_handler.md#environment).

---

## Where data lives

| Layer | Location | Notes |
| :--- | :--- | :--- |
| Bundled defaults | `skillware/data/evm_defaults.yaml` | Shipped in wheel; do not edit in `site-packages` |
| User config | `~/.config/skillware/evm.yaml` | Created by `skillware evm init` |
| Global YAML | `~/.config/skillware/config.yaml` | Optional inline `evm:` block |
| Project YAML | `.skillware.yaml` | Optional `evm.config_path` or inline `evm.chains` / `evm.tokens` |
| RPC secrets | `.env` | URLs only — YAML stores **`rpc_env`** names |

On Windows, `~/.config/skillware/` is `%APPDATA%/skillware/`. Data **survives** `pip install --upgrade skillware` unless you delete the folder.

**Precedence (later wins):** bundled defaults → user `evm.yaml` → inline `evm:` / `web3:` blocks in global and project YAML.

**Env override:** `EVM_CONFIG_PATH` → absolute path to an alternate `evm.yaml` file.

---

## CLI reference

Full command list: [`skillware evm`](cli.md#skillware-evm). Interactive menu: **`9` / `evm`**.

| Command | Purpose |
| :--- | :--- |
| `skillware evm` / `evm show` | Resolved path, merge sources, enabled chain count |
| `skillware evm init` | Copy bundled defaults to user `evm.yaml` |
| `skillware evm init --yes` | Non-interactive init (keep bundled enable flags) |
| `skillware evm chains list` | Table: chain, id, enabled, RPC source, RPC ready |
| `skillware evm chain add` | Add a custom network (wizard or flags) |
| `skillware evm tokens list` | Table: chain, symbol, contract address, decimals |
| `skillware evm token add` | Register a custom ERC-20 (`--chain`, `--symbol`, `--address`, `--decimals`) |
| `skillware evm rpc enable <chain>` | Set `enabled: true` on a chain |
| `skillware evm validate` | Schema, duplicate chain IDs, address format |
| `skillware evm open` / `open --dir` | Open file or folder in OS file manager |

Inspect merged settings: `skillware config show` (includes an **evm** block).

---

## Adding a custom chain

**Interactive:**

```bash
skillware evm init          # if you have no evm.yaml yet
skillware evm chain add     # wizard: name, chain_id, rpc_env or rpc_url
```

**Non-interactive example:**

```bash
skillware evm chain add --name arbitrum --chain-id 42161 --rpc-env ARBITRUM_RPC_URL
skillware evm token add --chain base --symbol degen --address 0x4ed4E862860beD51a9570b96d89aF5E1B0Efefed --decimals 18
```

Add matching secret to `.env`:

```bash
export ARBITRUM_RPC_URL="https://arb-mainnet.example.invalid"
```

**Project-only override** (no edit to global `evm.yaml`):

```yaml
# .skillware.yaml
evm:
  chains:
    anvil_local:
      enabled: true
      chain_id: 31337
      rpc_url: "http://127.0.0.1:8545"
      native_symbol: eth
      native_decimals: 18
```

Inline `rpc_url` is intended for **local devnets**. Production chains should use `rpc_env` and keep URLs in `.env`.

---

## Tokens vs people (do not mix)

| Registry | Holds | Example |
| :--- | :--- | :--- |
| **`evm.yaml` → `tokens:`** | ERC-20 contract metadata per chain | USDC, DEGEN addresses + decimals |
| **`addressbook.yaml`** | People and counterparty **EOA** wallets | Contact `public_0x` — [Address book operator config](addressbook_operator_config.md) |

Never put token or router contracts in the address book — name collisions can cause fund loss (see issue #373 design notes).

---

## Python API (for skills and hosts)

```python
from skillware.core.evm_config import (
    load_merged_evm_config,
    resolve_chain,
    resolve_rpc_url,
    normalize_evm_address,
    get_web3,  # requires web3
)

cfg = resolve_chain("base")
url = resolve_rpc_url("base")
# w3 = get_web3("base")  # when web3 is installed
```

Skills should import these helpers rather than duplicating `data/chains.yaml` per bundle ([#379](https://github.com/ARPAHLS/skillware/issues/379)). `defi/evm_tx_handler` merges operator `evm.yaml` at runtime ([#373](https://github.com/ARPAHLS/skillware/issues/373)).

---

## Troubleshooting

| Symptom | Check |
| :--- | :--- |
| `RPC READY: no` in `evm chains list` | Set the env var named in `rpc_env` (for example `ETHEREUM_RPC_URL`) |
| `Chain 'ethereum' is disabled` | `skillware evm rpc enable ethereum` |
| Confused with orchestration | Use `skillware chain list` for pipelines; use `skillware evm chains list` for networks |
| Invalid address on validate | 40 hex chars after `0x`; full EIP-55 when `web3` is installed |
| No writable config | Run `skillware evm init` |

---

## Related docs

- [CLI — skillware evm](cli.md#skillware-evm)
- [API keys — EVM RPC](api_keys.md#evm-rpc-and-operator-config)
- [Address book operator config](addressbook_operator_config.md) — people and `public_0x` (not tokens)
- [EVM Transaction Handler](../skills/evm_tx_handler.md) — signing skill env vars
- [DeFi skills](../skills/README.md#defi) — catalog index
- [Glossary](../glossary.md#operator-configuration)

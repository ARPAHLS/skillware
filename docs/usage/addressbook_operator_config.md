# Shared address book operator config

Cross-skill **contact identity** for mail, defi transfers, and future skills that resolve people by name instead of raw addresses or email strings. Operators configure contacts once in **`addressbook.yaml`**; skills read through `skillware.core.mail_config`.

**Not the same as:**

- **[EVM operator config](evm_operator_config.md)** — ERC-20 **token contracts** and chain RPC under `evm.yaml` → `tokens:` (never put token/router addresses on contacts).
- **[`skillware chain`](cli.md#skillware-chain)** — multi-skill **orchestration** pipelines from top-level `chains:` in YAML.

Vocabulary: [glossary — Operator configuration](../glossary.md#operator-configuration).

---

## Fresh install checklist

After `pip install skillware` (add `office_gmail_handler`, `defi_evm_tx_handler`, or `[all]` when using those skills):

| Step | Required? | What you get |
| :--- | :--- | :--- |
| Bundled empty template in wheel | Automatic | Read-only placeholder inside skill packages |
| `skillware addressbook init` | **Recommended** | Writable `addressbook.yaml` under user config |
| `skillware addressbook add` / `set-wallet` | Optional | Contacts with email, aliases, and/or `public_0x` |
| Project `.skillware.yaml` | Optional | Override `mail.addressbook_path` per repo |

**Out of the box (no init):** skills can **read** the bundled empty template. **Writes** (CLI add, skill `update_addressbook`, `set-wallet`) need a user-writable file from `init`.

### One-time operator setup (typical)

```bash
# 1) Writable contact directory (persists across skillware upgrades)
skillware addressbook init
skillware addressbook add
skillware addressbook set-wallet alice 0x3333333333333333333333333333333333333333

# 2) Inspect
skillware addressbook list
skillware addressbook list --with-wallet
skillware addressbook validate
skillware config show
```

For **mail-only** workflows, `skillware mail addressbook init` is the same file — see [Gmail Handler — address book (mail)](../skills/gmail_handler.md#address-book-mail).

For **defi transfers by name**, contacts need `public_0x` — see [EVM Transaction Handler — transfers by contact name](../skills/evm_tx_handler.md#transfers-by-contact-name).

---

## Where data lives

| Layer | Location | Notes |
| :--- | :--- | :--- |
| User config | `~/.config/skillware/addressbook.yaml` | Created by `skillware addressbook init` |
| Global YAML | `~/.config/skillware/config.yaml` | Optional `mail.addressbook_path` |
| Project YAML | `.skillware.yaml` | Optional `mail.addressbook_path` |
| Bundled template | Inside installed skill wheels | Read-only fallback |
| Env override | `GMAIL_ADDRESSBOOK_PATH` or `EVM_ADDRESSBOOK_PATH` | Same file — aliases for one shared book |

On Windows, `~/.config/skillware/` is `%APPDATA%/skillware/`. Data **survives** `pip install --upgrade skillware` unless you delete the folder.

**Precedence for path resolution:** `GMAIL_ADDRESSBOOK_PATH` / `EVM_ADDRESSBOOK_PATH` → project/global `mail.addressbook_path` → bundled template (read-only) → default user path above.

---

## Contact schema

Each contact is keyed by a stable **`contact_id`** (slug derived from display name unless you set it explicitly):

```yaml
contacts:
  alice:
    display_name: Alice Example
    emails:
      - alice@example.com
    aliases:
      - Ali
      - A. Example
    org: Skillware
    notes: Treasury approver for small sends
    public_0x: "0x3333333333333333333333333333333333333333"

org_domains: {}
```

| Field | Required | Purpose |
| :--- | :--- | :--- |
| `display_name` | Yes | Human label; shown in CLI and disambiguation prompts |
| `emails` | Email **or** `public_0x` | Mail skills resolve names → SMTP recipients |
| `public_0x` | Email **or** `public_0x` | Defi skills resolve names → EVM recipient EOAs |
| `aliases` | No | Extra match tokens (first name, nicknames) |
| `org` | No | Organization label for filtering and future CRM-style skills |
| `notes` | No | Operator-only context (not sent on-chain or in email headers) |
| `org_domains` | No (top-level) | Reserved for future domain → org hints |

Validation (`skillware addressbook validate`):

- At least one of **email** or **`public_0x`** per contact.
- `public_0x` must be a valid EVM address (EIP-55 when `web3` is installed).
- Duplicate wallet or email across contacts is flagged.

---

## Mail vs defi usage

| Skill domain | Resolves | Needs on contact | Skill action |
| :--- | :--- | :--- | :--- |
| **Mail** (`office/gmail_handler`) | Name / alias → email | `emails` | `resolve_recipients`, `send_email` |
| **Defi** (`defi/evm_tx_handler`) | Name / alias / id → EOA | `public_0x` | `transfer` with `recipient: "alice"` |
| **Future** (CRM, notifications, …) | Same YAML | Field-specific | Import `mail_config` helpers |

**Recipient resolution outcomes** (shared `resolve_recipient_query`):

| Status | Meaning | Operator action |
| :--- | :--- | :--- |
| `resolved` | Unique match | Skill proceeds with address or email |
| `needs_input` | Multiple matches | Agent asks user to pick `contact_id` |
| `missing_config` | Contact found, field missing | Add email (mail) or `set-wallet` (defi) |
| `error` | Invalid query | Rephrase or use explicit `0x` / email |

---

## CLI reference

Full command list: [`skillware addressbook`](cli.md#skillware-addressbook). Interactive menu: **`10` / `addressbook`**.

| Command | Purpose |
| :--- | :--- |
| `skillware addressbook` / `list` | Formatted contacts table |
| `skillware addressbook list --with-wallet` | Only contacts with `public_0x` |
| `skillware addressbook list --search john` | Filter by name, alias, email, wallet |
| `skillware addressbook list --json` | Machine-readable export |
| `skillware addressbook init` | Create user `addressbook.yaml` |
| `skillware addressbook add` | Wizard or flags (`--name`, `--email`, `--wallet`, …) |
| `skillware addressbook edit <id>` | Update fields on existing contact |
| `skillware addressbook set-wallet <id> <0x…>` | Attach or update `public_0x` |
| `skillware addressbook remove <id> --yes` | Delete contact |
| `skillware addressbook validate` | Schema and address checks |
| `skillware addressbook open` / `open --dir` | Open file or folder in OS file manager |
| `skillware mail addressbook …` | **Backward-compatible alias** for all mail-prefixed commands |
| `skillware config open` | Open global config directory |

Inspect merged settings: `skillware config show` (includes **mail** paths).

---

## Tokens vs people (do not mix)

| Registry | Holds | Example |
| :--- | :--- | :--- |
| **`evm.yaml` → `tokens:`** | ERC-20 contract metadata | USDC, DEGEN addresses + decimals |
| **`addressbook.yaml`** | People and counterparty **EOA** wallets | Contact `public_0x` |

Never store token contracts, routers, or pool addresses on contacts — name collisions can route funds to the wrong contract. See [EVM operator config — Tokens vs people](evm_operator_config.md#tokens-vs-people-do-not-mix).

---

## Python API (for skills and hosts)

```python
from skillware.core.mail_config import (
    load_merged_mail_settings,
    resolve_addressbook_path,
    load_addressbook_yaml,
    add_addressbook_contact,
    set_addressbook_wallet,
    filter_contacts,
    resolve_recipient_query,
)

mail = load_merged_mail_settings()
path = resolve_addressbook_path(mail=mail)
data = load_addressbook_yaml(path)
result = resolve_recipient_query(data, "alice")
# result["status"] in {"resolved", "needs_input", "missing_config", "error"}
```

Skills should use these helpers rather than duplicating per-bundle `data/addressbook.yaml` files. Legacy bundled labels in `defi/evm_tx_handler/data/addressbook.yaml` still work as a fallback when central config is empty.

---

## Skills that consume the address book

| Skill | Doc | Uses |
| :--- | :--- | :--- |
| `office/gmail_handler` | [Gmail Handler](../skills/gmail_handler.md) | `emails`, aliases → SMTP recipients |
| `defi/evm_tx_handler` | [EVM Transaction Handler](../skills/evm_tx_handler.md) | `public_0x`, aliases → transfer recipients |

Multi-skill recipe (pay on-chain, email receipt): [`examples/pay_and_notify_demo.py`](../../examples/pay_and_notify_demo.py) — edit `CONTACT_QUERY`, `AMOUNT_ETH`, and related constants; prerequisites listed in the script docstring.

When adding a new skill that resolves people by name, import `mail_config` and link back to this guide from the skill catalog page.

---

## Future expansion

The shared schema is intentionally small and YAML-first so operators can extend without framework releases:

- **`org_domains`** — map email domains to organizations for auto-tagging inbound mail.
- **Additional optional fields** — skills can ignore unknown keys; propose new standard fields via issues/PRs before wide adoption.
- **Per-chain wallets** — not in v1; today one `public_0x` per contact (same EOA on L1/L2). Multi-chain contact records may arrive in a later issue if operators need them.
- **Import/export** — use `list --json` today; dedicated import commands can build on the same `add_addressbook_contact` API.

---

## Troubleshooting

| Symptom | Check |
| :--- | :--- |
| Writes fail / read-only path | Run `skillware addressbook init` |
| Mail skill cannot resolve name | Contact needs `emails`; run `addressbook add` or `edit` |
| Transfer returns `missing_config` | Run `skillware addressbook set-wallet <id> <0x…>` |
| Transfer returns `needs_input` | Multiple contacts match — use explicit `contact_id` |
| Wrong registry for USDC address | Token belongs in `evm.yaml` → `tokens:`, not address book |
| Path confusion | `GMAIL_ADDRESSBOOK_PATH` and `EVM_ADDRESSBOOK_PATH` point to the **same** file |

---

## Related docs

- [CLI — skillware addressbook](cli.md#skillware-addressbook)
- [EVM operator config](evm_operator_config.md) — chains, RPC, token registry
- [API keys](api_keys.md) — Gmail App Password, EVM RPC, agent wallet key
- [Gmail Handler](../skills/gmail_handler.md) — mail-specific address book usage
- [EVM Transaction Handler](../skills/evm_tx_handler.md) — transfers by contact name
- [Skill chaining](skill_chaining.md) — multi-skill host orchestration
- [Examples index](../../examples/README.md) — `gemini_gmail_minimal.py`, `pay_and_notify_demo.py`
- [Glossary](../glossary.md#operator-configuration)

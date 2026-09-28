# DeFi Agent Skills

On-chain execution and trading for dedicated agent wallets (structured intent, previews, confirmations).

This hub is the documentation landing page for Skillware **defi** agent skills. Runtime bundles stay at `skills/defi/<skill_name>/` with stable registry IDs `defi/<skill_name>` — do not rename those folders for search indexing.

[Skill Library](../README.md) · [Glossary](../../glossary.md) · [Sitemap](../../sitemap.md) · [Agent loops](../../usage/agent_loops.md)

## Catalog

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[EVM Transaction Handler](evm_tx_handler.md)** | `defi/evm_tx_handler` | `0.3.0` | [@Hendobox](https://github.com/Hendobox) ([@ARPAHLS](https://github.com/ARPAHLS)) | Uni V2 quote, preview, execute, and name-based transfer on Ethereum/Base via central address book. |
| **[Token Security Scanner](token_security_scanner.md)** | `defi/token_security_scanner` | `0.1.0` | [@Hendobox](https://github.com/Hendobox) ([@ARPAHLS](https://github.com/ARPAHLS)) | Read-only GoPlus token honeypot/tax/ownership report before agent trades. |

## Typical host pipelines

- Quote, preview, then execute a Uni V2 swap or transfer from structured intent: `defi/evm_tx_handler`.
- Pre-trade token vet: `defi/token_security_scanner` → `defi/evm_tx_handler` preview/execute (optional future: `security/drainer_pattern_guard` first).
- Screen wallet then trade: `finance/wallet_screening` → `defi/evm_tx_handler` (preview / confirm before broadcast).

## Load by registry ID

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("defi/evm_tx_handler")
skill = bundle["class"]()
```

See the [Skill library](../README.md) for every category, and [install extras](../../usage/install_extras.md) for per-skill pip extras.

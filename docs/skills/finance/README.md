# Finance Agent Skills

Tools for financial analysis, blockchain interaction, and regulatory compliance.

This hub is the documentation landing page for Skillware **finance** agent skills. Runtime bundles stay at `skills/finance/<skill_name>/` with stable registry IDs `finance/<skill_name>` — do not rename those folders for search indexing.

[Skill Library](../README.md) · [Glossary](../../glossary.md) · [Sitemap](../../sitemap.md) · [Agent loops](../../usage/agent_loops.md)

## Catalog

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Wallet Screening](wallet_screening.md)** | `finance/wallet_screening` | `1.0.1` (23 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Comprehensive risk assessment for Ethereum wallets. Checks sanctions lists (OFAC, FBI) and identifies interactions with malicious contracts (Mixers, Scams). |
| **[UK Companies House Handler](uk_companies_house_handler.md)** | `finance/uk_companies_house_handler` | `1.3.0` (17 Sep 2026) | [@Areen-09](https://github.com/Areen-09) ([@ARPAHLS](https://github.com/ARPAHLS)) | Deterministic UK Companies House API handler: company search, officers with deterministic role/name filtering, PSC, filing history with helpers, and turn-by-turn pipeline orchestration. |

## Typical host pipelines

- Screen an Ethereum address against OFAC / FBI / mixer lists before a host agent acts: `finance/wallet_screening`.
- UK entity diligence: `finance/uk_companies_house_handler` `run_pipeline` (resolve → officers → filings).

## Load by registry ID

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("finance/wallet_screening")
skill = bundle["class"]()
```

See the [Skill library](../README.md) for every category, and [install extras](../../usage/install_extras.md) for per-skill pip extras.

# Monitoring Agent Skills

Observability and guardrails for long-running autonomous agent loops.

This hub is the documentation landing page for Skillware **monitoring** agent skills. Runtime bundles stay at `skills/monitoring/<skill_name>/` with stable registry IDs `monitoring/<skill_name>` — do not rename those folders for search indexing.

[Skill Library](../README.md) · [Glossary](../../glossary.md) · [Sitemap](../../sitemap.md) · [Agent loops](../../usage/agent_loops.md)

## Catalog

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Token Limiter](token_limiter.md)** | `monitoring/token_limiter` | `1.0.0` (16 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Deterministic token budget gate that returns CONTINUE, WARN, or FORCE_TERMINATE for host loops. |
| **[KPI Gate](kpi_gate.md)** | `monitoring/kpi_gate` | `0.1.0` (29 Aug 2026) | [@mrmasa88](https://github.com/mrmasa88) ([AO](https://github.com/0x-AO-Protocol)) | Deterministic business-KPI gate evaluating a metrics snapshot against a policy charter with fail-closed findings (issue #317). |

## Typical host pipelines

- Token budget for long-running host loops: `monitoring/token_limiter` (`CONTINUE` / `WARN` / `FORCE_TERMINATE`).
- Fail-closed business KPIs before the loop continues: `monitoring/kpi_gate`.

## Load by registry ID

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("monitoring/token_limiter")
skill = bundle["class"]()
```

See the [Skill library](../README.md) for every category, and [install extras](../../usage/install_extras.md) for per-skill pip extras.

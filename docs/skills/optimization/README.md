# Optimization Agent Skills

Middleware skills that operate on text or state to increase performance, security, or efficiency.

This hub is the documentation landing page for Skillware **optimization** agent skills. Runtime bundles stay at `skills/optimization/<skill_name>/` with stable registry IDs `optimization/<skill_name>` — do not rename those folders for search indexing.

[Skill Library](../README.md) · [Glossary](../../glossary.md) · [Sitemap](../../sitemap.md) · [Agent loops](../../usage/agent_loops.md)

## Catalog

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Prompt Compressor](prompt_compressor.md)**        | `optimization/prompt_compressor` | `1.0.0` (20 Nov 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Deterministic, offline prompt compression with protected code/JSON/templates, rule deduplication, cache-aware modes, and `target_tokens` budgeting. |
| **[Context Window Optimizer](context_optimizer.md)** | `optimization/context_optimizer` | `0.1.0` (16 Sep 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Query-aware extractive selection — local embeddings score document chunks against agent_goal and return only relevant spans.                        |

## Typical host pipelines

- Shrink a large document to the spans that match `agent_goal`: `optimization/context_optimizer`.
- Compress the selected spans further when they still blow the budget: optimizer → `optimization/prompt_compressor`.
- Untrusted documents: `security/prompt_injection_firewall` before either optimization skill.

## Load by registry ID

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("optimization/prompt_compressor")
skill = bundle["class"]()
```

See the [Skill library](../README.md) for every category, and [install extras](../../usage/install_extras.md) for per-skill pip extras.

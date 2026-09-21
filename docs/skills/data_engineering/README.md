# Data Engineering Agent Skills

Skills tailored for generating, parsing, and orchestrating large datasets for machine learning or analytics workflows.

This hub is the documentation landing page for Skillware **data engineering** agent skills. Runtime bundles stay at `skills/data_engineering/<skill_name>/` with stable registry IDs `data_engineering/<skill_name>` — do not rename those folders for search indexing.

[Skill Library](../README.md) · [Glossary](../../glossary.md) · [Sitemap](../../sitemap.md) · [Agent loops](../../usage/agent_loops.md)

## Catalog

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Synthetic Data Generator](synthetic_generator.md)** | `data_engineering/synthetic_generator` | `0.1.1` (9 Sep 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Generates high-entropy structured synthetic data for model fine-tuning to avoid mode collapse. |
| **[Novelty Extractor](novelty_extractor.md)** | `data_engineering/novelty_extractor` | `0.1.0` (16 Jul 2026) | [@rizzoMartin](https://github.com/rizzoMartin) ([@ARPAHLS](https://github.com/ARPAHLS)) | Filters a text dataset by semantic novelty, retaining only chunks that carry new information above a configurable threshold. |
| **[Semantic Web Proxy](semantic_web_proxy.md)** | `data_engineering/semantic_web_proxy` | `0.1.0` (5 Sep 2026) | [@rizzoMartin](https://github.com/rizzoMartin) ([@ARPAHLS](https://github.com/ARPAHLS)) | Converts a live web page or raw HTML into token-efficient Markdown, text, or JSON, stripping boilerplate behind an SSRF guard and reporting estimated token savings. |

## Typical host pipelines

- Fetch a page to token-efficient Markdown, then keep only novel chunks: `data_engineering/semantic_web_proxy` → `data_engineering/novelty_extractor`.
- Build a fine-tune corpus: `data_engineering/synthetic_generator` (optional Gemini / Anthropic backends).

## Load by registry ID

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("data_engineering/synthetic_generator")
skill = bundle["class"]()
```

See the [Skill library](../README.md) for every category, and [install extras](../../usage/install_extras.md) for per-skill pip extras.

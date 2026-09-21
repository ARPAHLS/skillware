# Compliance Agent Skills

Enforces privacy, guardrails, and secure handling of sensitive data before it reaches external endpoints.

This hub is the documentation landing page for Skillware **compliance** agent skills. Runtime bundles stay at `skills/compliance/<skill_name>/` with stable registry IDs `compliance/<skill_name>` — do not rename those folders for search indexing.

[Skill Library](../README.md) · [Glossary](../../glossary.md) · [Sitemap](../../sitemap.md) · [Agent loops](../../usage/agent_loops.md)

## Catalog

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[PII Masker](pii_masker.md)** | `compliance/pii_masker` | `0.1.0` (20 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | High-precision, local PII (Personally Identifiable Information) detection and redaction using the micro-f1-mask model. |
| **[MiCA Module](mica_module.md)** | `compliance/mica_module` | `0.1.1` (9 Sep 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Self-contained local Policy Enforcement and RAG engine strictly adhering to MiCA crypto-asset regulation. |
| **[Terms of Service Evaluator](tos_evaluator.md)** | `compliance/tos_evaluator` | `0.1.1` (9 Sep 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Local-first evaluation of robots.txt and website legal pages to decide whether an intended automated action appears permissible. |

## Typical host pipelines

- Redact PII locally before text leaves the host process: `compliance/pii_masker`.
- Check crypto-asset intent against bundled MiCA policy: `compliance/mica_module`.
- Confirm an automated fetch looks permitted, then scrape: `compliance/tos_evaluator` → `data_engineering/semantic_web_proxy`.

## Load by registry ID

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("compliance/pii_masker")
skill = bundle["class"]()
```

See the [Skill library](../README.md) for every category, and [install extras](../../usage/install_extras.md) for per-skill pip extras.

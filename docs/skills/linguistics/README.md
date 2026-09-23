# Linguistics Agent Skills

Language adapters: curated lexicons so host agents can interpret and produce informal, internet-native language that foundation models routinely miss.

This hub is the documentation landing page for Skillware **linguistics** agent skills. Runtime bundles stay at `skills/linguistics/<skill_name>/` with stable registry IDs `linguistics/<skill_name>` — do not rename those folders for search indexing.

[Skill Library](../README.md) · [Glossary](../../glossary.md) · [Sitemap](../../sitemap.md) · [Agent loops](../../usage/agent_loops.md)

## Catalog

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Korean Slang](korean_slang.md)** | `linguistics/korean_slang` | `0.1.0` (19 Sep 2026) | [@bd-c3](https://github.com/bd-c3) ([@ARPAHLS](https://github.com/ARPAHLS)) | Offline Korean Gen-Z slang interpreter and peer-register generator (September 2026 pack). |

## Typical host pipelines

- Interpret or produce Korean Gen-Z slang / internet register: `linguistics/korean_slang`.
- Untrusted comment fields: `security/prompt_injection_firewall` then `linguistics/korean_slang`.

## Load by registry ID

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("linguistics/korean_slang")
skill = bundle["class"]()
```

See the [Skill library](../README.md) for every category, and [install extras](../../usage/install_extras.md) for per-skill pip extras.

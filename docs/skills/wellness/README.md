# Wellness Agent Skills

Supportive coaching guardrails, crisis triage, and grounded psychoeducation for host agents.

This hub is the documentation landing page for Skillware **wellness** agent skills. Runtime bundles stay at `skills/wellness/<skill_name>/` with stable registry IDs `wellness/<skill_name>` — do not rename those folders for search indexing.

[Skill Library](../README.md) · [Glossary](../../glossary.md) · [Sitemap](../../sitemap.md) · [Agent loops](../../usage/agent_loops.md)

## Catalog

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Mental Coach](mental_coach.md)** | `wellness/mental_coach` | `0.1.1` (9 Sep 2026) | [@mrmasa88](https://github.com/mrmasa88) ([AO](https://github.com/0x-AO-Protocol)) | Deterministic wellness coaching firewall with crisis triage, scope limits, and cited KB retrieval. |

## Typical host pipelines

- Crisis triage and scoped coaching so the host agent does not invent clinical advice: `wellness/mental_coach`.
- Untrusted chat: `security/prompt_injection_firewall` then `wellness/mental_coach`.

## Load by registry ID

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("wellness/mental_coach")
skill = bundle["class"]()
```

See the [Skill library](../README.md) for every category, and [install extras](../../usage/install_extras.md) for per-skill pip extras.

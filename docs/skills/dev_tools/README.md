# Dev Tools Agent Skills

Skills that assist developers in understanding codebases, planning changes, and resolving issues across any repository.

This hub is the documentation landing page for Skillware **dev tools** agent skills. Runtime bundles stay at `skills/dev_tools/<skill_name>/` with stable registry IDs `dev_tools/<skill_name>` — do not rename those folders for search indexing.

[Skill Library](../README.md) · [Glossary](../../glossary.md) · [Sitemap](../../sitemap.md) · [Agent loops](../../usage/agent_loops.md)

## Catalog

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Issue Resolver](issue_resolver.md)** | `dev_tools/issue_resolver` | `0.3.0` (3 Aug 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | GitHub issue URL prep, optional caller-fetched repository profiles, nine-stage agent workflow, conditional verify/commit gates, and commit-message validation. |

## Typical host pipelines

- Turn a GitHub issue URL into a staged, gated resolve workflow: `dev_tools/issue_resolver`.
- Long loops: pair with `monitoring/token_limiter` so the host agent stops on budget.

## Load by registry ID

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("dev_tools/issue_resolver")
skill = bundle["class"]()
```

See the [Skill library](../README.md) for every category, and [install extras](../../usage/install_extras.md) for per-skill pip extras.

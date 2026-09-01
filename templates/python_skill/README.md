# My Awesome Skill

Starter bundle under `skills/<category>/<skill_name>/`. Copy this template from `templates/python_skill/`, then replace every placeholder before opening a PR.

Roles: [Skill anatomy](../../docs/introduction.md#skill-anatomy) — **Contract** (`manifest.yaml`), **Effect** (`skill.py`), **Directive** (`instructions.md`), **Assurance** (`test_skill.py`), optional **Presentation** (`card.json`).

## Before you submit

1. **Rename** the folder to match your skill ID (e.g. `skills/finance/my_skill`).
2. **Packaging**: Add empty `__init__.py` files in `skills/<category>/` (new categories only) and in your skill folder so PyPI wheels include the full bundle. List runtime packages in `manifest.yaml` `requirements` (PEP 508; pin with `>=` when the skill needs a minimum version — see [Install extras](../../docs/usage/install_extras.md#loader-behavior)), then run `python scripts/sync_extras.py` to update optional extras in `pyproject.toml`.
3. **`manifest.yaml` (Contract)**: Set real `name` to the full registry ID (`category/skill_name`, matching the folder path), `version`, `description`, `short_description`, `parameters`, `constitution`, and `issuer` (`name` + `email` required; `github` / `org` optional). `SkillLoader.load_skill()` warns when `name` diverges from the path under registry layout; flat private layouts (`skills/<skill_name>/`) are not validated.
4. **`skill.py` (Effect)**: Implement deterministic logic with exactly one `BaseSkill` subclass (loaded as `bundle["class"]`); no LLM-generated code in the skill body. Co-located helpers (effect modules) may live in the same folder if imported only by `skill.py`.
5. **`instructions.md` (Directive)**: Tell the host when and how to use the tool (skill context, not host persona).
6. **`card.json` (Presentation)**: Mirror `issuer` from the manifest; customize UI fields.
7. **`test_skill.py` (Assurance)**: Bundle test (required; enforced by `tests/test_skill_issuer.py`); offline, mock external services, including HTTP clients, LLM APIs, embedding/model loaders, and any first-run model downloads; run `pytest skills/<category>/<skill_name>/test_skill.py` or `skillware test <category>/<skill_name>`. See [TESTING.md](../../docs/TESTING.md).
8. **`docs/skills/<skill_name>.md`**: Catalog page with **ID**, **Issuer**, **Version**, **Recommended install** (`pip install "skillware[<category>_<skill>]"`), optional **Bundle layout**, **Usage Examples** (all providers; see `docs/usage/skill_usage_template.md`), and **Skill history** (linked GitHub contributors).
9. **`docs/skills/README.md`**: Add a row (Skill, ID, **Version**, Issuer, Description).

Do not commit template placeholders (`Your Name`, `you@example.com`, `YOUR ORG`, etc.) under `skills/`—only real issuer details belong in the registry.

## Issuer block (manifest.yaml)

See [Issuer org](../../CONTRIBUTING.md#issuer-org) for when to set `org: ARPAHLS`, a contributor org, comma-separated co-affiliations, or omit.

```yaml
issuer:
  name: Your Name
  email: you@example.com
  github: your_github_username
  org: YOUR ORG
```

## Inputs

- `param1`: Description...

## Outputs

- `result`: Description...

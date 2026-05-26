# My Awesome Skill

Starter bundle under `skills/<category>/<skill_name>/`. Copy this template from `templates/python_skill/`, then replace every placeholder before opening a PR.

## Before you submit

1. **Rename** the folder to match your skill ID (e.g. `skills/finance/my_skill`).
2. **Packaging**: Add empty `__init__.py` files in `skills/<category>/` (new categories only) and in your skill folder so PyPI wheels include the full bundle. No `pyproject.toml` changes per skill.
3. **`manifest.yaml`**: Set real `name`, `version`, `description`, `short_description`, `parameters`, `constitution`, and `issuer` (`name` + `email` required; `github` / `org` optional).
4. **`skill.py`**: Implement deterministic logic; no LLM-generated code in the skill body.
5. **`instructions.md`**: Tell the agent when and how to use the tool.
6. **`card.json`**: Mirror `issuer` from the manifest; customize UI fields.
7. **`test_skill.py`**: Add tests; run `pytest skills/<category>/<skill_name>/test_skill.py`.
8. **`docs/skills/<skill_name>.md`**: Catalog page with **ID**, **Issuer**, and **Usage Examples** (all providers; see `docs/usage/skill_usage_template.md`).
9. **`docs/skills/README.md`**: Add a row to the skill library table.

Do not commit template placeholders (`Your Name`, `you@example.com`, `YOUR ORG`, etc.) under `skills/`—only real issuer details belong in the registry.

## Issuer block (manifest.yaml)

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

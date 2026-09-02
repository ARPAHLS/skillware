## Description

<!--
Summarize what this PR does and why it is needed. Link the issue (Fixes #123 or Refs #123).
Agents: map each acceptance criterion to a file or test in your diff.
-->

### Type of Change

- [ ] **New Skill** — new registry bundle under `skills/`
- [ ] **Skill Upgrade** — changes to an existing skill under `skills/`
- [ ] **Bug Fix** — incorrect runtime or framework behavior
- [ ] **Documentation** — docs, README, CONTRIBUTING only
- [ ] **Framework Feature** — `skillware/core/` loader, env, adapters
- [ ] **CLI** — `skillware/cli.py`, `docs/usage/cli.md`
- [ ] **Examples** — `examples/*.py`, agent loops, `examples/README.md`
- [ ] **Packaging** — PyPI wheel, `pyproject.toml`, `MANIFEST.in`
- [ ] **RFC / meta** — templates, labels, CI, or large design doc

## Checklist (all PRs)

- [ ] Linked GitHub issue (`Fixes #…` or `Refs #…`)
- [ ] Scope matches the issue — no unrelated refactors
- [ ] `python -m black --check .` and `flake8` pass locally (or CI-equivalent subset)
- [ ] `pytest skills/` and `pytest tests/` pass locally when relevant
- [ ] `CHANGELOG.md` updated under `[Unreleased]` when user-visible behavior changes
- [ ] `examples/README.md` updated if this PR adds, renames, or removes a runnable script
- [ ] Ran `pytest tests/test_registry_docs.py` when skills, examples index, or agent-loops matrix changed

## New or updated skill

Skip unless this PR adds or changes files under `skills/`.

### Bundle and metadata

- [ ] Skill at `skills/<category>/<skill_name>/` (from `templates/python_skill/` or equivalent)
- [ ] `manifest.yaml`: `name` (full ID), `version`, `description`, `parameters`, `constitution`, real `issuer`
- [ ] Optional: `short_description`, `issuer.github`, `issuer.org`, `requirements`, `env_vars`

### Effect, Directive, Assurance

- [ ] Deterministic `skill.py` (Effect; no ad-hoc LLM-generated execution paths)
- [ ] `instructions.md` (Directive) explains when and how to use the skill
- [ ] `card.json` (Presentation) issuer matches manifest when present
- [ ] `test_skill.py` (Assurance) covers execution and schema expectations
- [ ] `SkillLoader.load_skill("<category>/<skill_name>")` succeeds (or deps documented)

### Documentation and catalog

- [ ] `docs/skills/<skill_name>.md` and row in `docs/skills/README.md`
- [ ] Usage Examples for Gemini, Claude, OpenAI, DeepSeek, Ollama per [skill usage template](docs/usage/skill_usage_template.md)

## Constitution and safety (skills only)

<!--
Example: read-only API access; no transaction signing without explicit confirmation.
-->

## Related Issues

<!-- Fixes #123 -->

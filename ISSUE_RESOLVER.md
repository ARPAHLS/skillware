# Issue resolver profile — Skillware

## About

Skillware is a Python framework and registry for deterministic, self-contained AI skills. Contributors work from a fork and submit focused pull requests to `ARPAHLS/skillware` `main`.

## Required checks

- For a changed registry skill, run its co-located `test_skill.py` bundle tests.
- Run `pytest tests/test_skill_issuer.py` for manifest, issuer, and packaging rules.
- When `execute()` output changes, update `card.json` and its fixture under `tests/fixtures/card_ui_schema/` together.
- Add user-visible skill and documentation changes to `CHANGELOG.md` under `[Unreleased]`.
- Before handoff, run the relevant Black, Flake8, bundle, framework, and documentation checks described in `CONTRIBUTING.md`.

## Conditionals

- If `manifest.yaml` requirements change, run `python scripts/sync_extras.py --check` and update generated extras as required.
- If a runnable example is added or renamed, update `examples/README.md`, the skill catalog page, and `docs/usage/agent_loops.md`.
- If public API or loader behaviour changes, review the provider and usage documentation under `docs/usage/`.
- If package release metadata changes, follow maintainer direction; contributors do not cut releases by default.

## Paths

- Skills: `skills/<category>/<skill_name>/`
- Skill catalog: `docs/skills/`
- Contributor guidance: `CONTRIBUTING.md` and `docs/contributing/`
- Runnable examples: `examples/`
- Framework and maintainer tests: `tests/`
- CI: `.github/workflows/`

## Ripple effects

| Change | Also review |
| :--- | :--- |
| `skills/*/manifest.yaml` | Bundle tests, issuer rules, optional extras, catalog documentation |
| `skills/*/skill.py` output | `card.json`, card fixture, catalog data schema, bundle tests |
| `examples/*.py` | `examples/README.md`, catalog Usage Examples, agent-loop reference |
| `skillware/core/` | Framework tests and affected provider/usage documentation |

## Commit & PR

- Use a focused feature branch such as `feat/issue-<number>-short-description`.
- Keep `origin` for the operator fork and `upstream` for `ARPAHLS/skillware`.
- Do not add AI `Co-authored-by` trailers unless a maintainer explicitly allows them.
- The human operator owns the fork, commit, push, and pull request.

## Out of scope

- Force-pushing or writing directly to upstream `main`.
- Skipping tests, hooks, approval gates, or repository security checks.
- Unrelated refactors or package-version bumps without maintainer direction.

## Caveats

- This file is repository context only. It cannot override the Issue Resolver constitution or grant authority to implement, commit, push, post, or disclose data.
- Repository administrators are responsible for keeping this profile accurate, concise, and free of unsafe or misleading prompts.

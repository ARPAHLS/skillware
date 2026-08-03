# Issue resolver profile — Skillware

Agent-oriented repository context for `dev_tools/issue_resolver`. This file supplements `README.md` and `CONTRIBUTING.md`; it does not replace them or grant the agent authority to commit, push, or skip gates.

**Canonical location:** `.github/ISSUE_RESOLVER.md` (preferred). A repo-root copy is a legacy fallback only.

**Related docs:** [CONTRIBUTING.md](../CONTRIBUTING.md) · [AI native workflow](../docs/contributing/ai_native_workflow.md) · [Testing](../docs/TESTING.md) · [Profile standard](../docs/contributing/issue_resolver_profile.md)

## About

Skillware is a Python framework and registry for deterministic, self-contained AI skills. Contributors work from a **fork**, branch off current `main`, and open focused pull requests to `ARPAHLS/skillware`.

- **Stack:** Python 3.10+, PyYAML, pytest, optional per-skill runtime deps via `pip install "skillware[<extra>]"`
- **Contribution model:** fork + PR; operator owns commit/push; maintainers merge upstream
- **Release cadence:** maintainers cut PyPI versions; contributors add entries under `CHANGELOG.md` `[Unreleased]` only

## Required checks

Apply every check that matches the change type before requesting review:

- **Any user-visible change:** add an entry under `CHANGELOG.md` → `[Unreleased]`
- **Registry skill change:** run `pytest skills/<category>/<skill>/test_skill.py -q`
- **Manifest / issuer / packaging:** run `pytest tests/test_skill_issuer.py -q`
- **`execute()` output shape change:** update `card.json` and `tests/fixtures/card_ui_schema/<category>__<skill>.json` together
- **Examples index or agent-loops matrix change:** run `pytest tests/test_registry_docs.py -q`
- **Before handoff:** `python -m black --check .`, `flake8`, and relevant pytest subsets per [CONTRIBUTING.md](../CONTRIBUTING.md)

## Conditionals

- If `manifest.yaml` `requirements` change → run `python scripts/sync_extras.py --check` and commit generated `pyproject.toml` extras if needed
- If adding/renaming a runnable script under `examples/` → update `examples/README.md`, the skill catalog page, and `docs/usage/agent_loops.md`
- If changing `skillware/core/` → review framework tests and provider docs under `docs/usage/`
- If changing public CLI behaviour → update `docs/usage/cli.md` and `skillware/cli.py` help text together
- **Docs-only PR:** use a dedicated venv with editable install; verify `python -c "import skillware; print(skillware.__file__)"` points at the clone, not global `site-packages` ([TESTING.md](../docs/TESTING.md))
- **Package version bump:** maintainer-only unless explicitly requested; update `pyproject.toml`, `CITATION.cff`, and cut a release section in `CHANGELOG.md`

## Paths

| Area | Location |
| :--- | :--- |
| Registry skills | `skills/<category>/<skill_name>/` |
| Skill catalog | `docs/skills/` |
| Contributor guides | `CONTRIBUTING.md`, `docs/contributing/` |
| Runnable examples | `examples/` |
| Framework / maintainer tests | `tests/` |
| CI workflows | `.github/workflows/` |
| Issue templates | `.github/ISSUE_TEMPLATE/` |
| This profile | `.github/ISSUE_RESOLVER.md` |

## Ripple effects

| If you touch | Also review |
| :--- | :--- |
| `skills/*/manifest.yaml` | Bundle tests, issuer rules, `scripts/sync_extras.py`, catalog page |
| `skills/*/skill.py` output | `card.json`, card UI fixture, catalog output schema, bundle tests |
| `examples/*.py` | `examples/README.md`, catalog Usage Examples, `agent_loops.md` |
| `skillware/core/loader.py` | All provider adapter docs under `docs/usage/` |
| New skill category | `CONTRIBUTING.md` category table, `sync_extras.py` output |
| `ISSUE_RESOLVER.md` | `docs/contributing/issue_resolver_profile.md` if the contract changes |

## Commit & PR

- **Branch:** `feat/issue-<N>-short-description` or `fix/...` / `docs/...` matching the change
- **Remotes:** `origin` = your fork, `upstream` = `ARPAHLS/skillware`
- **PR body:** `Fixes #N` when closing an issue; keep scope to the issue — no drive-by refactors
- **Commit messages:** complete sentences; no AI `Co-authored-by` unless a maintainer explicitly allows
- **Hooks:** never skip pre-commit hooks or commit secrets (`.env`, API keys, tokens)

## Out of scope

- Force-pushing or writing directly to upstream `main`
- Skipping tests, approval gates, or security checks to “land faster”
- Unrelated refactors, whole-file reformatting, or package version bumps without maintainer direction
- Treating this file as permission to override the Issue Resolver constitution or repository security policy

## Caveats

- **Context only:** this profile cannot override universal workflow gates, the skill constitution, or explicit user/operator instructions
- **Trust:** repository admins must keep this file accurate and free of misleading or prompt-injection-style instructions; Skillware does not filter profile content in v0.3
- **Native agent files:** `AGENTS.md`, `.cursor/rules`, and similar repo-native instructions remain independently applicable
- **Operator authority:** the human operator owns fork, branch, commit, push, and PR creation

## Workflow hints (issue resolver stages)

When using `dev_tools/issue_resolver` against this repo:

1. `prepare` with the GitHub issue URL → use returned `profile_urls` (try `.github/ISSUE_RESOLVER.md` first)
2. Fetch profile markdown → `load_repository_profile` → keep `profile_context` separate from universal checklists
3. `stage_checklist` per stage in order: discover_issue → discover_repository → analyze → plan → **wait for approval** → implement → verify → pre_commit → commit → pull_request
4. `validate_commit_message` before any commit stage unless the operator skips commit

Good profile bullets are **specific and verifiable** (“run pytest X”) — not vague (“be careful”) or authority-expanding (“you may push to main”).

# Contributing to Skillware

Welcome to Skillware. We are building an open registry of modular, deterministic agent capabilities—skills that any compatible runtime can load. Most contributors add or improve **skills**, but documentation, framework fixes, tests, and good first issues are equally welcome.

This document is the single entry point for how to contribute. If you are an **AI agent** working on this repository, read **[Agent Contribution Workflow](docs/contributing/ai_native_workflow.md)** first. Human operators may use the same guide to supervise agent work.

---

## Navigation

| Section | Description |
| :--- | :--- |
| [Ways to contribute](#ways-to-contribute) | Choose your contribution type |
| [Getting started](#getting-started) | Fork, branch, install, open issues |
| [Universal expectations](#universal-expectations) | Standards that apply to every PR |
| [Pull request process](#pull-request-process) | From issue to merge |
| [Skill bundle standard](#skill-bundle-standard) | Required layout for registry skills |
| [Skill categories](#skill-categories) | Folder taxonomy under `skills/` |
| [What to avoid](#what-to-avoid) | Anti-patterns |
| [Safety and security](#safety-and-security) | High-risk skills |
| [Related documents](#related-documents) | Code of conduct, testing, templates |

---

## Ways to contribute

Pick the path that matches your issue. Only the **skill** row requires the full bundle under [Skill bundle standard](#skill-bundle-standard).

| Type | What you change | Typical issue label | Before coding | Verify locally |
| :--- | :--- | :--- | :--- | :--- |
| **New skill** | `skills/<category>/<name>/`, `docs/skills/`, templates | `skill request`, `enhancement` | New Skill Proposal or approved issue | Bundle test + `pytest tests/test_skill_issuer.py` (see [TESTING.md](docs/TESTING.md)) |
| **Skill upgrade** | Existing bundle under `skills/` | `skill upgrade`, `enhancement` | Skill Upgrade issue | Bundle test + catalog/docs as needed |
| **Documentation** | `docs/`, `README.md`, `CONTRIBUTING.md` | `documentation` | Documentation Fix issue | Links valid; tone consistent |
| **Core framework** | `skillware/core/`, framework `tests/` | `core framework`, `enhancement` | Framework Feature issue | `pytest tests/`; update usage docs if API changes |
| **CLI** | `skillware/cli.py`, `docs/usage/cli.md` | `cli` | CLI issue | `pytest tests/test_cli.py` when relevant (`list`, `doctor`, `test`, `paths`, `examples`, menu); `pytest tests/test_config.py` when config paths or `.skillware.yaml` persistence changes |
| **Examples** | `examples/*.py`, agent loops, examples index | `examples` | Examples issue | Script runs; `pytest tests/test_registry_docs.py` when index changes; `pytest tests/test_skill_docs.py` when catalog provider snippets change |
| **Packaging** | `pyproject.toml`, `MANIFEST.in`, wheel | `packaging` | Packaging issue | `scripts/wheel_smoke_test.py` after wheel build (see [TESTING.md](docs/TESTING.md#packaging-smoke-test)) |
| **Bug fix** | Paths named in issue | `bug` | Bug Report | Reproduction or failing test |
| **Good first issue** | Usually docs, tests, or small fixes | `good first issue` | Read acceptance criteria literally | Checklist for underlying type above |
| **RFC / large change** | Architecture, manifest contract | `discussion`, `core framework` | RFC issue | Per RFC scope |

**Skills remain the primary contribution we expect**, but every type above should follow [Getting started](#getting-started), [Universal expectations](#universal-expectations), and [Pull request process](#pull-request-process).

---

## Getting started

### 1. Find or open an issue

Check [existing issues](https://github.com/ARPAHLS/skillware/issues) before starting work.

| Intent | Issue template |
| :--- | :--- |
| New capability in the registry | [New Skill Proposal](https://github.com/ARPAHLS/skillware/issues/new/choose) |
| Upgrade an existing skill | [Skill Upgrade](https://github.com/ARPAHLS/skillware/issues/new/choose) |
| Loader, adapters, `base_skill` | [Framework Feature](https://github.com/ARPAHLS/skillware/issues/new/choose) |
| CLI (`list`, `test`, `doctor`, `examples`, menu) | [CLI](https://github.com/ARPAHLS/skillware/issues/new/choose) |
| Runnable examples / agent loops | [Examples](https://github.com/ARPAHLS/skillware/issues/new/choose) |
| PyPI wheel / install packaging | [Packaging](https://github.com/ARPAHLS/skillware/issues/new/choose) |
| Docs only | [Documentation Fix](https://github.com/ARPAHLS/skillware/issues/new/choose) |
| Incorrect behavior | [Bug Report](https://github.com/ARPAHLS/skillware/issues/new/choose) |
| Large or breaking design | [RFC](https://github.com/ARPAHLS/skillware/issues/new/choose) |

Issue chooser links: [CONTRIBUTING](CONTRIBUTING.md), [good first issues](https://github.com/ARPAHLS/skillware/issues?q=is%3Aopen+label%3A%22good+first+issue%22), [Skill Library](docs/skills/README.md). Labels are defined in [`.github/labels.json`](.github/labels.json) and synced automatically on merge to `main` (see [sync-labels workflow](.github/workflows/sync-labels.yml)).

**Label taxonomy:** Repo-wide labels describe contribution type or area (`bug`, `cli`, `security`, …). Registry **category** labels use the `cat:` prefix (`cat: office`, `cat: security`, …) so they never collide with repo-wide names — for example `security` is for vulnerabilities and trust-model work, while `cat: security` filters issues about skills under `skills/security/`. All `cat:` labels share one pastel color (`#E6D9F5`). Maintainers may add a `cat:` label when triaging skill issues and PRs.

Wait for maintainer feedback on non-trivial work before investing in a large PR.

Before writing docs, read the [glossary](docs/glossary.md).

### 2. Fork and clone

Fork [ARPAHLS/skillware](https://github.com/ARPAHLS/skillware) to your GitHub account, then clone your fork:

```bash
git clone https://github.com/<your-username>/skillware.git
cd skillware
git remote add upstream https://github.com/ARPAHLS/skillware.git
```

### 3. Sync and branch

```bash
git fetch upstream
git checkout main
git pull upstream main
git checkout -b feat/issue-<number>-short-description
```

### 4. Install dependencies

```bash
pip install -e ".[dev,all]"
```

For documentation-only PRs, `pip install -e ".[dev]"` is sufficient. For skill or framework work, use `[dev,all]` to match CI (optional `[agents]` for SDK examples — see [Install extras](docs/usage/install_extras.md)).

#### Editable vs PyPI on the same Python

Use **one install mode per interpreter** — editable **or** PyPI wheel, not both. Mixing `pip install -e ".[dev,all]"` from a clone with `pip install skillware` / `pip install -U skillware` on the same Python can leave orphan `skillware-*.dist-info` folders and make the CLI print `skillware None` / `vNone` ([#333](https://github.com/ARPAHLS/skillware/issues/333)).

**Before switching modes:**

```bash
python -m pip uninstall skillware -y
```

Then either editable (`pip install -e ".[dev,all]"` from the repo) or PyPI (`pip install skillware`). On Windows, prefer `py -3.13 -m pip` (or your target version) so you do not accidentally install into a different Python.

**If `pip uninstall` fails** (`uninstall-no-record-file`), run `skillware doctor --install` for copy-paste recovery commands, or use [`scripts/dev_install.ps1`](scripts/dev_install.ps1) / [`scripts/dev_install.sh`](scripts/dev_install.sh) from a clean repo checkout.

See [TESTING.md](docs/TESTING.md) for the bundle / framework / maintainer / example model and pytest usage.

### 5. Implement and verify

Follow the table in [Ways to contribute](#ways-to-contribute), then [Pull request process](#pull-request-process).

---

## Universal expectations

These apply to **all** contributions, regardless of type.

### Code of conduct

Follow the [Agent Code of Conduct](CODE_OF_CONDUCT.md): deterministic skill outputs, documented dependencies, no malicious or deceptive code.

### Style

- **No emojis** in source code, documentation, commit messages, or PR titles.
- Use **Black** for formatting (CI runs `black --check`) and **Flake8** for linting (see [TESTING.md](docs/TESTING.md)).
- Match existing naming, structure, and documentation tone in the files you touch.
- Use [glossary.md](docs/glossary.md) terms in new prose. Inclusive language: [inclusive-language.md](docs/contributing/inclusive-language.md). Do not global-replace `user` with `operator`.

### Scope

- Change only what the issue requires. Avoid unrelated refactors or drive-by edits.
- Do not bump the package version in `pyproject.toml` (or `CITATION.cff` `version` / `date-released`) unless the issue or a maintainer explicitly requests it (skill-only PRs typically do not version the framework). See [Maintainer: cutting a framework release](#maintainer-cutting-a-framework-release).
- When a PR changes **user-visible behavior** (framework features, new or changed skills, breaking fixes, CLI or documentation users rely on), add entries under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md) in the same PR (Keep a Changelog sections: Added / Changed / Fixed / Removed). Do not add version headers or publish releases; maintainers cut releases.
- Skill-only PRs that will not ship in the next PyPI release may omit a CHANGELOG entry; ask on the issue or use maintainer judgment.

### Tests and CI

- Add or update tests in the correct layer when behavior changes (see [TESTING.md](docs/TESTING.md)).
- **Skill bundle test** — `skills/<category>/<name>/test_skill.py` (required for new skills; ships in the wheel; runs in CI via `pytest skills/`).
- **Framework test** — `tests/test_*.py` at repo root (loader, CLI, issuer rules, doc-drift guards).
- **Maintainer skill test** — optional `tests/skills/<category>/test_<name>.py` for extra loader or edge-case coverage.
- **Usage examples** — `examples/*.py` are not tests and are not run in CI.
- **GitHub Actions** runs two jobs on every PR (see [`.github/workflows/ci.yml`](.github/workflows/ci.yml)):
  - **`build`** — editable install `pip install -e ".[dev,all]"`, then `python -m black --check .`, `flake8 .`, **`pytest skills/`** (bundle tests), **`pytest tests/`** (framework + maintainer tests).
  - **`wheel-smoke`** — builds a wheel, installs it in a fresh venv (base deps only), runs **`scripts/wheel_smoke_test.py`** to verify every bundled registry skill ships correctly. See [Packaging smoke test](docs/TESTING.md#packaging-smoke-test).
- Do not add per-skill pip lines or hardcoded skill paths to `.github/workflows/ci.yml`.
- Run locally before opening a PR:

  ```bash
  python -m black --check .
  python -m flake8 .
  python -m pytest skills/
  python -m pytest tests/
  ```

  Bundle tests can also be run with `skillware test` (see [CLI reference](docs/usage/cli.md#skillware-test)); requires `[dev]` or `[dev,all]`.

  For a single skill:

  ```bash
  python -m pytest skills/<category>/<skill_name>/test_skill.py
  ```

  Or: `skillware test <category>/<skill_name>`.

- Install packages from that skill's `manifest.yaml` `requirements` when they are not covered by `[all]`. After adding a skill with new third-party deps, run `python scripts/sync_extras.py` (see [Install extras](docs/usage/install_extras.md)).
- Wait for GitHub Actions CI to pass before requesting review.

### Pull request template

Use the [pull request template](.github/PULL_REQUEST_TEMPLATE.md). Complete the **New or updated skill** section only when this PR adds or changes files under `skills/`.

Before requesting review, verify your PR template checklist:

- Select the correct **change type** (skill, documentation, framework, bug fix).
- Confirm **local `flake8`, `black` and `pytest`** pass (both `pytest skills/` and `pytest tests/`).
- Add a **CHANGELOG** entry under `[Unreleased]` when the change is user-visible.
- Fill only the checkboxes that truthfully apply; do not leave unchecked defaults.

### AI agents and operators

Agents must follow [Agent Contribution Workflow](docs/contributing/ai_native_workflow.md). Human operators: approve the agent's plan before implementation, verify tests, and own the fork, commit, and PR. The operator remains responsible for the merged diff.

---

## Pull request process

1. **Link an issue** — Reference it in the PR description (`Fixes #123` or `Refs #123`).
2. **Fork and branch** — Work on a feature branch, not `main` of the upstream repo.
3. **Implement** — Use the checklist for your contribution type ([Ways to contribute](#ways-to-contribute)).
4. **Verify locally**:

   ```bash
   python -m black --check .
   python -m flake8 .
   pytest skills/
   pytest tests/
   ```

   Or `skillware test` for bundle tests (see [CLI reference](docs/usage/cli.md#skillware-test)).

   For skill work, also run:

   ```bash
   pytest skills/<category>/<skill_name>/test_skill.py
   pytest tests/test_skill_issuer.py
   ```

   Or `skillware test <category>/<skill_name>` for the bundle test only.

5. **Commit** — Clear imperative message, no emojis; include issue reference when appropriate. Do not add AI tools in `Co-authored-by:` trailers (see [Agent Code of Conduct](CODE_OF_CONDUCT.md#contribution-process)).
6. **Changelog** — If the PR is user-visible, add lines under `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md) before opening the PR.
7. **Push** to your fork and open a PR into `ARPAHLS/skillware` `main`.
8. **CI** — Ensure checks pass; address review feedback on the same branch.

### Skill-specific steps (in addition to the above)

1. Copy or align with `templates/python_skill/`.
2. Create `skills/<category>/<skill_name>/` with the full bundle (see [Skill bundle standard](#skill-bundle-standard)).
3. Add `docs/skills/<category>/<skill_name>.md`, a row in `docs/skills/<category>/README.md`, a row in [docs/skills/README.md](docs/skills/README.md), and a link in [docs/sitemap.md](docs/sitemap.md).
4. When adding or renaming a runnable script under `examples/`, update [examples/README.md](examples/README.md) in the same PR.
5. Confirm `SkillLoader.load_skill("<category>/<skill_name>")` works or document required packages and environment variables.

---

## Skill bundle standard

Skills you submit are reviewed for origin and quality, not sandboxed at runtime — operators run them in their own process. Understand the [skill trust model](docs/security/skill-trust-model.md) before designing a skill's behavior.

Every registry skill lives in `skills/<category>/<skill_name>/` and **must** include the files below. This is the detailed standard for the **skill** contribution type.

### Skill anatomy (vocabulary)

Checklists below use **file names**; each file implements a **role**. The [README Mission](README.md#mission) summarizes the core roles; full reference: [docs/introduction.md — Skill anatomy](docs/introduction.md#skill-anatomy). Terms: [glossary.md](docs/glossary.md).

| Role | v0 file(s) | Required |
| :--- | :--- | :---: |
| **Contract** | `manifest.yaml` | Yes |
| **Effect** | `skill.py` (+ effect modules in the same folder) | Yes |
| **Directive** | `instructions.md` | Yes |
| **Assurance** | `test_skill.py` | Yes (registry) |
| **Presentation** | `card.json` | Recommended |
| **Corpus** | `kb/`, `data/`, bundled knowledge files | Optional |
| **Reference** | `schemas/`, maps, in-bundle spec fixtures | Optional |
| **Interface** | `skillware/core/loader.py` adapters | Framework (not in bundle) |

**Effect modules** (for example `workflow.py`, `budget.py`) are imported by `skill.py`—implementation detail, not a separate required file. **Corpus tooling** (for example `maintenance/`) refreshes Corpus offline and is not loaded by `execute()`.

### 1. `manifest.yaml` (Contract)

Defines the tool interface, safety constitution, dependencies, and issuer attribution.

**Required fields and sections:**

- `name` — registry skill ID in `category/skill_name` form; **must match** the folder path under `skills/` (same string as `SkillLoader.load_skill(...)` and the CLI `ID` column). Do not use a short name alone (for example `pdf_form_filler` without the `office/` prefix). The loader emits `SkillwareIdentityWarning` when a registry-layout skill (`<skill_root>/<category>/<skill_name>/`) has a missing or mismatched `name` (warn-only in v1; may become an error later). Flat private layouts (`<skill_root>/<skill_name>/`) skip this check. Enforced in CI via `tests/test_registry_identity.py` — mismatched or duplicate `manifest.name` blocks merge (#280).
- `version`, `description`
- `issuer` — see [Issuer attribution](#issuer-attribution); `name` and `email` required, `github` and `org` optional
- `short_description` — one-line summary (≤ 160 chars, recommended ~80–120 chars) shown in `skillware list` and used by `SkillContext(mode="brief")` for agent routing. It should be concise, readable, and explicitly state what the skill does and when to use it (see [Skill chaining](docs/usage/skill_chaining.md)).

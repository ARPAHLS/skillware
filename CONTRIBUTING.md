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
| [Skill Package Standard](#skill-package-standard) | Required layout for registry skills |
| [Skill categories](#skill-categories) | Folder taxonomy under `skills/` |
| [What to avoid](#what-to-avoid) | Anti-patterns |
| [Safety and security](#safety-and-security) | High-risk skills |
| [Related documents](#related-documents) | Code of conduct, testing, templates |

---

## Ways to contribute

Pick the path that matches your issue. Only the **skill** row requires the full bundle under [Skill Package Standard](#skill-package-standard).

| Type | What you change | Typical issue label | Before coding | Verify locally |
| :--- | :--- | :--- | :--- | :--- |
| **New or updated skill** | `skills/<category>/<name>/`, `docs/skills/`, templates | Skill proposal, enhancement | Skill proposal or approved issue | `pytest` for skill + `tests/test_skill_issuer.py` |
| **Documentation** | `docs/`, `README.md`, `CONTRIBUTING.md` | Documentation, good first issue | Doc issue or typo/fix issue | Links valid; tone consistent |
| **Core framework** | `skillware/core/`, `tests/` | Framework feature | Framework feature issue | `pytest tests/`; update usage docs if API changes |
| **Bug fix** | Paths named in issue | Bug report | Reproduction or failing test | Targeted test + full `pytest tests/` when touching shared code |
| **Good first issue** | Usually docs, tests, or small fixes | Good first issue | Read acceptance criteria literally | Checklist for underlying type above |
| **RFC / large change** | Architecture, manifest contract, loader | RFC | Maintainer discussion on issue | Per RFC scope |

**Skills remain the primary contribution we expect**, but every type above should follow [Getting started](#getting-started), [Universal expectations](#universal-expectations), and [Pull request process](#pull-request-process).

---

## Getting started

### 1. Find or open an issue

Check [existing issues](https://github.com/ARPAHLS/skillware/issues) before starting work.

| Intent | Issue template |
| :--- | :--- |
| New capability in the registry | [Skill proposal](https://github.com/ARPAHLS/skillware/issues/new/choose) |
| Loader, adapters, `base_skill` | [Framework feature](https://github.com/ARPAHLS/skillware/issues/new/choose) |
| Incorrect behavior | [Bug report](https://github.com/ARPAHLS/skillware/issues/new/choose) |
| Large or breaking design | [RFC](https://github.com/ARPAHLS/skillware/issues/new/choose) |

Wait for maintainer feedback on non-trivial work before investing in a large PR.

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
pip install -e .[dev]
```

See [TESTING.md](docs/TESTING.md) for formatting, linting, and pytest usage.

### 5. Implement and verify

Follow the table in [Ways to contribute](#ways-to-contribute), then [Pull request process](#pull-request-process).

---

## Universal expectations

These apply to **all** contributions, regardless of type.

### Code of conduct

Follow the [Agent Code of Conduct](CODE_OF_CONDUCT.md): deterministic skill outputs, documented dependencies, no malicious or deceptive code.

### Style

- **No emojis** in source code, documentation, commit messages, or PR titles.
- Use **Black** for formatting and **Flake8** for linting (see [TESTING.md](docs/TESTING.md)).
- Match existing naming, structure, and documentation tone in the files you touch.

### Scope

- Change only what the issue requires. Avoid unrelated refactors or drive-by edits.
- Do not bump the package version in `pyproject.toml` unless the issue or a maintainer explicitly requests it (skill-only PRs typically do not version the framework).

### Tests and CI

- Add or update tests when behavior changes.
- Run `python -m flake8 .` and `pytest tests/` before opening a PR.
- Wait for GitHub Actions CI to pass before requesting review.

### Pull request template

Use the [pull request template](.github/PULL_REQUEST_TEMPLATE.md). Complete the **New or updated skill** section only when this PR adds or changes files under `skills/`.

### AI agents and operators

Agents must follow [Agent Contribution Workflow](docs/contributing/ai_native_workflow.md). Human operators: approve the agent's plan before implementation, verify tests, and own the fork, commit, and PR. The operator remains responsible for the merged diff.

---

## Pull request process

1. **Link an issue** — Reference it in the PR description (`Fixes #123` or `Refs #123`).
2. **Fork and branch** — Work on a feature branch, not `main` of the upstream repo.
3. **Implement** — Use the checklist for your contribution type ([Ways to contribute](#ways-to-contribute)).
4. **Verify locally**:

   ```bash
   python -m black .
   python -m flake8 .
   pytest tests/
   ```

   For skill work, also run:

   ```bash
   pytest skills/<category>/<skill_name>/test_skill.py
   pytest tests/test_skill_issuer.py
   ```

5. **Commit** — Clear imperative message, no emojis; include issue reference when appropriate.
6. **Push** to your fork and open a PR into `ARPAHLS/skillware` `main`.
7. **CI** — Ensure checks pass; address review feedback on the same branch.

### Skill-specific steps (in addition to the above)

1. Copy or align with `templates/python_skill/`.
2. Create `skills/<category>/<skill_name>/` with the full bundle (see [Skill Package Standard](#skill-package-standard)).
3. Add `docs/skills/<skill_name>.md` and a row in [docs/skills/README.md](docs/skills/README.md).
4. When adding or renaming a runnable script under `examples/`, update [examples/README.md](examples/README.md) in the same PR.
5. Confirm `SkillLoader.load_skill("<category>/<skill_name>")` works or document required packages and environment variables.

---

## Skill Package Standard

Every registry skill lives in `skills/<category>/<skill_name>/` and **must** include the files below. This is the detailed standard for the **skill** contribution type.

### 1. `manifest.yaml` (metadata and governance)

Defines the tool interface, safety constitution, dependencies, and issuer attribution.

**Required fields and sections:**

- `name`, `version`, `description`
- `issuer` — see [Issuer attribution](#issuer-attribution)
- `parameters` — valid JSON Schema for LLM tool calling
- `constitution` — safety boundaries enforced at the prompt level
- `requirements` — when external packages are needed (for example `requests`, `pandas`)

**Optional but common:**

- `env_vars` — API keys and configuration (never hardcode secrets in `skill.py`); document the same names on the skill catalog page and link to [API keys for skills](docs/usage/api_keys.md)
- `category`, `outputs`, `presentation` — when they clarify the skill contract

**Example:**

```yaml
name: generic_hello
version: 1.0.0
description: A friendly greeting skill.
issuer:
  name: Your Name
  email: you@example.com
  github: your_github_username
  org: YOUR ORG
parameters:
  type: object
  properties:
    name:
      type: string
  required:
    - name
constitution: |
  1. Do not greet offensive names.
  2. Always maintain a polite tone.
requirements:
  - requests
```

### 2. `skill.py` (logic)

- Implement deterministic Python logic (planned: inherit from `BaseSkill` where applicable).
- Accept a dictionary of inputs; return a JSON-serializable dictionary.
- Catch internal errors and return a structured error report; do not crash the host agent.
- Do **not** print to stdout or stderr for normal operation.
- Do **not** embed open-ended LLM code generation as the skill implementation.

### 3. `instructions.md` (cognition)

The primary guide for the host LLM.

- Open with context such as: "You are an agent equipped with [Skill Name]..."
- Explain **when** to invoke the tool.
- Explain how to interpret outputs and handle edge cases.
- Keep prompts and persona here, not in `skill.py`.

### 4. `card.json` (presentation)

- Optional but recommended for user-facing agents and catalog UIs.
- Describes UI presentation (`name`, `description`, `icon`, `ui_schema`, and similar).
- When present, include an `issuer` object that matches `manifest.yaml` (`name` and `email` at minimum; copy `github` and `org` when used).

### 5. `test_skill.py` (validation)

- Unit tests for schema compliance and deterministic execution paths.
- Run: `pytest skills/<category>/<skill_name>/test_skill.py`

### Packaging (PyPI and `pip install`)

Registry skills are shipped inside the `skillware` wheel. You do **not** edit `pyproject.toml` per skill. Instead:

- Add an empty `__init__.py` in `skills/<category>/` when you introduce a **new category**, and in `skills/<category>/<skill_name>/` for each new skill directory (enforced by `tests/test_skill_issuer.py`).
- Non-Python files (`manifest.yaml`, `instructions.md`, `card.json`, data files) are included automatically via `MANIFEST.in` and `[tool.setuptools.package-data]` (`skills = ["**/*"]`).
- Confirm `SkillLoader.load_skill("<category>/<skill_name>")` works from the repo root and, when changing the loader, from a clean `pip install` of the built wheel.

### 6. `docs/skills/<skill_name>.md` (catalog page)

- Human-readable documentation linked from the [Skill Library](docs/skills/README.md).
- Include **ID** and **Issuer** near the top (for example linked GitHub handle and optional org).
- Describe capabilities, prerequisites, arguments, and limitations.
- If the skill calls external services, list its environment variables in a short table and link to [API keys for skills](docs/usage/api_keys.md). Do not duplicate the full setup guide on the skill page.
- Add a **Usage Examples** section with runnable snippets for Gemini, Claude, OpenAI, DeepSeek, and Ollama (prompt mode). Follow [skill usage example template](docs/usage/skill_usage_template.md) and link to [usage guides](docs/usage/README.md) and [agent loops](docs/usage/agent_loops.md).

### 7. Registry index row

- Add or update the skill table in [docs/skills/README.md](docs/skills/README.md) (Skill, ID, Issuer, Description).

### Issuer attribution

The manifest is the **source of truth** for issuer data. Use real contact details in everything under `skills/`—not template placeholders (`Your Name`, `you@example.com`, `YOUR ORG`, and similar).

| Field | Required | Notes |
| :--- | :--- | :--- |
| `issuer.name` | Yes | Display name of the contributor or maintainer |
| `issuer.email` | Yes | Contact email for the skill author |
| `issuer.github` | No | GitHub username without `@` |
| `issuer.org` | No | GitHub organization or affiliation |

Registry-wide issuer rules are enforced in `tests/test_skill_issuer.py` (skills under `skills/` only; templates are excluded).

---

## Skill categories

Place each skill under one top-level directory under `skills/`. Use an existing category when it fits; propose a new category in the issue if none apply.

| Category | Purpose | Examples in registry |
| :--- | :--- | :--- |
| `compliance` | Privacy, policy, regulatory guardrails | `pii_masker`, `mica_module`, `tos_evaluator` |
| `data_engineering` | Datasets, generation, ETL-style tooling | `synthetic_generator` |
| `finance` | Blockchain, risk, financial analysis | `wallet_screening` |
| `office` | Documents, productivity | `pdf_form_filler` |
| `optimization` | Middleware, compression, efficiency | `prompt_rewriter` |

Skill IDs follow `category/skill_name` and should match the path under `skills/`.

---

## What to avoid

- **God skills** — One skill that does everything; split into focused capabilities.
- **Hardcoded models** — Do not hide prompts in `skill.py`; use `instructions.md`.
- **Vendor lock-in** — Prefer standard Python over framework-specific wrappers in skill logic.
- **Environment leaks** — No API keys in source; document `env_vars` in the manifest.
- **Placeholder issuers** — No template names or emails in committed registry skills.
- **Unrequested version bumps** — Do not change `pyproject.toml` version in routine skill PRs.

---

## Safety and security

- Skills that touch real-world assets (wallets, email, production APIs) should support a **dry run** or read-only mode when feasible.
- Sanitize inputs in `skill.py` before external calls.
- Respect the skill `constitution` in both code and documentation.
- Malicious or deceptive contributions may be rejected and blocked from the project.

---

## Related documents

| Document | Purpose |
| :--- | :--- |
| [API keys for skills](docs/usage/api_keys.md) | Configuring credentials for skills that call external services |
| [Agent Contribution Workflow](docs/contributing/ai_native_workflow.md) | Workflow written for contributing agents; operators supervise |
| [TESTING.md](docs/TESTING.md) | Black, Flake8, Pytest, local CI parity |
| [Agent Code of Conduct](CODE_OF_CONDUCT.md) | Behavioral expectations for humans and agents |
| [docs/introduction.md](docs/introduction.md) | Architecture: Mind, Body, Conscience |
| [docs/skills/README.md](docs/skills/README.md) | Published skill catalog |
| [templates/python_skill/](templates/python_skill/) | Boilerplate for new skills |
| [Pull request template](.github/PULL_REQUEST_TEMPLATE.md) | PR checklist |
| [Security policy](SECURITY.md) | Reporting vulnerabilities |

---

Thank you for helping make agent capabilities portable, safe, and reusable.

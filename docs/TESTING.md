# Testing & Code Quality

Skillware maintains high standards for code quality and reliability. Before submitting a Pull Request, please ensure your code passes all linting and testing checks.

Tests fall into four layers: **bundle**, **framework**, **maintainer**, and **example**. Use that vocabulary consistently in docs and PRs.

## Status

| Capability | Status |
| :--- | :---: |
| Bundle tests in CI (`pytest skills/`) | Done |
| Every registry skill ships `test_skill.py` | Done |
| Issuer enforces bundle tests on new skills | Done |
| Bundle tests mock network and model downloads in CI | Done |
| Maintainer tests under `tests/skills/` (optional per skill) | Done |
| `[all]` extra covers bundle-test runtime deps | Done |
| CLI `skillware test` for bundle discovery | Done |
| Doc-drift guards (`test_registry_docs.py`) | Done |
| GitHub label policy test (`test_github_labels.py`) | Done |
| PyPI wheel packaging smoke test (`scripts/wheel_smoke_test.py`) | Done |

Every pull request runs `black --check`, `flake8`, `pytest skills/`, `pytest tests/`, and a **wheel-smoke** job that builds a wheel, installs it in a fresh venv (base install only — no `[all]` or per-skill extras), and verifies every bundled registry skill is present and loadable. Bundle tests gate merge the same as framework and maintainer tests.

When [`.github/labels.json`](../../.github/labels.json) changes on `main`, the [Sync GitHub Labels](../../.github/workflows/sync-labels.yml) workflow updates label colors and descriptions on the repository automatically — do not edit labels manually in the GitHub UI.

## Quick Setup

Install lint tools, pytest, and optional skill runtime deps in one go (matches GitHub Actions CI):

```bash
pip install -e ".[dev,all]"
```

Or use the dev pointer file:

```bash
pip install -r requirements.txt
```

## Four test layers

| Layer | Location | Shipped in pip wheel? | CI on PR? |
| :--- | :--- | :---: | :---: |
| **Skill bundle test** | `skills/<category>/<skill_name>/test_skill.py` | Yes | Yes |
| **Framework test** | `tests/test_*.py` (not under `tests/skills/`) | No (clone only) | Yes |
| **Maintainer skill test** | `tests/skills/<category>/test_<name>.py` | No (clone only) | Yes when present |
| **Usage example** | `examples/*.py` | No | No — not pytest |

### Skill bundle test

- Lives **inside the skill bundle**; ships with `pip install skillware`.
- **Required** for every new registry skill (see `templates/python_skill/test_skill.py`).
- Offline and mockable: manifest consistency, validation, deterministic `execute()` paths — no live network.
- Run locally: `pytest skills/<category>/<skill_name>/test_skill.py` or `pytest skills/`.
- Install packages from the skill's `manifest.yaml` `requirements` when they are not already satisfied by `[all]`.
- Bundle tests run in CI on every pull request and must not make live HTTP requests, use API keys, or download models.
- Mock HTTP clients, LLM clients, embedding loaders, and model download paths such as HuggingFace, Ollama, `fastembed`, and similar integrations.
- Real inference belongs in maintainer tests under `tests/skills/` or in local/manual runs, not in bundle CI gates.

### Framework test

- Core engine health: loader, CLI, issuer rules, version policy, parameter schema validation (`tests/test_validate_params.py`).
- `tests/test_skill_issuer.py` also enforces registry packaging (`__init__.py`), issuer metadata, presence of `test_skill.py` in every skill bundle, and rejects legacy manifest `output:` keys.
- `tests/test_registry_docs.py` enforces doc-drift parity: skill catalog index matches manifests, examples README matches scripts on disk, and agent-loops.md references every registered skill.
- Lives at the **root of `tests/`** only (`tests/test_loader.py`, `tests/test_cli.py`, …).
- Clone-repo only; runs in CI via `pytest tests/` together with maintainer tests below.

### Maintainer skill test

- **Optional** extra depth for skill maintainers: loader wiring, heavy mocks, edge cases.
- Not required for every skill; when present, runs in CI as part of `pytest tests/`.
- Example: `tests/skills/compliance/test_tos_evaluator.py`.

### Usage example

- Runnable provider demos under `examples/` — **not tests**.
- Never collected by pytest; never run in CI. May need real API keys.
- See [examples/README.md](../examples/README.md).

## Which tests go where?

| You are testing… | Put it here | Example in this repo |
| :--- | :--- | :--- |
| Manifest + execute contract for one skill | Bundle test | `skills/compliance/tos_evaluator/test_skill.py` |
| Loader path + mocked externals (optional depth) | Maintainer test | `tests/skills/compliance/test_tos_evaluator.py` |
| Loader, CLI, registry issuer rules, param validation | Framework test | `tests/test_loader.py`, `tests/test_skill_issuer.py`, `tests/test_validate_params.py`, `tests/test_registry_docs.py` |
| End-to-end provider demo script | Usage example | `examples/gemini_tos_evaluator.py` |

**Rule of thumb:** if it ships with the skill and must pass before merge → **bundle test** (CI + local). If it is extra regression depth for clone-repo work → **maintainer test** (optional). If it proves provider integration → **example**, not pytest.

## Packaging smoke test

Editable clone tests (`pytest skills/`, `pytest tests/`) do not prove that a **built PyPI wheel** ships every registry bundle. CI runs an additional **wheel-smoke** job (see [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)) that:

1. Builds a wheel from the PR branch (`python -m build --wheel`).
2. Creates a fresh virtualenv and `pip install`s the wheel (**base install only** — no `[all]` or per-skill extras).
3. Runs `scripts/wheel_smoke_test.py`, which checks every bundled skill for required bundle files, manifest/name parity, instructions and card assets, and `SkillLoader.load_skill(..., check_requirements=False)`.

Skills whose optional runtime deps are not in the base wheel may be **deferred** (packaging verified, import skipped until extras are installed). That is expected; bundle tests in editable mode still cover execute paths with mocked deps.

Run locally after building a wheel:

```bash
python -m build --wheel --outdir dist/
python -m venv /tmp/wheel-smoke-venv
/tmp/wheel-smoke-venv/bin/pip install dist/skillware-*.whl
/tmp/wheel-smoke-venv/bin/python scripts/wheel_smoke_test.py
```

On Windows, use `Scripts\python` and `Scripts\pip` under the venv path.

## 1. Code Formatting (Black)

We use **Black** as our uncompromising code formatter. It ensures that all code looks the same, regardless of who wrote it, eliminating discussions about style.

### Installation

```bash
pip install black
```

### Usage

Run Black on the entire repository to automatically fix formatting issues:

```bash
python -m black .
```

Run `python -m black --check .` to verify formatting without writing files. GitHub Actions runs the same check on every pull request before flake8 and pytest; run `python -m black .` locally to fix issues before you push.

## 2. Linting (Flake8)

We use **Flake8** to catch logic errors, unused imports, and other code quality issues that Black does not handle.

### Installation

```bash
pip install flake8
```

### Usage

Run Flake8 from the root of the repository:

```bash
python -m flake8 .
```

**Note:** We aim for zero warnings/errors. Do not suppress errors with `# noqa` unless absolutely necessary and justified.

## 3. Unit Tests (Pytest)

We use **pytest** for automated tests. All new features and bug fixes must be accompanied by relevant tests in the correct layer (see above).

### Installation

```bash
pip install pytest
```

### CI (GitHub Actions)

GitHub Actions installs `pip install -e ".[dev,all]"`, then runs:

```bash
python -m black --check .
python -m flake8 .
python -m pytest skills/
python -m pytest tests/
```

That covers **skill bundle tests** under `skills/` and **framework + maintainer tests** under `tests/`. It does not run `examples/`. Do not add per-skill pip lines or hardcoded skill paths to `.github/workflows/ci.yml`.

Pushes to `main` that touch `.github/labels.json` also run [`.github/workflows/sync-labels.yml`](../../.github/workflows/sync-labels.yml) to upsert GitHub labels from the JSON file.

The `[all]` extra includes optional SDK groups plus registry skill runtime deps (`web3`, `fastembed`, `numpy`, …) so `pytest skills/` works after `pip install -e ".[dev,all]"`. When a skill adds new `manifest.yaml` `requirements`, add the same packages to the matching optional extra and to `[all]` in `pyproject.toml`.

### Local commands

Match CI:

```bash
python -m pytest skills/
python -m pytest tests/
```

Or use the CLI (same bundle paths; requires `pip install -e ".[dev]"` or `[dev,all]`):

```bash
skillware test
skillware test <category>/<skill_name>
skillware test --category <category>
```

See [CLI reference](usage/cli.md#skillware-test).

Single skill bundle test:

```bash
python -m pytest skills/<category>/<skill_name>/test_skill.py
```

Optional maintainer depth only:

```bash
python -m pytest tests/skills/<category>/test_<skill_name>.py
```

Pytest is configured to collect from `tests/` and `skills/` only (`examples/` is ignored). See `[tool.pytest.ini_options]` in `pyproject.toml`.

### Writing tests

- **Bundle test:** `skills/<category>/<name>/test_skill.py` — required for new skills; copy from `templates/python_skill/test_skill.py`.
- **Maintainer test:** `tests/skills/<category>/test_<name>.py` — optional; use shared fixtures in `tests/conftest.py` when helpful.
- **Framework test:** `tests/test_*.py` at repo root — for loader, CLI, issuer, and cross-cutting rules.

## Pre-Commit Checklist

Before pushing your code, run the following commands:

1. `skillware list` (verify install and path resolution)
2. `python -m black --check .` (verify formatting; use `python -m black .` to fix)
3. `python -m flake8 .` (check quality)
4. `python -m pytest skills/` or `skillware test` (bundle tests — same scope as CI)
5. `python -m pytest tests/` (framework + maintainer tests — same scope as CI)
6. `python -m pytest skills/<category>/<skill_name>/test_skill.py` or `skillware test <category>/<skill_name>` for a single skill

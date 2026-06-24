# Testing & Code Quality

Skillware maintains high standards for code quality and reliability. Before submitting a Pull Request, please ensure your code passes all linting and testing checks.

Tests fall into four layers: **bundle**, **framework**, **maintainer**, and **example**. Use that vocabulary consistently in docs and PRs.

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

- Core engine health: loader, CLI, issuer rules, version policy.
- `tests/test_skill_issuer.py` also enforces registry packaging (`__init__.py`), issuer metadata, and presence of `test_skill.py` in every skill bundle.
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
| Loader, CLI, registry issuer rules | Framework test | `tests/test_loader.py`, `tests/test_skill_issuer.py` |
| End-to-end provider demo script | Usage example | `examples/gemini_tos_evaluator.py` |

**Rule of thumb:** if it ships with the skill and must pass before merge → **bundle test** (CI + local). If it is extra regression depth for clone-repo work → **maintainer test** (optional). If it proves provider integration → **example**, not pytest.

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

Run `python -m black --check .` to verify formatting without writing files. GitHub Actions runs the same check before flake8 and pytest.

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

The `[all]` extra includes optional SDK groups plus registry skill runtime deps (`web3`, `fastembed`, `numpy`, …) so `pytest skills/` works after `pip install -e ".[dev,all]"`. When a skill adds new `manifest.yaml` `requirements`, add the same packages to the matching optional extra and to `[all]` in `pyproject.toml`.

### Local commands

Match CI:

```bash
python -m pytest skills/
python -m pytest tests/
```

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
4. `python -m pytest skills/` (bundle tests — same scope as CI)
5. `python -m pytest tests/` (framework + maintainer tests — same scope as CI)
6. `python -m pytest skills/<category>/<skill_name>/test_skill.py` when you want a single-skill subset

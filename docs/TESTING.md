# Testing & Code Quality

Skillware maintains high standards for code quality and reliability. Before submitting a Pull Request, please ensure your code passes all linting and testing checks.

## Quick Setup

Install all testing and linting dependencies in one go:

```bash
pip install -e .[dev]
```

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

If your PR fails the CI check for formatting, running this command locally will resolve it.

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

We use **pytest** for unit testing. All new features and bug fixes must be accompanied by relevant tests.

### Installation
```bash
pip install pytest
```

### Usage
Run the full test suite:
```bash
python -m pytest tests/
```

### Testing Individual Skills
Every skill now comes with a `test_skill.py` boilerplate. You can run tests for a specific skill without running the entire suite:

```bash
python -m pytest skills/<category>/<skill_name>/test_skill.py
```

### Writing Tests
- **Global Tests**: Place core framework tests in the `tests/` directory.
- **Skill Tests**: Place skill-specific logic tests in a `test_skill.py` file within the skill's own directory.
- Use `conftest.py` for shared fixtures (e.g., mocking LLM clients).

## Pre-Commit Checklist

Before pushing your code, run the following commands to ensure your changes are ready for review:

1. `skillware list` (Verify install and path resolution are working)
2. `python -m black .` (Format code)
3. `python -m flake8 .` (Check quality)
4. `python -m pytest tests/` (Verify framework functionality)
5. `python -m pytest skills/` (Verify all skills pass their local tests)

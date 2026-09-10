"""Five-provider Usage Examples guard for skill catalog pages (#104)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_ROOT = REPO_ROOT / "docs" / "skills"

PROVIDERS = ("Gemini", "Claude", "OpenAI", "DeepSeek", "Ollama")
PROVIDER_HEADING = re.compile(r"^### (" + "|".join(PROVIDERS) + r")\b", re.MULTILINE)
CLOUD_PROVIDERS = {"Gemini", "Claude", "OpenAI", "DeepSeek"}
FENCE_PATTERN = re.compile(r"```python\n(.*?)```", re.DOTALL)


def _usage_examples_section(content: str) -> str:
    match = re.search(r"^## Usage Examples\b", content, re.MULTILINE)
    if not match:
        return ""
    rest = content[match.start() :]
    next_h2 = re.search(r"^## (?!Usage Examples)", rest[1:], re.MULTILINE)
    if next_h2:
        return rest[: next_h2.start() + 1]
    return rest


def _provider_blocks(usage: str) -> dict[str, str]:
    """Return provider name -> section text (heading through next provider or end)."""
    headings = list(PROVIDER_HEADING.finditer(usage))
    blocks: dict[str, str] = {}
    for index, match in enumerate(headings):
        provider = match.group(1)
        start = match.start()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(usage)
        blocks[provider] = usage[start:end]
    return blocks


def _python_blocks(section: str) -> list[str]:
    return FENCE_PATTERN.findall(section)


def _has_load_skill(code: str) -> bool:
    return "SkillLoader.load_skill" in code


def _has_execute(code: str) -> bool:
    for line in code.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "skill.execute(" in stripped:
            return True
    return False


def _has_load_env(code: str) -> bool:
    return "load_env_file()" in code


@pytest.fixture(scope="session")
def catalog_pages() -> list[Path]:
    return sorted(path for path in DOCS_ROOT.glob("*.md") if path.name != "README.md")


def test_catalog_pages_have_five_provider_sections(catalog_pages: list[Path]):
    """Every catalog page lists Gemini, Claude, OpenAI, DeepSeek, and Ollama."""
    failures: list[str] = []

    for page in catalog_pages:
        usage = _usage_examples_section(page.read_text(encoding="utf-8"))
        if not usage:
            failures.append(f"{page.name}: missing ## Usage Examples")
            continue

        found = set(_provider_blocks(usage))
        missing = [p for p in PROVIDERS if p not in found]
        if missing:
            failures.append(
                f"{page.name}: missing provider section(s): {', '.join(missing)}"
            )

    assert not failures, "Incomplete provider headings:\n" + "\n".join(
        f"  - {item}" for item in failures
    )


def test_catalog_provider_snippets_are_runnable_loops(catalog_pages: list[Path]):
    """Each provider block includes load_skill and skill.execute in a python fence."""
    failures: list[str] = []

    for page in catalog_pages:
        usage = _usage_examples_section(page.read_text(encoding="utf-8"))
        if not usage:
            continue

        for provider, section in _provider_blocks(usage).items():
            python_blocks = _python_blocks(section)
            if not python_blocks:
                failures.append(f"{page.name} / {provider}: no ```python block")
                continue

            code = python_blocks[0]
            if not _has_load_skill(code):
                failures.append(
                    f"{page.name} / {provider}: missing SkillLoader.load_skill"
                )
            if not _has_execute(code):
                failures.append(f"{page.name} / {provider}: missing skill.execute")
            if provider in CLOUD_PROVIDERS and not _has_load_env(code):
                failures.append(f"{page.name} / {provider}: missing load_env_file()")

    assert not failures, "Incomplete provider snippets:\n" + "\n".join(
        f"  - {item}" for item in failures
    )

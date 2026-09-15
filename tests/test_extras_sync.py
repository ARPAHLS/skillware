"""Validate generated optional-dependencies stay in sync with manifests."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from skillware.core.extras import (
    GENERATED_BEGIN,
    GENERATED_END,
    build_extras_map,
    collect_skill_requirements,
    extra_to_registry_id,
    registry_id_to_extra,
    render_generated_block,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
SKILLS_ROOT = REPO_ROOT / "skills"
INSTALL_EXTRAS = REPO_ROOT / "docs" / "usage" / "install_extras.md"

# Optional lanes documented in install_extras.md but not generated from manifests.
DOCUMENTED_OPTIONAL_EXTRAS = frozenset(
    {
        "security_deceptive_ui_guard_render",
        "data_engineering_semantic_web_proxy_tokenizer",
    }
)


def _generated_section() -> str:
    content = PYPROJECT.read_text(encoding="utf-8")
    assert GENERATED_BEGIN in content and GENERATED_END in content
    _, rest = content.split(GENERATED_BEGIN, 1)
    block, _ = rest.split(GENERATED_END, 1)
    return block.strip()


def _parse_toml_lists(section: str) -> dict[str, list[str]]:
    extras: dict[str, list[str]] = {}
    for match in re.finditer(
        r"^([a-z0-9_]+)\s*=\s*\[(.*?)\]",
        section,
        flags=re.MULTILINE | re.DOTALL,
    ):
        name = match.group(1)
        body = match.group(2)
        items = re.findall(r'"([^"]+)"', body)
        extras[name] = items
    return extras


def test_generated_block_matches_manifests():
    expected = render_generated_block(SKILLS_ROOT)
    content = PYPROJECT.read_text(encoding="utf-8")
    assert expected in content, (
        "pyproject.toml generated extras differ from manifests. "
        "Run: python scripts/sync_extras.py"
    )


def test_every_registry_skill_has_extra():
    skill_reqs = collect_skill_requirements(SKILLS_ROOT)
    parsed = _parse_toml_lists(_generated_section())
    for skill_id in skill_reqs:
        extra = registry_id_to_extra(skill_id)
        assert extra in parsed, f"Missing skill extra {extra!r} for {skill_id}"


def test_skill_extras_match_non_core_manifest_requirements():
    skill_reqs = collect_skill_requirements(SKILLS_ROOT)
    parsed = _parse_toml_lists(_generated_section())
    for skill_id, expected in skill_reqs.items():
        extra = registry_id_to_extra(skill_id)
        assert (
            parsed[extra] == expected
        ), f"{extra} in pyproject.toml does not match manifest for {skill_id}"


def test_category_extras_are_unions():
    skill_reqs = collect_skill_requirements(SKILLS_ROOT)
    parsed = _parse_toml_lists(_generated_section())
    expected = build_extras_map(SKILLS_ROOT)
    for category in {skill_id.split("/", 1)[0] for skill_id in skill_reqs}:
        assert parsed[category] == expected[category]


def test_all_extra_matches_union():
    parsed = _parse_toml_lists(_generated_section())
    expected = build_extras_map(SKILLS_ROOT)["all"]
    assert parsed["all"] == expected


def _section_between(content: str, start: str, end: str) -> str:
    _, rest = content.split(start, 1)
    section, _ = rest.split(end, 1)
    return section


def _parse_backtick_list(cell: str) -> list[str]:
    return re.findall(r"`([^`]+)`", cell)


def _parse_packages_cell(cell: str) -> list[str]:
    if "none today" in cell.lower():
        return []
    items = _parse_backtick_list(cell)
    if items:
        return items
    return [part.strip() for part in cell.split(",") if part.strip()]


def _parse_markdown_table(section: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in section.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or stripped.startswith("| :"):
            continue
        rows.append([cell.strip() for cell in stripped.strip("|").split("|")])
    return rows


def _parse_install_extras_skill_table(
    content: str,
) -> dict[str, tuple[str, list[str]]]:
    section = _section_between(content, "## Skill extras", "## Meta extras")
    result: dict[str, tuple[str, list[str]]] = {}
    for row in _parse_markdown_table(section)[1:]:
        extra_name = _parse_backtick_list(row[0])[0]
        registry_id = _parse_backtick_list(row[1])[0]
        packages = _parse_packages_cell(row[2])
        result[extra_name] = (registry_id, packages)
    return result


def test_install_extras_guide_matches_pyproject():
    """Hand-maintained install_extras.md tables match generated pyproject extras."""
    content = INSTALL_EXTRAS.read_text(encoding="utf-8")
    parsed = _parse_toml_lists(_generated_section())
    skill_reqs = collect_skill_requirements(SKILLS_ROOT)

    category_section = _section_between(
        content, "## Category extras", "## Skill extras"
    )
    for row in _parse_markdown_table(category_section)[1:]:
        category = _parse_backtick_list(row[0])[0]
        documented = set(_parse_backtick_list(row[1]))
        expected = {
            skill_id for skill_id in skill_reqs if skill_id.startswith(f"{category}/")
        }
        assert documented == expected, (
            f"Category {category!r} skills in install_extras.md "
            f"({sorted(documented)}) != expected ({sorted(expected)})"
        )
        documented_pkgs = set(_parse_packages_cell(row[2]))
        assert documented_pkgs == set(parsed[category]), (
            f"Category {category!r} packages in install_extras.md "
            f"({sorted(documented_pkgs)}) != pyproject ({sorted(parsed[category])})"
        )

    skill_table = _parse_install_extras_skill_table(content)
    for skill_id in skill_reqs:
        extra = registry_id_to_extra(skill_id)
        assert (
            extra in skill_table
        ), f"Missing skill extra row {extra!r} in install_extras.md"
        documented_id, documented_pkgs = skill_table[extra]
        assert documented_id == skill_id
        assert set(documented_pkgs) == set(parsed[extra]), (
            f"{extra} packages in install_extras.md "
            f"({documented_pkgs}) != pyproject ({parsed[extra]})"
        )

    for extra_name, (registry_id, _) in skill_table.items():
        if extra_name in DOCUMENTED_OPTIONAL_EXTRAS:
            continue
        assert (
            registry_id in skill_reqs
        ), f"Orphan extra row {extra_name!r} in install_extras.md"
        assert extra_name == registry_id_to_extra(registry_id)

    meta_section = content.split("## Meta extras", 1)[1].split(
        "## Agent SDK extras", 1
    )[0]
    for row in _parse_markdown_table(meta_section)[1:]:
        if _parse_backtick_list(row[0]) == ["all"]:
            documented_all = set(_parse_packages_cell(row[2]))
            assert documented_all == set(parsed["all"]), (
                "Meta [all] packages in install_extras.md "
                f"({sorted(documented_all)}) != pyproject ({sorted(parsed['all'])})"
            )
            break
    else:
        raise AssertionError("Meta extras table missing [all] row")


def test_sync_extras_check_script():
    result = subprocess.run(
        [sys.executable, "scripts/sync_extras.py", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_extra_to_registry_id_treats_bedrock_as_meta_extra():
    assert extra_to_registry_id("bedrock", categories=["compliance"]) is None

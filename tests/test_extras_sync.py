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
    registry_id_to_extra,
    render_generated_block,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
SKILLS_ROOT = REPO_ROOT / "skills"


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


def test_sync_extras_check_script():
    result = subprocess.run(
        [sys.executable, "scripts/sync_extras.py", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout

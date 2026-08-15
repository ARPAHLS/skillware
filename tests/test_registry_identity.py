"""Registry-layout skills must have manifest.name matching their path and globally unique names."""

from collections import defaultdict
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"


def _discover_skill_dirs():
    if not SKILLS_ROOT.is_dir():
        return []
    return sorted(p.parent for p in SKILLS_ROOT.rglob("manifest.yaml"))


def _load_manifest(skill_dir: Path) -> dict:
    with open(skill_dir / "manifest.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _expected_registry_id(skill_dir: Path):
    """Return category/skill_name for registry-layout skills, None for flat or non-standard layouts."""
    try:
        relative = skill_dir.relative_to(SKILLS_ROOT)
    except ValueError:
        return None
    if len(relative.parts) != 2:
        return None
    return relative.as_posix()


def test_registry_manifest_name_matches_path():
    """Every registry-layout skill's manifest.name must equal its path-derived registry ID."""
    skill_dirs = _discover_skill_dirs()
    assert skill_dirs, "expected at least one skill under skills/"

    mismatches = []
    for skill_dir in skill_dirs:
        expected = _expected_registry_id(skill_dir)
        if expected is None:
            continue

        manifest = _load_manifest(skill_dir)
        manifest_name = (manifest.get("name") or "").strip()
        rel_path = skill_dir.relative_to(REPO_ROOT).as_posix()

        if not manifest_name:
            mismatches.append(
                f"{rel_path}: manifest.yaml missing 'name' (expected {expected!r})"
            )
        elif manifest_name != expected:
            mismatches.append(
                f"{rel_path}: manifest.name is {manifest_name!r}, expected {expected!r}"
            )

    assert not mismatches, "manifest.name parity violations:\n  " + "\n  ".join(
        mismatches
    )


def test_registry_manifest_names_are_globally_unique():
    """No two registry-layout skills may share the same manifest.name."""
    name_to_paths = defaultdict(list)

    for skill_dir in _discover_skill_dirs():
        if _expected_registry_id(skill_dir) is None:
            continue

        manifest = _load_manifest(skill_dir)
        manifest_name = (manifest.get("name") or "").strip()
        if not manifest_name:
            continue

        rel_path = skill_dir.relative_to(REPO_ROOT).as_posix()
        name_to_paths[manifest_name].append(rel_path)

    duplicates = {
        name: paths for name, paths in name_to_paths.items() if len(paths) > 1
    }
    assert (
        not duplicates
    ), f"duplicate manifest.name across registry skills: {dict(duplicates)}"

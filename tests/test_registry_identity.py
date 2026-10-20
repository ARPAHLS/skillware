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


def test_registry_manifests_satisfy_v2_schema():
    """All bundled registry skills must strictly satisfy Manifest v2 schema with explicit taxonomy."""
    from skillware.core.manifest_schema import (
        TAG_REGEX,
        VALID_SHAPES,
        VALID_TARGETS,
        VALID_TIERS,
        validate_manifest_schema,
    )

    skill_dirs = _discover_skill_dirs()
    assert skill_dirs, "expected at least one skill under skills/"

    schema_errors = []
    for skill_dir in skill_dirs:
        expected = _expected_registry_id(skill_dir)
        if expected is None:
            continue

        manifest = _load_manifest(skill_dir)
        rel_path = skill_dir.relative_to(REPO_ROOT).as_posix()

        # 1. Full schema validation
        errs = validate_manifest_schema(manifest, skill_id=expected)
        if errs:
            schema_errors.extend(errs)
            continue

        # 2. Strict explicit declaration requirement for first-party catalog
        if "shape" not in manifest or manifest["shape"] not in VALID_SHAPES:
            schema_errors.append(
                f"{rel_path}: missing or invalid 'shape' ({manifest.get('shape')!r})"
            )
        if "tier" not in manifest or manifest["tier"] not in VALID_TIERS:
            schema_errors.append(
                f"{rel_path}: missing or invalid 'tier' ({manifest.get('tier')!r})"
            )
        target = manifest.get("target")
        if (
            not isinstance(target, list)
            or not target
            or not all(t in VALID_TARGETS for t in target)
        ):
            schema_errors.append(
                f"{rel_path}: missing or invalid 'target' list ({target!r})"
            )
        tags = manifest.get("tags")
        if (
            not isinstance(tags, list)
            or len(tags) < 2
            or len(tags) > 10
            or len(tags) != len(set(tags))
            or not all(isinstance(t, str) and TAG_REGEX.match(t) for t in tags)
        ):
            schema_errors.append(
                f"{rel_path}: invalid 'tags' list (must be 2-10 unique lowercase keywords: {tags!r})"
            )

    assert not schema_errors, "Manifest v2 catalog violations:\n  " + "\n  ".join(
        schema_errors
    )


def test_template_manifest_satisfies_v2_schema():
    """Starter template manifest must satisfy Manifest v2 schema."""
    from skillware.core.manifest_schema import (
        VALID_SHAPES,
        VALID_TARGETS,
        VALID_TIERS,
        validate_manifest_schema,
    )

    template_file = REPO_ROOT / "templates" / "python_skill" / "manifest.yaml"
    assert template_file.is_file(), f"missing template manifest: {template_file}"

    with open(template_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    errs = validate_manifest_schema(data, skill_id="templates/python_skill")
    assert not errs, f"template manifest schema errors: {errs}"

    assert data.get("shape") in VALID_SHAPES
    assert data.get("tier") in VALID_TIERS
    assert isinstance(data.get("target"), list) and all(
        t in VALID_TARGETS for t in data["target"]
    )
    assert isinstance(data.get("tags"), list)

#!/usr/bin/env python3
"""
Packaging smoke test for installed skillware wheels.

Run after ``pip install`` of a built wheel (not editable). Validates that every
registry skill bundle shipped in the wheel is present on disk and loadable
without installing optional per-skill extras or downloading models.

Usage (CI):
    python -m venv /tmp/smoke-venv
    /tmp/smoke-venv/bin/pip install dist/skillware-*.whl
    /tmp/smoke-venv/bin/python scripts/wheel_smoke_test.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Sequence

import yaml

from skillware.core.discovery import bundled_skills_root, list_registry_skill_ids
from skillware.core.loader import SkillLoader

BUNDLE_FILES = (
    "manifest.yaml",
    "skill.py",
    "instructions.md",
    "card.json",
    "test_skill.py",
)

REQUIRED_BUNDLE_KEYS = ("manifest", "instructions", "module", "class")


@dataclass
class SkillSmokeResult:
    skill_id: str
    loaded: bool
    deferred: bool = False
    reason: str = ""


@dataclass
class SmokeReport:
    skill_ids: List[str] = field(default_factory=list)
    loaded: List[str] = field(default_factory=list)
    deferred: List[SkillSmokeResult] = field(default_factory=list)
    failures: List[str] = field(default_factory=list)


def _missing_manifest_requirements(manifest: dict) -> List[str]:
    missing: List[str] = []
    for req in manifest.get("requirements") or []:
        import_name = SkillLoader._requirement_import_name(req)
        if importlib.util.find_spec(import_name) is None:
            missing.append(import_name)
    return missing


def _verify_bundle_files(skill_dir: Path, skill_id: str, failures: List[str]) -> None:
    for filename in BUNDLE_FILES:
        path = skill_dir / filename
        if not path.is_file():
            failures.append(f"{skill_id}: missing bundle file {filename}")

    category_init = skill_dir.parent / "__init__.py"
    if not category_init.is_file():
        failures.append(f"{skill_id}: missing category __init__.py at {category_init}")

    skill_init = skill_dir / "__init__.py"
    if not skill_init.is_file():
        failures.append(f"{skill_id}: missing skill __init__.py")


def _verify_manifest_assets(
    skill_dir: Path, skill_id: str, failures: List[str]
) -> dict:
    manifest_path = skill_dir / "manifest.yaml"
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        failures.append(f"{skill_id}: invalid manifest.yaml — {exc}")
        return {}

    manifest_name = str(manifest.get("name", "")).strip()
    if manifest_name != skill_id:
        failures.append(
            f"{skill_id}: manifest name {manifest_name!r} does not match registry id"
        )

    instructions_path = skill_dir / "instructions.md"
    instructions = instructions_path.read_text(encoding="utf-8").strip()
    if not instructions:
        failures.append(f"{skill_id}: instructions.md is empty")

    card_path = skill_dir / "card.json"
    try:
        json.loads(card_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        failures.append(f"{skill_id}: invalid card.json — {exc}")

    return manifest


def _try_load_skill(skill_id: str, manifest: dict) -> SkillSmokeResult:
    try:
        bundle = SkillLoader.load_skill(skill_id, check_requirements=False)
    except ImportError as exc:
        missing_reqs = _missing_manifest_requirements(manifest)
        if missing_reqs:
            return SkillSmokeResult(
                skill_id=skill_id,
                loaded=False,
                deferred=True,
                reason=(
                    f"optional extras not installed ({', '.join(missing_reqs)}); "
                    f"bundle files verified — {exc}"
                ),
            )
        return SkillSmokeResult(
            skill_id=skill_id,
            loaded=False,
            reason=f"import failed without optional extras: {exc}",
        )
    except Exception as exc:
        return SkillSmokeResult(
            skill_id=skill_id,
            loaded=False,
            reason=f"load failed: {exc}",
        )

    missing_keys = [key for key in REQUIRED_BUNDLE_KEYS if key not in bundle]
    if missing_keys:
        return SkillSmokeResult(
            skill_id=skill_id,
            loaded=False,
            reason=f"bundle missing keys: {', '.join(missing_keys)}",
        )

    if not bundle.get("instructions"):
        return SkillSmokeResult(
            skill_id=skill_id,
            loaded=False,
            reason="bundle instructions empty",
        )

    return SkillSmokeResult(skill_id=skill_id, loaded=True)


def run_wheel_smoke() -> SmokeReport:
    bundled_root = bundled_skills_root()
    if not bundled_root.is_dir():
        raise SystemExit(f"Bundled skills root not found: {bundled_root}")

    skill_ids = list_registry_skill_ids(bundled_root)
    if not skill_ids:
        raise SystemExit(f"No registry skills found under {bundled_root}")

    report = SmokeReport(skill_ids=skill_ids)

    for skill_id in skill_ids:
        skill_dir = bundled_root / skill_id
        failures_before = len(report.failures)

        _verify_bundle_files(skill_dir, skill_id, report.failures)
        manifest = _verify_manifest_assets(skill_dir, skill_id, report.failures)
        if len(report.failures) > failures_before:
            continue

        result = _try_load_skill(skill_id, manifest)
        if result.loaded:
            report.loaded.append(skill_id)
        elif result.deferred:
            report.deferred.append(result)
        else:
            report.failures.append(f"{skill_id}: {result.reason}")

    return report


def _isolated_smoke_env() -> None:
    """Avoid project ./skills/ or SKILLWARE_SKILL_PATH shadowing bundled wheel."""
    os.environ.pop("SKILLWARE_SKILL_PATH", None)
    os.chdir(tempfile.mkdtemp(prefix="skillware-wheel-smoke-"))


def main(argv: Sequence[str] | None = None) -> int:
    del argv
    _isolated_smoke_env()
    report = run_wheel_smoke()

    print(f"Wheel smoke: {len(report.skill_ids)} registry skill(s) in bundled wheel")
    print(f"  loaded:   {len(report.loaded)}")
    print(f"  deferred: {len(report.deferred)} (optional extras not installed)")
    for item in report.deferred:
        print(f"    - {item.skill_id}: {item.reason}")

    if report.failures:
        print(f"  failed:   {len(report.failures)}", file=sys.stderr)
        for line in report.failures:
            print(f"    - {line}", file=sys.stderr)
        return 1

    if not report.loaded and not report.deferred:
        print("No skills loaded or deferred — unexpected", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

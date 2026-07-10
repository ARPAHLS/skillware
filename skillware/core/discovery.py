"""Shared skill root discovery for SkillLoader and the CLI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

SKILLWARE_SKILL_PATH_ENV = "SKILLWARE_SKILL_PATH"
_MAX_PARENT_WALK = 6


class SkillRootTier(str, Enum):
    """Provenance tier for a filesystem skills root (aligned with trust doc / #234)."""

    EXTERNAL = "external"
    PROJECT = "project"
    BUNDLED = "bundled"
    OVERRIDE = "override"


@dataclass(frozen=True)
class SkillRoot:
    """A directory searched for registry-layout skills (`category/skill_name/`)."""

    path: Path
    tier: SkillRootTier
    source: str
    exists: bool

    @property
    def order_label(self) -> str:
        labels = {
            SkillRootTier.EXTERNAL: "1 — external",
            SkillRootTier.PROJECT: "2 — project",
            SkillRootTier.BUNDLED: "3 — bundled",
            SkillRootTier.OVERRIDE: "override",
        }
        return labels.get(self.tier, self.tier.value)


@dataclass(frozen=True)
class ShadowConflict:
    """Same registry ID discovered in multiple roots; the first root wins on load."""

    skill_id: str
    winner: SkillRoot
    shadowed: SkillRoot


def bundled_skills_root() -> Path:
    """Skills shipped inside the installed skillware package."""
    return Path(__file__).resolve().parent.parent.parent / "skills"


def is_skill_dir(path: Path) -> bool:
    return path.is_dir() and (path / "skill.py").is_file()


def env_skill_roots(*, include_missing: bool = False) -> List[SkillRoot]:
    raw = os.environ.get(SKILLWARE_SKILL_PATH_ENV, "").strip()
    if not raw:
        return []

    roots: List[SkillRoot] = []
    for entry in raw.split(os.pathsep):
        entry = entry.strip()
        if not entry:
            continue
        path = Path(entry).expanduser()
        resolved = path.resolve() if path.exists() else path
        exists = path.is_dir()
        if exists or include_missing:
            roots.append(
                SkillRoot(
                    path=resolved,
                    tier=SkillRootTier.EXTERNAL,
                    source=SKILLWARE_SKILL_PATH_ENV,
                    exists=exists,
                )
            )
    return roots


def cwd_skill_roots(*, include_missing: bool = False) -> List[SkillRoot]:
    roots: List[SkillRoot] = []
    current = Path.cwd().resolve()
    for _ in range(_MAX_PARENT_WALK):
        candidate = current / "skills"
        resolved = candidate.resolve()
        exists = candidate.is_dir()
        if exists or include_missing:
            if not any(r.path == resolved for r in roots):
                roots.append(
                    SkillRoot(
                        path=resolved,
                        tier=SkillRootTier.PROJECT,
                        source=f"./skills/ (from {current})",
                        exists=exists,
                    )
                )
        parent = current.parent
        if parent == current:
            break
        current = parent
    return roots


def bundled_skill_root(*, include_missing: bool = False) -> SkillRoot:
    path = bundled_skills_root()
    exists = path.is_dir()
    return SkillRoot(
        path=path.resolve() if exists else path,
        tier=SkillRootTier.BUNDLED,
        source="bundled wheel (site-packages/skills/)",
        exists=exists,
    )


def get_skill_roots(
    skills_root_override: Optional[Path] = None,
    *,
    for_display: bool = False,
) -> List[SkillRoot]:
    """
    Return skill roots in loader resolution order.

    When ``for_display`` is False (default), only existing directories are
    returned — used by ``list``, ``test``, and ``load_skill``.

    When ``for_display`` is True (``skillware paths``), configured env entries
    and the bundled root are shown even when missing so operators can diagnose
    misconfiguration.
    """
    if skills_root_override is not None:
        exists = skills_root_override.is_dir()
        if exists or for_display:
            return [
                SkillRoot(
                    path=(
                        skills_root_override.expanduser().resolve()
                        if exists
                        else skills_root_override.expanduser()
                    ),
                    tier=SkillRootTier.OVERRIDE,
                    source="--skills-root",
                    exists=exists,
                )
            ]
        return []

    include_missing = for_display
    roots: List[SkillRoot] = []
    seen: set[str] = set()

    for root in (
        env_skill_roots(include_missing=include_missing)
        + cwd_skill_roots(include_missing=include_missing)
        + [bundled_skill_root(include_missing=True)]
    ):
        key = str(root.path)
        if key in seen:
            continue
        if root.exists or include_missing:
            seen.add(key)
            roots.append(root)

    if for_display:
        return roots

    return [root for root in roots if root.exists]


def existing_skill_root_paths(
    skills_root_override: Optional[Path] = None,
) -> List[Path]:
    """Paths only — backward-compatible helper for callers expecting ``List[Path]``."""
    return [root.path for root in get_skill_roots(skills_root_override)]


def list_registry_skill_ids(root: Path) -> List[str]:
    """Registry-layout skill IDs under ``root`` (`category/skill_name``)."""
    if not root.is_dir():
        return []

    skill_ids: List[str] = []
    for manifest_path in sorted(root.glob("*/*/manifest.yaml")):
        skill_dir = manifest_path.parent
        if is_skill_dir(skill_dir):
            skill_ids.append(f"{skill_dir.parent.name}/{skill_dir.name}")
    return skill_ids


def find_shadow_conflicts(roots: Sequence[SkillRoot]) -> List[ShadowConflict]:
    """Detect registry IDs that appear in more than one root (first root wins)."""
    winner_for_id: Dict[str, SkillRoot] = {}
    conflicts: List[ShadowConflict] = []

    for root in roots:
        if not root.exists:
            continue
        for skill_id in list_registry_skill_ids(root.path):
            if skill_id in winner_for_id:
                conflicts.append(
                    ShadowConflict(
                        skill_id=skill_id,
                        winner=winner_for_id[skill_id],
                        shadowed=root,
                    )
                )
            else:
                winner_for_id[skill_id] = root

    return conflicts


def collect_search_paths_for_skill_id(skill_id: str) -> List[str]:
    """Absolute paths tried when resolving a registry ID (existing roots only)."""
    searched: List[str] = []
    for root in get_skill_roots():
        attempt = (root.path / skill_id).resolve()
        searched.append(str(attempt))
    return searched


def build_skill_not_found_message(skill_id: str) -> str:
    """Operator-facing error text aligned with ``skillware paths`` output."""
    searched = collect_search_paths_for_skill_id(skill_id)
    lines = [
        f"Skill not found: {skill_id!r}. Searched:",
        *[f"  {path}" for path in searched],
        f"Set {SKILLWARE_SKILL_PATH_ENV} or pass an absolute path to the skill directory.",
        "Run `skillware paths` to inspect resolution order and shadowing.",
    ]
    return "\n".join(lines)


def resolution_order_summary() -> List[Tuple[str, str]]:
    """Short tier descriptions for docs and CLI help."""
    return [
        (
            "External",
            f"Roots in {SKILLWARE_SKILL_PATH_ENV} (OS path separator between entries)",
        ),
        ("Project", "`./skills/` under cwd and up to six parent directories"),
        ("Bundled", "Registry shipped inside the installed skillware package"),
    ]

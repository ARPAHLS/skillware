"""Shared skill root discovery for SkillLoader and the CLI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from skillware.core.config import PathsSettings, SkillwareConfig, load_merged_config

SKILLWARE_SKILL_PATH_ENV = "SKILLWARE_SKILL_PATH"
_MAX_PARENT_WALK = 6


class SkillRootTier(str, Enum):
    """Provenance tier for a filesystem skills root (see skill trust model doc)."""

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


def _external_roots_from_config(
    paths: PathsSettings, *, include_missing: bool = False
) -> List[SkillRoot]:
    roots: List[SkillRoot] = []
    seen: set[str] = set()

    for entry in paths.external:
        path = Path(entry).expanduser()
        resolved = path.resolve() if path.exists() else path
        key = str(resolved)
        if key in seen:
            continue
        exists = path.is_dir()
        if exists or include_missing:
            seen.add(key)
            roots.append(
                SkillRoot(
                    path=resolved,
                    tier=SkillRootTier.EXTERNAL,
                    source="config paths.external",
                    exists=exists,
                )
            )

    if paths.honor_skillware_skill_path:
        for root in env_skill_roots(include_missing=include_missing):
            key = str(root.path)
            if key in seen:
                continue
            seen.add(key)
            roots.append(root)

    return roots


def _project_roots_from_config(
    paths: PathsSettings, *, include_missing: bool = False
) -> List[SkillRoot]:
    if paths.project_is_auto():
        return cwd_skill_roots(include_missing=include_missing)

    path = Path(str(paths.project)).expanduser()
    resolved = path.resolve() if path.exists() else path
    exists = path.is_dir()
    if exists or include_missing:
        return [
            SkillRoot(
                path=resolved,
                tier=SkillRootTier.PROJECT,
                source="config paths.project",
                exists=exists,
            )
        ]
    return []


def _configured_skill_roots(
    config: SkillwareConfig, *, include_missing: bool = False
) -> List[SkillRoot]:
    paths = config.paths
    tier_builders = {
        SkillRootTier.PROJECT: lambda: _project_roots_from_config(
            paths, include_missing=include_missing
        ),
        SkillRootTier.EXTERNAL: lambda: _external_roots_from_config(
            paths, include_missing=include_missing
        ),
        SkillRootTier.BUNDLED: lambda: [bundled_skill_root(include_missing=True)],
    }

    roots: List[SkillRoot] = []
    seen: set[str] = set()
    for tier_name in paths.resolution_order:
        try:
            tier = SkillRootTier(tier_name)
        except ValueError:
            continue
        builder = tier_builders.get(tier)
        if builder is None:
            continue
        for root in builder():
            key = str(root.path)
            if key in seen:
                continue
            if root.exists or include_missing:
                seen.add(key)
                roots.append(root)

    return roots


def _legacy_skill_roots(*, include_missing: bool = False) -> List[SkillRoot]:
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

    return roots


def get_skill_roots(
    skills_root_override: Optional[Path] = None,
    *,
    for_display: bool = False,
) -> List[SkillRoot]:
    """
    Return skill roots in loader resolution order.

    When no global or project config file exists, uses legacy resolution:
    ``SKILLWARE_SKILL_PATH`` → cwd ``./skills/`` walk → bundled.

    When config files exist, uses merged YAML (global then project) with
    ``resolution.order`` (default: project → external → bundled). Bundled is
    always included. Set ``legacy.honor_skillware_skill_path: false`` to ignore
    the env var when config is active.

    When ``for_display`` is True (``skillware paths``), missing configured
    directories are listed so operators can diagnose misconfiguration.
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
    config = load_merged_config()
    if config.has_config_files:
        roots = _configured_skill_roots(config, include_missing=include_missing)
    else:
        roots = _legacy_skill_roots(include_missing=include_missing)

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
    return [path for _, path in collect_search_attempts_for_skill_id(skill_id)]


def collect_search_attempts_for_skill_id(skill_id: str) -> List[Tuple[str, str]]:
    """Return ``(tier, absolute_path)`` pairs tried for a registry ID."""
    attempts: List[Tuple[str, str]] = []
    for root in get_skill_roots():
        attempt = (root.path / skill_id).resolve()
        attempts.append((root.tier.value, str(attempt)))
    return attempts


def list_flat_layout_skill_names(root: Path) -> List[str]:
    """Skill folder names at ``<root>/<name>/`` (excluded from ``skillware list``)."""
    if not root.is_dir():
        return []

    names: List[str] = []
    for child in sorted(root.iterdir()):
        if is_skill_dir(child):
            names.append(child.name)
    return names


def build_skill_not_found_message(skill_id: str) -> str:
    """Operator-facing error text aligned with ``skillware paths`` output."""
    config = load_merged_config()
    attempts = collect_search_attempts_for_skill_id(skill_id)
    lines = [
        f"Skill not found: {skill_id!r}. Searched:",
        *[f"  {tier}: {path}" for tier, path in attempts],
    ]
    if config.has_config_files:
        lines.append(
            "Check paths in .skillware.yaml or global config "
            "(skillware config show)."
        )
    else:
        lines.append(
            f"Set {SKILLWARE_SKILL_PATH_ENV}, add .skillware.yaml, "
            "or pass an absolute path to the skill directory."
        )
    lines.append("Run `skillware paths` to inspect resolution order and shadowing.")
    return "\n".join(lines)


def resolution_order_summary() -> List[Tuple[str, str]]:
    """Short tier descriptions for docs and CLI help."""
    config = load_merged_config()
    if config.has_config_files:
        order = " → ".join(config.paths.resolution_order)
        return [
            (
                "Config",
                f"Merged from {len(config.layers)} file(s); order: {order}",
            ),
            (
                "Project",
                "Explicit path or auto `./skills/` walk when tier is enabled",
            ),
            (
                "External",
                "Paths from config `paths.external`"
                + (
                    f" and {SKILLWARE_SKILL_PATH_ENV}"
                    if config.paths.honor_skillware_skill_path
                    else ""
                ),
            ),
            (
                "Bundled",
                "Registry shipped inside the installed skillware package (always on)",
            ),
        ]

    return [
        (
            "External",
            f"Roots in {SKILLWARE_SKILL_PATH_ENV} (OS path separator between entries)",
        ),
        ("Project", "`./skills/` under cwd and up to six parent directories"),
        ("Bundled", "Registry shipped inside the installed skillware package"),
    ]

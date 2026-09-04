"""Supported-version policy and CLI upgrade advisory."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import List, Optional, Set

from packaging.version import Version

PACKAGE_NAME = "skillware"
MIN_SECURITY_SUPPORTED = Version("0.5.4")
MIN_UNSUPPORTED = Version("0.4.6")
UPGRADE_TARGET = "0.5.4"


def is_version_check_disabled() -> bool:
    return os.environ.get("SKILLWARE_NO_VERSION_CHECK", "").strip() == "1"


def get_installed_version() -> Optional[Version]:
    """Return the installed package version, or None for dev/editable/unparseable."""
    try:
        raw = metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return None
    if not raw or raw in ("dev", "None"):
        return None
    try:
        return Version(raw)
    except Exception:
        return None


def should_emit_unsupported_advisory(installed: Version) -> bool:
    """True only for installs below MIN_UNSUPPORTED (e.g. 0.4.5 and earlier)."""
    return installed < MIN_UNSUPPORTED


def format_unsupported_message(installed: Version) -> str:
    return (
        f"Skillware {installed} is unsupported. "
        f"Upgrade to >={UPGRADE_TARGET}: pip install -U skillware"
    )


def emit_upgrade_advisory() -> None:
    """Print one dim stderr advisory for unsupported CLI installs; otherwise silent."""
    if is_version_check_disabled():
        return

    installed = get_installed_version()
    if installed is None or not should_emit_unsupported_advisory(installed):
        return

    message = format_unsupported_message(installed)
    try:
        from rich.console import Console

        Console(stderr=True).print(message, style="dim")
    except ImportError:
        print(message, file=sys.stderr)


@dataclass(frozen=True)
class InstallConflict:
    """One detected local install-state problem and how to fix it."""

    code: str
    summary: str
    fix_unix: str
    fix_windows: str


def _metadata_name(dist: metadata.Distribution) -> str:
    """Return a distribution's normalized project name, or empty on failure."""
    try:
        name = dist.metadata["Name"]
    except Exception:
        return ""
    return str(name or "").strip().lower()


def _parseable_version(dist: metadata.Distribution) -> bool:
    """True when the distribution carries a parseable PEP 440 version."""
    raw = None
    try:
        raw = dist.version
    except Exception:
        return False
    if not raw or raw in ("dev", "None"):
        return False
    try:
        Version(raw)
    except Exception:
        return False
    return True


def _has_metadata_version(dist: metadata.Distribution) -> bool:
    """True when the distribution metadata exposes Metadata-Version."""
    try:
        return bool(dist.metadata["Metadata-Version"])
    except Exception:
        return False


def _dist_info_path(dist: metadata.Distribution) -> Optional[Path]:
    """Best-effort path to the distribution's .dist-info directory."""
    try:
        path = getattr(dist, "_path", None)
    except Exception:
        return None
    if path is None:
        return None
    try:
        return Path(path)
    except Exception:
        return None


def _skillware_dist_infos() -> List[Path]:
    """Return every skillware-*.dist-info directory visible on sys.path."""
    found: Set[Path] = set()
    roots: List[Path] = []
    try:
        import site

        roots.extend(Path(p) for p in site.getsitepackages())
    except Exception:
        pass
    roots.extend(Path(p) for p in sys.path if p)
    for dist in metadata.distributions():
        if _metadata_name(dist) != PACKAGE_NAME:
            continue
        dist_info = _dist_info_path(dist)
        if dist_info is not None:
            roots.append(dist_info.parent)
    for root in roots:
        try:
            for candidate in root.glob(f"{PACKAGE_NAME}-*.dist-info"):
                found.add(candidate.resolve())
        except Exception:
            continue
    return sorted(found)


def detect_install_conflicts() -> List[InstallConflict]:
    """Detect duplicate, corrupt, or orphan skillware installs on this Python.

    Returns a list of :class:`InstallConflict`; an empty list means the local
    install state is healthy.
    """
    conflicts: List[InstallConflict] = []

    skillware_dists = [
        dist
        for dist in metadata.distributions()
        if _metadata_name(dist) == PACKAGE_NAME
    ]

    if len(skillware_dists) > 1:
        conflicts.append(
            InstallConflict(
                code="duplicate",
                summary=(
                    f"{len(skillware_dists)} skillware distributions are "
                    "registered; pip may pick a corrupt one."
                ),
                fix_unix=(
                    "python -m pip uninstall skillware -y\n"
                    "python -m pip install -U skillware"
                ),
                fix_windows=(
                    "py -m pip uninstall skillware -y\n"
                    "py -m pip install -U skillware"
                ),
            )
        )

    for dist in skillware_dists:
        if not _has_metadata_version(dist):
            conflicts.append(
                InstallConflict(
                    code="missing-metadata-version",
                    summary=(
                        f"A skillware distribution ({dist.version!r}) has no "
                        "Metadata-Version."
                    ),
                    fix_unix=(
                        "python -m pip uninstall skillware -y\n"
                        "python -m pip install -U skillware"
                    ),
                    fix_windows=(
                        "py -m pip uninstall skillware -y\n"
                        "py -m pip install -U skillware"
                    ),
                )
            )
        if not _parseable_version(dist):
            conflicts.append(
                InstallConflict(
                    code="unparseable-version",
                    summary=(
                        f"A skillware distribution has an unparseable version "
                        f"({dist.version!r})."
                    ),
                    fix_unix=(
                        "python -m pip uninstall skillware -y\n"
                        "python -m pip install -U skillware"
                    ),
                    fix_windows=(
                        "py -m pip uninstall skillware -y\n"
                        "py -m pip install -U skillware"
                    ),
                )
            )

    dist_infos = _skillware_dist_infos()
    for dist_info in dist_infos:
        try:
            has_metadata = (dist_info / "METADATA").is_file()
            has_record = (dist_info / "RECORD").is_file()
        except Exception:
            continue
        if has_metadata and has_record:
            continue
        missing = []
        if not has_metadata:
            missing.append("METADATA")
        if not has_record:
            missing.append("RECORD")
        conflicts.append(
            InstallConflict(
                code="orphan",
                summary=(
                    f"Orphan dist-info {dist_info.name} is missing "
                    f"{', '.join(missing)}; pip uninstall may fail."
                ),
                fix_unix=(f"rm -rf {dist_info}\n" "python -m pip install -U skillware"),
                fix_windows=(
                    f"rmdir /s /q {dist_info}\n" "py -m pip install -U skillware"
                ),
            )
        )

    editable = [dist for dist in skillware_dists if _read_direct_url_is_editable(dist)]
    wheel_like = [
        dist for dist in skillware_dists if not _read_direct_url_is_editable(dist)
    ]
    if editable and wheel_like:
        conflicts.append(
            InstallConflict(
                code="editable-wheel-mix",
                summary=(
                    "Editable and wheel installs coexist on this Python; "
                    "use one mode per interpreter."
                ),
                fix_unix=(
                    "python -m pip uninstall skillware -y\n"
                    "python -m pip install -e '.[dev,all]'"
                ),
                fix_windows=(
                    "py -m pip uninstall skillware -y\n" 'py -m pip install -e "."'
                ),
            )
        )

    return conflicts


def _read_direct_url_is_editable(dist: metadata.Distribution) -> bool:
    """True when a distribution's direct_url.json marks an editable install."""
    try:
        raw = dist.read_text("direct_url.json")
    except Exception:
        return False
    if not raw:
        return False
    try:
        import json

        payload = json.loads(raw)
    except Exception:
        return False
    try:
        return bool(payload.get("dir_info", {}).get("editable"))
    except Exception:
        return False

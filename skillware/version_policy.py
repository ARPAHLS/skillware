"""Supported-version policy, install health, and CLI advisories."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from importlib import metadata
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

from packaging.version import InvalidVersion, Version

PACKAGE_NAME = "skillware"
MIN_SECURITY_SUPPORTED = Version("0.5.6")
MIN_UNSUPPORTED = Version("0.4.6")
UPGRADE_TARGET = "0.5.6"


@dataclass(frozen=True)
class InstallIssue:
    """One detected install-state problem."""

    code: str
    message: str
    dist_label: str = ""


@dataclass
class InstallHealth:
    """Result of ``assess_install_health()``."""

    ok: bool
    issues: List[InstallIssue] = field(default_factory=list)
    distribution_count: int = 0
    display_version: str = "dev"
    parsed_version: Optional[Version] = None
    fix_commands_unix: List[str] = field(default_factory=list)
    fix_commands_windows: List[str] = field(default_factory=list)

    @property
    def summary_one_liner(self) -> str:
        if self.ok:
            return f"Skillware install OK (skillware {self.display_version})."
        if self.issues:
            return self.issues[0].message
        return "Skillware install may be corrupt (duplicate or orphan metadata)."


def is_version_check_disabled() -> bool:
    return os.environ.get("SKILLWARE_NO_VERSION_CHECK", "").strip() == "1"


def _is_invalid_version_string(raw: Optional[str]) -> bool:
    if raw is None:
        return True
    text = str(raw).strip()
    if not text:
        return True
    if text.lower() in {"dev", "none"}:
        return True
    return False


def iter_skillware_distributions() -> Iterable[metadata.Distribution]:
    for dist in metadata.distributions():
        try:
            name = (dist.metadata.get("Name") or "").strip()
        except Exception:
            continue
        if name.lower() == PACKAGE_NAME:
            yield dist


def _distribution_dist_info_dir(dist: metadata.Distribution) -> Optional[Path]:
    try:
        return Path(dist.locate_file("METADATA")).parent
    except Exception:
        pass
    path = getattr(dist, "_path", None)
    if path:
        try:
            return Path(path)
        except (TypeError, ValueError, OSError):
            return None
    return None


def _distribution_label(dist: metadata.Distribution) -> str:
    dist_info = _distribution_dist_info_dir(dist)
    if dist_info is not None:
        return dist_info.name
    try:
        version = dist.version
    except Exception:
        version = "unknown"
    return f"{PACKAGE_NAME}-{version}.dist-info"


def _distribution_version_raw(dist: metadata.Distribution) -> Optional[str]:
    raw: Optional[str] = None
    try:
        raw = dist.version
    except Exception:
        raw = None
    if _is_invalid_version_string(raw):
        try:
            raw = dist.metadata.get("Version")
        except Exception:
            raw = None
    if _is_invalid_version_string(raw):
        return None
    return str(raw).strip()


def _distribution_has_record(dist: metadata.Distribution) -> bool:
    try:
        files = dist.files
    except Exception:
        return False
    return bool(files)


def _distribution_is_editable(dist: metadata.Distribution) -> bool:
    dist_info = _distribution_dist_info_dir(dist)
    if dist_info is None:
        return False
    return (dist_info / "direct_url.json").is_file()


def _parse_version(raw: str) -> Optional[Version]:
    try:
        return Version(raw)
    except (InvalidVersion, TypeError, ValueError):
        return None


def _collect_parsed_versions(
    distributions: Sequence[metadata.Distribution],
) -> List[Version]:
    versions: List[Version] = []
    for dist in distributions:
        raw = _distribution_version_raw(dist)
        if raw is None:
            continue
        parsed = _parse_version(raw)
        if parsed is not None:
            versions.append(parsed)
    return versions


def _format_recovery_commands() -> tuple[List[str], List[str]]:
    py = sys.executable
    unix = [
        f"{py} -m pip uninstall skillware -y",
        f"{py} -m pip install --force-reinstall skillware",
    ]
    windows = [
        f'"{py}" -m pip uninstall skillware -y',
        f'"{py}" -m pip install --force-reinstall skillware',
    ]
    return unix, windows


def _format_editable_recovery_commands() -> tuple[List[str], List[str]]:
    py = sys.executable
    unix = [
        f"{py} -m pip uninstall skillware -y",
        f'{py} -m pip install -e ".[dev,all]"',
    ]
    windows = [
        f'"{py}" -m pip uninstall skillware -y',
        f'"{py}" -m pip install -e ".[dev,all]"',
    ]
    return unix, windows


def assess_install_health() -> InstallHealth:
    """Detect duplicate, orphan, or mixed editable/wheel skillware registrations."""
    distributions = list(iter_skillware_distributions())
    issues: List[InstallIssue] = []
    editable_count = 0
    wheel_count = 0

    for dist in distributions:
        label = _distribution_label(dist)
        has_record = _distribution_has_record(dist)
        is_editable = _distribution_is_editable(dist)
        version_raw = _distribution_version_raw(dist)

        if not has_record:
            issues.append(
                InstallIssue(
                    code="orphan_dist_info",
                    message=(
                        f"Orphan install metadata ({label}): missing RECORD/METADATA. "
                        "pip may show 'skillware None' or fail uninstall."
                    ),
                    dist_label=label,
                )
            )

        if is_editable:
            editable_count += 1
        elif has_record:
            wheel_count += 1

        if has_record and version_raw is None:
            issues.append(
                InstallIssue(
                    code="missing_version",
                    message=(
                        f"Install metadata ({label}) has no parseable Version field."
                    ),
                    dist_label=label,
                )
            )

    if len(distributions) > 1:
        issues.append(
            InstallIssue(
                code="duplicate_distribution",
                message=(
                    f"Found {len(distributions)} skillware distributions on this Python "
                    "(expected one). Uninstall before switching editable ↔ PyPI."
                ),
            )
        )

    if editable_count > 0 and wheel_count > 0:
        issues.append(
            InstallIssue(
                code="editable_and_wheel",
                message=(
                    "Editable and PyPI wheel installs overlap on the same interpreter. "
                    "Use one mode per Python — see CONTRIBUTING.md."
                ),
            )
        )

    parsed_versions = _collect_parsed_versions(distributions)
    parsed_version = max(parsed_versions) if parsed_versions else None
    display_version = str(parsed_version) if parsed_version is not None else "dev"

    if distributions and parsed_version is None:
        issues.append(
            InstallIssue(
                code="no_parseable_version",
                message=(
                    "skillware is installed but no parseable version was found "
                    "(CLI may show vNone). Run skillware doctor --install."
                ),
            )
        )

    unix_fix, win_fix = _format_recovery_commands()
    if editable_count > 0 and wheel_count == 0 and len(distributions) == 1:
        unix_fix, win_fix = _format_editable_recovery_commands()

    ok = len(issues) == 0
    return InstallHealth(
        ok=ok,
        issues=issues,
        distribution_count=len(distributions),
        display_version=display_version,
        parsed_version=parsed_version,
        fix_commands_unix=unix_fix,
        fix_commands_windows=win_fix,
    )


def get_installed_version() -> Optional[Version]:
    """Return the best installed package version, or None for dev/unparseable."""
    distributions = list(iter_skillware_distributions())
    parsed_versions = _collect_parsed_versions(distributions)
    if parsed_versions:
        return max(parsed_versions)

    try:
        raw = metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return None
    if _is_invalid_version_string(raw):
        return None
    return _parse_version(str(raw).strip())


def get_package_version_display() -> str:
    """Version string for splash and ``--version``; never empty or ``None``."""
    installed = get_installed_version()
    if installed is not None:
        return str(installed)
    return "dev"


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
    _print_dim_stderr(message)


def emit_install_conflict_advisory() -> None:
    """Print one dim stderr line when install metadata looks corrupt or duplicated."""
    if is_version_check_disabled():
        return

    report = assess_install_health()
    if report.ok:
        return

    message = f"{report.summary_one_liner} " "Run: skillware doctor --install"
    _print_dim_stderr(message)


def format_install_health_report(report: InstallHealth) -> str:
    """Plain-text report for ``skillware doctor --install``."""
    lines: List[str] = []
    lines.append("Skillware install health")
    lines.append("")
    lines.append(f"  Distributions found: {report.distribution_count}")
    lines.append(f"  Display version:     skillware {report.display_version}")
    if report.parsed_version is not None:
        lines.append(f"  Parsed version:      {report.parsed_version}")
    lines.append(f"  Status:              {'OK' if report.ok else 'CONFLICT'}")
    lines.append("")

    if report.issues:
        lines.append("Issues:")
        for issue in report.issues:
            prefix = f"  [{issue.code}]"
            if issue.dist_label:
                lines.append(f"{prefix} ({issue.dist_label}) {issue.message}")
            else:
                lines.append(f"{prefix} {issue.message}")
        lines.append("")
        lines.append(
            "Rule: use one install mode per Python interpreter — editable OR PyPI wheel, "
            "not both. Uninstall before switching."
        )
        lines.append("")
        lines.append("Suggested fix (Unix / macOS):")
        for cmd in report.fix_commands_unix:
            lines.append(f"  {cmd}")
        lines.append("")
        lines.append("Suggested fix (Windows PowerShell):")
        for cmd in report.fix_commands_windows:
            lines.append(f"  {cmd}")
        lines.append("")
        lines.append(
            "If pip uninstall fails with uninstall-no-record-file, remove orphan "
            "skillware*.dist-info folders under site-packages, then reinstall."
        )
    else:
        lines.append("No duplicate or orphan skillware install metadata detected.")

    return "\n".join(lines)


def _print_dim_stderr(message: str) -> None:
    try:
        from rich.console import Console

        Console(stderr=True).print(message, style="dim")
    except ImportError:
        print(message, file=sys.stderr)

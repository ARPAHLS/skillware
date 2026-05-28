"""Supported-version policy and CLI upgrade advisory."""

from __future__ import annotations

import os
import sys
from importlib import metadata
from typing import Optional

from packaging.version import Version

PACKAGE_NAME = "skillware"
MIN_SECURITY_SUPPORTED = Version("0.3.1")
MIN_UNSUPPORTED = Version("0.2.6")
UPGRADE_TARGET = "0.3.1"


def is_version_check_disabled() -> bool:
    return os.environ.get("SKILLWARE_NO_VERSION_CHECK", "").strip() == "1"


def get_installed_version() -> Optional[Version]:
    """Return the installed package version, or None for dev/editable/unparseable."""
    try:
        raw = metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return None
    if not raw or raw == "dev":
        return None
    try:
        return Version(raw)
    except Exception:
        return None


def should_emit_unsupported_advisory(installed: Version) -> bool:
    """True only for installs below MIN_UNSUPPORTED (e.g. 0.2.5 and earlier)."""
    return installed < MIN_UNSUPPORTED


def format_unsupported_message(installed: Version) -> str:
    return (
        f"Skillware {installed} is unsupported. "
        f'Upgrade to >={UPGRADE_TARGET}: pip install -U "skillware[cli]"'
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

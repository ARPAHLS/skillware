"""Cross-platform helpers for opening paths in the OS file manager."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def open_path_in_os(path: Path, *, open_parent: bool = False) -> None:
    """Open a file or its parent directory in the native file manager."""
    target = path.parent if open_parent else path
    if sys.platform == "win32":
        os.startfile(str(target))  # type: ignore[attr-defined]
        return
    if sys.platform == "darwin":
        subprocess.run(["open", str(target)], check=False)
        return
    subprocess.run(["xdg-open", str(target)], check=False)

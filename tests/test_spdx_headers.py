"""Tests for standardized SPDX license identifiers and copyright headers."""

from pathlib import Path
from typing import List, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLWARE_ROOT = REPO_ROOT / "skillware"
TEMPLATES_ROOT = REPO_ROOT / "templates" / "python_skill"

EXPECTED_CORE_COPYRIGHT = "# Copyright (c) 2026 ARPA Hellenic Logical Systems"
EXPECTED_SPDX_IDENTIFIER = "# SPDX-License-Identifier: MIT"


def test_core_framework_files_have_copyright_and_spdx_headers():
    """Verify all Python files under skillware/ start with copyright and SPDX headers."""
    py_files = sorted(SKILLWARE_ROOT.rglob("*.py"))
    assert py_files, "expected at least one Python file under skillware/"
    assert (
        len(py_files) >= 20
    ), f"expected at least 20 files in skillware/, got {len(py_files)}"

    missing_headers: List[Tuple[str, str]] = []
    for file_path in py_files:
        lines = [
            line.rstrip("\r\n")
            for line in file_path.read_text(encoding="utf-8").splitlines()
        ]
        rel_path = file_path.relative_to(REPO_ROOT).as_posix()

        if len(lines) < 2:
            missing_headers.append((rel_path, f"File too short ({len(lines)} lines)"))
            continue

        if lines[0] != EXPECTED_CORE_COPYRIGHT:
            missing_headers.append(
                (
                    rel_path,
                    f"Line 1 expected '{EXPECTED_CORE_COPYRIGHT}', got '{lines[0]}'",
                )
            )
        if lines[1] != EXPECTED_SPDX_IDENTIFIER:
            missing_headers.append(
                (
                    rel_path,
                    f"Line 2 expected '{EXPECTED_SPDX_IDENTIFIER}', got '{lines[1]}'",
                )
            )

    assert not missing_headers, (
        "Core framework files missing standardized copyright or SPDX headers:\n"
        + "\n".join(f"  {path}: {reason}" for path, reason in missing_headers)
    )


def test_template_skill_files_have_spdx_header():
    """Verify starter template Python files have SPDX-License-Identifier header."""
    template_files = sorted(TEMPLATES_ROOT.rglob("*.py"))
    assert (
        template_files
    ), "expected at least one Python file under templates/python_skill/"

    missing_spdx: List[Tuple[str, str]] = []
    for file_path in template_files:
        lines = [
            line.rstrip("\r\n")
            for line in file_path.read_text(encoding="utf-8").splitlines()
        ]
        rel_path = file_path.relative_to(REPO_ROOT).as_posix()

        if not lines:
            missing_spdx.append((rel_path, "File is empty"))
            continue

        if lines[0] != EXPECTED_SPDX_IDENTIFIER:
            missing_spdx.append(
                (
                    rel_path,
                    f"Line 1 expected '{EXPECTED_SPDX_IDENTIFIER}', got '{lines[0]}'",
                )
            )

    assert not missing_spdx, "Template files missing SPDX header:\n" + "\n".join(
        f"  {path}: {reason}" for path, reason in missing_spdx
    )

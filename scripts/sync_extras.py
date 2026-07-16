#!/usr/bin/env python3
"""Sync generated optional-dependencies in pyproject.toml from skill manifests."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skillware.core.extras import (  # noqa: E402
    GENERATED_BEGIN,
    GENERATED_END,
    render_generated_block,
)


def _read_pyproject() -> str:
    return PYPROJECT.read_text(encoding="utf-8")


def _replace_generated_block(content: str, generated: str) -> str:
    if GENERATED_BEGIN not in content or GENERATED_END not in content:
        raise SystemExit(
            f"{PYPROJECT} is missing sync markers:\n"
            f"  {GENERATED_BEGIN}\n"
            f"  {GENERATED_END}"
        )

    before, rest = content.split(GENERATED_BEGIN, 1)
    _, after = rest.split(GENERATED_END, 1)
    return before.rstrip() + "\n\n" + generated + after


def sync_extras(*, check: bool = False, skills_root: Path | None = None) -> int:
    current = _read_pyproject()
    generated = render_generated_block(skills_root)
    updated = _replace_generated_block(current, generated)

    if check:
        if updated != current:
            print(
                "pyproject.toml optional-dependencies are out of sync with manifests.\n"
                "Run: python scripts/sync_extras.py",
                file=sys.stderr,
            )
            return 1
        print("Optional extras sync OK.")
        return 0

    if updated == current:
        print("Optional extras already up to date.")
        return 0

    PYPROJECT.write_text(updated, encoding="utf-8", newline="\n")
    print(f"Updated {PYPROJECT.relative_to(REPO_ROOT)} from skill manifests.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit 1 when pyproject.toml generated extras differ from manifests.",
    )
    parser.add_argument(
        "--skills-root",
        type=Path,
        default=None,
        help="Override bundled skills root (for tests).",
    )
    args = parser.parse_args(argv)
    return sync_extras(check=args.check, skills_root=args.skills_root)


if __name__ == "__main__":
    raise SystemExit(main())

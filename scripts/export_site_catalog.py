# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""
scripts/export_site_catalog.py
Export all manifested skills into a normalized JSON payload for skillware.site.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from skillware.core.discovery import bundled_skills_root  # noqa: E402
from skillware.core.manifest_schema import (  # noqa: E402
    normalize_manifest_v2,
    validate_manifest_schema,
)


def collect_catalog(
    skills_root: Optional[Path] = None,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Walk all skills under skills_root, validate manifests, and return (catalog, errors)."""
    root = skills_root or bundled_skills_root()
    if not root.is_dir():
        return [], [f"Skills root '{root}' does not exist or is not a directory."]

    catalog: List[Dict[str, Any]] = []
    errors: List[str] = []

    for manifest_path in sorted(root.glob("*/*/manifest.yaml")):
        category = manifest_path.parent.parent.name
        skill_name = manifest_path.parent.name
        skill_id = f"{category}/{skill_name}"

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as exc:
            errors.append(f"Failed to parse {manifest_path}: {exc}")
            continue

        validation_errors = validate_manifest_schema(data, skill_id=skill_id)
        if validation_errors:
            errors.extend(validation_errors)

        normalized = normalize_manifest_v2(data)
        issuer = normalized.get("issuer") or {}

        entry = {
            "id": skill_id,
            "name": normalized.get("name", skill_id),
            "version": normalized.get("version", ""),
            "shape": normalized.get("shape", "atomic"),
            "tier": normalized.get("tier", "core"),
            "target": normalized.get("target", ["software"]),
            "tags": normalized.get("tags", []),
            "description": normalized.get("description", ""),
            "short_description": normalized.get("short_description", ""),
            "issuer": {
                "name": issuer.get("name", ""),
                "email": issuer.get("email", ""),
                "github": issuer.get("github", ""),
                "org": issuer.get("org", ""),
            },
            "presentation": normalized.get("presentation") or {},
            "requirements": normalized.get("requirements") or [],
        }
        catalog.append(entry)

    return catalog, errors


def export_catalog(
    output_path: Optional[Path] = None,
    skills_root: Optional[Path] = None,
    check_only: bool = False,
) -> int:
    """Validate manifests and optionally write catalog.json. Returns 0 on success, 1 on errors."""
    catalog, errors = collect_catalog(skills_root)

    if errors:
        for err in errors:
            print(f"Error: {err}", file=sys.stderr)
        print(
            f"Catalog validation failed with {len(errors)} error(s).", file=sys.stderr
        )
        return 1

    print(f"Validated {len(catalog)} skill manifests successfully.")

    if check_only:
        return 0

    payload = {
        "version": "2.0.0",
        "total_skills": len(catalog),
        "skills": catalog,
    }

    if output_path is None:
        print(json.dumps(payload, indent=2))
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        print(f"Wrote catalog to {output_path}")

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export all manifested skills into a normalized JSON payload for skillware.site."
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Path to output JSON file (default: stdout).",
    )
    parser.add_argument(
        "--skills-root",
        type=Path,
        default=None,
        help="Path to skills directory (default: bundled skills root).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Validate all manifests without writing output.",
    )
    args = parser.parse_args()
    sys.exit(export_catalog(args.output, args.skills_root, args.check))


if __name__ == "__main__":
    main()

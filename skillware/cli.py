import argparse
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional

from skillware.core.loader import SkillLoader

TABLE_STYLE     = "bold #C7CEEA"    # lavender  - headers
CATEGORY_STYLE  = "bold #FFDAC1"    # peach     - category column
ID_STYLE        = "#B5EAD7"       # mint      - skill ID column
BORDER_STYLE    = "#C7CEEA"       # lavender  - table border


def _get_skill_roots(skills_root_override: Optional[Path] = None) -> List[Path]:
    """Return the list of roots to search for skills, mirrors SkillLoader resolution order."""
    if skills_root_override is not None:
        if skills_root_override.exists():
            return [skills_root_override]
        return []

    roots = []
    seen = set()

    for root in (
        SkillLoader._env_skill_roots()
        + SkillLoader._cwd_skill_roots()
        + [SkillLoader._bundled_skills_root()]
    ):
        resolved = root.resolve()
        if resolved not in seen and resolved.exists():
            seen.add(resolved)
            roots.append(resolved)

    return roots

def _short_description(data: Dict[str, Any], max_len: int = 80) -> str:
    """Return short_description if present, else first sentence of description truncated."""
    short = data.get("short_description", "").strip()
    if short:
        return short[:max_len] + ("..." if len(short) > max_len else "")

    desc = data.get("description", "").strip()

    seps = [".", "!", "?"]

    for sep in seps:
        idx = desc.find(sep)
        if idx != -1:
            desc = desc[: idx + 1]
            break
    
    return desc[:max_len] + ("..." if len(desc) > max_len else "")


def _discover_skills(
    skills_root_override: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Walk all skill roots and return a list of dicts with each skill's metadata."""
    roots = _get_skill_roots(skills_root_override)

    skills = []
    seen_ids = set()

    for root in roots:
        for manifest_path in root.glob("*/*/manifest.yaml"):

            if not SkillLoader._is_skill_dir(manifest_path.parent):
                continue

            with open(manifest_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            skill_id = f"{manifest_path.parent.parent.name}/{manifest_path.parent.name}"

            # skip duplicates found in multiple roots
            if skill_id in seen_ids:
                continue
            seen_ids.add(skill_id)

            issuer = data.get("issuer") or {}

            skills.append(
                {
                    "id": skill_id,
                    "category": manifest_path.parent.parent.name,
                    "name": manifest_path.parent.name,
                    "version": data.get("version", "?").strip(),
                    "description": _short_description(data),
                    "requirements": ", ".join(data.get("requirements") or []).strip(),
                    "issuer": issuer.get("github") or issuer.get("name") or "",
                }
            )

    return skills


def cmd_list(
    skills_root_override: Optional[Path] = None,
    category_filter: Optional[str] = None,
    issuer_filter: Optional[str] = None,
    console=None,
) -> None:
    """Print a formatted table of all available skills."""
    try:
        from rich.table import Table
        from rich.console import Console
        from rich import box
    except ImportError:
        raise SystemExit(
            "rich is required for the CLI. Install it with: pip install 'skillware[cli]'"
        )

    if console is None:
        console = Console()

    skills = _discover_skills(skills_root_override)

    if category_filter:
        skills = [s for s in skills if s["category"] == category_filter]

    if issuer_filter:
        skills = [s for s in skills if s["issuer"] == issuer_filter]

    if not skills:
        console.print("No skills found.")
        return

    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style=BORDER_STYLE,
        header_style=TABLE_STYLE
    )

    table.add_column("ID",              style=ID_STYLE,     no_wrap=True)
    table.add_column("VERSION",         style="dim")
    table.add_column("CATEGORY",        style=CATEGORY_STYLE)
    table.add_column("ISSUER",          style="dim")
    table.add_column("DESCRIPTION")
    table.add_column("REQUIREMENTS",    style="dim")

    for skill in skills:
        table.add_row(
            skill["id"],
            skill["version"],
            skill["category"],
            skill["issuer"],
            skill["description"],
            skill["requirements"],
        )

    console.print(table)

def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(prog="skillware")
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="List all available skills.")
    list_parser.add_argument(
        "--skills-root",
        type=Path,
        default=None,
        help="Override the skills directory path.",
    )
    list_parser.add_argument(
        "--category",
        default=None,
        help="Filter skills by category.",
    )
    list_parser.add_argument(
        "--issuer",
        default=None,
        help="Filter skills by issuer GitHub handle or name.",
    )

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(
            skills_root_override=args.skills_root,
            category_filter=args.category,
            issuer_filter=args.issuer,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

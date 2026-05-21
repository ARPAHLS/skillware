import argparse
import yaml
from pathlib import Path
from rich.table import Table
from rich.console import Console


def _discover_skills(skills_root):
    """Walk skills_root and return a list of dicts with each skill's metadata."""
    if not skills_root.exists():
        raise FileNotFoundError(f"Skills directory not found: {skills_root}")

    skills = []

    for manifest_path in skills_root.glob("*/*/manifest.yaml"):
        with open(manifest_path) as f:
            data = yaml.safe_load(f)

        skills.append(
            {
                "id": f"{manifest_path.parent.parent.name}/{manifest_path.parent.name}",
                "category": manifest_path.parent.parent.name,
                "name": manifest_path.parent.name,  # always from filesystem, never from manifest
                "version": data.get("version", "?").strip(),
                "description": data.get("description", "").strip(),
                "requirements": ", ".join(data.get("requirements") or []).strip(),
            }
        )

    return skills


def cmd_list(skills_root):
    """Print a formatted table of all available skills."""
    skills = _discover_skills(skills_root)

    if not skills:
        print("No skills found.")
        return

    console = Console()
    table = Table()

    table.add_column("ID")
    table.add_column("VERSION")
    table.add_column("CATEGORY")
    table.add_column("DESCRIPTION")
    table.add_column("REQUIREMENTS")

    for skill in skills:
        table.add_row(
            skill["id"],
            skill["version"],
            skill["category"],
            skill["description"],
            skill["requirements"],
        )

    console.print(table)


def main():
    """CLI entry ponint."""
    parser = argparse.ArgumentParser(prog="skillware")
    subparsers = parser.add_subparsers(dest="command")

    list_parser = subparsers.add_parser("list", help="List all available skills.")
    list_parser.add_argument(
        "--skills-root",
        type=Path,
        default=Path("skills"),
        help="Path to the skills directory.",
    )

    args = parser.parse_args()

    if args.command == "list":
        cmd_list(args.skills_root)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()

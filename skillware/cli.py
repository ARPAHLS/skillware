import argparse
import subprocess
import sys
import yaml
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from rich.table import Table
from rich.console import Console
from rich.text import Text
from rich import box

import importlib.metadata

from skillware.core.loader import SkillLoader
from skillware.version_policy import emit_upgrade_advisory, get_installed_version

TABLE_STYLE = "bold #C7CEEA"  # lavender  - headers
CATEGORY_STYLE = "bold #FFDAC1"  # peach     - category column
ID_STYLE = "#B5EAD7"  # mint      - skill ID column
BORDER_STYLE = "#C7CEEA"  # lavender  - table border

SPLASH_STYLE = "#C7CEEA"  # lavender  - skillware splash color
MENU_STYLE = "#FFDAC1"  # peach     - menu category


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
        return short[:max_len] + ("…" if len(short) > max_len else "")

    desc = data.get("description", "").strip()

    seps = [".", "!", "?"]

    for sep in seps:
        idx = desc.find(sep)
        if idx != -1:
            desc = desc[: idx + 1]
            break

    return desc[:max_len] + ("…" if len(desc) > max_len else "")


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


def _resolve_pytest_targets(
    skills_root_override: Optional[Path] = None,
    skill_id: Optional[str] = None,
    category: Optional[str] = None,
) -> Tuple[List[Path], Optional[str]]:
    """Build pytest path arguments for bundle tests (skills/**/test_skill.py)."""
    if skill_id and category:
        return [], "Use either a skill ID or --category, not both."

    roots = _get_skill_roots(skills_root_override)
    if not roots:
        return [], "No skill roots found. Check --skills-root or SKILLWARE_SKILL_PATH."

    if skill_id:
        parts = skill_id.split("/")
        if len(parts) != 2 or not all(parts):
            return (
                [],
                f"Invalid skill ID '{skill_id}'. Expected category/skill_name.",
            )

        category_name, skill_name = parts
        searched: List[Path] = []
        for root in roots:
            test_path = root / category_name / skill_name / "test_skill.py"
            searched.append(test_path)
            if test_path.is_file():
                return [test_path], None

        lines = [f"No bundle test found for '{skill_id}'."]
        for path in searched:
            lines.append(f"  looked for: {path}")
        return [], "\n".join(lines)

    if category:
        targets: List[Path] = []
        searched: List[Path] = []
        for root in roots:
            category_dir = root / category
            searched.append(category_dir)
            if category_dir.is_dir():
                targets.append(category_dir)

        if targets:
            return targets, None

        lines = [f"No skills directory found for category '{category}'."]
        for path in searched:
            lines.append(f"  looked for: {path}")
        return [], "\n".join(lines)

    return roots, None


def cmd_test(
    skills_root_override: Optional[Path] = None,
    skill_id: Optional[str] = None,
    category: Optional[str] = None,
    verbose: bool = False,
    no_header: bool = False,
    console=None,
) -> int:
    """Run bundle tests via pytest. Returns pytest's exit code."""
    if console is None:
        console = Console(stderr=True)

    targets, error = _resolve_pytest_targets(
        skills_root_override=skills_root_override,
        skill_id=skill_id,
        category=category,
    )
    if error:
        console.print(error, style="bold #FF9AA2")
        return 2 if skill_id and category else 1

    pytest_args = [sys.executable, "-m", "pytest"]
    if verbose:
        pytest_args.append("-v")
    if no_header:
        pytest_args.append("--no-header")
    pytest_args.extend(str(path) for path in targets)

    result = subprocess.run(pytest_args, check=False)
    return result.returncode


def cmd_list(
    skills_root_override: Optional[Path] = None,
    category_filter: Optional[str] = None,
    issuer_filter: Optional[str] = None,
    console=None,
) -> None:
    """Print a formatted table of all available skills."""
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
        header_style=TABLE_STYLE,
        expand=True,
    )

    table.add_column("ID", style=ID_STYLE, no_wrap=True, ratio=2)
    table.add_column("VERSION", style="dim", no_wrap=True, ratio=1)
    table.add_column("CATEGORY", style=CATEGORY_STYLE, no_wrap=True, ratio=1)
    table.add_column("ISSUER", style="dim", no_wrap=True, ratio=1)
    table.add_column("DESCRIPTION", ratio=3)
    table.add_column("REQUIREMENTS", style="dim", ratio=2)

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


def _print_menu(console, menu) -> None:
    for num, name, desc in menu:
        console.print(f"    [{num}] {name:<20}— {desc}", style=MENU_STYLE)

    console.print()


def cmd_help(console=None) -> None:
    """Print rich-formatted help to the console."""
    if console is None:
        console = Console()

    console.print(Text("Usage", style=f"bold {TABLE_STYLE}"))
    console.print("  skillware                     — open interactive menu")
    console.print("  skillware list                — list all installed skills")
    console.print("  skillware list --category <n> — filter by category")
    console.print("  skillware list --issuer <h>   — filter by issuer")
    console.print("  skillware list --skills-root  — override skills directory")
    console.print("  skillware test                — run all bundle tests")
    console.print("  skillware test <category/name> — run one skill bundle test")
    console.print("  skillware test --category <n> — run tests for a category")
    console.print("  skillware --version           — print installed version")
    console.print()

    console.print(Text("Commands", style=f"bold {TABLE_STYLE}"))
    console.print("  list      available now", style=ID_STYLE)
    console.print("  test      available now", style=ID_STYLE)
    console.print("  paths     coming soon", style="dim")
    console.print()

    console.print(Text("Interactive mode", style=f"bold {TABLE_STYLE}"))
    console.print(
        "  skillware                     — open interactive menu", style="dim"
    )
    console.print("  1-4 or command name           — select a menu option", style="dim")
    console.print("  q or Ctrl+C                   — exit", style="dim")
    console.print()

    console.print(Text("Examples", style=f"bold {TABLE_STYLE}"))
    console.print("  skillware list --category compliance", style=MENU_STYLE)
    console.print("  skillware list --issuer rosspeili", style=MENU_STYLE)
    console.print("  skillware test finance/wallet_screening", style=MENU_STYLE)
    console.print("  skillware test --category compliance -v", style=MENU_STYLE)
    console.print()

    console.print(Text("Install", style=f"bold {TABLE_STYLE}"))
    console.print("  pip install skillware", style="dim")
    console.print()

    console.print(Text("Docs", style=f"bold {TABLE_STYLE}"))
    console.print(
        "  https://github.com/arpahls/skillware/blob/main/docs/usage/cli.md",
        style=f"dim {SPLASH_STYLE}",
    )


def cmd_interactive(console=None, parser=None) -> None:
    """Launch ASCII splash screen and interactive menu."""
    if console is None:
        console = Console()

    try:
        version = importlib.metadata.version("skillware")
    except importlib.metadata.PackageNotFoundError:
        version = "dev"

    splash = r"""
  ███████╗██╗  ██╗██╗██╗     ██╗    ██╗ █████╗ ██████╗ ███████╗
  ██╔════╝██║ ██╔╝██║██║     ██║    ██║██╔══██╗██╔══██╗██╔════╝
  ███████╗█████╔╝ ██║██║     ██║ █╗ ██║███████║██████╔╝█████╗
  ╚════██║██╔═██╗ ██║██║     ██║███╗██║██╔══██║██╔══██╗██╔══╝
  ███████║██║  ██╗██║███████╗╚███╔███╔╝██║  ██║██║  ██║███████╗
  ╚══════╝╚═╝  ╚═╝╚═╝╚══════╝ ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝"""

    console.print(Text(splash, style=SPLASH_STYLE))
    console.print(
        Text(
            f"  Skill Management Framework — v{version}",
            style=f"dim {SPLASH_STYLE}",
        )
    )

    console.print(
        Text(
            "  https://skillware.site  ·  https://github.com/arpahls/skillware\n",
            style=f"dim {SPLASH_STYLE}",
        )
    )

    menu = [
        ("1", "list", "discover and display all locally installed skills"),
        ("2", "paths (soon)", "show and repair skill directory resolution paths"),
        ("3", "test", "run bundle tests (test_skill.py) for one or all skills"),
        ("4", "help", "usage guide for any command"),
    ]

    commands = {
        "1": "list",
        "list": "list",
        "2": "paths",
        "paths": "paths",
        "3": "test",
        "test": "test",
        "4": "help",
        "help": "help",
    }

    _print_menu(console, menu)

    while True:
        try:
            choice = input("  > ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            console.print("\n  Bye.", style="dim")
            return

        if choice == "q":
            console.print("  Bye.", style="dim")
            return

        command = commands.get(choice)

        if command == "list":
            cmd_list(console=console)
        elif command == "test":
            cmd_test(console=console)
        elif command == "paths":
            console.print(
                "  'paths' is not yet implemented. Coming in a future release.",
                style="dim",
            )
        elif command == "help":
            cmd_help(console=console)
        else:
            console.print(f"  Unknown command: '{choice}'", style="dim #FF9AA2")

        console.print()
        _print_menu(console, menu)


def main() -> None:
    """CLI entry point."""
    emit_upgrade_advisory()

    parser = argparse.ArgumentParser(prog="skillware", add_help=False)

    parser.add_argument(
        "-h",
        "--help",
        action="store_true",
        help="Show this help message and exit.",
    )

    _ver = get_installed_version()
    _version_str = str(_ver) if _ver else "dev"

    parser.add_argument(
        "--version",
        "-V",
        action="version",
        version=f"skillware {_version_str}",
    )

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

    test_parser = subparsers.add_parser(
        "test",
        help="Run skill bundle tests (test_skill.py) via pytest.",
    )
    test_parser.add_argument(
        "skill_id",
        nargs="?",
        default=None,
        help="Skill ID (category/skill_name) to test.",
    )
    test_parser.add_argument(
        "--skills-root",
        type=Path,
        default=None,
        help="Override the skills directory path.",
    )
    test_parser.add_argument(
        "--category",
        default=None,
        help="Run bundle tests for all skills in a category.",
    )
    test_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Pass -v to pytest.",
    )
    test_parser.add_argument(
        "--no-header",
        action="store_true",
        help="Pass --no-header to pytest.",
    )

    args = parser.parse_args()

    if args.help and args.command is None:
        cmd_help(Console())
        return

    if args.command == "list":
        cmd_list(
            skills_root_override=args.skills_root,
            category_filter=args.category,
            issuer_filter=args.issuer,
        )
    elif args.command == "test":
        raise SystemExit(
            cmd_test(
                skills_root_override=args.skills_root,
                skill_id=args.skill_id,
                category=args.category,
                verbose=args.verbose,
                no_header=args.no_header,
            )
        )
    else:
        cmd_interactive(parser=parser)


if __name__ == "__main__":
    main()

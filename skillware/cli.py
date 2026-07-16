import argparse
import re
import subprocess
import sys
import yaml
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union

import requests

from rich.table import Table
from rich.console import Console
from rich.text import Text
from rich import box

import importlib.metadata

from skillware.core.loader import SkillLoader
from skillware.core.discovery import (
    SKILLWARE_SKILL_PATH_ENV,
    find_shadow_conflicts,
    get_skill_roots,
    list_registry_skill_ids,
    resolution_order_summary,
)
from skillware.version_policy import emit_upgrade_advisory, get_installed_version

TABLE_STYLE = "bold #C7CEEA"  # lavender  - headers
CATEGORY_STYLE = "bold #FFDAC1"  # peach     - category column
ID_STYLE = "#B5EAD7"  # mint      - skill ID column
BORDER_STYLE = "#C7CEEA"  # lavender  - table border

SPLASH_STYLE = "#C7CEEA"  # lavender  - skillware splash color
MENU_STYLE = "#FFDAC1"  # peach     - menu category

SPLASH_GRADIENT_START = (0xD4, 0xE4, 0xF1)
SPLASH_GRADIENT_MID = (0x79, 0xB6, 0xD8)
SPLASH_GRADIENT_END = (0xEB, 0xD8, 0xDC)

_SPLASH_LOGO_LINES = (
    "  ███████╗██╗  ██╗██╗██╗     ██╗     ██╗    ██╗ █████╗ ██████╗ ███████╗",
    "  ██╔════╝██║ ██╔╝██║██║     ██║     ██║    ██║██╔══██╗██╔══██╗██╔════╝",
    "  ███████╗█████╔╝ ██║██║     ██║     ██║ █╗ ██║███████║██████╔╝█████╗",
    "  ╚════██║██╔═██╗ ██║██║     ██║     ██║███╗██║██╔══██║██╔══██╗██╔══╝",
    "  ███████║██║  ██╗██║███████╗███████╗╚███╔███╔╝██║  ██║██║  ██║███████╗",
    "  ╚══════╝╚═╝  ╚═╝╚═╝╚══════╝╚══════╝ ╚══╝╚══╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝",
)

_EXAMPLES_README_REL = Path("examples") / "README.md"
_PARENT_WALK_LIMIT = 6
_SKILL_ID_PATTERN = re.compile(r"`([\w-]+/[\w-]+)`")
_EXAMPLES_GITHUB_BLOB_BASE = "https://github.com/ARPAHLS/skillware/blob/main/examples"
_EXAMPLES_README_GITHUB_URL = (
    "https://github.com/ARPAHLS/skillware/blob/main/examples/README.md"
)
_EXAMPLES_README_RAW_URL = (
    "https://raw.githubusercontent.com/ARPAHLS/skillware/main/examples/README.md"
)
_EXAMPLES_INDEX_SOURCE = Union[Path, str]


def _flatten_table_cell(text: str, max_len: int = 80) -> str:
    """Strip markdown backticks and truncate for compact terminal tables."""
    cleaned = " ".join(text.replace("`", "").split())
    if len(cleaned) > max_len:
        return cleaned[: max_len - 1] + "…"
    return cleaned


def _examples_readme_display_path(source: _EXAMPLES_INDEX_SOURCE) -> str:
    """Prefer a short relative path in CLI output; GitHub URL when loaded remotely."""
    if isinstance(source, str):
        return source
    try:
        return source.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return "examples/README.md"


def _example_github_url(script: str) -> str:
    """Canonical GitHub blob URL for an indexed example script."""
    return f"{_EXAMPLES_GITHUB_BLOB_BASE}/{script}"


def _examples_readme_path() -> Optional[Path]:
    """Resolve a local examples/README.md from checkout or cwd walk."""
    candidates: List[Path] = []

    package_root = Path(__file__).resolve().parent.parent
    candidates.append(package_root.parent / _EXAMPLES_README_REL)

    cwd = Path.cwd()
    for directory in [cwd, *list(cwd.parents)[:_PARENT_WALK_LIMIT]]:
        candidates.append(directory / _EXAMPLES_README_REL)

    seen = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        if resolved.is_file():
            return resolved

    return None


def _fetch_examples_readme_from_github() -> Optional[str]:
    """Download examples/README.md from the canonical repo on GitHub."""
    try:
        response = requests.get(_EXAMPLES_README_RAW_URL, timeout=10)
        response.raise_for_status()
        return response.text
    except (requests.RequestException, OSError):
        return None


def _parse_examples_index_text(text: str) -> List[Dict[str, Any]]:
    """Parse the Runnable Scripts table from examples/README.md content."""
    section_start = text.find("## Runnable Scripts")
    if section_start == -1:
        return []

    rows: List[Dict[str, Any]] = []
    for line in text[section_start:].splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or ":---" in stripped:
            continue
        if "Script" in stripped and "Skill ID" in stripped:
            continue

        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if len(cells) < 5:
            continue

        script = cells[0].strip("`")
        skill_ids = _SKILL_ID_PATTERN.findall(cells[1])
        if not skill_ids:
            skill_ids = [part.strip() for part in cells[1].split(",") if part.strip()]

        rows.append(
            {
                "script": script,
                "skill_ids": skill_ids,
                "provider": cells[2],
                "extra": cells[3],
                "env_vars": cells[4],
            }
        )

    return rows


def _parse_examples_index(readme_path: Path) -> List[Dict[str, Any]]:
    """Parse the Runnable Scripts table from a local examples/README.md file."""
    return _parse_examples_index_text(readme_path.read_text(encoding="utf-8"))


def _example_counts_by_skill(rows: List[Dict[str, Any]]) -> Dict[str, int]:
    """Map skill ID to indexed script count (multi-skill rows count toward each ID)."""
    counts: Dict[str, int] = defaultdict(int)
    for row in rows:
        for skill_id in row["skill_ids"]:
            counts[skill_id] += 1
    return dict(counts)


def _load_examples_index() -> (
    Tuple[List[Dict[str, Any]], Optional[_EXAMPLES_INDEX_SOURCE]]
):
    readme_path = _examples_readme_path()
    if readme_path is not None:
        return (
            _parse_examples_index_text(readme_path.read_text(encoding="utf-8")),
            readme_path,
        )

    text = _fetch_examples_readme_from_github()
    if text is not None:
        return _parse_examples_index_text(text), _EXAMPLES_README_GITHUB_URL

    return [], None


def _get_skill_roots(skills_root_override: Optional[Path] = None) -> List[Path]:
    """Return existing skill root paths in loader resolution order."""
    return [root.path for root in get_skill_roots(skills_root_override)]


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
    show_examples: bool = False,
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

    example_counts: Dict[str, int] = {}
    if show_examples:
        rows, readme_source = _load_examples_index()
        if readme_source is None:
            console.print(
                "examples/README.md not found locally or on GitHub; "
                "cannot show example counts.",
                style="bold #FF9AA2",
            )
        else:
            example_counts = _example_counts_by_skill(rows)

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
    if show_examples:
        table.add_column("EXAMPLES", style="dim", no_wrap=True, ratio=1)

    for skill in skills:
        row = [
            skill["id"],
            skill["version"],
            skill["category"],
            skill["issuer"],
            skill["description"],
            skill["requirements"],
        ]
        if show_examples:
            count = example_counts.get(skill["id"], 0)
            row.append(str(count) if count else "-")
        table.add_row(*row)

    console.print(table)
    console.print(
        "Optional runtime deps: see docs/usage/install_extras.md",
        style="dim",
    )


def cmd_examples(
    skill_id: Optional[str] = None,
    console=None,
) -> int:
    """Print runnable example scripts from examples/README.md."""
    if console is None:
        console = Console()

    rows, readme_source = _load_examples_index()
    if readme_source is None:
        console.print(
            "Could not load examples/README.md from the repo or GitHub.",
            style="bold #FF9AA2",
        )
        return 1

    if skill_id:
        parts = skill_id.split("/")
        if len(parts) != 2 or not all(parts):
            console.print(
                f"Invalid skill ID '{skill_id}'. Expected category/skill_name.",
                style="bold #FF9AA2",
            )
            return 2

        rows = [row for row in rows if skill_id in row["skill_ids"]]
        if not rows:
            console.print(
                f"No indexed examples for '{skill_id}'. "
                f"See {_examples_readme_display_path(readme_source)} for the full inventory.",
                style="bold #FF9AA2",
            )
            return 1

    if not rows:
        console.print("No runnable scripts found in examples/README.md.")
        return 1

    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style=BORDER_STYLE,
        header_style=TABLE_STYLE,
        expand=True,
    )
    table.add_column("SCRIPT", style=ID_STYLE, no_wrap=True, ratio=2)
    table.add_column("SKILL ID", style=CATEGORY_STYLE, ratio=2)
    table.add_column("PROVIDER", no_wrap=True, ratio=1)
    table.add_column("EXTRA", style="dim", ratio=1)
    table.add_column("GITHUB", style=f"dim {SPLASH_STYLE}", ratio=3)

    for row in rows:
        table.add_row(
            row["script"],
            ", ".join(row["skill_ids"]),
            _flatten_table_cell(row["provider"], max_len=32),
            _flatten_table_cell(row["extra"], max_len=28),
            _example_github_url(row["script"]),
        )

    console.print(table)
    console.print(
        f"Full notes: {_examples_readme_display_path(readme_source)}",
        style="dim",
    )
    return 0


def cmd_paths(
    skills_root_override: Optional[Path] = None,
    console=None,
) -> int:
    """Show skill root resolution order, tiers, and shadowing (read-only; #246 adds config)."""
    if console is None:
        console = Console()

    cwd = Path.cwd().resolve()
    console.print(Text("Skill path resolution", style=f"bold {TABLE_STYLE}"))
    console.print(f"  cwd: {cwd}", style="dim")
    console.print()

    roots = get_skill_roots(skills_root_override, for_display=True)
    if not roots:
        console.print(
            "No skill roots configured. Set "
            f"{SKILLWARE_SKILL_PATH_ENV} or use --skills-root.",
            style="bold #FF9AA2",
        )
        return 1

    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style=BORDER_STYLE,
        header_style=TABLE_STYLE,
        expand=True,
    )
    table.add_column("ORDER", style=CATEGORY_STYLE, no_wrap=True, ratio=1)
    table.add_column("TIER", style=ID_STYLE, no_wrap=True, ratio=1)
    table.add_column("PATH", ratio=4)
    table.add_column("STATUS", no_wrap=True, ratio=1)
    table.add_column("SKILLS", style="dim", no_wrap=True, ratio=1)

    for index, root in enumerate(roots, start=1):
        skill_count = len(list_registry_skill_ids(root.path)) if root.exists else 0
        status = "ok" if root.exists else "missing"
        status_style = ID_STYLE if root.exists else "bold #FF9AA2"
        table.add_row(
            str(index),
            root.tier.value,
            str(root.path),
            Text(status, style=status_style),
            str(skill_count) if root.exists else "—",
        )

    console.print(table)
    console.print()

    conflicts = find_shadow_conflicts(roots)
    if conflicts:
        console.print(
            Text("Shadowing (first root wins on load)", style=f"bold {TABLE_STYLE}")
        )
        for conflict in conflicts[:20]:
            console.print(
                f"  {conflict.skill_id}: "
                f"{conflict.winner.tier.value} at {conflict.winner.path} "
                f"shadows {conflict.shadowed.tier.value} at {conflict.shadowed.path}",
                style="bold #FF9AA2",
            )
        if len(conflicts) > 20:
            console.print(f"  … and {len(conflicts) - 20} more", style="dim")
        console.print()

    console.print(Text("Resolution order", style=f"bold {TABLE_STYLE}"))
    for label, detail in resolution_order_summary():
        console.print(f"  {label}: {detail}", style="dim")
    console.print()

    console.print(Text("Tips", style=f"bold {TABLE_STYLE}"))
    console.print(
        "  • One-shot override: skillware list --skills-root /path/to/skills",
        style=MENU_STYLE,
    )
    console.print(
        f"  • Persistent external roots: export {SKILLWARE_SKILL_PATH_ENV}=/path/to/skills",
        style=MENU_STYLE,
    )
    console.print(
        "  • Trust tiers: docs/security/skill-trust-model.md",
        style=f"dim {SPLASH_STYLE}",
    )
    console.print(
        "  • Persist project/external paths in config: tracked in #246",
        style="dim",
    )
    console.print(
        "  • Flat-layout skills (<root>/<name>/) load but may not appear in list",
        style="dim",
    )
    return 0


def _prompt_examples_skill_id(console) -> Tuple[Optional[str], bool]:
    """Return (skill_id or None for all, should_run)."""
    try:
        raw = input("  skill id (optional, Enter for all): ").strip()
    except (KeyboardInterrupt, EOFError):
        console.print("\n  Cancelled.", style="dim")
        return None, False
    if not raw:
        return None, True
    parts = raw.split("/")
    if len(parts) != 2 or not all(parts):
        console.print(
            f"  Invalid skill ID '{raw}'. Expected category/skill_name.",
            style="dim #FF9AA2",
        )
        return None, False
    return raw, True


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
    console.print(
        "  skillware list --examples     — add per-skill example script count"
    )
    console.print("  skillware examples            — list indexed runnable scripts")
    console.print("  skillware examples <id>       — scripts for one skill")
    console.print("  skillware test                — run all bundle tests")
    console.print("  skillware test <category/name> — run one skill bundle test")
    console.print("  skillware test --category <n> — run tests for a category")
    console.print("  skillware paths               — show skill root resolution")
    console.print("  skillware --version           — print installed version")
    console.print()

    console.print(Text("Commands", style=f"bold {TABLE_STYLE}"))
    console.print("  list      available now", style=ID_STYLE)
    console.print("  examples  available now", style=ID_STYLE)
    console.print("  test      available now", style=ID_STYLE)
    console.print("  paths     available now", style=ID_STYLE)
    console.print()

    console.print(Text("Interactive mode", style=f"bold {TABLE_STYLE}"))
    console.print(
        "  skillware                     — open interactive menu", style="dim"
    )
    console.print("  1-5 or command name           — select a menu option", style="dim")
    console.print("  q or Ctrl+C                   — exit", style="dim")
    console.print()

    console.print(Text("Examples", style=f"bold {TABLE_STYLE}"))
    console.print("  skillware list --category compliance", style=MENU_STYLE)
    console.print("  skillware list --examples --category dev_tools", style=MENU_STYLE)
    console.print("  skillware examples compliance/tos_evaluator", style=MENU_STYLE)
    console.print("  skillware test finance/wallet_screening", style=MENU_STYLE)
    console.print("  skillware paths", style=MENU_STYLE)
    console.print()

    console.print(Text("Install", style=f"bold {TABLE_STYLE}"))
    console.print("  pip install skillware", style="dim")
    console.print()

    console.print(Text("Docs", style=f"bold {TABLE_STYLE}"))
    console.print(
        "  https://github.com/arpahls/skillware/blob/main/docs/usage/cli.md",
        style=f"dim {SPLASH_STYLE}",
    )


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def _lerp_rgb(
    start: Tuple[int, int, int], end: Tuple[int, int, int], t: float
) -> Tuple[int, int, int]:
    return tuple(int(start[i] + (end[i] - start[i]) * t) for i in range(3))


def _splash_gradient_color(column: int, width: int) -> str:
    if width <= 1:
        return _rgb_to_hex(SPLASH_GRADIENT_START)
    t = column / (width - 1)
    if t <= 0.5:
        rgb = _lerp_rgb(SPLASH_GRADIENT_START, SPLASH_GRADIENT_MID, t / 0.5)
    else:
        rgb = _lerp_rgb(SPLASH_GRADIENT_MID, SPLASH_GRADIENT_END, (t - 0.5) / 0.5)
    return _rgb_to_hex(rgb)


def _gradient_text_line(line: str, width: int) -> Text:
    text = Text()
    for column, char in enumerate(line):
        text.append(char, style=_splash_gradient_color(column, width))
    return text


def _gradient_splash_text(logo_lines: Tuple[str, ...]) -> Text:
    width = max(len(line) for line in logo_lines)
    text = Text()
    for line in logo_lines:
        text.append(_gradient_text_line(line, width))
        text.append("\n")
    return text


def _package_version_str() -> str:
    installed = get_installed_version()
    if installed is not None:
        return str(installed)
    try:
        return importlib.metadata.version("skillware")
    except importlib.metadata.PackageNotFoundError:
        return "dev"


def cmd_interactive(console=None, parser=None) -> None:
    """Launch ASCII splash screen and interactive menu."""
    if console is None:
        console = Console()

    version = _package_version_str()
    logo_width = max(len(line) for line in _SPLASH_LOGO_LINES)

    console.print(_gradient_splash_text(_SPLASH_LOGO_LINES))
    console.print(
        _gradient_text_line(
            f"  Skillware v{version} — Skill Management Framework",
            logo_width,
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
        ("2", "examples", "browse runnable scripts from examples/README.md"),
        ("3", "test", "run bundle tests (test_skill.py) for one or all skills"),
        ("4", "paths", "show skill directory resolution order and shadowing"),
        ("5", "help", "usage guide for any command"),
    ]

    commands = {
        "1": "list",
        "list": "list",
        "2": "examples",
        "examples": "examples",
        "3": "test",
        "test": "test",
        "4": "paths",
        "paths": "paths",
        "5": "help",
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
        elif command == "examples":
            skill_id, run = _prompt_examples_skill_id(console)
            if run:
                cmd_examples(skill_id=skill_id, console=console)
        elif command == "test":
            cmd_test(console=console)
        elif command == "paths":
            cmd_paths(console=console)
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

    _version_str = _package_version_str()

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
    list_parser.add_argument(
        "--examples",
        action="store_true",
        help="Add EXAMPLES column with indexed script count per skill.",
    )

    examples_parser = subparsers.add_parser(
        "examples",
        help="List runnable example scripts from examples/README.md.",
    )
    examples_parser.add_argument(
        "skill_id",
        nargs="?",
        default=None,
        help="Optional skill ID (category/skill_name) to filter scripts.",
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

    paths_parser = subparsers.add_parser(
        "paths",
        help="Show skill root resolution order and shadowing.",
    )
    paths_parser.add_argument(
        "--skills-root",
        type=Path,
        default=None,
        help="Override the skills directory path for this command only.",
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
            show_examples=args.examples,
        )
    elif args.command == "examples":
        raise SystemExit(cmd_examples(skill_id=args.skill_id))
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
    elif args.command == "paths":
        raise SystemExit(cmd_paths(skills_root_override=args.skills_root))
    else:
        cmd_interactive(parser=parser)


if __name__ == "__main__":
    main()

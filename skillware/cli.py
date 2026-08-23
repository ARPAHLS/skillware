import argparse
import builtins
import re
import subprocess
import sys
import yaml
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union

import requests

from rich.table import Table
from rich.console import Console
from rich.text import Text
from rich.status import Status
from rich import box

import importlib.metadata

from skillware.core.loader import SkillLoader
from skillware.core.config import (
    GLOBAL_CONFIG_FILENAME,
    PROJECT_CONFIG_FILENAME,
    format_config_sources,
    global_config_path,
    load_merged_config,
    load_project_paths_settings,
    project_config_write_path,
    save_global_presentation_theme,
    save_project_config,
)
from skillware.core.mail_config import format_mail_config_lines
from skillware.cli_mail import cmd_mail, cmd_mail_submenu
from skillware.core.discovery import (
    SKILLWARE_SKILL_PATH_ENV,
    bundled_skill_root,
    find_shadow_conflicts,
    get_skill_roots,
    list_flat_layout_skill_names,
    list_registry_skill_ids,
    resolution_order_summary,
)
from skillware.version_policy import emit_upgrade_advisory, get_installed_version


@dataclass(frozen=True)
class ThemePalette:
    """Semantic Rich styles for one built-in CLI theme."""

    heading_style: str
    category_style: str
    id_style: str
    border_style: str
    splash_style: str
    menu_style: str
    error_color: str
    gradient_start: Tuple[int, int, int]
    gradient_mid: Tuple[int, int, int]
    gradient_end: Tuple[int, int, int]


THEMES: Dict[str, ThemePalette] = {
    "pastel": ThemePalette(
        heading_style="bold #C7CEEA",
        category_style="bold #FFDAC1",
        id_style="#B5EAD7",
        border_style="#C7CEEA",
        splash_style="#C7CEEA",
        menu_style="#FFDAC1",
        error_color="#FF9AA2",
        gradient_start=(0xD4, 0xE4, 0xF1),
        gradient_mid=(0x79, 0xB6, 0xD8),
        gradient_end=(0xEB, 0xD8, 0xDC),
    ),
    "ocean": ThemePalette(
        heading_style="bold #7DD3FC",
        category_style="bold #38BDF8",
        id_style="#BAE6FD",
        border_style="#0284C7",
        splash_style="#38BDF8",
        menu_style="#7DD3FC",
        error_color="#F87171",
        gradient_start=(0x0C, 0x4A, 0x6E),
        gradient_mid=(0x02, 0x84, 0xC7),
        gradient_end=(0x7D, 0xD3, 0xFC),
    ),
    "mono": ThemePalette(
        heading_style="bold #D0D0D0",
        category_style="bold #A8A8A8",
        id_style="#E0E0E0",
        border_style="#808080",
        splash_style="#C0C0C0",
        menu_style="#A8A8A8",
        error_color="#B0B0B0",
        gradient_start=(0xF0, 0xF0, 0xF0),
        gradient_mid=(0xA0, 0xA0, 0xA0),
        gradient_end=(0x60, 0x60, 0x60),
    ),
}


def _active_theme() -> ThemePalette:
    """Return the configured palette; config normalization guarantees fallback."""
    theme_name = load_merged_config().presentation.theme
    return THEMES.get(theme_name, THEMES["pastel"])


_DEFAULT_PALETTE = THEMES["pastel"]
TABLE_STYLE = _DEFAULT_PALETTE.heading_style
CATEGORY_STYLE = _DEFAULT_PALETTE.category_style
ID_STYLE = _DEFAULT_PALETTE.id_style
BORDER_STYLE = _DEFAULT_PALETTE.border_style
SPLASH_STYLE = _DEFAULT_PALETTE.splash_style
MENU_STYLE = _DEFAULT_PALETTE.menu_style
ERROR_STYLE = f"bold {_DEFAULT_PALETTE.error_color}"
ERROR_DIM_STYLE = f"dim {_DEFAULT_PALETTE.error_color}"
SPLASH_GRADIENT_START = _DEFAULT_PALETTE.gradient_start
SPLASH_GRADIENT_MID = _DEFAULT_PALETTE.gradient_mid
SPLASH_GRADIENT_END = _DEFAULT_PALETTE.gradient_end


def _apply_active_theme() -> None:
    """Refresh module styles from the currently merged configuration."""
    palette = _active_theme()
    global TABLE_STYLE, CATEGORY_STYLE, ID_STYLE, BORDER_STYLE
    global SPLASH_STYLE, MENU_STYLE, ERROR_STYLE, ERROR_DIM_STYLE
    global SPLASH_GRADIENT_START, SPLASH_GRADIENT_MID, SPLASH_GRADIENT_END

    TABLE_STYLE = palette.heading_style
    CATEGORY_STYLE = palette.category_style
    ID_STYLE = palette.id_style
    BORDER_STYLE = palette.border_style
    SPLASH_STYLE = palette.splash_style
    MENU_STYLE = palette.menu_style
    ERROR_STYLE = f"bold {palette.error_color}"
    ERROR_DIM_STYLE = f"dim {palette.error_color}"
    SPLASH_GRADIENT_START = palette.gradient_start
    SPLASH_GRADIENT_MID = palette.gradient_mid
    SPLASH_GRADIENT_END = palette.gradient_end


_DOCS_CLI = "docs/usage/cli.md"
_DOCS_CLI_LIST = f"{_DOCS_CLI}#skillware-list"
_DOCS_CLI_EXAMPLES = f"{_DOCS_CLI}#skillware-examples"
_DOCS_CLI_PATHS = f"{_DOCS_CLI}#skillware-paths"
_DOCS_CLI_CONFIG = f"{_DOCS_CLI}#skillware-config"
_DOCS_CLI_MAIL = f"{_DOCS_CLI}#skillware-mail"

HELP_GROUPS: List[Tuple[str, List[Tuple[str, str]], str]] = [
    (
        "Skills",
        [
            ("skillware list", "discover installed registry skills"),
            ("skillware list --category <n>", "filter by category"),
            ("skillware list --issuer <h>", "filter by issuer"),
            ("skillware list --examples", "per-skill example script counts"),
            ("skillware list --skills-root <path>", "one-shot skills root override"),
            ("skillware test [id]", "run bundle tests via pytest"),
            ("skillware test --category <n>", "test all skills in a category"),
            ("skillware doctor [id]", "check deps and skill.py import"),
            ("skillware doctor --category <n>", "diagnose a category"),
        ],
        _DOCS_CLI_LIST,
    ),
    (
        "Examples",
        [
            ("skillware examples", "list runnable scripts from examples/README.md"),
            ("skillware examples <id>", "scripts for one skill ID"),
        ],
        _DOCS_CLI_EXAMPLES,
    ),
    (
        "Paths",
        [
            ("skillware paths", "show resolution order, tiers, and shadowing"),
            ("skillware paths --skills-root <path>", "one-shot root override"),
            (
                "skillware (menu 4 / paths)",
                "interactive paths submenu — view, edit, diagnose",
            ),
        ],
        _DOCS_CLI_PATHS,
    ),
    (
        "Config",
        [
            ("skillware config show", "merged global + project YAML (read-only)"),
            ("skillware (menu 8 / theme)", "choose and save the global CLI theme"),
        ],
        _DOCS_CLI_CONFIG,
    ),
    (
        "Mail",
        [
            ("skillware mail", "resolved address book and signature paths"),
            ("skillware mail addressbook init", "create user config addressbook.yaml"),
            ("skillware mail addressbook add", "interactive contact wizard"),
            ("skillware mail addressbook show", "resolved path and contact count"),
            ("skillware mail addressbook validate", "schema check"),
            ("skillware mail signature set", "paste or --file signature text"),
            (
                "skillware mail signature init",
                "default plain + HTML signature with logo",
            ),
            ("skillware (menu 7 / mail)", "interactive mail submenu"),
        ],
        _DOCS_CLI_MAIL,
    ),
    (
        "General",
        [
            ("skillware", "interactive menu (splash + numbered options)"),
            ("skillware --help", "grouped command reference"),
            ("skillware --version", "installed package version"),
        ],
        _DOCS_CLI,
    ),
]

_PATHS_SUBMENU = [
    ("1", "view", "show resolution order, tiers, and shadowing"),
    ("2", "bundled", "view bundled registry root (read-only)"),
    ("3", "project", "set project path (auto or explicit directory)"),
    ("4", "external", "add or remove external skill roots"),
    ("5", "shadows", "shadowing summary only"),
    ("6", "flat", "diagnose flat-layout skills not shown in list"),
]

_THEME_CHOICES = [
    ("1", "pastel", "original Skillware palette"),
    ("2", "ocean", "deep blue, sky, and cyan"),
    ("3", "mono", "grayscale"),
]

_NAV_EXIT = "exit"
_NAV_BACK = "back"

# Interactive help topics: (key, slug, summary, HELP_GROUPS index or special tag)
_HELP_MENU: List[Tuple[str, str, str, Union[int, str]]] = [
    ("1", "skills", "list, test, doctor", 0),
    ("2", "examples", "indexed runnable scripts", 1),
    ("3", "paths", "resolution and path editor", 2),
    ("4", "config", "merged YAML settings", 3),
    ("5", "mail", "address book and signature setup", 4),
    ("6", "general", "menu, help, version", 5),
    ("7", "install", "pip install skillware", "install"),
    ("8", "docs", "full CLI guide online", "docs"),
    ("9", "interactive", "numbered splash menu", "interactive"),
]

_CLI_USAGE_EXAMPLES: Tuple[str, ...] = (
    "skillware list --category compliance",
    "skillware list --examples --category dev_tools",
    "skillware examples compliance/tos_evaluator",
    "skillware test finance/wallet_screening",
    "skillware paths",
    "skillware config show",
    "skillware mail addressbook show",
    "skillware doctor --category compliance",
)
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


def _example_github_cell(script: str) -> Text:
    """Compact clickable label for the examples table (full URL is the link target)."""
    url = _example_github_url(script)
    return Text.from_markup(f'[link="{url}" dim {SPLASH_STYLE}]{script}[/link]')


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
    _apply_active_theme()
    if console is None:
        console = Console(stderr=True)

    targets, error = _resolve_pytest_targets(
        skills_root_override=skills_root_override,
        skill_id=skill_id,
        category=category,
    )
    if error:
        console.print(error, style=ERROR_STYLE)
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
    _apply_active_theme()
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
                style=ERROR_STYLE,
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
    _apply_active_theme()
    if console is None:
        console = Console()

    rows, readme_source = _load_examples_index()
    if readme_source is None:
        console.print(
            "Could not load examples/README.md from the repo or GitHub.",
            style=ERROR_STYLE,
        )
        return 1

    if skill_id:
        parts = skill_id.split("/")
        if len(parts) != 2 or not all(parts):
            console.print(
                f"Invalid skill ID '{skill_id}'. Expected category/skill_name.",
                style=ERROR_STYLE,
            )
            return 2

        rows = [row for row in rows if skill_id in row["skill_ids"]]
        if not rows:
            console.print(
                f"No indexed examples for '{skill_id}'. "
                f"See {_examples_readme_display_path(readme_source)} for the full inventory.",
                style=ERROR_STYLE,
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
    table.add_column("EXTRA", style="dim", ratio=2)
    table.add_column("GITHUB", style=f"dim {SPLASH_STYLE}", no_wrap=True, ratio=1)

    for row in rows:
        script = row["script"]
        table.add_row(
            script,
            ", ".join(row["skill_ids"]),
            _flatten_table_cell(row["provider"], max_len=36),
            _flatten_table_cell(row["extra"], max_len=48),
            _example_github_cell(script),
        )

    console.print(table)
    console.print(
        f"Full notes: {_examples_readme_display_path(readme_source)}",
        style="dim",
    )
    return 0


def _read_line(prompt: str, input_fn=None) -> Optional[str]:
    if input_fn is None:
        input_fn = builtins.input
    try:
        return input_fn(prompt).strip()
    except (KeyboardInterrupt, EOFError):
        return None


def _parse_nav(raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse menu input. Returns ``(choice, nav)`` where ``nav`` is ``_NAV_EXIT``,
    ``_NAV_BACK``, or ``None`` for a normal command choice.
    """
    if raw is None:
        return None, _NAV_BACK
    text = raw.strip()
    if not text:
        return "", None
    key = text.lower()
    if key in ("0", "q", "quit", "exit"):
        return None, _NAV_EXIT
    if key in ("b", "back", "esc", "escape"):
        return None, _NAV_BACK
    return text, None


def _print_nav_footer(console, *, show_back: bool = True) -> None:
    console.print("  ---", style="dim")
    if show_back:
        console.print("  b — back to previous menu", style="dim")
    console.print("  0 — exit Skillware", style="dim")
    console.print()


def _print_help_command_group(
    console, group: Tuple[str, List[Tuple[str, str]], str]
) -> None:
    group_name, commands, doc_link = group
    console.print(Text(group_name, style=TABLE_STYLE))
    for command, description in commands:
        console.print(f"  {command} — {description}", style=MENU_STYLE)
    console.print(f"  Read more: {doc_link}", style=f"dim {SPLASH_STYLE}")
    console.print()


def _print_help_index(console) -> None:
    console.print(Text("Usage", style=TABLE_STYLE))
    console.print(
        "  Run skillware and choose help (6) for full topic details.",
        style="dim",
    )
    console.print()
    console.print(Text("Topics", style=TABLE_STYLE))
    for key, slug, summary, _target in _HELP_MENU:
        console.print(f"  {key} {slug:<12}— {summary}", style=MENU_STYLE)
    console.print()


def _print_cli_usage_examples(console) -> None:
    console.print(Text("CLI usage examples", style=TABLE_STYLE))
    for line in _CLI_USAGE_EXAMPLES:
        console.print(f"  {line}", style=MENU_STYLE)
    console.print()


def _print_help_static_topic(console, topic: str) -> None:
    if topic == "install":
        console.print(Text("Install", style=TABLE_STYLE))
        console.print("  pip install skillware", style=MENU_STYLE)
        console.print('  pip install -e ".[dev,all]"  # local development', style="dim")
    elif topic == "docs":
        console.print(Text("Docs", style=TABLE_STYLE))
        console.print(
            "  https://github.com/arpahls/skillware/blob/main/docs/usage/cli.md",
            style=f"dim {SPLASH_STYLE}",
        )
    elif topic == "interactive":
        console.print(Text("Interactive mode", style=TABLE_STYLE))
        console.print("  skillware — open splash menu", style=MENU_STYLE)
        console.print("  1-8 or command name — run a command", style="dim")
        console.print("  0 — exit from any menu level", style="dim")
    console.print()


def _print_help_groups(console, *, compact: bool = False) -> None:
    """Print all help groups (legacy flat dump). Prefer cmd_help(brief=True)."""
    console.print(Text("Usage", style=TABLE_STYLE))
    for group in HELP_GROUPS:
        _print_help_command_group(console, group)


def cmd_help_submenu(console=None, input_fn=None) -> Optional[str]:
    """Interactive help topics. Returns _NAV_EXIT to quit Skillware."""
    _apply_active_theme()
    if console is None:
        console = Console()

    topic_map = {key: target for key, _slug, _summary, target in _HELP_MENU}
    topic_map.update({slug: target for key, slug, _summary, target in _HELP_MENU})

    while True:
        console.print(Text("Help", style=TABLE_STYLE))
        for key, slug, summary, _target in _HELP_MENU:
            console.print(f"    [{key}] {slug:<12}— {summary}", style=MENU_STYLE)
        _print_nav_footer(console, show_back=True)

        raw = _read_line("  help> ", input_fn)
        choice, nav = _parse_nav(raw)
        if nav == _NAV_EXIT:
            return _NAV_EXIT
        if nav == _NAV_BACK:
            return None
        if not choice:
            continue

        target = topic_map.get(choice.lower())
        if target is None:
            console.print(f"  Unknown topic: '{choice}'", style=ERROR_DIM_STYLE)
            console.print()
            continue

        if isinstance(target, int):
            _print_help_command_group(console, HELP_GROUPS[target])
        else:
            _print_help_static_topic(console, target)

        pause = _read_line("  Press Enter to return to help topics… ", input_fn)
        _, pause_nav = _parse_nav(pause if pause else "")
        if pause_nav == _NAV_EXIT:
            return _NAV_EXIT
        if pause_nav == _NAV_BACK:
            continue
        console.print()


def _print_paths_submenu(console) -> None:
    console.print(Text("Paths", style=TABLE_STYLE))
    console.print(
        f"  Project config: {project_config_write_path()}",
        style="dim",
    )
    console.print(
        "  Bundled registry is read-only and always available.",
        style="dim",
    )
    console.print()
    for key, name, desc in _PATHS_SUBMENU:
        console.print(f"    [{key}] {name:<10}— {desc}", style=MENU_STYLE)
    _print_nav_footer(console, show_back=True)


def _cmd_paths_show_bundled(console) -> None:
    root = bundled_skill_root(include_missing=True)
    console.print(Text("Bundled registry (read-only)", style=TABLE_STYLE))
    console.print(f"  path: {root.path}", style=MENU_STYLE)
    console.print(f"  status: {'ok' if root.exists else 'missing'}", style="dim")
    if root.exists:
        skill_ids = list_registry_skill_ids(root.path)
        console.print(f"  skills: {len(skill_ids)} registry IDs", style=MENU_STYLE)
        for skill_id in skill_ids[:12]:
            console.print(f"    - {skill_id}", style="dim")
        if len(skill_ids) > 12:
            console.print(f"    … and {len(skill_ids) - 12} more", style="dim")
    console.print(
        "  Bundled skills ship with pip install skillware and cannot be edited here.",
        style="dim",
    )


def _cmd_paths_shadows_only(
    console, skills_root_override: Optional[Path] = None
) -> None:
    roots = get_skill_roots(skills_root_override, for_display=True)
    conflicts = find_shadow_conflicts(roots)
    if not conflicts:
        console.print("No shadowing detected across active roots.", style=MENU_STYLE)
        return

    console.print(Text("Shadowing (first root wins)", style=TABLE_STYLE))
    for conflict in conflicts[:30]:
        console.print(
            f"  {conflict.skill_id}: "
            f"{conflict.winner.tier.value} at {conflict.winner.path} "
            f"shadows {conflict.shadowed.tier.value} at {conflict.shadowed.path}",
            style=ERROR_STYLE,
        )
    if len(conflicts) > 30:
        console.print(f"  … and {len(conflicts) - 30} more", style="dim")


def _cmd_paths_flat_diagnose(
    console, skills_root_override: Optional[Path] = None
) -> None:
    roots = get_skill_roots(skills_root_override, for_display=True)
    console.print(Text("Flat-layout skills (loadable, not in list)", style=TABLE_STYLE))
    found_any = False
    for root in roots:
        if not root.exists:
            continue
        flat_names = list_flat_layout_skill_names(root.path)
        if not flat_names:
            continue
        found_any = True
        console.print(
            f"  {root.tier.value} @ {root.path}:",
            style=MENU_STYLE,
        )
        for name in flat_names:
            console.print(f"    - {name}/  (use absolute path or flat ID)", style="dim")
    if not found_any:
        console.print(
            "  No flat-layout skills found under active roots.",
            style="dim",
        )
    console.print(
        "  Registry layout category/skill_name/ appears in skillware list.",
        style="dim",
    )


def _cmd_paths_edit_project(console, input_fn=None) -> None:
    paths = load_project_paths_settings()
    current = paths.project if paths.project is not None else "auto"
    console.print(f"  Current project path: {current}", style=MENU_STYLE)
    console.print(
        "  Enter 'auto', a directory path, or press Enter to keep.", style="dim"
    )
    raw = _read_line("  project> ", input_fn)
    if raw is None:
        console.print("  Cancelled.", style="dim")
        return
    if not raw:
        return

    if raw.lower() == "auto":
        paths.project = "auto"
    else:
        candidate = Path(raw).expanduser()
        if not candidate.is_dir():
            console.print(f"  Not a directory: {candidate}", style=ERROR_STYLE)
            return
        paths.project = str(candidate.resolve())

    target = save_project_config(paths)
    console.print(f"  Saved project path to {target}", style=ID_STYLE)


def _cmd_paths_edit_external(console, input_fn=None) -> None:
    paths = load_project_paths_settings()
    while True:
        console.print(Text("External paths (project config)", style=TABLE_STYLE))
        if paths.external:
            for index, entry in enumerate(paths.external, start=1):
                console.print(f"    [{index}] {entry}", style=MENU_STYLE)
        else:
            console.print("    (none)", style="dim")
        console.print("  [a] add  [r] remove  [Enter] done", style="dim")
        raw = _read_line("  external> ", input_fn)
        if raw is None:
            console.print("  Cancelled.", style="dim")
            return
        if not raw:
            return

        choice = raw.lower()
        if choice == "a":
            path_raw = _read_line("  path> ", input_fn)
            if path_raw is None:
                console.print("  Cancelled.", style="dim")
                return
            if not path_raw:
                continue
            candidate = Path(path_raw).expanduser()
            if not candidate.is_dir():
                console.print(f"  Not a directory: {candidate}", style=ERROR_STYLE)
                continue
            resolved = str(candidate.resolve())
            if resolved not in paths.external:
                paths.external.append(resolved)
                target = save_project_config(paths)
                console.print(f"  Added and saved to {target}", style=ID_STYLE)
            else:
                console.print("  Path already listed.", style="dim")
        elif choice == "r":
            if not paths.external:
                console.print("  Nothing to remove.", style="dim")
                continue
            index_raw = _read_line("  remove #> ", input_fn)
            if index_raw is None:
                console.print("  Cancelled.", style="dim")
                return
            try:
                index = int(index_raw)
            except ValueError:
                console.print("  Enter a list number.", style=ERROR_STYLE)
                continue
            if index < 1 or index > len(paths.external):
                console.print("  Invalid number.", style=ERROR_STYLE)
                continue
            removed = paths.external.pop(index - 1)
            target = save_project_config(paths)
            console.print(f"  Removed {removed}; saved to {target}", style=ID_STYLE)
        else:
            console.print("  Unknown choice.", style=ERROR_DIM_STYLE)


def cmd_paths_submenu(
    skills_root_override: Optional[Path] = None,
    console=None,
    input_fn=None,
) -> Optional[str]:
    """Interactive paths submenu (menu option 4). Returns _NAV_EXIT to quit Skillware."""
    _apply_active_theme()
    if console is None:
        console = Console()

    submenu_commands = {
        "1": "view",
        "view": "view",
        "2": "bundled",
        "bundled": "bundled",
        "3": "project",
        "project": "project",
        "4": "external",
        "external": "external",
        "5": "shadows",
        "shadows": "shadows",
        "6": "flat",
        "flat": "flat",
    }

    while True:
        _print_paths_submenu(console)
        raw = _read_line("  paths> ", input_fn)
        choice, nav = _parse_nav(raw)
        if nav == _NAV_EXIT:
            return _NAV_EXIT
        if nav == _NAV_BACK:
            return None
        if not choice:
            continue

        command = submenu_commands.get(choice.lower())
        if command == "view":
            cmd_paths(skills_root_override=skills_root_override, console=console)
        elif command == "bundled":
            _cmd_paths_show_bundled(console)
        elif command == "project":
            _cmd_paths_edit_project(console, input_fn=input_fn)
        elif command == "external":
            _cmd_paths_edit_external(console, input_fn=input_fn)
        elif command == "shadows":
            _cmd_paths_shadows_only(console, skills_root_override=skills_root_override)
        elif command == "flat":
            _cmd_paths_flat_diagnose(console, skills_root_override=skills_root_override)
        elif command is None:
            console.print(f"  Unknown choice: '{choice}'", style=ERROR_DIM_STYLE)
        console.print()


def cmd_paths(
    skills_root_override: Optional[Path] = None,
    console=None,
) -> int:
    """Show skill root resolution order, tiers, and shadowing (read-only config via skillware config show)."""
    _apply_active_theme()
    if console is None:
        console = Console()

    cwd = Path.cwd().resolve()
    console.print(Text("Skill path resolution", style=TABLE_STYLE))
    console.print(f"  cwd: {cwd}", style="dim")
    console.print()

    roots = get_skill_roots(skills_root_override, for_display=True)
    if not roots:
        console.print(
            "No skill roots configured. Set "
            f"{SKILLWARE_SKILL_PATH_ENV} or use --skills-root.",
            style=ERROR_STYLE,
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
        status_style = ID_STYLE if root.exists else ERROR_STYLE
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
        console.print(Text("Shadowing (first root wins on load)", style=TABLE_STYLE))
        for conflict in conflicts[:20]:
            console.print(
                f"  {conflict.skill_id}: "
                f"{conflict.winner.tier.value} at {conflict.winner.path} "
                f"shadows {conflict.shadowed.tier.value} at {conflict.shadowed.path}",
                style=ERROR_STYLE,
            )
        if len(conflicts) > 20:
            console.print(f"  … and {len(conflicts) - 20} more", style="dim")
        console.print()

    console.print(Text("Resolution order", style=TABLE_STYLE))
    for label, detail in resolution_order_summary():
        console.print(f"  {label}: {detail}", style="dim")
    console.print()

    console.print(Text("Tips", style=TABLE_STYLE))
    console.print(
        "  • One-shot override: skillware list --skills-root /path/to/skills",
        style=MENU_STYLE,
    )
    console.print(
        f"  • Persistent paths: {PROJECT_CONFIG_FILENAME} or {global_config_path()}",
        style=MENU_STYLE,
    )
    console.print(
        f"  • Legacy env override: export {SKILLWARE_SKILL_PATH_ENV}=/path/to/skills",
        style=MENU_STYLE,
    )
    console.print("  • Inspect merged config: skillware config show", style=MENU_STYLE)
    console.print(
        "  • Trust tiers: docs/security/skill-trust-model.md",
        style=f"dim {SPLASH_STYLE}",
    )
    console.print(
        "  • Flat-layout skills (<root>/<name>/) load but may not appear in list",
        style="dim",
    )
    return 0


def cmd_config_show(console=None) -> int:
    """Print merged global + project configuration (read-only)."""
    _apply_active_theme()
    if console is None:
        console = Console()

    config = load_merged_config(refresh=True)
    paths = config.paths
    console.print(Text("Skillware config", style=TABLE_STYLE))
    console.print()

    console.print(Text("Config files", style=TABLE_STYLE))
    console.print(f"  Global (default): {global_config_path()}", style="dim")
    for line in format_config_sources(config):
        console.print(f"  Loaded: {line}", style=MENU_STYLE if config.layers else "dim")
    console.print()

    console.print(Text("presentation (active)", style=TABLE_STYLE))
    console.print(f"  theme: {config.presentation.theme}", style=MENU_STYLE)
    console.print()

    if not config.has_config_files:
        console.print(
            "No config files found — using legacy resolution "
            f"({SKILLWARE_SKILL_PATH_ENV} → ./skills/ walk → bundled).",
            style="dim",
        )
        console.print(
            f"Create {PROJECT_CONFIG_FILENAME} or {GLOBAL_CONFIG_FILENAME} to persist settings.",
            style="dim",
        )
        console.print(
            "  docs/usage/cli.md#skillware-config", style=f"dim {SPLASH_STYLE}"
        )
        console.print()
        console.print(Text("mail (resolved defaults)", style=f"bold {TABLE_STYLE}"))
        for line in format_mail_config_lines(config.mail):
            console.print(line, style=MENU_STYLE)
        return 0

    console.print(Text("paths (active)", style=TABLE_STYLE))
    project_label = paths.project if paths.project is not None else "auto"
    console.print(f"  project: {project_label}", style=MENU_STYLE)
    if paths.external:
        console.print("  external:", style=MENU_STYLE)
        for entry in paths.external:
            console.print(f"    - {entry}", style="dim")
    else:
        console.print("  external: []", style=MENU_STYLE)

    order = " → ".join(paths.resolution_order)
    console.print(f"  resolution.order: {order}", style=MENU_STYLE)
    console.print(
        f"  legacy.honor_skillware_skill_path: {paths.honor_skillware_skill_path}",
        style=MENU_STYLE,
    )
    console.print()

    console.print(Text("mail (active)", style=f"bold {TABLE_STYLE}"))
    for line in format_mail_config_lines(config.mail):
        console.print(line, style=MENU_STYLE)
    console.print()

    if config.extra:
        console.print(Text("Other sections (reserved)", style=TABLE_STYLE))
        for key in sorted(config.extra):
            console.print(f"  {key}: (present, not applied yet)", style="dim")
        console.print()

    console.print(
        "Bundled registry is always included and cannot be removed via config.",
        style="dim",
    )
    console.print(
        "Edit via interactive menu (paths, mail, themes) or YAML manually.",
        style="dim",
    )
    return 0


def cmd_theme_picker(console=None, input_fn=None) -> Optional[str]:
    """Select and persist a global CLI theme. Returns _NAV_EXIT when requested."""
    if console is None:
        console = Console()

    choices = {key: name for key, name, _description in _THEME_CHOICES}
    choices.update({name: name for _key, name, _description in _THEME_CHOICES})

    while True:
        _apply_active_theme()
        current = load_merged_config().presentation.theme
        console.print(Text("Theme", style=TABLE_STYLE))
        console.print(f"  Current: {current}", style=ID_STYLE)
        console.print()
        for key, name, description in _THEME_CHOICES:
            console.print(
                f"    [{key}] {name:<8}— {description}",
                style=MENU_STYLE,
            )
        _print_nav_footer(console, show_back=True)

        raw = _read_line("  theme> ", input_fn)
        choice, nav = _parse_nav(raw)
        if nav == _NAV_EXIT:
            return _NAV_EXIT
        if nav == _NAV_BACK:
            return None
        if not choice:
            continue

        selected = choices.get(choice.lower())
        if selected is None:
            console.print(f"  Unknown theme: '{choice}'", style=ERROR_DIM_STYLE)
            console.print()
            continue

        target = save_global_presentation_theme(selected)
        _apply_active_theme()
        effective = load_merged_config().presentation.theme
        console.print(f"  Saved global theme '{selected}' to {target}", style=ID_STYLE)
        if effective != selected:
            console.print(
                f"  Project config keeps '{effective}' active in this directory.",
                style="dim",
            )
        return None


def _doctor_load_target(
    skill_id: str, skills_root_override: Optional[Path] = None
) -> str:
    """Resolve skill path for doctor; honor --skills-root like list discovery."""
    if skills_root_override is not None:
        candidate = skills_root_override.expanduser().resolve() / skill_id
        if candidate.is_dir() and SkillLoader._is_skill_dir(candidate):
            return str(candidate)
    return skill_id


def _resolve_doctor_skill_ids(
    skills_root_override: Optional[Path] = None,
    skill_id: Optional[str] = None,
    category: Optional[str] = None,
) -> Tuple[List[str], Optional[str]]:
    if skill_id and category:
        return [], "Use either a skill ID or --category, not both."

    if skill_id:
        return [skill_id.replace("\\", "/").strip("/")], None

    skills = _discover_skills(skills_root_override)
    if category:
        skills = [skill for skill in skills if skill["category"] == category]

    if not skills:
        if category:
            return [], f"No skills found in category '{category}'."
        return [], "No skills found."

    return [skill["id"] for skill in skills], None


def _diagnose_skill(
    skill_id: str,
    skills_root_override: Optional[Path] = None,
) -> Tuple[str, str, str]:
    """Return (deps_status, load_status, detail). Status values: ok, fail, skip."""
    load_target = _doctor_load_target(skill_id, skills_root_override)

    try:
        SkillLoader.load_skill(
            load_target,
            execute_module=False,
            check_requirements=True,
        )
        deps_status = "ok"
    except ImportError as exc:
        detail = _flatten_table_cell(str(exc).splitlines()[0], 72)
        return "fail", "skip", detail

    try:
        SkillLoader.load_skill(
            load_target,
            execute_module=True,
            check_requirements=False,
        )
        return deps_status, "ok", ""
    except ImportError as exc:
        detail = _flatten_table_cell(str(exc).splitlines()[0], 72)
        return deps_status, "fail", detail


def cmd_doctor(
    skills_root_override: Optional[Path] = None,
    skill_id: Optional[str] = None,
    category: Optional[str] = None,
    console=None,
) -> int:
    """Check manifest deps and skill.py import without running execute()."""
    _apply_active_theme()
    if console is None:
        console = Console(stderr=True)

    skill_ids, error = _resolve_doctor_skill_ids(
        skills_root_override=skills_root_override,
        skill_id=skill_id,
        category=category,
    )
    if error:
        console.print(error, style=ERROR_STYLE)
        return 2 if skill_id and category else 1

    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style=BORDER_STYLE,
        header_style=TABLE_STYLE,
        expand=True,
    )
    table.add_column("ID", style=ID_STYLE, no_wrap=True, ratio=2)
    table.add_column("DEPS", no_wrap=True, ratio=1)
    table.add_column("LOAD", no_wrap=True, ratio=1)
    table.add_column("DETAIL", style="dim", ratio=4)

    failures = 0
    rows: List[Tuple[str, Text, Text, str]] = []
    spinner_label = (
        f"Diagnosing {len(skill_ids)} skill(s)…"
        if len(skill_ids) != 1
        else f"Diagnosing {skill_ids[0]}…"
    )
    with Status(spinner_label, console=console, spinner="dots"):
        for sid in sorted(skill_ids):
            try:
                deps_status, load_status, detail = _diagnose_skill(
                    sid, skills_root_override=skills_root_override
                )
            except FileNotFoundError as exc:
                console.print(str(exc), style=ERROR_STYLE)
                return 1

            if deps_status != "ok" or load_status == "fail":
                failures += 1

            deps_cell = Text(
                deps_status,
                style=ID_STYLE if deps_status == "ok" else ERROR_STYLE,
            )
            if load_status == "skip":
                load_cell = Text("—", style="dim")
            elif load_status == "ok":
                load_cell = Text(load_status, style=ID_STYLE)
            else:
                load_cell = Text(load_status, style=ERROR_STYLE)

            rows.append((sid, deps_cell, load_cell, detail or "—"))

    for sid, deps_cell, load_cell, detail in rows:
        table.add_row(sid, deps_cell, load_cell, detail)

    console.print(table)
    console.print(
        "DEPS = manifest requirements; LOAD = skill.py import. "
        "See docs/usage/install_extras.md",
        style="dim",
    )
    return 1 if failures else 0


def _prompt_examples_skill_id(
    console, input_fn=None
) -> Tuple[Optional[str], Optional[str]]:
    """
    Return (skill_id or None for all, nav).
    nav is _NAV_EXIT or _NAV_BACK when the user cancels or navigates out.
    """
    console.print("  skill id (optional, Enter for all)", style="dim")
    raw = _read_line("  examples> ", input_fn)
    choice, nav = _parse_nav(raw if raw is not None else "")
    if nav == _NAV_EXIT:
        return None, _NAV_EXIT
    if nav == _NAV_BACK:
        return None, _NAV_BACK
    if raw is None:
        return None, _NAV_BACK
    if not choice:
        return None, None
    parts = choice.split("/")
    if len(parts) != 2 or not all(parts):
        console.print(
            f"  Invalid skill ID '{choice}'. Expected category/skill_name.",
            style=ERROR_DIM_STYLE,
        )
        return None, _NAV_BACK
    return choice, None


def _print_menu(console, menu) -> None:
    for num, name, desc in menu:
        console.print(f"    [{num}] {name:<20}— {desc}", style=MENU_STYLE)
    _print_nav_footer(console, show_back=False)


def cmd_help(console=None, *, brief: bool = True) -> None:
    """Print CLI help. Brief mode (default) shows topics + examples only."""
    _apply_active_theme()
    if console is None:
        console = Console()

    if brief:
        _print_help_index(console)
        _print_cli_usage_examples(console)
        console.print(Text("Install", style=TABLE_STYLE))
        console.print("  pip install skillware", style="dim")
        console.print()
        console.print(Text("Docs", style=TABLE_STYLE))
        console.print(
            "  https://github.com/arpahls/skillware/blob/main/docs/usage/cli.md",
            style=f"dim {SPLASH_STYLE}",
        )
        console.print()
        console.print(Text("Interactive mode", style=TABLE_STYLE))
        console.print(
            "  skillware — menu 1-8; help topic drill-down via 6", style="dim"
        )
        console.print("  0 — exit from any menu level", style="dim")
        console.print()
        return

    for group in HELP_GROUPS:
        _print_help_command_group(console, group)
    _print_cli_usage_examples(console)


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
    _apply_active_theme()
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
        ("4", "paths", "paths submenu — view, edit, and diagnose skill roots"),
        ("5", "doctor", "check manifest deps and skill.py import readiness"),
        ("6", "help", "grouped help topics and doc links"),
        ("7", "mail", "address book and signature for office/gmail_handler"),
        ("8", "theme", "choose and save the CLI color theme"),
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
        "5": "doctor",
        "doctor": "doctor",
        "6": "help",
        "help": "help",
        "7": "mail",
        "mail": "mail",
        "8": "theme",
        "theme": "theme",
    }

    _print_menu(console, menu)

    while True:
        raw = _read_line("  > ")
        if raw is None:
            console.print("\n  Bye.", style="dim")
            return
        choice, nav = _parse_nav(raw)
        if nav == _NAV_EXIT:
            console.print("  Bye.", style="dim")
            return
        if nav == _NAV_BACK:
            continue
        if not choice:
            continue

        command = commands.get(choice.lower())

        if command == "list":
            cmd_list(console=console)
        elif command == "examples":
            skill_id, ex_nav = _prompt_examples_skill_id(console)
            if ex_nav == _NAV_EXIT:
                console.print("  Bye.", style="dim")
                return
            if ex_nav != _NAV_BACK:
                cmd_examples(skill_id=skill_id, console=console)
        elif command == "test":
            console.print("  Running bundle tests (pytest)…", style="dim")
            cmd_test(console=console)
        elif command == "paths":
            paths_nav = cmd_paths_submenu(console=console)
            if paths_nav == _NAV_EXIT:
                console.print("  Bye.", style="dim")
                return
        elif command == "doctor":
            rc = cmd_doctor(console=console)
            if rc:
                console.print(
                    f"  doctor exited with status {rc}", style=ERROR_DIM_STYLE
                )
        elif command == "mail":
            mail_nav = cmd_mail_submenu(console=console)
            if mail_nav == _NAV_EXIT:
                console.print("  Bye.", style="dim")
                return
        elif command == "help":
            help_nav = cmd_help_submenu(console=console)
            if help_nav == _NAV_EXIT:
                console.print("  Bye.", style="dim")
                return
        elif command == "theme":
            theme_nav = cmd_theme_picker(console=console)
            if theme_nav == _NAV_EXIT:
                console.print("  Bye.", style="dim")
                return
        else:
            console.print(f"  Unknown command: '{choice}'", style=ERROR_DIM_STYLE)

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

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check manifest deps and skill.py import readiness.",
    )
    doctor_parser.add_argument(
        "skill_id",
        nargs="?",
        default=None,
        help="Skill ID (category/skill_name) to diagnose.",
    )
    doctor_parser.add_argument(
        "--skills-root",
        type=Path,
        default=None,
        help="Override the skills directory path.",
    )
    doctor_parser.add_argument(
        "--category",
        default=None,
        help="Diagnose all skills in a category.",
    )

    config_parser = subparsers.add_parser(
        "config",
        help="Show merged Skillware configuration (read-only).",
    )
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    config_subparsers.add_parser(
        "show",
        help="Print merged global and project YAML settings.",
    )

    mail_parser = subparsers.add_parser(
        "mail",
        help="Address book and signature settings for office/gmail_handler.",
    )
    mail_subparsers = mail_parser.add_subparsers(dest="mail_area")
    mail_addressbook = mail_subparsers.add_parser(
        "addressbook",
        help="Manage addressbook.yaml path and validation.",
    )
    mail_addressbook_sub = mail_addressbook.add_subparsers(dest="mail_action")
    mail_addressbook_sub.add_parser(
        "show", help="Show resolved path and contact count."
    )
    ab_init = mail_addressbook_sub.add_parser(
        "init", help="Create template address book."
    )
    ab_init.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Target file path (default: resolved path).",
    )
    ab_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing file.",
    )
    mail_addressbook_sub.add_parser("validate", help="Validate address book schema.")
    ab_add = mail_addressbook_sub.add_parser(
        "add",
        help="Add a contact (interactive wizard or flags).",
    )
    ab_add.add_argument("--name", dest="display_name", default=None)
    ab_add.add_argument("--email", default=None)
    ab_add.add_argument("--aliases", default=None, help="Comma-separated aliases.")
    ab_add.add_argument("--org", default=None)
    ab_add.add_argument("--id", dest="contact_id", default=None)
    ab_set = mail_addressbook_sub.add_parser(
        "set-path",
        help="Persist mail.addressbook_path in project config.",
    )
    ab_set.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Path to addressbook.yaml.",
    )

    mail_signature = mail_subparsers.add_parser(
        "signature",
        help="Manage outbound mail signature (plain text).",
    )
    mail_signature_sub = mail_signature.add_subparsers(dest="mail_action")
    mail_signature_sub.add_parser("show", help="Show resolved signature.")
    sig_init = mail_signature_sub.add_parser(
        "init",
        help="Create template signature file or inline config.",
    )
    sig_init.add_argument(
        "--path",
        type=Path,
        default=None,
        help="Target signature file path.",
    )
    sig_init.add_argument(
        "--inline",
        action="store_true",
        help="Store default signature in mail.signature_plain instead of a file.",
    )
    sig_init.add_argument(
        "--force",
        action="store_true",
        help="Overwrite an existing signature file.",
    )
    mail_signature_sub.add_parser("validate", help="Validate configured signature.")
    mail_signature_sub.add_parser("clear", help="Remove signature from project config.")
    mail_signature_sub.add_parser(
        "profiles",
        help="List named signature profiles and active profile.",
    )
    sig_profile = mail_signature_sub.add_parser(
        "set-profile",
        help="Set active signature profile in project config.",
    )
    sig_profile.add_argument(
        "profile_id",
        nargs="?",
        default=None,
        help="Profile id (e.g. default, formal).",
    )
    sig_add = mail_signature_sub.add_parser(
        "add-profile",
        help="Register plain/HTML paths for a named signature profile.",
    )
    sig_add.add_argument(
        "profile_id",
        nargs="?",
        default=None,
        help="Profile id to create or update.",
    )
    sig_add.add_argument(
        "--html",
        type=Path,
        dest="html_path",
        default=None,
        help="Path to HTML signature file.",
    )
    sig_add.add_argument(
        "--plain",
        type=Path,
        dest="plain_path",
        default=None,
        help="Path to plain-text signature file.",
    )
    sig_set = mail_signature_sub.add_parser(
        "set",
        help="Set signature from --file or inline text argument.",
    )
    sig_set.add_argument(
        "--file",
        type=Path,
        dest="signature_file",
        default=None,
        help="Read signature text from a file.",
    )
    sig_set.add_argument(
        "text",
        nargs="?",
        default=None,
        help="Signature plain text (use --file for multi-line).",
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
    elif args.command == "doctor":
        raise SystemExit(
            cmd_doctor(
                skills_root_override=args.skills_root,
                skill_id=args.skill_id,
                category=args.category,
            )
        )
    elif args.command == "config":
        if args.config_command == "show":
            raise SystemExit(cmd_config_show())
        config_parser.print_help()
        raise SystemExit(2)
    elif args.command == "mail":
        if args.mail_area is None:
            raise SystemExit(cmd_mail())
        action = getattr(args, "mail_action", None) or "show"
        kwargs = {}
        if args.mail_area == "addressbook":
            if action == "init":
                kwargs["path"] = getattr(args, "path", None)
                kwargs["force"] = getattr(args, "force", False)
            elif action == "add":
                kwargs["display_name"] = getattr(args, "display_name", None)
                kwargs["email"] = getattr(args, "email", None)
                kwargs["aliases"] = getattr(args, "aliases", None)
                kwargs["org"] = getattr(args, "org", None)
                kwargs["contact_id"] = getattr(args, "contact_id", None)
            elif action == "set-path":
                kwargs["path"] = getattr(args, "path", None)
        elif args.mail_area == "signature":
            if action == "init":
                kwargs["path"] = getattr(args, "path", None)
                kwargs["inline"] = getattr(args, "inline", False)
                kwargs["force"] = getattr(args, "force", False)
            elif action == "set":
                kwargs["file_path"] = getattr(args, "signature_file", None)
                kwargs["text"] = getattr(args, "text", None)
            elif action == "set-profile":
                kwargs["profile_id"] = getattr(args, "profile_id", None)
            elif action == "add-profile":
                kwargs["profile_id"] = getattr(args, "profile_id", None)
                kwargs["html_path"] = getattr(args, "html_path", None)
                kwargs["plain_path"] = getattr(args, "plain_path", None)
        raise SystemExit(cmd_mail(args.mail_area, action, **kwargs))
    else:
        cmd_interactive(parser=parser)


if __name__ == "__main__":
    main()

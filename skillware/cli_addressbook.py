"""CLI commands for the shared operator address book."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple

from rich import box
from rich.console import Console
from rich.table import Table
from rich.text import Text

from skillware.cli_mail import (
    ReadLineFn,
    _read_line,
    cmd_mail_addressbook_add,
    cmd_mail_addressbook_init,
    cmd_mail_addressbook_set_path,
    cmd_mail_addressbook_show,
    cmd_mail_addressbook_validate,
)
from skillware.cli_os import open_path_in_os
from skillware.cli_theme import THEMES, active_theme
from skillware.core.config import global_config_dir, project_config_write_path
from skillware.core.mail_config import (
    delete_addressbook_contact,
    ensure_writable_addressbook_path,
    filter_contacts,
    load_addressbook_yaml,
    load_merged_mail_settings,
    resolve_addressbook_path,
    set_addressbook_wallet,
    update_addressbook_contact,
)

_DEFAULT_PALETTE = THEMES["pastel"]
TABLE_STYLE = _DEFAULT_PALETTE.heading_style
ID_STYLE = _DEFAULT_PALETTE.id_style
MENU_STYLE = _DEFAULT_PALETTE.menu_style
ERROR_STYLE = f"bold {_DEFAULT_PALETTE.error_color}"

_ADDRESSBOOK_SUBMENU = [
    ("1", "show", "resolved path and contact count"),
    ("2", "list", "formatted contacts table"),
    ("3", "init", "create user config addressbook.yaml"),
    ("4", "add", "interactive contact wizard"),
    ("5", "edit", "update an existing contact"),
    ("6", "set-wallet", "attach or update public_0x"),
    ("7", "remove", "delete a contact"),
    ("8", "validate", "schema check"),
    ("9", "set-path", "persist mail.addressbook_path"),
    ("10", "open", "open addressbook.yaml in OS file manager"),
]

_NAV_EXIT = "exit"
_NAV_BACK = "back"


def _apply_active_theme() -> None:
    palette = active_theme()
    global TABLE_STYLE, ID_STYLE, MENU_STYLE, ERROR_STYLE
    TABLE_STYLE = palette.heading_style
    ID_STYLE = palette.id_style
    MENU_STYLE = palette.menu_style
    ERROR_STYLE = f"bold {palette.error_color}"


def _parse_nav(raw: Optional[str]) -> Tuple[str, Optional[str]]:
    if raw is None:
        return "", _NAV_EXIT
    text = raw.strip()
    if not text:
        return "", None
    lowered = text.lower()
    if lowered in {"0", "q", "quit", "exit"}:
        return "", _NAV_EXIT
    if lowered in {"b", "back"}:
        return "", _NAV_BACK
    return text, None


def _format_cell(value: object, *, empty: str = "—") -> str:
    if value is None:
        return empty
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else empty
    text = str(value).strip()
    return text or empty


def _short_wallet(value: object) -> str:
    text = _format_cell(value)
    if text == "—" or len(text) < 12:
        return text
    return f"{text[:6]}...{text[-4:]}"


def _resolved_writable_path() -> Path:
    mail = load_merged_mail_settings(refresh=True)
    resolved = resolve_addressbook_path(mail=mail)
    return ensure_writable_addressbook_path(resolved)


def cmd_addressbook_list(
    console: Optional[Console] = None,
    *,
    with_wallet: bool = False,
    search: Optional[str] = None,
    json_output: bool = False,
) -> int:
    _apply_active_theme()
    console = console or Console()
    mail = load_merged_mail_settings(refresh=True)
    path = resolve_addressbook_path(mail=mail)
    data = load_addressbook_yaml(path)
    rows = filter_contacts(data, with_wallet=with_wallet, search=search)

    if json_output:
        payload = {
            "path": str(path),
            "contacts": [{"contact_id": cid, **contact} for cid, contact in rows],
        }
        console.print(json.dumps(payload, indent=2))
        return 0

    table = Table(
        title="Address book contacts",
        box=box.SIMPLE_HEAVY,
        show_lines=False,
        header_style=TABLE_STYLE,
    )
    for col in (
        "CONTACT ID",
        "DISPLAY NAME",
        "EMAILS",
        "PUBLIC 0X",
        "ALIASES",
        "ORG",
        "NOTES",
    ):
        table.add_column(col)

    for contact_id, contact in rows:
        table.add_row(
            contact_id,
            _format_cell(contact.get("display_name")),
            _format_cell(contact.get("emails")),
            _short_wallet(contact.get("public_0x")),
            _format_cell(contact.get("aliases")),
            _format_cell(contact.get("org")),
            _format_cell(contact.get("notes")),
        )

    console.print(table)
    console.print(f"  path: {path}", style="dim")
    console.print(f"  shown: {len(rows)} contact(s)", style="dim")
    return 0


def cmd_addressbook_edit(
    contact_id: Optional[str] = None,
    console: Optional[Console] = None,
    input_fn: ReadLineFn = None,
) -> int:
    _apply_active_theme()
    console = console or Console()
    path = _resolved_writable_path()
    if not path.is_file():
        console.print(
            f"  Missing address book: {path} — run: skillware addressbook init",
            style=ERROR_STYLE,
        )
        return 1

    cid = (contact_id or "").strip()
    if not cid:
        cid_raw = _read_line("  Contact ID to edit> ", input_fn)
        if cid_raw is None:
            console.print("  Cancelled.", style="dim")
            return 1
        cid = cid_raw.strip()
    if not cid:
        console.print("  Contact ID required.", style=ERROR_STYLE)
        return 1

    data = load_addressbook_yaml(path)
    contacts = data.get("contacts") or {}
    existing = contacts.get(cid)
    if not isinstance(existing, dict):
        console.print(f"  Contact {cid!r} not found.", style=ERROR_STYLE)
        return 1

    def _prompt_field(label: str, current: object) -> Optional[str]:
        current_text = _format_cell(current, empty="")
        suffix = f" [{current_text}]" if current_text else ""
        raw = _read_line(f"  {label}{suffix}: ", input_fn)
        if raw is None:
            return None
        value = raw.strip()
        return value if value else current_text

    display_name = _prompt_field("Display name", existing.get("display_name"))
    if display_name is None:
        console.print("  Cancelled.", style="dim")
        return 1
    emails = _prompt_field(
        "Emails (comma-separated)", ", ".join(existing.get("emails") or [])
    )
    if emails is None:
        console.print("  Cancelled.", style="dim")
        return 1
    aliases = _prompt_field(
        "Aliases (comma-separated)", ", ".join(existing.get("aliases") or [])
    )
    if aliases is None:
        console.print("  Cancelled.", style="dim")
        return 1
    wallet = _prompt_field("public_0x (optional)", existing.get("public_0x"))
    if wallet is None:
        console.print("  Cancelled.", style="dim")
        return 1
    org = _prompt_field("Organization (optional)", existing.get("org"))
    if org is None:
        console.print("  Cancelled.", style="dim")
        return 1
    notes = _prompt_field("Notes (optional)", existing.get("notes"))
    if notes is None:
        console.print("  Cancelled.", style="dim")
        return 1

    updates = {
        "display_name": display_name,
        "emails": emails,
        "aliases": aliases,
        "public_0x": wallet or None,
        "org": org or None,
        "notes": notes or None,
    }
    try:
        update_addressbook_contact(path, cid, updates)
    except ValueError as exc:
        console.print(f"  {exc}", style=ERROR_STYLE)
        return 1

    console.print(f"  Updated contact {cid!r} → {path}", style=ID_STYLE)
    return 0


def cmd_addressbook_set_wallet(
    contact_id: str,
    wallet_0x: str,
    console: Optional[Console] = None,
) -> int:
    _apply_active_theme()
    console = console or Console()
    path = _resolved_writable_path()
    if not path.is_file():
        console.print(
            f"  Missing address book: {path} — run: skillware addressbook init",
            style=ERROR_STYLE,
        )
        return 1
    try:
        set_addressbook_wallet(path, contact_id, wallet_0x)
    except ValueError as exc:
        console.print(f"  {exc}", style=ERROR_STYLE)
        return 1
    console.print(
        f"  Updated {contact_id!r} EVM wallet in {path}",
        style=ID_STYLE,
    )
    return 0


def cmd_addressbook_remove(
    contact_id: str,
    console: Optional[Console] = None,
    *,
    yes: bool = False,
    input_fn: ReadLineFn = None,
) -> int:
    _apply_active_theme()
    console = console or Console()
    path = _resolved_writable_path()
    if not path.is_file():
        console.print(f"  Missing address book: {path}", style=ERROR_STYLE)
        return 1

    if not yes:
        confirm = _read_line(f"  Remove contact {contact_id!r}? [y/N] ", input_fn)
        if confirm is None or confirm.strip().lower() not in {"y", "yes"}:
            console.print("  Cancelled.", style="dim")
            return 1

    try:
        delete_addressbook_contact(path, contact_id)
    except ValueError as exc:
        console.print(f"  {exc}", style=ERROR_STYLE)
        return 1
    console.print(f"  Removed {contact_id!r} from {path}", style=ID_STYLE)
    return 0


def cmd_addressbook_open(
    console: Optional[Console] = None,
    *,
    open_dir: bool = False,
) -> int:
    _apply_active_theme()
    console = console or Console()
    mail = load_merged_mail_settings(refresh=True)
    path = resolve_addressbook_path(mail=mail)
    target = path if path.is_file() else path.parent
    open_path_in_os(target, open_parent=open_dir)
    console.print(f"  Opened {target}", style=ID_STYLE)
    return 0


def cmd_config_open(
    console: Optional[Console] = None,
    *,
    open_dir: bool = False,
) -> int:
    _apply_active_theme()
    console = console or Console()
    project_path = project_config_write_path()
    if project_path.is_file():
        target = project_path
    else:
        target = global_config_dir()
    open_path_in_os(target, open_parent=open_dir)
    console.print(f"  Opened {target}", style=ID_STYLE)
    return 0


def _print_addressbook_submenu(console: Console) -> None:
    _apply_active_theme()
    console.print(Text("Address book (shared identity)", style=TABLE_STYLE))
    console.print(
        f"  User config dir (survives pip uninstall): {global_config_dir()}",
        style="dim",
    )
    console.print()
    for key, slug, summary in _ADDRESSBOOK_SUBMENU:
        console.print(f"  {key}  {slug:<14} {summary}", style=MENU_STYLE)
    console.print("  0 / q  exit     b  back", style="dim")


def cmd_addressbook(console: Optional[Console] = None) -> int:
    _apply_active_theme()
    console = console or Console()
    return cmd_mail_addressbook_show(console)


def cmd_addressbook_interactive(
    console: Optional[Console] = None,
    input_fn: ReadLineFn = None,
) -> int:
    _apply_active_theme()
    console = console or Console()
    commands = {
        "1": "show",
        "show": "show",
        "2": "list",
        "list": "list",
        "3": "init",
        "init": "init",
        "4": "add",
        "add": "add",
        "5": "edit",
        "edit": "edit",
        "6": "set-wallet",
        "set-wallet": "set-wallet",
        "7": "remove",
        "remove": "remove",
        "8": "validate",
        "validate": "validate",
        "9": "set-path",
        "set-path": "set-path",
        "10": "open",
        "open": "open",
    }

    while True:
        _print_addressbook_submenu(console)
        raw = _read_line("  addressbook> ", input_fn)
        choice, nav = _parse_nav(raw)
        if nav == _NAV_EXIT:
            return 0
        if nav == _NAV_BACK:
            return 0
        command = commands.get(choice.lower())
        if not command:
            console.print(f"  Unknown choice: {choice!r}", style=ERROR_STYLE)
            continue
        cmd_addressbook_dispatch(command, "run", console=console, input_fn=input_fn)


def cmd_addressbook_dispatch(
    area: str,
    action: str,
    *,
    console: Optional[Console] = None,
    input_fn: ReadLineFn = None,
    **kwargs,
) -> int:
    _apply_active_theme()
    console = console or Console()

    if area == "show":
        return cmd_mail_addressbook_show(console)
    if area == "init":
        return cmd_mail_addressbook_init(
            console,
            path=kwargs.get("path"),
            force=kwargs.get("force", False),
        )
    if area == "list":
        return cmd_addressbook_list(
            console,
            with_wallet=kwargs.get("with_wallet", False),
            search=kwargs.get("search"),
            json_output=kwargs.get("json_output", False),
        )
    if area == "add":
        return cmd_mail_addressbook_add(
            console,
            input_fn=input_fn,
            display_name=kwargs.get("display_name"),
            email=kwargs.get("email"),
            aliases=kwargs.get("aliases"),
            org=kwargs.get("org"),
            contact_id=kwargs.get("contact_id"),
            public_0x=kwargs.get("public_0x"),
        )
    if area == "edit":
        return cmd_addressbook_edit(
            kwargs.get("contact_id"),
            console=console,
            input_fn=input_fn,
        )
    if area == "set-wallet":
        contact_id = kwargs.get("contact_id")
        wallet = kwargs.get("wallet_0x")
        if not contact_id or not wallet:
            console.print("  contact_id and wallet_0x are required.", style=ERROR_STYLE)
            return 1
        return cmd_addressbook_set_wallet(contact_id, wallet, console)
    if area == "remove":
        contact_id = kwargs.get("contact_id")
        if not contact_id:
            console.print("  contact_id is required.", style=ERROR_STYLE)
            return 1
        return cmd_addressbook_remove(
            contact_id,
            console,
            yes=kwargs.get("yes", False),
            input_fn=input_fn,
        )
    if area == "validate":
        return cmd_mail_addressbook_validate(console)
    if area == "set-path":
        return cmd_mail_addressbook_set_path(
            console,
            path=kwargs.get("path"),
            input_fn=input_fn,
        )
    if area == "open":
        return cmd_addressbook_open(console, open_dir=kwargs.get("open_dir", False))

    console.print(f"  Unknown addressbook action: {area}", style=ERROR_STYLE)
    return 1

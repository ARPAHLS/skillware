# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""CLI commands for the shared operator address book."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional, Tuple, Union

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
from skillware.core.legal_profile import mask_legal_profile
from skillware.core.mail_config import (
    delete_addressbook_contact,
    ensure_writable_addressbook_path,
    filter_contacts,
    load_addressbook_yaml,
    load_merged_mail_settings,
    resolve_addressbook_path,
    set_addressbook_legal_profile,
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
        safe_rows = []
        for cid, contact in rows:
            item = dict(contact)
            if isinstance(item.get("legal_profile"), dict):
                item["legal_profile"] = mask_legal_profile(item["legal_profile"])
            safe_rows.append({"contact_id": cid, **item})
        payload = {
            "path": str(path),
            "contacts": safe_rows,
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
        "PROFILE",
        "NOTES",
    ):
        table.add_column(col)

    for contact_id, contact in rows:
        lp = contact.get("legal_profile")
        if isinstance(lp, dict):
            ptype = str(lp.get("type") or "profile")
            badge = f"self/{ptype}" if contact.get("is_self") else ptype
        elif contact.get("is_self"):
            badge = "self"
        else:
            badge = "—"
        table.add_row(
            contact_id,
            _format_cell(contact.get("display_name")),
            _format_cell(contact.get("emails")),
            _short_wallet(contact.get("public_0x")),
            _format_cell(contact.get("aliases")),
            _format_cell(contact.get("org")),
            badge,
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


def cmd_addressbook_show(
    contact_id: Optional[str] = None,
    console: Optional[Console] = None,
    *,
    unmask: bool = False,
    json_output: bool = False,
) -> int:
    """Show addressbook path/count, or inspect one contact (masking PII by default)."""
    _apply_active_theme()
    console = console or Console()
    if not contact_id:
        return cmd_mail_addressbook_show(console)

    mail = load_merged_mail_settings(refresh=True)
    path = resolve_addressbook_path(mail=mail)
    data = load_addressbook_yaml(path)
    contacts = data.get("contacts") or {}
    contact = contacts.get(contact_id)
    if not isinstance(contact, dict):
        console.print(f"  Contact {contact_id!r} not found.", style=ERROR_STYLE)
        return 1

    rendered = dict(contact)
    if not unmask and isinstance(rendered.get("legal_profile"), dict):
        rendered["legal_profile"] = mask_legal_profile(rendered["legal_profile"])

    if json_output:
        console.print(json.dumps({"contact_id": contact_id, **rendered}, indent=2))
        return 0

    console.print(Text(f"Contact: {contact_id}", style=TABLE_STYLE))
    console.print(
        f"  display_name: {_format_cell(rendered.get('display_name'))}", style=ID_STYLE
    )
    if rendered.get("is_self"):
        console.print("  is_self: true", style=MENU_STYLE)
    console.print(f"  emails: {_format_cell(rendered.get('emails'))}", style=MENU_STYLE)
    if rendered.get("org"):
        console.print(f"  org: {rendered['org']}", style=MENU_STYLE)
    if rendered.get("public_0x"):
        console.print(f"  public_0x: {rendered['public_0x']}", style=MENU_STYLE)
    lp = rendered.get("legal_profile")
    if isinstance(lp, dict):
        console.print("  legal_profile:", style=TABLE_STYLE)
        for k, v in lp.items():
            console.print(
                f"    {k}: {json.dumps(v) if isinstance(v, (dict, list)) else v}",
                style=MENU_STYLE,
            )
        if not unmask:
            console.print(
                "  (sensitive fields masked — pass --unmask to reveal)", style="dim"
            )
    return 0


def cmd_addressbook_set_legal_profile(
    contact_id: str,
    console: Optional[Console] = None,
    *,
    profile_type: Optional[str] = None,
    is_self: Optional[bool] = None,
    citizenship: Optional[str] = None,
    tax_country: Optional[str] = None,
    tin: Optional[str] = None,
    tin_type: Optional[str] = None,
    ein: Optional[str] = None,
    ssn: Optional[str] = None,
    giin: Optional[str] = None,
    lei: Optional[str] = None,
    dob: Optional[str] = None,
    street: Optional[str] = None,
    city: Optional[str] = None,
    state: Optional[str] = None,
    postal: Optional[str] = None,
    country: Optional[str] = None,
    entity_class: Optional[str] = None,
    signatory_name: Optional[str] = None,
    signatory_title: Optional[str] = None,
    input_fn: ReadLineFn = None,
) -> int:
    """Attach or update a contact's ``legal_profile`` via flags or interactive prompts."""
    _apply_active_theme()
    console = console or Console()
    path = _resolved_writable_path()
    if not path.is_file():
        console.print(
            f"  Missing address book: {path} — run: skillware addressbook init",
            style=ERROR_STYLE,
        )
        return 1

    has_flags = any(
        v is not None
        for v in (
            profile_type,
            is_self,
            citizenship,
            tax_country,
            tin,
            tin_type,
            ein,
            ssn,
            giin,
            lei,
            dob,
            street,
            city,
            state,
            postal,
            country,
            entity_class,
            signatory_name,
            signatory_title,
        )
    )
    if not has_flags:
        profile_type = (
            _read_line("  Profile type [individual/entity]: ", input_fn) or ""
        ).strip() or "individual"
        citizenship = (
            _read_line("  Citizenship (e.g. GR, US, Germany): ", input_fn) or ""
        ).strip() or None
        tax_country = (
            _read_line("  Tax residence country (e.g. GR, DE): ", input_fn) or ""
        ).strip() or None
        tin = (
            _read_line("  Tax ID / TIN (optional): ", input_fn) or ""
        ).strip() or None
        dob = (
            _read_line("  Date of birth YYYY-MM-DD (optional): ", input_fn) or ""
        ).strip() or None
        street = (
            _read_line("  Street address (optional): ", input_fn) or ""
        ).strip() or None
        city = (_read_line("  City (optional): ", input_fn) or "").strip() or None
        postal = (
            _read_line("  Postal code (optional): ", input_fn) or ""
        ).strip() or None
        country = (
            _read_line("  Address country (optional): ", input_fn) or ""
        ).strip() or None

    lp: dict[str, Any] = {}
    if profile_type:
        lp["type"] = profile_type.strip().lower()
    if citizenship:
        lp["citizenship"] = citizenship.strip()
    if dob:
        lp["date_of_birth"] = dob.strip()
    if tax_country:
        res_entry: dict[str, Any] = {"country": tax_country.strip()}
        if tin:
            res_entry["tin"] = tin.strip()
        if tin_type:
            res_entry["tin_type"] = tin_type.strip()
        lp["tax_residency"] = [res_entry]
    elif tin:
        lp["tax_id"] = tin.strip()

    tax_ids: dict[str, str] = {}
    if ein:
        tax_ids["US_EIN"] = ein.strip()
    if ssn:
        tax_ids["US_SSN"] = ssn.strip()
    if giin:
        tax_ids["GIIN"] = giin.strip()
    if lei:
        tax_ids["LEI"] = lei.strip()
    if tax_ids:
        lp["tax_ids"] = tax_ids

    addr: dict[str, str] = {}
    if street:
        addr["street"] = street.strip()
    if city:
        addr["city"] = city.strip()
    if state:
        addr["state_province"] = state.strip()
    if postal:
        addr["postal_code"] = postal.strip()
    if country:
        addr["country"] = country.strip()
    if addr:
        lp["residence_address"] = addr

    if entity_class:
        lp["company_registration"] = {
            "entity_classification": entity_class.strip().lower()
        }
    if signatory_name or signatory_title:
        sig: dict[str, str] = {}
        if signatory_name:
            sig["name"] = signatory_name.strip()
        if signatory_title:
            sig["title"] = signatory_title.strip()
        lp["authorized_signatory"] = sig

    try:
        set_addressbook_legal_profile(path, contact_id, lp, is_self=is_self)
    except (KeyError, ValueError) as exc:
        console.print(f"  {exc}", style=ERROR_STYLE)
        return 1

    console.print(
        f"  Updated legal_profile for {contact_id!r} in {path}", style=ID_STYLE
    )
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
    *,
    return_navigation: bool = False,
) -> Union[int, str]:
    """Keep CLI status codes by default; optionally propagate a parent-menu exit."""
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
            return _NAV_EXIT if return_navigation else 0
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
    **kwargs: Any,
) -> int:
    _apply_active_theme()
    console = console or Console()

    if area == "show":
        return cmd_addressbook_show(
            kwargs.get("contact_id"),
            console,
            unmask=kwargs.get("unmask", False),
            json_output=kwargs.get("json_output", False),
        )
    if area == "set-legal-profile":
        contact_id = kwargs.get("contact_id")
        if not contact_id:
            console.print("  contact_id is required.", style=ERROR_STYLE)
            return 1
        return cmd_addressbook_set_legal_profile(
            contact_id,
            console,
            profile_type=kwargs.get("profile_type"),
            is_self=kwargs.get("is_self"),
            citizenship=kwargs.get("citizenship"),
            tax_country=kwargs.get("tax_country"),
            tin=kwargs.get("tin"),
            tin_type=kwargs.get("tin_type"),
            ein=kwargs.get("ein"),
            ssn=kwargs.get("ssn"),
            giin=kwargs.get("giin"),
            lei=kwargs.get("lei"),
            dob=kwargs.get("dob"),
            street=kwargs.get("street"),
            city=kwargs.get("city"),
            state=kwargs.get("state"),
            postal=kwargs.get("postal"),
            country=kwargs.get("country"),
            entity_class=kwargs.get("entity_class"),
            signatory_name=kwargs.get("signatory_name"),
            signatory_title=kwargs.get("signatory_title"),
            input_fn=input_fn,
        )
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

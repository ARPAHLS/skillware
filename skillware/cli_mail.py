"""CLI commands for mail operator settings (office/gmail_handler)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from rich.console import Console
from rich.text import Text

from skillware.core.mail_config import (
    DEFAULT_SIGNATURE_PLAIN,
    ENV_ADDRESSBOOK_PATH,
    ENV_SIGNATURE_HTML_PATH,
    ENV_SIGNATURE_PATH,
    ENV_SIGNATURE_PLAIN,
    add_addressbook_contact,
    count_addressbook_contacts,
    default_global_addressbook_path,
    ensure_writable_addressbook_path,
    format_mail_config_lines,
    init_addressbook_file,
    init_signature_bundle,
    load_addressbook_yaml,
    load_merged_mail_settings,
    load_project_mail_settings,
    persist_global_mail_paths,
    resolve_addressbook_path,
    resolve_signature_html,
    resolve_signature_plain,
    clear_mail_signature_settings,
    save_global_mail_settings,
    save_project_mail_settings,
    slugify_contact_id,
    validate_addressbook_data,
    validate_signature_text,
)
from skillware.core.config import global_config_dir

TABLE_STYLE = "bold #C7CEEA"
ID_STYLE = "#B5EAD7"
MENU_STYLE = "#FFDAC1"

_NAV_EXIT = "exit"
_NAV_BACK = "back"

_MAIL_SUBMENU = [
    ("1", "addressbook show", "resolved path and contact count"),
    ("2", "addressbook init", "create user config addressbook.yaml"),
    ("3", "addressbook add", "interactive contact wizard"),
    ("4", "addressbook validate", "schema check"),
    ("5", "addressbook set-path", "persist mail.addressbook_path"),
    ("6", "signature show", "resolved signature (plain + HTML status)"),
    ("7", "signature init", "default template (plain + HTML + logo copy)"),
    ("8", "signature set", "paste text or --file"),
    ("9", "signature validate", "non-empty, length, secret patterns"),
    ("10", "signature clear", "remove signature from project config"),
]

ReadLineFn = Optional[Callable[[str], Optional[str]]]


def _read_line(prompt: str, input_fn: ReadLineFn = None) -> Optional[str]:
    if input_fn is not None:
        return input_fn(prompt)
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        return None


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


def _print_mail_submenu(console: Console) -> None:
    console.print(
        Text("Mail settings (office/gmail_handler)", style=f"bold {TABLE_STYLE}")
    )
    console.print(
        "  Precedence: env > project YAML > global YAML > skill defaults",
        style="dim",
    )
    console.print(
        f"  User config dir (survives pip uninstall): {global_config_dir()}",
        style="dim",
    )
    console.print()
    for key, slug, summary in _MAIL_SUBMENU:
        console.print(f"  {key}  {slug:<22} {summary}", style=MENU_STYLE)
    console.print("  0 / q  exit     b  back", style="dim")


def cmd_mail_addressbook_show(console: Optional[Console] = None) -> int:
    if console is None:
        console = Console()
    mail = load_merged_mail_settings(refresh=True)
    path = resolve_addressbook_path(mail=mail)
    data = load_addressbook_yaml(path)
    count = count_addressbook_contacts(data)
    console.print(Text("Address book", style=f"bold {TABLE_STYLE}"))
    console.print(f"  path: {path}", style=ID_STYLE)
    console.print(f"  contacts: {count}", style=MENU_STYLE)
    if path.is_file():
        console.print("  status: ok", style="dim")
        if str(path).startswith(str(global_config_dir())):
            console.print(
                "  storage: user config (persists across skillware upgrades)",
                style="dim",
            )
        elif "site-packages" in str(path):
            console.print(
                "  storage: bundled wheel path — run addressbook init for a writable copy",
                style="bold #FF9AA2",
            )
    else:
        console.print(
            "  status: file missing — run: skillware mail addressbook init",
            style="dim",
        )
    return 0


def cmd_mail_addressbook_init(
    console: Optional[Console] = None,
    *,
    path: Optional[Path] = None,
    force: bool = False,
) -> int:
    if console is None:
        console = Console()
    target = path or default_global_addressbook_path()
    try:
        init_addressbook_file(target, overwrite=force)
    except FileExistsError:
        console.print(
            f"  Already exists: {target} (use --force to overwrite)",
            style="bold #FF9AA2",
        )
        return 1
    saved = persist_global_mail_paths(addressbook_path=str(target))
    console.print(f"  Created {target}", style=ID_STYLE)
    console.print(f"  Registered in {saved}", style="dim")
    console.print(
        "  Stored under your user config — safe if skillware is upgraded or reinstalled.",
        style="dim",
    )
    return 0


def _prompt_required(
    label: str,
    input_fn: ReadLineFn,
    *,
    default: Optional[str] = None,
) -> Optional[str]:
    suffix = f" [{default}]" if default else ""
    while True:
        raw = _read_line(f"  {label}{suffix}: ", input_fn)
        if raw is None:
            return None
        value = raw.strip() or (default or "")
        if value:
            return value


def cmd_mail_addressbook_add(
    console: Optional[Console] = None,
    input_fn: ReadLineFn = None,
    *,
    display_name: Optional[str] = None,
    email: Optional[str] = None,
    aliases: Optional[str] = None,
    org: Optional[str] = None,
    contact_id: Optional[str] = None,
) -> int:
    if console is None:
        console = Console()

    mail = load_merged_mail_settings(refresh=True)
    resolved = resolve_addressbook_path(mail=mail)
    path = ensure_writable_addressbook_path(resolved)
    if not path.is_file():
        console.print(f"  Creating address book at {path}", style="dim")
        init_addressbook_file(path)
        persist_global_mail_paths(addressbook_path=str(path))

    name = display_name or _prompt_required("Display name", input_fn)
    if name is None:
        console.print("  Cancelled.", style="dim")
        return 1
    mail_addr = email or _prompt_required("Email", input_fn)
    if mail_addr is None:
        console.print("  Cancelled.", style="dim")
        return 1

    alias_list: List[str] = []
    if aliases:
        alias_list = [part.strip() for part in aliases.split(",") if part.strip()]
    elif input_fn is not None or display_name is None:
        alias_raw = _read_line("  Aliases (comma-separated, optional): ", input_fn)
        if alias_raw is None:
            console.print("  Cancelled.", style="dim")
            return 1
        alias_list = [part.strip() for part in alias_raw.split(",") if part.strip()]

    org_value = org
    if org_value is None and (input_fn is not None or display_name is None):
        org_raw = _read_line("  Organization (optional): ", input_fn)
        if org_raw is None:
            console.print("  Cancelled.", style="dim")
            return 1
        org_value = org_raw.strip() or None

    suggested_id = contact_id or slugify_contact_id(name)
    cid = contact_id
    if cid is None and (input_fn is not None or display_name is None):
        cid_raw = _read_line(f"  Contact ID [{suggested_id}]: ", input_fn)
        if cid_raw is None:
            console.print("  Cancelled.", style="dim")
            return 1
        cid = cid_raw.strip() or suggested_id

    try:
        saved_id = add_addressbook_contact(
            path,
            display_name=name,
            email=mail_addr,
            aliases=alias_list or None,
            org=org_value,
            contact_id=cid,
        )
    except ValueError as exc:
        console.print(f"  {exc}", style="bold #FF9AA2")
        return 1

    console.print(f"  Added contact {saved_id!r} → {path}", style=ID_STYLE)
    return 0


def cmd_mail_addressbook_validate(console: Optional[Console] = None) -> int:
    if console is None:
        console = Console()
    mail = load_merged_mail_settings(refresh=True)
    path = resolve_addressbook_path(mail=mail)
    if not path.is_file():
        console.print(f"  Missing address book: {path}", style="bold #FF9AA2")
        return 1
    data = load_addressbook_yaml(path)
    errors = validate_addressbook_data(data)
    if errors:
        console.print(Text("Address book validation failed", style="bold #FF9AA2"))
        for error in errors:
            console.print(f"  • {error}")
        return 1
    console.print(f"  Valid: {path}", style=ID_STYLE)
    return 0


def cmd_mail_addressbook_set_path(
    console: Optional[Console] = None,
    *,
    path: Optional[str] = None,
    input_fn: ReadLineFn = None,
) -> int:
    if console is None:
        console = Console()
    raw = path
    if raw is None:
        default = default_global_addressbook_path()
        console.print(f"  Default: {default}", style="dim")
        raw = _read_line("  addressbook path> ", input_fn)
        if raw is None:
            console.print("  Cancelled.", style="dim")
            return 1
    raw = raw.strip()
    if not raw:
        console.print("  Path required.", style="bold #FF9AA2")
        return 1

    project_mail = load_project_mail_settings()
    project_mail.addressbook_path = raw
    target = save_project_mail_settings(project_mail)
    console.print(f"  Saved mail.addressbook_path to {target}", style=ID_STYLE)
    return 0


def cmd_mail_signature_show(console: Optional[Console] = None) -> int:
    if console is None:
        console = Console()
    mail = load_merged_mail_settings(refresh=True)
    text, source = resolve_signature_plain(mail=mail)
    html, html_source = resolve_signature_html(mail=mail)
    console.print(Text("Mail signature", style=f"bold {TABLE_STYLE}"))
    console.print(f"  plain source: {source}", style=MENU_STYLE)
    console.print(f"  html source: {html_source}", style=MENU_STYLE)
    if not text and not html:
        console.print(
            "  (none configured — run: skillware mail signature init)", style="dim"
        )
        return 0
    if text:
        preview = text if len(text) <= 240 else text[:240] + "..."
        console.print("  plain text:", style="dim")
        for line in preview.splitlines():
            console.print(f"    {line}")
    if html:
        console.print(
            "  html: present (logo + links; used for HTML-capable clients)", style="dim"
        )
    return 0


def cmd_mail_signature_init(
    console: Optional[Console] = None,
    *,
    path: Optional[Path] = None,
    inline: bool = False,
    force: bool = False,
) -> int:
    if console is None:
        console = Console()
    config_dir = global_config_dir()
    if inline:
        from skillware.core.mail_config import MailSettings

        settings = MailSettings(signature_plain=DEFAULT_SIGNATURE_PLAIN.strip())
        target = save_global_mail_settings(settings)
        console.print(f"  Set mail.signature_plain in {target}", style=ID_STYLE)
        console.print(
            "  Tip: run signature init without --inline for HTML + logo.", style="dim"
        )
        return 0

    target_dir = path.parent if path else config_dir
    if path and path.suffix:
        target_dir = path.parent
    try:
        txt_path, html_path, logo_path = init_signature_bundle(
            target_dir, overwrite=force
        )
    except FileExistsError as exc:
        console.print(
            f"  Already exists: {exc} (use --force to overwrite)",
            style="bold #FF9AA2",
        )
        return 1

    saved = persist_global_mail_paths(
        signature_path=str(txt_path),
        signature_html_path=str(html_path),
    )
    console.print(f"  Created {txt_path}", style=ID_STYLE)
    console.print(f"  Created {html_path}", style=ID_STYLE)
    if logo_path:
        console.print(f"  Copied logo to {logo_path}", style=ID_STYLE)
    console.print(f"  Registered in {saved}", style="dim")
    console.print(
        "  HTML signature includes Skillware logo (40px) + links to skillware.site, GitHub, arpacorp.net",
        style="dim",
    )
    return 0


def cmd_mail_signature_set(
    console: Optional[Console] = None,
    *,
    file_path: Optional[Path] = None,
    text: Optional[str] = None,
    input_fn: ReadLineFn = None,
) -> int:
    if console is None:
        console = Console()

    if file_path is not None:
        if not file_path.is_file():
            console.print(f"  File not found: {file_path}", style="bold #FF9AA2")
            return 1
        body = file_path.read_text(encoding="utf-8").strip()
        project_mail = load_project_mail_settings()
        project_mail.signature_path = str(file_path.expanduser().resolve())
        project_mail.signature_plain = None
        save_project_mail_settings(project_mail)
        errors = validate_signature_text(body)
        if errors:
            console.print("  Warning:", style="bold #FF9AA2")
            for error in errors:
                console.print(f"    • {error}")
        console.print(
            f"  Using signature file {project_mail.signature_path}", style=ID_STYLE
        )
        return 0

    if text is None:
        console.print("  Paste signature text; end with a blank line:", style="dim")
        lines: List[str] = []
        while True:
            line = _read_line("", input_fn)
            if line is None:
                console.print("  Cancelled.", style="dim")
                return 1
            if not line.strip() and lines:
                break
            lines.append(line)
        text = "\n".join(lines).strip()

    errors = validate_signature_text(text or "")
    if errors:
        console.print("  Invalid signature:", style="bold #FF9AA2")
        for error in errors:
            console.print(f"    • {error}")
        return 1

    project_mail = load_project_mail_settings()
    project_mail.signature_plain = text
    project_mail.signature_path = None
    target = save_project_mail_settings(project_mail)
    console.print(f"  Saved mail.signature_plain to {target}", style=ID_STYLE)
    return 0


def cmd_mail_signature_validate(console: Optional[Console] = None) -> int:
    if console is None:
        console = Console()
    mail = load_merged_mail_settings(refresh=True)
    text, source = resolve_signature_plain(mail=mail)
    errors = validate_signature_text(text)
    if errors:
        console.print(Text("Signature validation failed", style="bold #FF9AA2"))
        console.print(f"  source: {source}", style="dim")
        for error in errors:
            console.print(f"  • {error}")
        return 1
    console.print(f"  Valid signature ({source})", style=ID_STYLE)
    return 0


def cmd_mail_signature_clear(console: Optional[Console] = None) -> int:
    if console is None:
        console = Console()
    updated = clear_mail_signature_settings()
    if updated:
        for target in updated:
            console.print(f"  Cleared mail signature keys in {target}", style=ID_STYLE)
    else:
        console.print("  No signature keys in project/global config.", style="dim")
    console.print(
        "  Env overrides (GMAIL_SIGNATURE_*) still apply at runtime.",
        style="dim",
    )
    return 0


def cmd_mail_show(console: Optional[Console] = None) -> int:
    """Summary of resolved mail settings (read-only)."""
    if console is None:
        console = Console()
    mail = load_merged_mail_settings(refresh=True)
    console.print(Text("Mail settings (resolved)", style=f"bold {TABLE_STYLE}"))
    for line in format_mail_config_lines(mail):
        console.print(line, style=MENU_STYLE)
    console.print()
    console.print("  Env overrides:", style="dim")
    for key in (
        ENV_ADDRESSBOOK_PATH,
        ENV_SIGNATURE_PATH,
        ENV_SIGNATURE_PLAIN,
        ENV_SIGNATURE_HTML_PATH,
    ):
        if key in os.environ:
            console.print(f"    {key}=set", style="dim")
    return 0


def cmd_mail_submenu(
    console: Optional[Console] = None, input_fn: ReadLineFn = None
) -> Optional[str]:
    """Interactive mail submenu. Returns _NAV_EXIT to quit Skillware."""
    if console is None:
        console = Console()

    commands = {
        "1": "addressbook show",
        "addressbook show": "addressbook show",
        "2": "addressbook init",
        "addressbook init": "addressbook init",
        "3": "addressbook add",
        "addressbook add": "addressbook add",
        "4": "addressbook validate",
        "addressbook validate": "addressbook validate",
        "5": "addressbook set-path",
        "addressbook set-path": "addressbook set-path",
        "6": "signature show",
        "signature show": "signature show",
        "7": "signature init",
        "signature init": "signature init",
        "8": "signature set",
        "signature set": "signature set",
        "9": "signature validate",
        "signature validate": "signature validate",
        "10": "signature clear",
        "signature clear": "signature clear",
    }

    while True:
        _print_mail_submenu(console)
        raw = _read_line("  mail> ", input_fn)
        choice, nav = _parse_nav(raw)
        if nav == _NAV_EXIT:
            return _NAV_EXIT
        if nav == _NAV_BACK:
            return None
        if not choice:
            continue

        command = commands.get(choice.lower())
        if command == "addressbook show":
            cmd_mail_addressbook_show(console)
        elif command == "addressbook init":
            cmd_mail_addressbook_init(console)
        elif command == "addressbook add":
            cmd_mail_addressbook_add(console, input_fn=input_fn)
        elif command == "addressbook validate":
            cmd_mail_addressbook_validate(console)
        elif command == "addressbook set-path":
            cmd_mail_addressbook_set_path(console, input_fn=input_fn)
        elif command == "signature show":
            cmd_mail_signature_show(console)
        elif command == "signature init":
            cmd_mail_signature_init(console)
        elif command == "signature set":
            cmd_mail_signature_set(console, input_fn=input_fn)
        elif command == "signature validate":
            cmd_mail_signature_validate(console)
        elif command == "signature clear":
            cmd_mail_signature_clear(console)
        elif command is None:
            console.print(f"  Unknown choice: {choice!r}", style="dim #FF9AA2")
        else:
            console.print(f"  Unknown choice: {choice!r}", style="dim #FF9AA2")
        console.print()


def cmd_mail(
    area: Optional[str] = None,
    action: Optional[str] = None,
    console: Optional[Console] = None,
    **kwargs,
) -> int:
    """Dispatch skillware mail [area] [action]."""
    if console is None:
        console = Console()

    if area is None:
        return cmd_mail_show(console)

    area = area.lower()
    action = (action or "show").lower()

    if area == "addressbook":
        if action == "show":
            return cmd_mail_addressbook_show(console)
        if action == "init":
            return cmd_mail_addressbook_init(
                console,
                path=kwargs.get("path"),
                force=kwargs.get("force", False),
            )
        if action == "validate":
            return cmd_mail_addressbook_validate(console)
        if action == "add":
            return cmd_mail_addressbook_add(
                console,
                input_fn=kwargs.get("input_fn"),
                display_name=kwargs.get("display_name"),
                email=kwargs.get("email"),
                aliases=kwargs.get("aliases"),
                org=kwargs.get("org"),
                contact_id=kwargs.get("contact_id"),
            )
        if action == "set-path":
            return cmd_mail_addressbook_set_path(console, path=kwargs.get("path"))
        console.print(f"  Unknown addressbook action: {action}", style="bold #FF9AA2")
        return 1

    if area == "signature":
        if action == "show":
            return cmd_mail_signature_show(console)
        if action == "init":
            return cmd_mail_signature_init(
                console,
                path=kwargs.get("path"),
                inline=kwargs.get("inline", False),
                force=kwargs.get("force", False),
            )
        if action == "validate":
            return cmd_mail_signature_validate(console)
        if action == "clear":
            return cmd_mail_signature_clear(console)
        if action == "set":
            return cmd_mail_signature_set(
                console,
                file_path=kwargs.get("file_path"),
                text=kwargs.get("text"),
            )
        console.print(f"  Unknown signature action: {action}", style="bold #FF9AA2")
        return 1

    console.print(f"  Unknown mail area: {area}", style="bold #FF9AA2")
    console.print("  Use: addressbook | signature", style="dim")
    return 1

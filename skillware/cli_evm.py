"""CLI commands for EVM operator configuration (chains and RPC)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich import box

from skillware.cli_os import open_path_in_os
from skillware.cli_theme import THEMES, active_theme
from skillware.core.config import global_config_dir
from skillware.core.evm_config import (
    ENV_EVM_CONFIG_PATH,
    add_chain_to_config,
    add_token_to_config,
    bundled_evm_defaults_path,
    default_global_evm_path,
    enable_chain_in_config,
    init_evm_config_file,
    is_rpc_configured,
    list_configured_chains,
    load_merged_evm_config,
    resolve_evm_config_path,
    validate_evm_config_data,
    load_evm_yaml,
)

_DEFAULT_PALETTE = THEMES["pastel"]
TABLE_STYLE = _DEFAULT_PALETTE.heading_style
ID_STYLE = _DEFAULT_PALETTE.id_style
MENU_STYLE = _DEFAULT_PALETTE.menu_style
ERROR_STYLE = f"bold {_DEFAULT_PALETTE.error_color}"
ERROR_DIM_STYLE = f"dim {_DEFAULT_PALETTE.error_color}"

_NAV_EXIT = "exit"
_NAV_BACK = "back"

_EVM_SUBMENU = [
    ("1", "show", "resolved evm.yaml path and enabled chains"),
    ("2", "init", "create user evm.yaml from bundled defaults"),
    ("3", "chains list", "table of chains, RPC source, readiness"),
    ("4", "chain add", "interactive custom chain wizard"),
    ("5", "token add", "register a custom ERC-20 token"),
    ("6", "rpc enable", "enable a bundled or custom chain"),
    ("7", "validate", "schema and address checksum checks"),
    ("8", "open", "open evm.yaml or its directory in the OS file manager"),
]

ReadLineFn = Optional[Callable[[str], Optional[str]]]


def _apply_active_theme() -> None:
    palette = active_theme()
    global TABLE_STYLE, ID_STYLE, MENU_STYLE, ERROR_STYLE, ERROR_DIM_STYLE
    TABLE_STYLE = palette.heading_style
    ID_STYLE = palette.id_style
    MENU_STYLE = palette.menu_style
    ERROR_STYLE = f"bold {palette.error_color}"
    ERROR_DIM_STYLE = f"dim {palette.error_color}"


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


def cmd_evm_show(console: Optional[Console] = None) -> int:
    _apply_active_theme()
    console = console or Console()
    path = resolve_evm_config_path()
    merged = load_merged_evm_config(refresh=True)

    console.print(Text("EVM config", style=TABLE_STYLE))
    console.print(f"  path: {path}", style=MENU_STYLE)
    if os.environ.get(ENV_EVM_CONFIG_PATH):
        console.print(f"  source: env {ENV_EVM_CONFIG_PATH}", style="dim")
    elif path.is_file():
        console.print("  status: user config present", style="dim")
    else:
        console.print(
            "  status: file missing — run: skillware evm init",
            style=ERROR_DIM_STYLE,
        )
    console.print(f"  bundled defaults: {bundled_evm_defaults_path()}", style="dim")
    console.print(
        f"  enabled chains: {len(list_configured_chains(merged, enabled_only=True))}",
        style=MENU_STYLE,
    )
    if merged.sources:
        console.print("  merge sources:", style="dim")
        for source in merged.sources:
            console.print(f"    - {source}", style="dim")
    return 0


def cmd_evm_init(
    console: Optional[Console] = None,
    *,
    path: Optional[Path] = None,
    force: bool = False,
    input_fn: ReadLineFn = None,
    non_interactive: bool = False,
) -> int:
    _apply_active_theme()
    console = console or Console()
    target = path or default_global_evm_path()

    bundled = load_evm_yaml(bundled_evm_defaults_path())
    bundled_chains = (
        bundled.get("chains") if isinstance(bundled.get("chains"), dict) else {}
    )
    enabled: Optional[List[str]] = None

    if not non_interactive and bundled_chains:
        console.print(Text("Enable bundled chains", style=TABLE_STYLE))
        for name in sorted(bundled_chains):
            console.print(f"  - {name}", style=MENU_STYLE)
        console.print(
            "Enter comma-separated chain names to enable (blank = enable all shown):",
            style="dim",
        )
        raw = _read_line("  > ", input_fn=input_fn)
        if raw is None:
            console.print("  Cancelled.", style=ERROR_DIM_STYLE)
            return 1
        if raw.strip():
            enabled = [part.strip() for part in raw.split(",") if part.strip()]

    try:
        init_evm_config_file(target, overwrite=force, enabled_chains=enabled)
    except FileExistsError:
        console.print(
            f"  File already exists: {target}. Use --force to overwrite.",
            style=ERROR_STYLE,
        )
        return 1

    console.print(f"  Created {target}", style=MENU_STYLE)
    console.print(
        "  Set RPC URLs in .env (ETHEREUM_RPC_URL, BASE_RPC_URL, …).",
        style="dim",
    )
    return 0


def cmd_evm_chains_list(
    console: Optional[Console] = None,
    *,
    json_output: bool = False,
) -> int:
    _apply_active_theme()
    console = console or Console()
    merged = load_merged_evm_config(refresh=True)
    entries = list_configured_chains(merged, enabled_only=False)

    if json_output:
        import json

        payload = []
        for name, cfg in entries:
            rpc_env = cfg.get("rpc_env")
            rpc_url = cfg.get("rpc_url")
            payload.append(
                {
                    "chain": name,
                    "chain_id": cfg.get("chain_id"),
                    "enabled": cfg.get("enabled", True),
                    "rpc_env": rpc_env,
                    "rpc_url": rpc_url,
                    "rpc_configured": is_rpc_configured(name),
                }
            )
        console.print(json.dumps(payload, indent=2))
        return 0

    table = Table(
        title="EVM chains",
        box=box.SIMPLE_HEAVY,
        expand=True,
        show_header=True,
        header_style=TABLE_STYLE,
    )
    table.add_column("CHAIN", style=ID_STYLE, no_wrap=True, ratio=2)
    table.add_column("CHAIN ID", no_wrap=True, ratio=1)
    table.add_column("ENABLED", no_wrap=True, ratio=1)
    table.add_column("RPC SOURCE", ratio=3)
    table.add_column("RPC READY", no_wrap=True, ratio=1)

    for name, cfg in entries:
        enabled = cfg.get("enabled", True)
        rpc_env = cfg.get("rpc_env")
        rpc_url = cfg.get("rpc_url")
        if rpc_env:
            rpc_source = str(rpc_env)
        elif rpc_url:
            rpc_source = str(rpc_url)
        else:
            rpc_source = "—"
        ready = "yes" if is_rpc_configured(name) else "no"
        table.add_row(
            name,
            str(cfg.get("chain_id", "—")),
            "yes" if enabled else "no",
            rpc_source,
            ready,
        )

    console.print(table)
    return 0


def cmd_evm_chain_add(
    console: Optional[Console] = None,
    *,
    input_fn: ReadLineFn = None,
    chain_name: Optional[str] = None,
    chain_id: Optional[int] = None,
    rpc_env: Optional[str] = None,
    rpc_url: Optional[str] = None,
) -> int:
    _apply_active_theme()
    console = console or Console()
    path = resolve_evm_config_path()
    if not path.is_file():
        console.print(
            "  evm.yaml missing — run: skillware evm init",
            style=ERROR_STYLE,
        )
        return 1

    name = chain_name or _read_line("  Chain name (e.g. arbitrum): ", input_fn=input_fn)
    if not name or not str(name).strip():
        console.print("  Chain name is required.", style=ERROR_STYLE)
        return 1
    name = str(name).strip().lower()

    if chain_id is None:
        raw_id = _read_line("  Chain ID (integer): ", input_fn=input_fn)
        if raw_id is None or not str(raw_id).strip():
            console.print("  Chain ID is required.", style=ERROR_STYLE)
            return 1
        try:
            chain_id = int(str(raw_id).strip())
        except ValueError:
            console.print("  Chain ID must be an integer.", style=ERROR_STYLE)
            return 1

    if not rpc_env and not rpc_url:
        rpc_env = _read_line(
            "  RPC env var name (blank to use inline rpc_url): ",
            input_fn=input_fn,
        )
        if rpc_env is not None and not str(rpc_env).strip():
            rpc_env = None
            rpc_url = _read_line("  Inline RPC URL: ", input_fn=input_fn)

    chain_data = {
        "enabled": True,
        "chain_id": chain_id,
        "native_symbol": "eth",
        "native_decimals": 18,
    }
    if rpc_env and str(rpc_env).strip():
        chain_data["rpc_env"] = str(rpc_env).strip()
    elif rpc_url and str(rpc_url).strip():
        chain_data["rpc_url"] = str(rpc_url).strip()
    else:
        console.print("  rpc_env or rpc_url is required.", style=ERROR_STYLE)
        return 1

    add_chain_to_config(path, name, chain_data)
    console.print(f"  Added chain {name!r} to {path}", style=MENU_STYLE)
    return 0


def cmd_evm_token_add(
    console: Optional[Console] = None,
    *,
    input_fn: ReadLineFn = None,
    chain_name: Optional[str] = None,
    symbol: Optional[str] = None,
    address: Optional[str] = None,
    decimals: Optional[int] = None,
) -> int:
    _apply_active_theme()
    console = console or Console()
    path = resolve_evm_config_path()
    if not path.is_file():
        console.print(
            "  evm.yaml missing — run: skillware evm init",
            style=ERROR_STYLE,
        )
        return 1

    chain = chain_name or _read_line("  Chain name (e.g. base): ", input_fn=input_fn)
    if not chain or not str(chain).strip():
        console.print("  Chain name is required.", style=ERROR_STYLE)
        return 1
    chain = str(chain).strip().lower()

    sym = symbol or _read_line("  Token symbol (e.g. degen): ", input_fn=input_fn)
    if not sym or not str(sym).strip():
        console.print("  Token symbol is required.", style=ERROR_STYLE)
        return 1
    sym = str(sym).strip().lower()

    token_address = address or _read_line(
        "  Contract address (0x…): ", input_fn=input_fn
    )
    if not token_address or not str(token_address).strip():
        console.print("  Token address is required.", style=ERROR_STYLE)
        return 1

    token_decimals = decimals
    if token_decimals is None:
        raw_dec = _read_line("  Decimals (e.g. 18): ", input_fn=input_fn)
        if raw_dec is None or not str(raw_dec).strip():
            console.print("  Decimals are required.", style=ERROR_STYLE)
            return 1
        try:
            token_decimals = int(str(raw_dec).strip())
        except ValueError:
            console.print("  Decimals must be an integer.", style=ERROR_STYLE)
            return 1

    try:
        add_token_to_config(
            path,
            chain,
            sym,
            {"address": str(token_address).strip(), "decimals": token_decimals},
        )
    except (ValueError, ImportError) as exc:
        console.print(f"  {exc}", style=ERROR_STYLE)
        return 1

    console.print(
        f"  Added token {sym!r} on chain {chain!r} to {path}",
        style=MENU_STYLE,
    )
    return 0


def cmd_evm_rpc_enable(
    chain_name: str,
    console: Optional[Console] = None,
) -> int:
    _apply_active_theme()
    console = console or Console()
    path = resolve_evm_config_path()
    if not path.is_file():
        console.print(
            "  evm.yaml missing — run: skillware evm init",
            style=ERROR_STYLE,
        )
        return 1
    try:
        enable_chain_in_config(path, chain_name)
    except ValueError as exc:
        console.print(f"  {exc}", style=ERROR_STYLE)
        return 1
    console.print(
        f"  Enabled chain {chain_name.strip().lower()!r} in {path}",
        style=MENU_STYLE,
    )
    return 0


def cmd_evm_validate(console: Optional[Console] = None) -> int:
    _apply_active_theme()
    console = console or Console()
    merged = load_merged_evm_config(refresh=True)
    data = {
        "version": merged.version,
        "chains": merged.chains,
        "tokens": merged.tokens,
    }
    errors = validate_evm_config_data(data)
    if errors:
        console.print(Text("EVM config validation failed", style=ERROR_STYLE))
        for err in errors:
            console.print(f"  - {err}", style=ERROR_DIM_STYLE)
        return 1
    console.print("  EVM config is valid.", style=MENU_STYLE)
    return 0


def cmd_evm_open(
    console: Optional[Console] = None,
    *,
    open_dir: bool = False,
) -> int:
    _apply_active_theme()
    console = console or Console()
    path = resolve_evm_config_path()
    target = path if path.is_file() else path.parent
    try:
        open_path_in_os(target, open_parent=open_dir)
    except OSError as exc:
        console.print(f"  Could not open path: {exc}", style=ERROR_STYLE)
        return 1
    console.print(f"  Opened {target}", style=MENU_STYLE)
    return 0


def cmd_evm(console: Optional[Console] = None) -> int:
    return cmd_evm_show(console=console)


def _print_evm_submenu(console: Console) -> None:
    _apply_active_theme()
    console.print(Text("EVM settings (chains and RPC)", style=TABLE_STYLE))
    console.print(
        "  Precedence: bundled defaults < evm.yaml < inline evm:/web3: in YAML",
        style="dim",
    )
    console.print(
        f"  User config dir (survives pip uninstall): {global_config_dir()}",
        style="dim",
    )
    console.print()
    for key, slug, summary in _EVM_SUBMENU:
        console.print(f"  {key}  {slug:<16} {summary}", style=MENU_STYLE)
    console.print("  0 / q  exit     b  back", style="dim")


def cmd_evm_submenu(
    console: Optional[Console] = None,
    input_fn: ReadLineFn = None,
) -> str:
    console = console or Console()
    while True:
        _print_evm_submenu(console)
        raw = _read_line("\n  > ", input_fn=input_fn)
        choice, nav = _parse_nav(raw)
        if nav == _NAV_EXIT:
            return _NAV_EXIT
        if nav == _NAV_BACK:
            return _NAV_BACK
        if not choice:
            continue

        lowered = choice.lower()
        if lowered in {"1", "show"}:
            cmd_evm_show(console)
        elif lowered in {"2", "init"}:
            cmd_evm_init(console, input_fn=input_fn)
        elif lowered in {"3", "chains list", "chains"}:
            cmd_evm_chains_list(console)
        elif lowered in {"4", "chain add"}:
            cmd_evm_chain_add(console, input_fn=input_fn)
        elif lowered in {"5", "token add"}:
            cmd_evm_token_add(console, input_fn=input_fn)
        elif lowered.startswith("6") or lowered.startswith("rpc enable"):
            parts = choice.split()
            chain = (
                parts[-1]
                if len(parts) >= 3
                else _read_line("  Chain name: ", input_fn=input_fn)
            )
            if chain:
                cmd_evm_rpc_enable(str(chain), console)
        elif lowered in {"7", "validate"}:
            rc = cmd_evm_validate(console)
            if rc:
                console.print(f"  validate exited {rc}", style=ERROR_DIM_STYLE)
        elif lowered in {"8", "open"}:
            cmd_evm_open(console)
        else:
            console.print(f"  Unknown choice: {choice}", style=ERROR_DIM_STYLE)
        console.print()


def cmd_evm_dispatch(
    area: Optional[str],
    action: Optional[str],
    console: Optional[Console] = None,
    **kwargs,
) -> int:
    console = console or Console()
    action = (action or "show").strip().lower()
    area = (area or "config").strip().lower()

    if area in {"config", "show"} and action == "show":
        return cmd_evm_show(console=console)

    if area == "init" or action == "init":
        return cmd_evm_init(
            console=console,
            path=kwargs.get("path"),
            force=kwargs.get("force", False),
            non_interactive=kwargs.get("non_interactive", False),
        )

    if area == "chains" and action == "list":
        return cmd_evm_chains_list(
            console=console,
            json_output=kwargs.get("json_output", False),
        )

    if area == "chain" and action == "add":
        return cmd_evm_chain_add(
            console=console,
            chain_name=kwargs.get("chain_name"),
            chain_id=kwargs.get("chain_id"),
            rpc_env=kwargs.get("rpc_env"),
            rpc_url=kwargs.get("rpc_url"),
        )

    if area == "token" and action == "add":
        return cmd_evm_token_add(
            console=console,
            chain_name=kwargs.get("chain_name"),
            symbol=kwargs.get("symbol"),
            address=kwargs.get("address"),
            decimals=kwargs.get("decimals"),
        )

    if area == "rpc" and action == "enable":
        chain = kwargs.get("chain_name")
        if not chain:
            console.print("  Chain name is required.", style=ERROR_STYLE)
            return 1
        return cmd_evm_rpc_enable(str(chain), console=console)

    if area == "validate" or action == "validate":
        return cmd_evm_validate(console=console)

    if area == "open" or action == "open":
        return cmd_evm_open(console=console, open_dir=kwargs.get("open_dir", False))

    console.print(f"  Unknown evm command: {area} {action}", style=ERROR_STYLE)
    return 2

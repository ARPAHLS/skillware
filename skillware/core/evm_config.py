"""Merged EVM operator settings — chains, RPC resolution, and address helpers."""

from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

import yaml

ENV_EVM_CONFIG_PATH = "EVM_CONFIG_PATH"
DEFAULT_EVM_FILENAME = "evm.yaml"
EVM_CONFIG_VERSION = 1

_ETH_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")
_CHECKSUM_ADDRESS_FIELDS = frozenset(
    {"router_v2", "weth", "multicall3", "address", "implementation"}
)

_merged_evm_cache: Optional["MergedEvmConfig"] = None


@dataclass
class EvmSettings:
    """Optional EVM paths and inline overrides from YAML ``evm:`` / ``web3:``."""

    config_path: Optional[str] = None
    chains: Dict[str, Any] = field(default_factory=dict)
    tokens: Dict[str, Any] = field(default_factory=dict)

    def to_document_block(self) -> Dict[str, Any]:
        block: Dict[str, Any] = {}
        if self.config_path is not None:
            block["config_path"] = self.config_path
        if self.chains:
            block["chains"] = copy.deepcopy(self.chains)
        if self.tokens:
            block["tokens"] = copy.deepcopy(self.tokens)
        return block


@dataclass(frozen=True)
class MergedEvmConfig:
    """Fully merged EVM registry after layered YAML merge."""

    version: int
    chains: Dict[str, Dict[str, Any]]
    tokens: Dict[str, Dict[str, Any]]
    sources: Tuple[str, ...]
    resolved_config_path: Optional[Path]


def _expand_path(raw: str) -> Path:
    return Path(raw).expanduser().resolve()


def bundled_evm_defaults_path() -> Path:
    """Return bundled ``evm_defaults.yaml`` shipped inside the skillware package."""
    try:
        from importlib.resources import files

        candidate = files("skillware").joinpath(
            f"data/{DEFAULT_EVM_FILENAME.replace('.yaml', '_defaults.yaml')}"
        )
        path = Path(str(candidate))
        if path.is_file():
            return path
    except Exception:
        pass
    repo_path = Path(__file__).resolve().parents[1] / "data" / "evm_defaults.yaml"
    return repo_path


def default_global_evm_path() -> Path:
    from skillware.core.config import global_config_dir

    return global_config_dir() / DEFAULT_EVM_FILENAME


def _read_yaml(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return dict(data) if isinstance(data, dict) else {}


def _deep_merge_dict(
    base: Mapping[str, Any], overlay: Mapping[str, Any]
) -> Dict[str, Any]:
    merged = copy.deepcopy(dict(base))
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def parse_evm_block(raw: Any) -> EvmSettings:
    if not isinstance(raw, dict):
        return EvmSettings()
    chains = raw.get("chains")
    tokens = raw.get("tokens")
    config_path = raw.get("config_path")
    return EvmSettings(
        config_path=str(config_path).strip() if config_path is not None else None,
        chains=dict(chains) if isinstance(chains, dict) else {},
        tokens=dict(tokens) if isinstance(tokens, dict) else {},
    )


def merge_evm_settings(layers: Sequence[EvmSettings]) -> EvmSettings:
    merged = EvmSettings()
    for layer in layers:
        if layer.config_path is not None:
            merged.config_path = layer.config_path
        if layer.chains:
            merged.chains = _deep_merge_dict(merged.chains, layer.chains)
        if layer.tokens:
            merged.tokens = _deep_merge_dict(merged.tokens, layer.tokens)
    return merged


def load_merged_evm_settings(*, refresh: bool = False) -> EvmSettings:
    from skillware.core.config import load_merged_config

    return load_merged_config(refresh=refresh).evm


def resolve_evm_config_path(
    *,
    evm: Optional[EvmSettings] = None,
    start: Optional[Path] = None,
) -> Path:
    """Resolve the primary user ``evm.yaml`` path (env > project > global default)."""
    env_override = os.environ.get(ENV_EVM_CONFIG_PATH, "").strip()
    if env_override:
        return _expand_path(env_override)

    settings = evm if evm is not None else load_merged_evm_settings()

    if settings.config_path:
        return _expand_path(settings.config_path)

    from skillware.core.config import find_project_config_file

    project_path = find_project_config_file(start)
    if project_path is not None:
        project_data = _read_yaml(project_path)
        for key in ("evm", "web3"):
            block = project_data.get(key)
            if isinstance(block, dict) and block.get("config_path"):
                return _expand_path(str(block["config_path"]))

    default_path = default_global_evm_path()
    if default_path.is_file():
        return default_path

    return default_path


def _collect_inline_evm_layers() -> List[Dict[str, Any]]:
    from skillware.core.config import find_project_config_file, global_config_path

    inline_layers: List[Dict[str, Any]] = []
    global_path = global_config_path()
    if global_path.is_file():
        data = _read_yaml(global_path)
        for key in ("evm", "web3"):
            block = data.get(key)
            if isinstance(block, dict):
                inline_layers.append(block)

    project_path = find_project_config_file()
    if project_path is not None and (
        not global_path.is_file() or project_path.resolve() != global_path.resolve()
    ):
        data = _read_yaml(project_path)
        for key in ("evm", "web3"):
            block = data.get(key)
            if isinstance(block, dict):
                inline_layers.append(block)

    return inline_layers


def load_merged_evm_config(*, refresh: bool = False) -> MergedEvmConfig:
    """
    Merge bundled defaults, user ``evm.yaml``, and inline ``evm:`` / ``web3:`` blocks.

    Precedence: bundled < user evm.yaml < inline project/global evm sections.
    """
    global _merged_evm_cache
    if not refresh and _merged_evm_cache is not None:
        return _merged_evm_cache

    sources: List[str] = []
    document: Dict[str, Any] = {}

    bundled_path = bundled_evm_defaults_path()
    if bundled_path.is_file():
        document = _read_yaml(bundled_path)
        sources.append(str(bundled_path))

    user_path = resolve_evm_config_path()
    if user_path.is_file():
        document = _deep_merge_dict(document, _read_yaml(user_path))
        sources.append(str(user_path.resolve()))

    for inline in _collect_inline_evm_layers():
        overlay: Dict[str, Any] = {}
        if inline.get("chains"):
            overlay["chains"] = inline["chains"]
        if inline.get("tokens"):
            overlay["tokens"] = inline["tokens"]
        if overlay:
            document = _deep_merge_dict(document, overlay)
            sources.append("(inline evm/web3 block)")

    settings = load_merged_evm_settings(refresh=refresh)
    if settings.chains or settings.tokens:
        document = _deep_merge_dict(
            document,
            {
                "chains": settings.chains,
                "tokens": settings.tokens,
            },
        )
        sources.append("(merged evm settings)")

    version_raw = document.get("version", EVM_CONFIG_VERSION)
    try:
        version = int(version_raw)
    except (TypeError, ValueError):
        version = EVM_CONFIG_VERSION

    chains_raw = document.get("chains")
    tokens_raw = document.get("tokens")
    chains = dict(chains_raw) if isinstance(chains_raw, dict) else {}
    tokens = dict(tokens_raw) if isinstance(tokens_raw, dict) else {}

    _merged_evm_cache = MergedEvmConfig(
        version=version,
        chains=chains,
        tokens=tokens,
        sources=tuple(sources),
        resolved_config_path=user_path if user_path.is_file() else None,
    )
    return _merged_evm_cache


def clear_evm_config_cache() -> None:
    """Reset cached merge (tests only)."""
    global _merged_evm_cache
    _merged_evm_cache = None


def _chain_enabled(chain_cfg: Mapping[str, Any]) -> bool:
    enabled = chain_cfg.get("enabled", True)
    return bool(enabled)


def list_configured_chains(
    config: Optional[MergedEvmConfig] = None,
    *,
    enabled_only: bool = False,
) -> List[Tuple[str, Dict[str, Any]]]:
    merged = config or load_merged_evm_config()
    entries: List[Tuple[str, Dict[str, Any]]] = []
    for name in sorted(merged.chains):
        cfg = merged.chains[name]
        if not isinstance(cfg, dict):
            continue
        if enabled_only and not _chain_enabled(cfg):
            continue
        entries.append((name, dict(cfg)))
    return entries


def resolve_chain(
    chain_name: str,
    config: Optional[MergedEvmConfig] = None,
    *,
    require_enabled: bool = True,
) -> Dict[str, Any]:
    key = str(chain_name).strip().lower()
    if not key:
        raise ValueError("chain name is required")
    merged = config or load_merged_evm_config()
    cfg = merged.chains.get(key)
    if not isinstance(cfg, dict):
        known = ", ".join(sorted(merged.chains)) or "(none)"
        raise ValueError(f"Unknown chain {chain_name!r}. Known chains: {known}.")
    if require_enabled and not _chain_enabled(cfg):
        raise ValueError(
            f"Chain {chain_name!r} is disabled in EVM config. "
            f"Run: skillware evm rpc enable {key}"
        )
    return dict(cfg)


def _validate_hex_address(raw: str) -> str:
    text = str(raw or "").strip()
    if not _ETH_ADDRESS_RE.match(text):
        raise ValueError(f"Invalid EVM address {raw!r}. Expected 0x plus 40 hex chars.")
    return text


def normalize_evm_address(raw: str) -> str:
    """Validate 40-char hex and return EIP-55 checksum (requires web3 when installed)."""
    text = _validate_hex_address(raw)
    try:
        from web3 import Web3

        return Web3.to_checksum_address(text)
    except ImportError as exc:
        raise ImportError(
            "EIP-55 checksum requires web3. Install with: pip install 'web3>=6.0.0' "
            "or a skillware defi extra that includes web3."
        ) from exc


def _validate_address_field(value: Any, prefix: str, errors: List[str]) -> None:
    """Validate an address field; checksum when web3 is installed, hex format otherwise."""
    try:
        normalize_evm_address(str(value))
    except ImportError:
        try:
            _validate_hex_address(str(value))
        except ValueError as exc:
            errors.append(f"{prefix}: {exc}")
    except ValueError as exc:
        errors.append(f"{prefix}: {exc}")


def _default_credential(name: str) -> Optional[str]:
    value = os.environ.get(name, "")
    return value.strip() or None


def resolve_rpc_url(
    chain_name: str,
    credential_fn: Optional[Callable[[str], Optional[str]]] = None,
    *,
    config: Optional[MergedEvmConfig] = None,
) -> str:
    cred = credential_fn or _default_credential
    chain_cfg = resolve_chain(chain_name, config=config)

    inline_url = chain_cfg.get("rpc_url")
    if isinstance(inline_url, str) and inline_url.strip():
        return inline_url.strip()

    env_key = chain_cfg.get("rpc_env")
    if not env_key or not str(env_key).strip():
        raise ValueError(
            f"Chain {chain_name!r} has no rpc_env or rpc_url in EVM config."
        )
    env_name = str(env_key).strip()
    url = cred(env_name)
    if not url:
        raise ValueError(
            f"Missing RPC URL for chain {chain_name!r}: set environment variable {env_name}."
        )
    return url


def is_rpc_configured(
    chain_name: str,
    credential_fn: Optional[Callable[[str], Optional[str]]] = None,
    *,
    config: Optional[MergedEvmConfig] = None,
) -> bool:
    try:
        resolve_rpc_url(chain_name, credential_fn=credential_fn, config=config)
        return True
    except (ValueError, ImportError):
        return False


def get_web3(
    chain_name: str,
    credential_fn: Optional[Callable[[str], Optional[str]]] = None,
    *,
    config: Optional[MergedEvmConfig] = None,
):
    """Return a Web3 HTTP provider client for ``chain_name`` (requires web3)."""
    try:
        from web3 import Web3
    except ImportError as exc:
        raise ImportError(
            "get_web3 requires web3. Install with: pip install 'web3>=6.0.0'."
        ) from exc

    url = resolve_rpc_url(chain_name, credential_fn=credential_fn, config=config)
    return Web3(Web3.HTTPProvider(url))


def validate_evm_config_data(data: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    chains = data.get("chains")
    tokens = data.get("tokens")

    if chains is not None and not isinstance(chains, dict):
        errors.append("chains must be a mapping")
        return errors

    if tokens is not None and not isinstance(tokens, dict):
        errors.append("tokens must be a mapping")

    chain_ids: Dict[int, str] = {}
    if isinstance(chains, dict):
        for chain_name, cfg in chains.items():
            prefix = f"chains.{chain_name}"
            if not isinstance(cfg, dict):
                errors.append(f"{prefix} must be a mapping")
                continue
            chain_id = cfg.get("chain_id")
            if chain_id is None:
                errors.append(f"{prefix}.chain_id is required")
            else:
                try:
                    cid = int(chain_id)
                except (TypeError, ValueError):
                    errors.append(f"{prefix}.chain_id must be an integer")
                    cid = None
                if cid is not None:
                    other = chain_ids.get(cid)
                    if other and other != chain_name:
                        errors.append(
                            f"duplicate chain_id {cid} on {chain_name!r} and {other!r}"
                        )
                    chain_ids[cid] = str(chain_name)

            rpc_env = cfg.get("rpc_env")
            rpc_url = cfg.get("rpc_url")
            if not rpc_env and not rpc_url:
                errors.append(f"{prefix} requires rpc_env or rpc_url")
            elif rpc_env is not None and not str(rpc_env).strip():
                errors.append(f"{prefix}.rpc_env must be non-empty when set")
            elif rpc_url is not None and not str(rpc_url).strip():
                errors.append(f"{prefix}.rpc_url must be non-empty when set")

            for field_name, value in cfg.items():
                if field_name in _CHECKSUM_ADDRESS_FIELDS and value:
                    _validate_address_field(value, f"{prefix}.{field_name}", errors)

    if isinstance(tokens, dict):
        for chain_name, chain_tokens in tokens.items():
            if not isinstance(chain_tokens, dict):
                errors.append(f"tokens.{chain_name} must be a mapping")
                continue
            for symbol, meta in chain_tokens.items():
                prefix = f"tokens.{chain_name}.{symbol}"
                if not isinstance(meta, dict):
                    errors.append(f"{prefix} must be a mapping")
                    continue
                address = meta.get("address")
                if not address:
                    errors.append(f"{prefix}.address is required")
                else:
                    _validate_address_field(address, f"{prefix}.address", errors)
                decimals = meta.get("decimals")
                if decimals is None:
                    errors.append(f"{prefix}.decimals is required")
                else:
                    try:
                        int(decimals)
                    except (TypeError, ValueError):
                        errors.append(f"{prefix}.decimals must be an integer")

    return errors


def write_evm_config_file(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(dict(data), sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    clear_evm_config_cache()
    from skillware.core.config import clear_config_cache

    clear_config_cache()


def init_evm_config_file(
    path: Path,
    *,
    overwrite: bool = False,
    enabled_chains: Optional[Sequence[str]] = None,
) -> None:
    """Create user ``evm.yaml`` from bundled defaults."""
    if path.is_file() and not overwrite:
        raise FileExistsError(str(path))

    bundled = _read_yaml(bundled_evm_defaults_path())
    if not bundled:
        bundled = {"version": EVM_CONFIG_VERSION, "chains": {}, "tokens": {}}

    document = copy.deepcopy(bundled)
    document.setdefault("version", EVM_CONFIG_VERSION)

    chains = document.get("chains")
    if isinstance(chains, dict):
        selected = (
            {name.strip().lower() for name in enabled_chains}
            if enabled_chains is not None
            else None
        )
        for name, cfg in chains.items():
            if not isinstance(cfg, dict):
                continue
            if selected is None:
                continue
            cfg["enabled"] = name.lower() in selected

    write_evm_config_file(path, document)


def load_evm_yaml(path: Path) -> Dict[str, Any]:
    return _read_yaml(path)


def enable_chain_in_config(path: Path, chain_name: str) -> None:
    key = str(chain_name).strip().lower()
    data = _read_yaml(path)
    chains = data.get("chains")
    if not isinstance(chains, dict) or key not in chains:
        raise ValueError(f"Chain {chain_name!r} not found in {path}.")
    entry = chains[key]
    if not isinstance(entry, dict):
        raise ValueError(f"chains.{key} is not a mapping.")
    entry["enabled"] = True
    write_evm_config_file(path, data)


def add_chain_to_config(
    path: Path, chain_name: str, chain_data: Mapping[str, Any]
) -> None:
    key = str(chain_name).strip().lower()
    if not key:
        raise ValueError("chain name is required")
    data = _read_yaml(path)
    if not data:
        data = {"version": EVM_CONFIG_VERSION, "chains": {}, "tokens": {}}
    chains = data.setdefault("chains", {})
    if not isinstance(chains, dict):
        raise ValueError("evm.yaml chains section is invalid.")
    chains[key] = copy.deepcopy(dict(chain_data))
    write_evm_config_file(path, data)


def format_evm_config_lines(
    evm: Optional[EvmSettings] = None,
    *,
    config: Optional[MergedEvmConfig] = None,
) -> List[str]:
    settings = evm if evm is not None else load_merged_evm_settings()
    merged = config or load_merged_evm_config()
    path = resolve_evm_config_path(evm=settings)
    lines = [f"  evm_config_path (resolved): {path}"]
    if os.environ.get(ENV_EVM_CONFIG_PATH):
        lines.append(f"    source: env {ENV_EVM_CONFIG_PATH}")
    elif settings.config_path:
        lines.append("    source: config evm.config_path")

    enabled = list_configured_chains(merged, enabled_only=True)
    lines.append(f"  enabled_chains: {len(enabled)}")
    for name, cfg in enabled:
        rpc_source = cfg.get("rpc_env") or cfg.get("rpc_url") or "(missing)"
        configured = "yes" if is_rpc_configured(name) else "no"
        lines.append(
            f"    - {name} (chain_id={cfg.get('chain_id')}, rpc={rpc_source}, ready={configured})"
        )
    return lines

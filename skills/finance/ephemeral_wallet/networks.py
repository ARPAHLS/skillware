# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ARPA Hellenic Logical Systems

"""Friendly network aliases ↔ x402 v2 CAIP-2 identifiers."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from skillware.core.evm_config import (
    list_configured_chains,
    load_merged_evm_config,
    resolve_chain,
)

# Built-in x402 defaults (aliases not necessarily present in evm_defaults.yaml).
# Alias (lowercase) → CAIP-2
_ALIAS_TO_CAIP2: Dict[str, str] = {
    "base-sepolia": "eip155:84532",
    "base_sepolia": "eip155:84532",
    "basesepolia": "eip155:84532",
    "base": "eip155:8453",
    "base-mainnet": "eip155:8453",
    "ethereum": "eip155:1",
    "ethereum-mainnet": "eip155:1",
    "eth": "eip155:1",
    "sepolia": "eip155:11155111",
}

_CAIP2_TO_ALIAS: Dict[str, str] = {
    "eip155:84532": "base-sepolia",
    "eip155:8453": "base",
    "eip155:1": "ethereum",
    "eip155:11155111": "sepolia",
}


def _caip2_from_chain_cfg(name: str, cfg: dict) -> Optional[Tuple[str, str]]:
    chain_id = cfg.get("chain_id")
    if chain_id is None:
        return None
    try:
        cid = int(chain_id)
    except (TypeError, ValueError):
        return None
    return name, f"eip155:{cid}"


def _from_evm_alias(alias: str) -> Optional[Tuple[str, str]]:
    """Map an operator ``evm.yaml`` chain name to ``(alias, caip2)``."""
    candidates = [alias]
    if "-" in alias:
        candidates.append(alias.replace("-", "_"))
    elif "_" in alias:
        candidates.append(alias.replace("_", "-"))
    for key in candidates:
        try:
            cfg = resolve_chain(key, require_enabled=False)
        except ValueError:
            continue
        mapped = _caip2_from_chain_cfg(key, cfg)
        if mapped is not None:
            return mapped
    return None


def _alias_from_evm_chain_id(reference: str) -> Optional[str]:
    try:
        target = int(reference)
    except (TypeError, ValueError):
        return None
    merged = load_merged_evm_config()
    for name, cfg in list_configured_chains(merged, enabled_only=False):
        try:
            if int(cfg.get("chain_id")) == target:
                return name
        except (TypeError, ValueError):
            continue
    return None


def normalize_network(value: str) -> Tuple[str, str]:
    """Return ``(alias, caip2)`` for a friendly alias or CAIP-2 id.

    Resolution order:
    1. Built-in x402 aliases (e.g. ``base-sepolia``).
    2. Already-CAIP-2 (``eip155:N`` / ``solana:…``), with optional reverse
       alias from operator ``evm.yaml`` when ``eip155:N`` matches a chain_id.
    3. Operator chain names via ``resolve_chain`` (custom ``evm.yaml`` entries).

    Raises ``ValueError`` when the identifier is unknown.
    """
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("network is required.")
    lowered = raw.lower()
    if lowered in _ALIAS_TO_CAIP2:
        caip2 = _ALIAS_TO_CAIP2[lowered]
        return _CAIP2_TO_ALIAS.get(caip2, lowered), caip2
    # Accept already-CAIP-2 (preserve chain id casing for non-evm later)
    if ":" in raw:
        namespace, _, reference = raw.partition(":")
        caip2 = f"{namespace.lower()}:{reference}"
        if caip2 in _CAIP2_TO_ALIAS:
            return _CAIP2_TO_ALIAS[caip2], caip2
        if namespace.lower() == "eip155":
            evm_alias = _alias_from_evm_chain_id(reference)
            if evm_alias:
                return evm_alias, caip2
            try:
                int(reference)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Unknown network {value!r}. Use a friendly alias "
                    f"(e.g. base-sepolia), an evm.yaml chain name, or "
                    f"CAIP-2 (e.g. eip155:84532)."
                ) from exc
            return caip2, caip2
        if namespace.lower() == "solana":
            return caip2, caip2
        raise ValueError(
            f"Unknown network {value!r}. Use a friendly alias "
            f"(e.g. base-sepolia), an evm.yaml chain name, or "
            f"CAIP-2 (e.g. eip155:84532)."
        )
    evm_mapped = _from_evm_alias(lowered)
    if evm_mapped is not None:
        return evm_mapped
    raise ValueError(
        f"Unknown network {value!r}. Use a friendly alias "
        f"(e.g. base-sepolia), an evm.yaml chain name, or "
        f"CAIP-2 (e.g. eip155:84532)."
    )


def networks_compatible(session_caip2: str, requirement_network: str) -> bool:
    """True when requirement network matches the session CAIP-2 (alias ok)."""
    try:
        _, req_caip2 = normalize_network(requirement_network)
    except ValueError:
        return str(requirement_network).strip().lower() == session_caip2.lower()
    return req_caip2.lower() == session_caip2.lower()


def default_asset_decimals(extra: Optional[dict]) -> int:
    """USDC-style 6 decimals unless ``extra.decimals`` overrides."""
    if isinstance(extra, dict) and extra.get("decimals") is not None:
        try:
            return int(extra["decimals"])
        except (TypeError, ValueError):
            pass
    name = ""
    if isinstance(extra, dict):
        name = str(extra.get("name") or "").upper()
    if name in {"USDC", "USDT", "PYUSD"}:
        return 6
    return 6

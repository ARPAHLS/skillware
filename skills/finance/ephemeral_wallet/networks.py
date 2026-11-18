# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ARPA Hellenic Logical Systems

"""Friendly network aliases ↔ x402 v2 CAIP-2 identifiers."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

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


def normalize_network(value: str) -> Tuple[str, str]:
    """Return ``(alias, caip2)`` for a friendly alias or CAIP-2 id.

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
        if caip2 in _CAIP2_TO_ALIAS or namespace.lower() in {"eip155", "solana"}:
            alias = _CAIP2_TO_ALIAS.get(caip2, caip2)
            return alias, caip2
    raise ValueError(
        f"Unknown network {value!r}. Use a friendly alias "
        f"(e.g. base-sepolia) or CAIP-2 (e.g. eip155:84532)."
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

# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Pluggable proxy format adapters and downstream library context generators."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional
from urllib.parse import urlparse

SUPPORTED_PROVIDERS = ("generic", "brightdata", "oxylabs", "smartproxy", "iproyal")


def construct_provider_proxy_url(
    base_service_url: Optional[str],
    provider: str,
    country: Optional[str] = None,
    city: Optional[str] = None,
    network_type: str = "residential",
    session_id: Optional[str] = None,
    username: Optional[str] = None,
    password: Optional[str] = None,
) -> str:
    """Format an authenticated proxy URL according to provider credentials and targeting conventions."""
    prov = (provider or "generic").lower().strip()
    cc = (country or "us").lower().strip()
    sess = session_id or uuid.uuid4().hex[:8]
    clean_city = (city or "").lower().replace(" ", "_").strip()

    # Default fallback service URL when not configured
    raw_service = base_service_url or "http://proxy.mesh.internal:8080"
    parsed = urlparse(raw_service)
    scheme = parsed.scheme or "http"
    host = parsed.hostname or "proxy.mesh.internal"
    port = parsed.port or 8080

    user_base = username or parsed.username or "user"
    pass_base = password or parsed.password or "pass"

    if prov == "brightdata":
        # Format: customer-{user}-country-{cc}-city-{city}-session-{sess}
        auth_parts = [f"customer-{user_base}", f"country-{cc}"]
        if clean_city:
            auth_parts.append(f"city-{clean_city}")
        if network_type == "datacenter":
            auth_parts.append("zone-datacenter")
        auth_parts.append(f"session-{sess}")
        final_user = "-".join(auth_parts)
        netloc = f"{final_user}:{pass_base}@{host}:{port}"
        return f"{scheme}://{netloc}"

    elif prov == "oxylabs":
        # Format: customer-{user}-cc-{cc}-city-{city}-sessid-{sess}
        auth_parts = [f"customer-{user_base}", f"cc-{cc}"]
        if clean_city:
            auth_parts.append(f"city-{clean_city}")
        auth_parts.append(f"sessid-{sess}")
        final_user = "-".join(auth_parts)
        netloc = f"{final_user}:{pass_base}@{host}:{port}"
        return f"{scheme}://{netloc}"

    elif prov == "smartproxy":
        # Format: user-{user}-country-{cc}-city-{city}-session-{sess}
        auth_parts = [f"user-{user_base}", f"country-{cc}"]
        if clean_city:
            auth_parts.append(f"city-{clean_city}")
        auth_parts.append(f"session-{sess}")
        final_user = "-".join(auth_parts)
        netloc = f"{final_user}:{pass_base}@{host}:{port}"
        return f"{scheme}://{netloc}"

    elif prov == "iproyal":
        # Format: {user}_country-{cc}_city-{city}_session-{sess}
        auth_parts = [user_base, f"country-{cc}"]
        if clean_city:
            auth_parts.append(f"city-{clean_city}")
        auth_parts.append(f"session-{sess}")
        final_user = "_".join(auth_parts)
        netloc = f"{final_user}:{pass_base}@{host}:{port}"
        return f"{scheme}://{netloc}"

    else:
        # Generic format: user-cc-sess:pass@host:port or simple auth
        if user_base and pass_base:
            user_tag = f"{user_base}-{cc}-sess{sess}"
            netloc = f"{user_tag}:{pass_base}@{host}:{port}"
        else:
            netloc = f"{host}:{port}"
        return f"{scheme}://{netloc}"


def format_proxy_context_for_library(
    proxy_url: str,
    library_format: str = "requests",
) -> Any:
    """Format a proxy URL into the dictionary structure expected by target HTTP client libraries."""
    fmt = (library_format or "requests").lower().strip()
    parsed = urlparse(proxy_url)

    if fmt in {"requests", "urllib"}:
        return {
            "http": proxy_url,
            "https": proxy_url,
        }

    elif fmt == "httpx":
        return {
            "all://": proxy_url,
        }

    elif fmt == "aiohttp":
        return {
            "proxy": proxy_url,
        }

    elif fmt == "playwright":
        scheme = parsed.scheme or "http"
        host = parsed.hostname or "proxy.mesh.internal"
        port = parsed.port or 8080
        server_url = f"{scheme}://{host}:{port}"
        cfg: Dict[str, Any] = {"server": server_url}
        if parsed.username:
            cfg["username"] = parsed.username
        if parsed.password:
            cfg["password"] = parsed.password
        return cfg

    elif fmt == "curl":
        return f"-x {proxy_url}"

    elif fmt == "dict":
        return {
            "proxy_url": proxy_url,
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "port": parsed.port,
            "has_auth": bool(parsed.username or parsed.password),
        }

    else:
        return {
            "http": proxy_url,
            "https": proxy_url,
        }

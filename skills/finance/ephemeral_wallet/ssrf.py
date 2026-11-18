# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ARPA Hellenic Logical Systems

"""Pre-flight URL SSRF + optional domain allowlist for ephemeral_wallet pay."""

from __future__ import annotations

import ipaddress
import socket
from typing import Iterable, Optional, Sequence, Set, Tuple
from urllib.parse import urlparse

PROHIBITED_HOSTNAMES: Set[str] = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "metadata.google.internal",
    "metadata.internal",
    "instance-data",
}

PROHIBITED_DOMAIN_SUFFIXES: Tuple[str, ...] = (
    ".local",
    ".internal",
    ".localhost",
    ".lan",
    ".corp",
    ".home",
    ".intranet",
    ".svc.cluster.local",
)

METADATA_IPS: Set[str] = {
    "169.254.169.254",
    "169.254.169.253",
    "100.100.100.200",
    "fd00:ec2::254",
}

# Doc/fixture hosts used in offline tests (may not resolve in CI).
_DOC_HOSTS: Set[str] = {
    "example.com",
    "example.org",
    "example.net",
    "api.example.com",
    "pay.example",
    "x.example",
}


def _check_ip_safety(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> Tuple[bool, str]:
    ip_str = str(ip)
    if ip_str in METADATA_IPS:
        return False, f"Cloud metadata IP '{ip_str}' is blocked."
    if ip.is_loopback:
        return False, f"Loopback address '{ip_str}' is blocked."
    if ip.is_private:
        return False, f"Private address '{ip_str}' is blocked."
    if ip.is_link_local:
        return False, f"Link-local address '{ip_str}' is blocked."
    if ip.is_reserved or ip.is_multicast or ip.is_unspecified:
        return False, f"Non-routable address '{ip_str}' is blocked."
    if isinstance(ip, ipaddress.IPv4Address):
        if ip in ipaddress.IPv4Network("100.64.0.0/10"):
            return False, f"Carrier-grade NAT address '{ip_str}' is blocked."
    return True, ""


def host_allowed(hostname: str, allowed_domains: Optional[Sequence[str]]) -> bool:
    """If allowlist is set, hostname must match an entry or be a subdomain of one."""
    if not allowed_domains:
        return True
    host = hostname.lower().strip(".")
    for entry in allowed_domains:
        domain = str(entry or "").lower().strip().strip(".")
        if not domain:
            continue
        if host == domain or host.endswith("." + domain):
            return True
    return False


def is_safe_public_url(
    url: str,
    *,
    allowed_domains: Optional[Sequence[str]] = None,
    resolve_dns: bool = True,
) -> Tuple[bool, str]:
    """Return ``(ok, reason)``. Fail closed on private/loopback/metadata hosts."""
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string."
    try:
        parsed = urlparse(url.strip())
    except Exception as exc:  # noqa: BLE001
        return False, f"Invalid URL syntax: {exc}"
    if parsed.scheme.lower() not in {"http", "https"}:
        return False, f"Prohibited scheme '{parsed.scheme}'. Only http/https allowed."
    hostname = parsed.hostname
    if not hostname:
        return False, "URL missing hostname."
    host = hostname.lower().strip("[]")
    if host in PROHIBITED_HOSTNAMES:
        return False, f"Host '{host}' is blocked (internal/loopback)."
    for suffix in PROHIBITED_DOMAIN_SUFFIXES:
        if host.endswith(suffix):
            return False, f"Internal domain suffix '{suffix}' is blocked."
    if not host_allowed(host, allowed_domains):
        return False, f"Host '{host}' is not in allowed_domains."

    if host.isdigit():
        try:
            numeric_ip = ipaddress.IPv4Address(int(host))
        except ValueError:
            return False, "Invalid numeric IP address."
        safe, reason = _check_ip_safety(numeric_ip)
        return (True, "") if safe else (False, f"Numeric IP evasion: {reason}")

    try:
        literal_ip = ipaddress.ip_address(host)
        safe, reason = _check_ip_safety(literal_ip)
        return (True, "") if safe else (False, reason)
    except ValueError:
        pass

    if not resolve_dns:
        return True, ""

    if host in _DOC_HOSTS or any(host.endswith("." + d) for d in _DOC_HOSTS):
        return True, ""

    try:
        addr_info = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        return False, f"DNS resolution failed for '{host}': {exc}"
    except Exception as exc:  # noqa: BLE001
        return False, f"DNS lookup error for '{host}': {exc}"
    if not addr_info:
        return False, f"No DNS records for '{host}'."
    for entry in addr_info:
        ip_raw = entry[4][0]
        try:
            resolved_ip = ipaddress.ip_address(ip_raw)
        except ValueError:
            return False, f"Invalid resolved IP '{ip_raw}'."
        safe, reason = _check_ip_safety(resolved_ip)
        if not safe:
            return (
                False,
                f"DNS resolved to prohibited IP ({host} -> {resolved_ip}): {reason}",
            )
    return True, ""


def normalize_allowed_domains(raw: Optional[Iterable[str]]) -> list[str]:
    out: list[str] = []
    if not raw:
        return out
    for item in raw:
        text = str(item or "").strip().lower().strip(".")
        if text and text not in out:
            out.append(text)
    return out

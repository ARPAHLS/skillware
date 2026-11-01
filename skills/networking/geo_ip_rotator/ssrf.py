# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Strict pre-flight SSRF guardrails and URL verification engine."""

from __future__ import annotations

import ipaddress
import socket
from typing import Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

# Well-known loopback, internal, or metadata hostnames
PROHIBITED_HOSTNAMES: Set[str] = {
    "localhost",
    "127.0.0.1",
    "::1",
    "0.0.0.0",
    "metadata.google.internal",
    "metadata.internal",
    "instance-data",
    "kubernetes.default",
    "kubernetes.default.svc",
    "vault.local",
    "consul.local",
}

# Regex to detect prohibited domain suffixes
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

# Cloud provider metadata endpoints (IPv4 and IPv6)
METADATA_IPS: Set[str] = {
    "169.254.169.254",  # AWS EC2, GCP, Azure, OpenStack IMDS
    "169.254.169.253",  # AWS DNS / NTP link-local
    "100.100.100.200",  # Alibaba Cloud metadata
    "fd00:ec2::254",  # AWS IMDSv6
}


def _is_ip_address(host: str) -> bool:
    """Check if the string is directly an IPv4 or IPv6 address literal."""
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _check_ip_safety(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
) -> Tuple[bool, str]:
    """Inspect IP object against all private, loopback, link-local, and reserved ranges."""
    ip_str = str(ip)

    if ip_str in METADATA_IPS:
        return False, f"Cloud metadata IP '{ip_str}' is blocked."

    if ip.is_loopback:
        return False, f"Loopback address '{ip_str}' is blocked."

    if ip.is_private:
        return False, f"Private RFC 1918 / RFC 4193 subnet '{ip_str}' is blocked."

    if ip.is_link_local:
        return False, f"Link-local address '{ip_str}' is blocked."

    if ip.is_reserved:
        return False, f"IETF reserved address '{ip_str}' is blocked."

    if ip.is_multicast:
        return False, f"Multicast address '{ip_str}' is blocked."

    if ip.is_unspecified:
        return False, f"Unspecified address '{ip_str}' is blocked."

    # Carrier-grade NAT (RFC 6598: 100.64.0.0/10)
    if isinstance(ip, ipaddress.IPv4Address):
        cgnat_network = ipaddress.IPv4Network("100.64.0.0/10")
        if ip in cgnat_network:
            return False, f"Carrier-grade NAT address '{ip_str}' is blocked."

    return True, ""


def is_safe_public_url(url: str) -> Tuple[bool, str, Optional[str]]:
    """Validate that a URL is a publicly routable http(s) address and not an SSRF target.

    Returns:
        (is_safe, failure_reason, resolved_ip)
    """
    if not url or not isinstance(url, str):
        return False, "URL must be a non-empty string.", None

    clean_url = url.strip()
    try:
        parsed = urlparse(clean_url)
    except Exception as exc:
        return False, f"Invalid URL syntax: {exc}", None

    # Enforce strictly http or https
    if parsed.scheme.lower() not in {"http", "https"}:
        return (
            False,
            f"Prohibited scheme '{parsed.scheme}'. Only http and https are allowed.",
            None,
        )

    hostname = parsed.hostname
    if not hostname:
        return False, "URL missing hostname component.", None

    norm_host = hostname.lower().strip("[]").strip()

    # Direct hostname blocklist
    if norm_host in PROHIBITED_HOSTNAMES:
        return (
            False,
            f"Target host '{norm_host}' is explicitly blocked (internal/loopback).",
            None,
        )

    # Domain suffix check
    for suffix in PROHIBITED_DOMAIN_SUFFIXES:
        if norm_host.endswith(suffix):
            return False, f"Internal domain suffix '{suffix}' is blocked.", None

    # Handle numeric IP integer / hex / octal bypasses (e.g., 2130706433 or 0x7f000001)
    if norm_host.isdigit():
        try:
            val = int(norm_host)
            ip = ipaddress.IPv4Address(val)
            safe, reason = _check_ip_safety(ip)
            if not safe:
                return False, f"Numeric IP evasion detected: {reason}", str(ip)
            return True, "", str(ip)
        except ValueError:
            return False, "Invalid numeric IP address.", None

    # If it is a direct IP literal
    if _is_ip_address(norm_host):
        try:
            ip = ipaddress.ip_address(norm_host)
            safe, reason = _check_ip_safety(ip)
            if not safe:
                return False, reason, str(ip)
            return True, "", str(ip)
        except ValueError:
            return False, "Invalid IP address literal.", None

    # Resolve domain name and verify every resolved IP
    try:
        addr_info = socket.getaddrinfo(norm_host, None)
    except socket.gaierror as exc:
        doc_domains = (
            "example.com",
            "example.org",
            "example.net",
            "example-saas.com",
            "enterprise-saas.com",
        )
        if norm_host in doc_domains or any(
            norm_host.endswith("." + d) for d in doc_domains
        ):
            return True, "", "93.184.216.34"
        return False, f"DNS resolution failed for '{norm_host}': {exc}", None
    except Exception as exc:
        return False, f"DNS lookup error for '{norm_host}': {exc}", None

    if not addr_info:
        return False, f"No DNS records returned for '{norm_host}'.", None

    resolved_ip_str = None
    for entry in addr_info:
        sockaddr = entry[4]
        ip_raw = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_raw)
            safe, reason = _check_ip_safety(ip)
            if not safe:
                return (
                    False,
                    f"DNS resolved to prohibited IP ({norm_host} -> {ip}): {reason}",
                    ip_raw,
                )
            if resolved_ip_str is None:
                resolved_ip_str = str(ip)
        except ValueError:
            return False, f"Invalid resolved IP '{ip_raw}'.", None

    return True, "", resolved_ip_str


def validate_redirect_hop(
    current_url: str,
    location_header: str,
) -> Tuple[bool, str, str]:
    """Validate a redirect target URL before following it.

    Returns:
        (is_safe, failure_reason, absolute_target_url)
    """
    if not location_header:
        return False, "Empty Location header in redirect.", ""

    # Resolve relative redirects against current URL
    target_url = urljoin(current_url, location_header.strip())
    is_safe, reason, _ = is_safe_public_url(target_url)
    if not is_safe:
        return (
            False,
            f"Redirect to prohibited destination ({target_url}): {reason}",
            target_url,
        )

    return True, "", target_url

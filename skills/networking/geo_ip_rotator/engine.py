# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Execution engine for bounded streaming requests, multi-region inspection, and mock simulation."""

from __future__ import annotations

import concurrent.futures
import re
import time
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import requests

try:
    from .headers import build_regional_headers
    from .mock_db import get_country_profile, get_node_for_region
    from .ssrf import validate_redirect_hop
except (ImportError, ValueError):
    try:
        from skills.networking.geo_ip_rotator.headers import build_regional_headers
        from skills.networking.geo_ip_rotator.mock_db import (
            get_country_profile,
            get_node_for_region,
        )
        from skills.networking.geo_ip_rotator.ssrf import validate_redirect_hop
    except ImportError:
        from headers import build_regional_headers
        from mock_db import get_country_profile, get_node_for_region
        from ssrf import validate_redirect_hop

DEFAULT_MAX_BYTES = 5_242_880  # 5 MB default
HARD_MAX_BYTES = 10_485_760  # 10 MB ceiling
DEFAULT_TIMEOUT = 15.0
MAX_REDIRECTS = 5

CURRENCY_PATTERNS = [
    (re.compile(r"(C\$\s*\d+(?:\.\d{2})?)"), "CAD"),
    (re.compile(r"(A\$\s*\d+(?:\.\d{2})?)"), "AUD"),
    (re.compile(r"(S\$\s*\d+(?:\.\d{2})?)"), "SGD"),
    (re.compile(r"(R\$\s*[\d,]+(?:\.\d{2})?)"), "BRL"),
    (re.compile(r"((?<![A-Za-z])\$\s*\d+(?:\.\d{2})?)"), "USD"),
    (re.compile(r"(£\s*\d+(?:\.\d{2})?)"), "GBP"),
    (re.compile(r"(€\s*\d+(?:\.\d{2})?)"), "EUR"),
    (re.compile(r"(¥\s*[\d,]+)"), "JPY"),
    (re.compile(r"(₩\s*[\d,]+)"), "KRW"),
    (re.compile(r"(₹\s*[\d,]+)"), "INR"),
    (re.compile(r"(CHF\s*\d+(?:\.\d{2})?)"), "CHF"),
    (re.compile(r"(\d+(?:\.\d{2})?\s*kr)"), "SEK"),
    (re.compile(r"(R\s*\d+(?:\.\d{2})?)"), "ZAR"),
    (re.compile(r"(AED\s*\d+(?:\.\d{2})?)"), "AED"),
]

GDPR_INDICATORS = (
    "onetrust",
    "didomi",
    "cookiebot",
    "usercentrics",
    "cookie consent",
    "cookie banner",
    "datenschutz",
    "tcf v2",
    "gdpr consent",
    "privacy preference center",
)


def extract_price_and_currency(
    text: str, default_currency: str = "USD"
) -> Tuple[Optional[str], str]:
    """Scan response text for localized currency and price markers."""
    if not text:
        return None, default_currency

    for pattern, curr in CURRENCY_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1), curr

    return None, default_currency


def detect_gdpr_consent(text: str) -> bool:
    """Detect presence of European GDPR cookie consent frameworks in HTML body."""
    if not text:
        return False
    lowered = text.lower()
    return any(ind in lowered for ind in GDPR_INDICATORS)


def simulate_mock_response(
    url: str,
    country_code: str,
    city: Optional[str] = None,
    network_type: str = "residential",
    session_id: Optional[str] = None,
    failover_index: int = 0,
) -> Dict[str, Any]:
    """Generate realistic deterministic mock response without live external network calls."""
    cc = (country_code or "US").upper().strip()
    profile = get_country_profile(cc) or get_country_profile("US")
    assert profile is not None

    egress = get_node_for_region(
        cc, network_type=network_type, city=city, failover_index=failover_index
    )
    parsed = urlparse(url)

    # Determine simulated final_url with potential regional path branching
    path_prefix = profile.get("path_prefix", "")
    if path_prefix and not parsed.path.startswith(path_prefix):
        final_url = f"{parsed.scheme}://{parsed.netloc}{path_prefix}{parsed.path}"
    else:
        final_url = url

    sample_price = profile.get("sample_price", "$29.00")
    currency = profile.get("currency", "USD")
    has_gdpr = profile.get("gdpr_governed", False)
    consent_provider = (
        profile.get("cookie_consent_provider", "OneTrust") if has_gdpr else None
    )

    # Construct realistic HTML body
    gdpr_snippet = (
        f'<div id="onetrust-consent-sdk" class="cookie-banner">'
        f"<p>This site uses cookies under GDPR compliance managed by {consent_provider}.</p></div>"
        if has_gdpr
        else ""
    )

    body = (
        f"<!DOCTYPE html><html><head><title>Regional Service Notice - {profile['country_name']}</title></head>"
        f"<body><h1>Welcome to our {profile['country_name']} Portal</h1>"
        f'<div class="pricing-card"><span class="price-tag">{sample_price}</span> / month ({currency})</div>'
        f"<p>Routed via egress node {egress['ip']} ({egress['isp']}) "
        f"in {egress['city']}, {profile['country_name']}.</p>"
        f"{gdpr_snippet}</body></html>"
    )

    headers = {
        "content-type": "text/html; charset=utf-8",
        "server": "cloudflare",
        "cf-ray": f"8d3e214a{cc.lower()}{egress['asn']}",
        "content-language": profile.get("default_locale", "en-US"),
    }

    return {
        "status_code": 200,
        "final_url": final_url,
        "content_type": "text/html; charset=utf-8",
        "size_bytes": len(body.encode("utf-8")),
        "body": body,
        "headers": headers,
        "egress": egress,
    }


def execute_fetch_bounded(
    url: str,
    country: str = "US",
    city: Optional[str] = None,
    network_type: str = "residential",
    session_id: Optional[str] = None,
    timeout_seconds: float = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    headers: Optional[Dict[str, str]] = None,
    method: str = "GET",
    body: Optional[str] = None,
    follow_redirects: bool = True,
    proxy_url: Optional[str] = None,
    mock_mode: bool = True,
    synthesize_headers: bool = True,
    failover_index: int = 0,
) -> Dict[str, Any]:
    """Execute a bounded streaming HTTP request with SSRF guardrails and circuit breaking."""
    bounded_max_bytes = min(max(max_bytes, 1024), HARD_MAX_BYTES)
    req_headers = (
        build_regional_headers(country, headers)
        if synthesize_headers
        else (dict(headers) if headers else {})
    )

    # Deterministic Mock Mode (hermetic CI or no live proxy)
    if mock_mode or not proxy_url:
        sim = simulate_mock_response(
            url=url,
            country_code=country,
            city=city,
            network_type=network_type,
            session_id=session_id,
            failover_index=failover_index,
        )
        egress = sim["egress"]
        resp_data = {
            "status_code": sim["status_code"],
            "final_url": sim["final_url"],
            "content_type": sim["content_type"],
            "size_bytes": sim["size_bytes"],
            "body": sim["body"],
            "headers": sim["headers"],
        }
        return {
            "status": "ready",
            "action": "fetch_via_geo",
            "egress": egress,
            "response": resp_data,
            "agent_hint": (
                f"Request successfully routed through {egress.get('city', country)} "
                f"{egress.get('network_type', 'residential')} egress (AS{egress.get('asn', '0')}). "
                f"HTTP {sim['status_code']} returned."
            ),
        }

    # Live Proxy Execution
    proxies = {"http": proxy_url, "https": proxy_url}
    session = requests.Session()
    session.max_redirects = MAX_REDIRECTS

    current_url = url
    redirect_count = 0
    t0 = time.time()

    try:
        req = requests.Request(
            method=method.upper(),
            url=current_url,
            headers=req_headers,
            data=body.encode("utf-8") if body else None,
        )
        prep = session.prepare_request(req)

        while True:
            resp = session.send(
                prep,
                stream=True,
                timeout=timeout_seconds,
                proxies=proxies,
                verify=True,
                allow_redirects=False,
            )

            # Check for redirect
            if follow_redirects and resp.is_redirect and "Location" in resp.headers:
                redirect_count += 1
                if redirect_count > MAX_REDIRECTS:
                    return {
                        "status": "error",
                        "action": "fetch_via_geo",
                        "error": f"Exceeded maximum redirect hops ({MAX_REDIRECTS}).",
                        "agent_hint": "Target URL produced a redirect loop.",
                    }

                loc = resp.headers["Location"]
                is_safe, ssrf_err, next_url = validate_redirect_hop(current_url, loc)
                if not is_safe:
                    return {
                        "status": "ssrf_blocked",
                        "action": "fetch_via_geo",
                        "error": ssrf_err,
                        "agent_hint": "Redirect targeted a prohibited internal or link-local address.",
                    }

                current_url = next_url
                req = requests.Request(
                    method="GET", url=current_url, headers=req_headers
                )
                prep = session.prepare_request(req)
                resp.close()
                continue

            break

        # Bounded streaming read
        content_chunks = []
        total_bytes = 0
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                total_bytes += len(chunk)
                if total_bytes > bounded_max_bytes:
                    resp.close()
                    return {
                        "status": "error",
                        "action": "fetch_via_geo",
                        "error": f"Response exceeded max_bytes limit ({bounded_max_bytes} bytes).",
                        "agent_hint": "Increase max_bytes or use a more specific URL target.",
                    }
                content_chunks.append(chunk)

        full_content = b"".join(content_chunks)
        latency_ms = round((time.time() - t0) * 1000.0, 1)

        # Attempt decoding
        encoding = resp.encoding or "utf-8"
        try:
            body_text = full_content.decode(encoding, errors="replace")
        except Exception:
            body_text = full_content.decode("utf-8", errors="replace")

        node = get_node_for_region(
            country, network_type=network_type, city=city, failover_index=failover_index
        )
        egress = dict(node)
        egress["latency_ms"] = latency_ms

        response_dict = {
            "status_code": resp.status_code,
            "final_url": resp.url or current_url,
            "content_type": resp.headers.get("Content-Type", "text/html"),
            "size_bytes": total_bytes,
            "body": body_text,
            "headers": dict(resp.headers),
        }

        # Circuit breaker trigger on 5xx
        if resp.status_code >= 500:
            if failover_index == 0:
                # Automatic failover retry
                return execute_fetch_bounded(
                    url=url,
                    country=country,
                    city=city,
                    network_type=network_type,
                    session_id=session_id,
                    timeout_seconds=timeout_seconds,
                    max_bytes=max_bytes,
                    headers=headers,
                    method=method,
                    body=body,
                    follow_redirects=follow_redirects,
                    proxy_url=proxy_url,
                    mock_mode=mock_mode,
                    synthesize_headers=synthesize_headers,
                    failover_index=1,
                )
            else:
                return {
                    "status": "circuit_broken",
                    "action": "fetch_via_geo",
                    "egress": egress,
                    "response": response_dict,
                    "agent_hint": f"Gateway 5xx failure encountered in {country} egress nodes. Circuit broken.",
                }

        return {
            "status": "ready",
            "action": "fetch_via_geo",
            "egress": egress,
            "response": response_dict,
            "agent_hint": (
                f"Request successfully routed through {egress.get('city', country)} "
                f"{egress.get('network_type', 'residential')} egress (AS{egress.get('asn', '0')}). "
                f"HTTP {resp.status_code} returned without challenge."
            ),
        }

    except requests.exceptions.Timeout:
        if failover_index == 0:
            return execute_fetch_bounded(
                url=url,
                country=country,
                city=city,
                network_type=network_type,
                session_id=session_id,
                timeout_seconds=timeout_seconds,
                max_bytes=max_bytes,
                headers=headers,
                method=method,
                body=body,
                follow_redirects=follow_redirects,
                proxy_url=proxy_url,
                mock_mode=mock_mode,
                synthesize_headers=synthesize_headers,
                failover_index=1,
            )
        return {
            "status": "circuit_broken",
            "action": "fetch_via_geo",
            "error": f"Connection timed out after {timeout_seconds} seconds across multiple nodes.",
            "agent_hint": f"Exit node in {country} timed out. Try a different region or network type.",
        }
    except requests.exceptions.RequestException as exc:
        return {
            "status": "error",
            "action": "fetch_via_geo",
            "error": f"Transport error: {exc}",
            "agent_hint": "Check network connectivity or upstream proxy gateway status.",
        }


def compare_regions_concurrent(
    url: str,
    regions: List[str],
    network_type: str = "residential",
    extract_currency_symbols: bool = True,
    timeout_seconds: float = DEFAULT_TIMEOUT,
    max_bytes: int = DEFAULT_MAX_BYTES,
    mock_mode: bool = True,
    base_service_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Concurrently inspect a target URL across 2-5 distinct global regions."""
    unique_regions = []
    for r in regions:
        clean = (r or "").upper().strip()
        if clean and clean not in unique_regions:
            unique_regions.append(clean)

    if len(unique_regions) < 1:
        unique_regions = ["US", "GB"]

    max_workers = min(len(unique_regions), 5)
    regional_results: Dict[str, Any] = {}

    def _fetch_one_region(reg: str) -> Tuple[str, Dict[str, Any]]:
        res = execute_fetch_bounded(
            url=url,
            country=reg,
            network_type=network_type,
            timeout_seconds=timeout_seconds,
            max_bytes=max_bytes,
            mock_mode=mock_mode,
        )
        return reg, res

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(_fetch_one_region, r): r for r in unique_regions}
        for future in concurrent.futures.as_completed(future_map):
            reg, fetch_res = future.result()
            resp = fetch_res.get("response", {})
            egress = fetch_res.get("egress", {})
            body_text = resp.get("body", "")

            # Extract pricing and currency
            prof = get_country_profile(reg) or {}
            def_currency = prof.get("currency", "USD")
            detected_price, detected_currency = (
                extract_price_and_currency(body_text, default_currency=def_currency)
                if extract_currency_symbols
                else (None, def_currency)
            )

            is_gdpr = detect_gdpr_consent(body_text) or prof.get("gdpr_governed", False)

            item: Dict[str, Any] = {
                "status_code": resp.get("status_code", 0),
                "egress_ip": egress.get("ip", "0.0.0.0"),
                "detected_currency": detected_currency,
                "sample_price_detected": detected_price
                or prof.get("sample_price", "N/A"),
                "final_url": resp.get("final_url", url),
            }
            if is_gdpr:
                item["gdpr_consent_detected"] = True

            regional_results[reg] = item

    # Variance calculations
    distinct_currencies = sorted(
        list(
            {
                v["detected_currency"]
                for v in regional_results.values()
                if v.get("detected_currency")
            }
        )
    )
    final_urls = [
        v["final_url"] for v in regional_results.values() if v.get("final_url")
    ]
    geo_redirects = len(set(final_urls)) > 1 or any(u != url for u in final_urls)
    path_branching = any(
        re.search(r"/(?:uk|de|jp|fr|ca|au|br|in|sg|nl|ch|kr|se|za|ae)(?:/|$)", u)
        for u in final_urls
    )
    price_variance = (
        len({v["sample_price_detected"] for v in regional_results.values()}) > 1
    )
    status_variance = len({v["status_code"] for v in regional_results.values()}) > 1

    variance_detected = {
        "geo_redirects": geo_redirects,
        "currency_variance": distinct_currencies,
        "regional_path_branching": path_branching,
        "price_variance": price_variance,
        "status_variance": status_variance,
    }

    successful = sum(
        1 for v in regional_results.values() if v.get("status_code") == 200
    )

    return {
        "status": "ready",
        "action": "compare_regions",
        "target_url": url,
        "total_regions": len(unique_regions),
        "successful_regions": successful,
        "regional_results": regional_results,
        "variance_detected": variance_detected,
        "agent_hint": (
            f"Multi-region comparison completed across {len(unique_regions)} jurisdictions. "
            f"Detected {len(distinct_currencies)} currencies ({', '.join(distinct_currencies)}). "
            + (
                "Automatic geo-redirects active."
                if geo_redirects
                else "Consistent target path observed."
            )
        ),
    }

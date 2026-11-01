# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Effect implementation for networking/geo_ip_rotator."""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional

import yaml

from skillware.core.base_skill import BaseSkill

try:
    from . import engine, mock_db, providers, sovereignty, ssrf
except (ImportError, ValueError):
    try:
        from skills.networking.geo_ip_rotator import (
            engine,
            mock_db,
            providers,
            sovereignty,
            ssrf,
        )
    except ImportError:
        sys.path.insert(0, os.path.dirname(__file__))
        import engine
        import mock_db
        import providers
        import sovereignty
        import ssrf


class GeoIpRotatorSkill(BaseSkill):
    """Geographic egress proxy routing, multi-region web inspection, and anti-blocking gateway."""

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as handle:
                return yaml.safe_load(handle)
        return {
            "name": "networking/geo_ip_rotator",
            "version": "0.1.0",
            "category": "networking",
        }

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params = params or {}
        action = params.get("action") or "fetch_via_geo"

        # Resolve credentials hermetically via BaseSkill.credential
        service_url = self.credential("PROXY_SERVICE_URL")
        username = self.credential("PROXY_USERNAME")
        password = self.credential("PROXY_PASSWORD")
        provider = (
            params.get("provider") or self.credential("PROXY_PROVIDER") or "generic"
        )

        mock_mode = not bool(service_url)

        if action == "fetch_via_geo":
            return self._handle_fetch_via_geo(
                params, service_url, username, password, provider, mock_mode
            )
        elif action == "compare_regions":
            return self._handle_compare_regions(
                params, service_url, username, password, provider, mock_mode
            )
        elif action == "resolve_egress":
            return self._handle_resolve_egress(
                params, service_url, username, password, provider, mock_mode
            )
        elif action == "get_proxy_context":
            return self._handle_get_proxy_context(
                params, service_url, username, password, provider
            )
        elif action == "list_supported_regions":
            return self._handle_list_supported_regions(params, provider)
        else:
            return {
                "status": "error",
                "action": action,
                "error": (
                    f"Unsupported action '{action}'. Supported actions: "
                    "fetch_via_geo, compare_regions, resolve_egress, "
                    "get_proxy_context, list_supported_regions."
                ),
                "agent_hint": "Verify the 'action' parameter matches one of the 5 supported capabilities.",
            }

    def _handle_fetch_via_geo(
        self,
        params: Dict[str, Any],
        service_url: Optional[str],
        username: Optional[str],
        password: Optional[str],
        provider: str,
        mock_mode: bool,
    ) -> Dict[str, Any]:
        url = (params.get("url") or "").strip()
        if not url:
            return {
                "status": "error",
                "action": "fetch_via_geo",
                "error": "Parameter 'url' is required for fetch_via_geo.",
                "agent_hint": "Supply a target URL (e.g. 'https://service.gov.uk/regional-notice').",
            }

        # Strict Pre-flight SSRF Validation (Constitution Rule 1)
        is_safe, ssrf_reason, _ = ssrf.is_safe_public_url(url)
        if not is_safe:
            return {
                "status": "ssrf_blocked",
                "action": "fetch_via_geo",
                "error": ssrf_reason,
                "agent_hint": "URL failed SSRF validation. Only publicly routable http(s) destinations are permitted.",
            }

        country = (params.get("country") or "US").upper().strip()
        city = params.get("city")
        network_type = params.get("network_type") or "residential"
        session_id = params.get("session_id")
        timeout = float(params.get("timeout_seconds") or 15.0)
        max_bytes = int(params.get("max_bytes") or engine.DEFAULT_MAX_BYTES)
        headers = params.get("headers")
        method = params.get("method") or "GET"
        body = params.get("body")
        follow_redirects = bool(params.get("follow_redirects", True))
        synthesize_headers = bool(params.get("synthesize_regional_headers", True))

        # Sovereignty Fence Enforcement
        fence_policy = params.get("jurisdiction_fence")
        if fence_policy:
            compliant, fence_reason = sovereignty.validate_jurisdiction_fence(
                country, fence_policy
            )
            if not compliant:
                return {
                    "status": "error",
                    "action": "fetch_via_geo",
                    "error": fence_reason,
                    "agent_hint": "Request halted due to sovereign jurisdiction fence violation.",
                }

        # Build proxy URL if service_url is present
        proxy_url = None
        if service_url:
            proxy_url = providers.construct_provider_proxy_url(
                base_service_url=service_url,
                provider=provider,
                country=country,
                city=city,
                network_type=network_type,
                session_id=session_id,
                username=username,
                password=password,
            )

        res = engine.execute_fetch_bounded(
            url=url,
            country=country,
            city=city,
            network_type=network_type,
            session_id=session_id,
            timeout_seconds=timeout,
            max_bytes=max_bytes,
            headers=headers,
            method=method,
            body=body,
            follow_redirects=follow_redirects,
            proxy_url=proxy_url,
            mock_mode=mock_mode,
            synthesize_headers=synthesize_headers,
        )

        # Attach verifiable sovereignty audit receipt
        if res.get("status") == "ready" and "response" in res:
            resp_body = res["response"].get("body", "")
            egress_ip = res.get("egress", {}).get("ip", "0.0.0.0")
            res["sovereignty"] = sovereignty.generate_sovereignty_receipt(
                payload=resp_body,
                country_code=country,
                egress_ip=egress_ip,
                target_url=url,
            )

        return res

    def _handle_compare_regions(
        self,
        params: Dict[str, Any],
        service_url: Optional[str],
        username: Optional[str],
        password: Optional[str],
        provider: str,
        mock_mode: bool,
    ) -> Dict[str, Any]:
        url = (params.get("url") or "").strip()
        if not url:
            return {
                "status": "error",
                "action": "compare_regions",
                "error": "Parameter 'url' is required for compare_regions.",
                "agent_hint": "Supply a target URL (e.g. 'https://example-saas.com/pricing').",
            }

        # Strict Pre-flight SSRF Validation
        is_safe, ssrf_reason, _ = ssrf.is_safe_public_url(url)
        if not is_safe:
            return {
                "status": "ssrf_blocked",
                "action": "compare_regions",
                "error": ssrf_reason,
                "agent_hint": "Target URL failed SSRF validation.",
            }

        regions = params.get("regions") or ["US", "GB", "DE", "JP"]
        if not isinstance(regions, list) or len(regions) < 1:
            regions = ["US", "GB"]

        network_type = params.get("network_type") or "residential"
        extract_curr = bool(params.get("extract_currency_symbols", True))
        timeout = float(params.get("timeout_seconds") or 15.0)
        max_bytes = int(params.get("max_bytes") or engine.DEFAULT_MAX_BYTES)

        return engine.compare_regions_concurrent(
            url=url,
            regions=regions,
            network_type=network_type,
            extract_currency_symbols=extract_curr,
            timeout_seconds=timeout,
            max_bytes=max_bytes,
            mock_mode=mock_mode,
            base_service_url=service_url,
        )

    def _handle_resolve_egress(
        self,
        params: Dict[str, Any],
        service_url: Optional[str],
        username: Optional[str],
        password: Optional[str],
        provider: str,
        mock_mode: bool,
    ) -> Dict[str, Any]:
        country = (params.get("country") or "US").upper().strip()
        city = params.get("city")
        network_type = params.get("network_type") or "residential"

        node = mock_db.get_node_for_region(
            country, network_type=network_type, city=city
        )
        jurisdiction = sovereignty.classify_jurisdiction(country)

        egress_dict = dict(node)
        egress_dict["jurisdiction"] = jurisdiction["jurisdiction_code"]
        egress_dict["data_protection_regime"] = jurisdiction["name"]

        return {
            "status": "ready",
            "action": "resolve_egress",
            "egress": egress_dict,
            "agent_hint": (
                f"Resolved exit node in {node.get('city', country)}, {node.get('country_name', country)}. "
                f"Egress IP: {node['ip']} (AS{node.get('asn', 0)} {node.get('isp', '')}). "
                f"Regime: {jurisdiction['jurisdiction_code']}."
            ),
        }

    def _handle_get_proxy_context(
        self,
        params: Dict[str, Any],
        service_url: Optional[str],
        username: Optional[str],
        password: Optional[str],
        provider: str,
    ) -> Dict[str, Any]:
        country = (params.get("country") or "DE").upper().strip()
        city = params.get("city")
        network_type = params.get("network_type") or "residential"
        session_id = params.get("session_id") or "sess_default"
        fmt = params.get("format") or "requests"

        proxy_url = providers.construct_provider_proxy_url(
            base_service_url=service_url or "http://proxy.mesh.internal:8080",
            provider=provider,
            country=country,
            city=city,
            network_type=network_type,
            session_id=session_id,
            username=username,
            password=password,
        )

        formatted_proxies = providers.format_proxy_context_for_library(
            proxy_url, library_format=fmt
        )

        return {
            "status": "ready",
            "action": "get_proxy_context",
            "country": country,
            "session_id": session_id,
            "format": fmt,
            "proxies": formatted_proxies,
            "confirmed_egress_country": country,
            "expires_in_seconds": 600,
            "agent_hint": (
                f"Pass 'proxies' dict into {fmt} request options or downstream skill execution parameters."
            ),
        }

    def _handle_list_supported_regions(
        self,
        params: Dict[str, Any],
        provider: str,
    ) -> Dict[str, Any]:
        continent = params.get("continent")
        supported = mock_db.list_all_supported_regions(continent=continent)

        return {
            "status": "ready",
            "action": "list_supported_regions",
            "total_countries": len(supported),
            "provider": provider,
            "supported_regions": supported,
            "agent_hint": f"Inventory contains {len(supported)} regional egress destinations.",
        }

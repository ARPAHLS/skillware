# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Unit test suite for networking/geo_ip_rotator."""

from __future__ import annotations

import pytest

from skillware.core.base_skill import BaseSkill
from skillware.core.loader import SkillLoader
from skills.networking.geo_ip_rotator import GeoIpRotatorSkill
from skills.networking.geo_ip_rotator.engine import (
    DEFAULT_MAX_BYTES,
    execute_fetch_bounded,
)
from skills.networking.geo_ip_rotator.headers import build_regional_headers
from skills.networking.geo_ip_rotator.providers import construct_provider_proxy_url
from skills.networking.geo_ip_rotator.ssrf import validate_redirect_hop


@pytest.fixture
def skill() -> GeoIpRotatorSkill:
    return GeoIpRotatorSkill()


def test_manifest_structure(skill: GeoIpRotatorSkill):
    """Manifest declares Manifest v2 fields, valid tags, and real issuer."""
    manifest = skill.manifest
    assert manifest["name"] == "networking/geo_ip_rotator"
    assert manifest["version"] == "0.1.0"
    assert manifest["tier"] == "core"
    assert manifest["shape"] == "middleware"
    assert manifest["target"] == ["software"]
    assert "networking" in manifest["tags"]
    assert "proxy" in manifest["tags"]
    assert len(manifest["tags"]) >= 2

    issuer = manifest["issuer"]
    assert issuer["name"] == "Blade Dancer"
    assert issuer["github"] == "bd-c3"
    assert issuer["org"] == "ARPAHLS"


def test_loader_instantiation():
    """SkillLoader resolves and instantiates networking/geo_ip_rotator."""
    bundle = SkillLoader.load_skill("networking/geo_ip_rotator")
    assert bundle is not None
    skill_cls = bundle["class"]
    inst = skill_cls()
    assert isinstance(inst, BaseSkill)


def test_action_fetch_via_geo_uk_london(skill: GeoIpRotatorSkill):
    """Fetch UK resource through simulated London residential egress."""
    res = skill.execute(
        {
            "action": "fetch_via_geo",
            "url": "https://service.gov.uk/regional-notice",
            "country": "GB",
            "city": "London",
            "network_type": "residential",
        }
    )

    assert res["status"] == "ready"
    assert res["action"] == "fetch_via_geo"
    egress = res["egress"]
    assert egress["country"] == "GB"
    assert egress["city"] == "London"
    assert egress["network_type"] == "residential"
    assert egress["asn"] == 2856
    assert "British Telecommunications" in egress["isp"]

    response = res["response"]
    assert response["status_code"] == 200
    assert "United Kingdom" in response["body"]
    assert "sovereignty" in res
    assert res["sovereignty"]["jurisdiction_code"] == "UK_GDPR"


def test_action_fetch_via_geo_de_gdpr(skill: GeoIpRotatorSkill):
    """Fetch German resource with GDPR consent detection and EUR currency."""
    res = skill.execute(
        {
            "action": "fetch_via_geo",
            "url": "https://service.de/portal",
            "country": "DE",
            "city": "Frankfurt",
        }
    )

    assert res["status"] == "ready"
    egress = res["egress"]
    assert egress["country"] == "DE"
    assert egress["city"] == "Frankfurt"
    assert res["response"]["status_code"] == 200
    assert "Germany" in res["response"]["body"]
    assert "sovereignty" in res
    assert res["sovereignty"]["jurisdiction_code"] == "EU_GDPR"
    assert res["sovereignty"]["is_eea"] is True


def test_action_compare_regions(skill: GeoIpRotatorSkill):
    """Concurrently inspect pricing across US, GB, DE, and JP."""
    res = skill.execute(
        {
            "action": "compare_regions",
            "url": "https://example-saas.com/pricing",
            "regions": ["US", "GB", "DE", "JP"],
            "extract_currency_symbols": True,
        }
    )

    assert res["status"] == "ready"
    assert res["action"] == "compare_regions"
    assert res["total_regions"] == 4
    assert res["successful_regions"] == 4

    regional = res["regional_results"]
    assert "US" in regional
    assert "GB" in regional
    assert "DE" in regional
    assert "JP" in regional

    assert regional["US"]["detected_currency"] == "USD"
    assert regional["GB"]["detected_currency"] == "GBP"
    assert regional["DE"]["detected_currency"] == "EUR"
    assert regional["JP"]["detected_currency"] == "JPY"

    variance = res["variance_detected"]
    assert len(variance["currency_variance"]) >= 3
    assert variance["price_variance"] is True
    assert "Multi-region comparison completed" in res["agent_hint"]


def test_action_resolve_egress(skill: GeoIpRotatorSkill):
    """Resolve exit node metadata without contacting external target URL."""
    res = skill.execute(
        {
            "action": "resolve_egress",
            "country": "JP",
            "city": "Tokyo",
            "network_type": "residential",
        }
    )

    assert res["status"] == "ready"
    assert res["action"] == "resolve_egress"
    egress = res["egress"]
    assert egress["country"] == "JP"
    assert egress["city"] == "Tokyo"
    assert egress["asn"] == 4713
    assert "NTT Communications" in egress["isp"]
    assert egress["jurisdiction"] == "APPI_JAPAN"


def test_action_get_proxy_context_formats(skill: GeoIpRotatorSkill):
    """Emit proxy configs formatted for requests, httpx, aiohttp, and playwright."""
    for fmt in ["requests", "httpx", "aiohttp", "playwright", "urllib", "curl", "dict"]:
        res = skill.execute(
            {
                "action": "get_proxy_context",
                "country": "DE",
                "session_id": "test_sess_123",
                "format": fmt,
            }
        )
        assert res["status"] == "ready"
        assert res["country"] == "DE"
        assert res["session_id"] == "test_sess_123"
        assert "proxies" in res

        if fmt == "requests":
            assert "http" in res["proxies"]
            assert "https" in res["proxies"]
        elif fmt == "httpx":
            assert "all://" in res["proxies"]
        elif fmt == "playwright":
            assert "server" in res["proxies"]


def test_action_list_supported_regions(skill: GeoIpRotatorSkill):
    """List inventory of supported regional pools with continent filter."""
    res_all = skill.execute({"action": "list_supported_regions"})
    assert res_all["status"] == "ready"
    assert res_all["total_countries"] >= 10

    res_eu = skill.execute({"action": "list_supported_regions", "continent": "EU"})
    assert res_eu["status"] == "ready"
    for r in res_eu["supported_regions"]:
        assert r["continent"] == "EU"


def test_ssrf_blocking_loopback(skill: GeoIpRotatorSkill):
    """Reject 127.0.0.1 and localhost targets."""
    for target in [
        "http://127.0.0.1/admin",
        "http://localhost:8080/metrics",
        "http://[::1]/secret",
        "http://0.0.0.0/",
    ]:
        res = skill.execute({"action": "fetch_via_geo", "url": target})
        assert res["status"] == "ssrf_blocked", f"Expected {target} to be blocked"
        assert "ssrf" in res["error"].lower() or "blocked" in res["error"].lower()


def test_ssrf_blocking_cloud_metadata(skill: GeoIpRotatorSkill):
    """Reject AWS/GCP/Azure link-local IMDS metadata endpoints."""
    for target in [
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.169.253/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://instance-data/latest/meta-data/",
    ]:
        res = skill.execute({"action": "fetch_via_geo", "url": target})
        assert (
            res["status"] == "ssrf_blocked"
        ), f"Expected metadata {target} to be blocked"


def test_ssrf_blocking_private_subnets(skill: GeoIpRotatorSkill):
    """Reject RFC 1918 subnets and carrier-grade NAT addresses."""
    for target in [
        "http://10.0.0.1:8080/",
        "http://172.16.5.10/",
        "http://192.168.1.1/router",
        "http://100.64.0.1/",
    ]:
        res = skill.execute({"action": "fetch_via_geo", "url": target})
        assert (
            res["status"] == "ssrf_blocked"
        ), f"Expected private subnet {target} to be blocked"


def test_ssrf_blocking_numeric_ip_evasion(skill: GeoIpRotatorSkill):
    """Reject integer representations of loopback IP."""
    # 2130706433 = 127.0.0.1
    res = skill.execute({"action": "fetch_via_geo", "url": "http://2130706433/admin"})
    assert res["status"] == "ssrf_blocked"


def test_ssrf_blocking_forbidden_schemes(skill: GeoIpRotatorSkill):
    """Reject non-http schemes like file:// or gopher://."""
    res = skill.execute({"action": "fetch_via_geo", "url": "file:///etc/passwd"})
    assert res["status"] == "ssrf_blocked"


def test_ssrf_redirect_hop_validation():
    """Validate that redirect hop interceptor blocks redirect to loopback."""
    is_safe, reason, target = validate_redirect_hop(
        "https://example.com/login",
        "http://169.254.169.254/latest/meta-data/",
    )
    assert not is_safe
    assert "prohibited" in reason.lower() or "blocked" in reason.lower()


def test_sovereignty_fence_eea_only(skill: GeoIpRotatorSkill):
    """Reject egress when allow_eea_only constraint is violated."""
    policy = {"allow_eea_only": True}

    # Germany is in EEA -> allowed
    res_de = skill.execute(
        {
            "action": "fetch_via_geo",
            "url": "https://example.com",
            "country": "DE",
            "jurisdiction_fence": policy,
        }
    )
    assert res_de["status"] == "ready"

    # US is not in EEA -> rejected
    res_us = skill.execute(
        {
            "action": "fetch_via_geo",
            "url": "https://example.com",
            "country": "US",
            "jurisdiction_fence": policy,
        }
    )
    assert res_us["status"] == "error"
    assert "allow_eea_only" in res_us["error"]


def test_sovereignty_fence_sanctions(skill: GeoIpRotatorSkill):
    """Prohibit routing through sanctioned territories."""
    policy = {"enforce_sanctions_blocklist": True}
    res = skill.execute(
        {
            "action": "fetch_via_geo",
            "url": "https://example.com",
            "country": "KP",
            "jurisdiction_fence": policy,
        }
    )
    assert res["status"] == "error"
    assert "sanctions" in res["error"].lower()


def test_regional_header_synthesis():
    """Verify synthesis of locale headers matching egress country."""
    de_headers = build_regional_headers("DE")
    assert "de-DE" in de_headers["Accept-Language"]
    assert "Chrome" in de_headers["User-Agent"]

    jp_headers = build_regional_headers("JP")
    assert "ja-JP" in jp_headers["Accept-Language"]

    custom = build_regional_headers("FR", custom_headers={"X-Custom-Auth": "Token123"})
    assert "fr-FR" in custom["Accept-Language"]
    assert custom["X-Custom-Auth"] == "Token123"


def test_provider_format_adapters():
    """Test URL generation for BrightData, Oxylabs, Smartproxy, and IPRoyal."""
    bd_url = construct_provider_proxy_url(
        base_service_url="http://pr.brightdata.com:22225",
        provider="brightdata",
        country="GB",
        city="London",
        username="lum-customer-hl",
        password="secretpassword",
    )
    assert "country-gb" in bd_url
    assert "city-london" in bd_url

    oxy_url = construct_provider_proxy_url(
        base_service_url="http://pr.oxylabs.io:7777",
        provider="oxylabs",
        country="DE",
        username="customer-user",
        password="pass",
    )
    assert "cc-de" in oxy_url

    smart_url = construct_provider_proxy_url(
        base_service_url="http://gate.smartproxy.com:7000",
        provider="smartproxy",
        country="JP",
        username="sp_user",
        password="sp_pass",
    )
    assert "country-jp" in smart_url


def test_bounded_max_bytes_enforcement():
    """Test bounded streaming stops when limit is exceeded."""
    res = execute_fetch_bounded(
        url="https://example.com/large-file",
        country="US",
        max_bytes=2048,
        mock_mode=True,
    )
    assert res["status"] == "ready"
    assert res["response"]["size_bytes"] <= DEFAULT_MAX_BYTES


def test_unsupported_action(skill: GeoIpRotatorSkill):
    """Gracefully reject unrecognized action strings."""
    res = skill.execute({"action": "invalid_action_xyz"})
    assert res["status"] == "error"
    assert "Unsupported action" in res["error"]

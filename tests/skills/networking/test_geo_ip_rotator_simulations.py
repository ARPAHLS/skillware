# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Simulations, multi-jurisdiction stress tests, and edge case suite for networking/geo_ip_rotator."""

from __future__ import annotations

import hashlib
import pytest
from unittest.mock import MagicMock, patch

from skills.networking.geo_ip_rotator.skill import GeoIpRotatorSkill
from skills.networking.geo_ip_rotator.engine import execute_fetch_bounded


@pytest.fixture
def skill() -> GeoIpRotatorSkill:
    return GeoIpRotatorSkill()


def test_simulation_multi_jurisdiction_compliance_pipeline(skill: GeoIpRotatorSkill):
    """
    Simulation: Enterprise Sovereign Compliance Auditor.
    An autonomous agent audits regional notices across 5 sovereign jurisdictions
    (Germany/EU, United Kingdom, Japan, United States, Singapore) with verifiable
    cryptographic SHA-256 receipts and data protection regime classifications.
    """
    target_regions = [
        ("DE", "EU_GDPR", True),
        ("GB", "UK_GDPR", False),
        ("JP", "APPI_JAPAN", False),
        ("US", "US_STATE_PRIVACY", False),
        ("SG", "PDPA_SINGAPORE", False),
    ]

    audit_log = []

    for country, expected_regime, is_eea in target_regions:
        res = skill.execute(
            {
                "action": "fetch_via_geo",
                "url": "https://service.example.org/statutory-filing",
                "country": country,
                "network_type": "residential",
            }
        )

        assert res["status"] == "ready"
        assert res["egress"]["country"] == country

        # Verify cryptographic audit receipt
        sovereignty = res["sovereignty"]
        assert sovereignty["country"] == country
        assert sovereignty["jurisdiction_code"] == expected_regime
        assert sovereignty["is_eea"] is is_eea

        # Verify payload hash integrity
        body = res["response"]["body"]
        expected_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
        assert sovereignty["payload_sha256"] == expected_hash

        audit_log.append(
            {
                "country": country,
                "regime": expected_regime,
                "receipt": sovereignty["audit_id"],
                "hash": expected_hash[:12],
            }
        )

    assert len(audit_log) == 5


def test_simulation_high_concurrency_market_pricing(skill: GeoIpRotatorSkill):
    """
    Simulation: High-concurrency pricing inspection across 10 global markets.
    Inspects US, GB, DE, JP, FR, CA, AU, BR, IN, and SG concurrently to identify
    global price distribution, currency variance, and regional path redirects.
    """
    ten_regions = ["US", "GB", "DE", "JP", "FR", "CA", "AU", "BR", "IN", "SG"]

    res = skill.execute(
        {
            "action": "compare_regions",
            "url": "https://enterprise-saas.com/pricing",
            "regions": ten_regions,
            "extract_currency_symbols": True,
        }
    )

    assert res["status"] == "ready"
    assert res["total_regions"] == 10
    assert res["successful_regions"] == 10

    regional = res["regional_results"]
    for r in ten_regions:
        assert r in regional
        assert regional[r]["status_code"] == 200
        assert regional[r]["egress_ip"] != "0.0.0.0"

    variance = res["variance_detected"]
    # Currencies should include USD, GBP, EUR, JPY, CAD, AUD, BRL, INR, SGD
    assert len(variance["currency_variance"]) >= 7
    assert variance["price_variance"] is True
    assert variance["geo_redirects"] is True


def test_simulation_ssrf_multi_vector_penetration_test(skill: GeoIpRotatorSkill):
    """
    Simulation: Adversarial penetration test against 15 SSRF bypass vectors.
    Verifies that all internal, metadata, loopback, and encoded vectors are blocked.
    """
    attack_vectors = [
        "http://127.0.0.1:8000/api",
        "http://localhost:5000/debug",
        "http://[::1]/internal",
        "http://0.0.0.0:80/",
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.169.253/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://instance-data/meta-data/",
        "http://2130706433/",  # Decimal for 127.0.0.1
        "http://10.254.1.1/secret",  # RFC 1918 Class A
        "http://172.16.10.100/admin",  # RFC 1918 Class B
        "http://192.168.0.254/config",  # RFC 1918 Class C
        "http://100.64.0.50/gw",  # Carrier Grade NAT
        "http://vault.local/v1/keys",  # Prohibited domain suffix
        "http://db.internal/query",  # Prohibited domain suffix
    ]

    for attack_url in attack_vectors:
        res = skill.execute({"action": "fetch_via_geo", "url": attack_url})
        assert (
            res["status"] == "ssrf_blocked"
        ), f"Attack vector not blocked: {attack_url}"
        assert "ssrf" in res["error"].lower() or "blocked" in res["error"].lower()


def test_simulation_cascading_node_failure_and_circuit_breaking():
    """
    Simulation: Exit node network failure with automatic failover and circuit breaker.
    """
    with patch("requests.Session.send") as mock_send:
        # Simulate gateway 502 bad gateway
        mock_resp = MagicMock()
        mock_resp.status_code = 502
        mock_resp.is_redirect = False
        mock_resp.encoding = "utf-8"
        mock_resp.iter_content.return_value = [b"Gateway Error 502"]
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.url = "https://example.com"
        mock_send.return_value = mock_resp

        res = execute_fetch_bounded(
            url="https://example.com",
            country="GB",
            proxy_url="http://mock-proxy:8080",
            mock_mode=False,
        )

        assert res["status"] == "circuit_broken"
        assert (
            "Circuit broken" in res["agent_hint"] or "circuit_broken" in res["status"]
        )


def test_simulation_sticky_session_continuity(skill: GeoIpRotatorSkill):
    """
    Simulation: Multi-turn agent session retaining consistent egress identity.
    """
    session_id = "checkout_flow_alpha_99"

    # Turn 1: Probing context
    res_ctx = skill.execute(
        {
            "action": "get_proxy_context",
            "country": "DE",
            "session_id": session_id,
            "format": "requests",
        }
    )
    assert res_ctx["status"] == "ready"
    assert res_ctx["session_id"] == session_id
    assert "sesscheckout_flow_alpha_99" in res_ctx["proxies"]["http"]

    # Turn 2: Egress routing
    res_fetch = skill.execute(
        {
            "action": "fetch_via_geo",
            "url": "https://service.de/step1",
            "country": "DE",
            "session_id": session_id,
        }
    )
    assert res_fetch["status"] == "ready"
    ip_turn1 = res_fetch["egress"]["ip"]

    # Turn 3: Follow-up turn with same session
    res_fetch2 = skill.execute(
        {
            "action": "fetch_via_geo",
            "url": "https://service.de/step2",
            "country": "DE",
            "session_id": session_id,
        }
    )
    assert res_fetch2["status"] == "ready"
    assert res_fetch2["egress"]["ip"] == ip_turn1


def test_simulation_cross_skill_downstream_handoff(skill: GeoIpRotatorSkill):
    """
    Simulation: Composing geo_ip_rotator with downstream extraction skill.
    geo_ip_rotator provides authenticated proxy config for Germany, which can
    be passed into requests or downstream skills.
    """
    ctx = skill.execute(
        {
            "action": "get_proxy_context",
            "country": "DE",
            "format": "requests",
        }
    )
    assert ctx["status"] == "ready"
    proxies = ctx["proxies"]
    assert "http" in proxies
    assert "https" in proxies

    # Downstream execution simulation
    simulated_downstream_request = {
        "url": "https://bundesanzeiger.de/search",
        "proxies": proxies,
        "timeout": 15,
    }
    assert simulated_downstream_request["proxies"]["http"].startswith("http://")

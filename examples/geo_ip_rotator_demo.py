#!/usr/bin/env python3
# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""
geo_ip_rotator_demo.py

Offline demonstration of geographic egress proxy routing, multi-region inspection,
strict SSRF containment, and data sovereignty compliance auditing using
networking/geo_ip_rotator.
"""

from __future__ import annotations

import json
from skillware.core.loader import SkillLoader


def main() -> None:
    print("=" * 75)
    print("Skillware: networking/geo_ip_rotator Egress Gateway Demo")
    print("=" * 75)

    # 1. Load skill bundle
    bundle = SkillLoader.load_skill("networking/geo_ip_rotator")
    skill = bundle["class"]()
    print(
        f"Loaded skill: {bundle['manifest']['name']} (v{bundle['manifest']['version']})"
    )
    print(f"Tier: {bundle['manifest']['tier']} | Shape: {bundle['manifest']['shape']}")
    print("-" * 75)

    # 2. Exit Node Resolution
    print("Step 1: Probing Exit Node Metadata (resolve_egress)")
    egress_uk = skill.execute(
        {
            "action": "resolve_egress",
            "country": "GB",
            "city": "London",
            "network_type": "residential",
        }
    )
    uk_node = egress_uk["egress"]
    print(f"   Country: {uk_node['country_name']} ({uk_node['country']})")
    print(f"   Exit IP: {uk_node['ip']} (AS{uk_node['asn']} - {uk_node['isp']})")
    print(
        f"   Jurisdiction: {uk_node['jurisdiction']} ({uk_node['data_protection_regime']})"
    )
    print("-" * 75)

    # 3. Targeted Geo Egress Request
    print("Step 2: Targeted Geo Egress Request (fetch_via_geo)")
    fetch_res = skill.execute(
        {
            "action": "fetch_via_geo",
            "url": "https://service.gov.uk/regional-notice",
            "country": "GB",
            "city": "London",
            "network_type": "residential",
        }
    )
    print(f"   Status: {fetch_res['status']}")
    print(f"   Confirmed Egress IP: {fetch_res['egress']['ip']}")
    print(f"   HTTP Status: {fetch_res['response']['status_code']}")
    print(f"   Payload Bytes: {fetch_res['response']['size_bytes']}")
    sovereign = fetch_res["sovereignty"]
    print(f"   Sovereignty Audit ID: {sovereign['audit_id']}")
    print(f"   Cryptographic SHA-256: {sovereign['payload_sha256'][:24]}...")
    print(f"   Legal Citation: {sovereign['legal_citation']}")
    print("-" * 75)

    # 4. Multi-Region Comparison
    print("Step 3: Multi-Region Market Comparison (compare_regions)")
    comparison = skill.execute(
        {
            "action": "compare_regions",
            "url": "https://example-saas.com/pricing",
            "regions": ["US", "GB", "DE", "JP"],
            "extract_currency_symbols": True,
        }
    )
    print(f"   Total Jurisdictions Inspected: {comparison['total_regions']}")
    for reg, data in comparison["regional_results"].items():
        gdpr_flag = " [GDPR Cookie Banner]" if data.get("gdpr_consent_detected") else ""
        print(
            f"   - [{reg}] Egress: {data['egress_ip']} | Currency: {data['detected_currency']} | "
            f"Sample Price: {data['sample_price_detected']}{gdpr_flag}"
        )

    variance = comparison["variance_detected"]
    print(f"   Currencies Detected: {', '.join(variance['currency_variance'])}")
    print(f"   Price Variance Detected: {variance['price_variance']}")
    print(f"   Path Branching Detected: {variance['regional_path_branching']}")
    print("-" * 75)

    # 5. Downstream Proxy Context Generation
    print("Step 4: Supplying Proxy Context to Downstream Skills (get_proxy_context)")
    ctx = skill.execute(
        {
            "action": "get_proxy_context",
            "country": "DE",
            "session_id": "checkout_session_9410",
            "format": "requests",
        }
    )
    print(f"   Country: {ctx['country']} (Sticky Session: {ctx['session_id']})")
    print(f"   Formatted Requests Proxies: {json.dumps(ctx['proxies'])}")
    print(f"   Agent Hint: {ctx['agent_hint']}")
    print("-" * 75)

    # 6. SSRF Protection Containment
    print("Step 5: SSRF Pre-flight Containment Test")
    ssrf_res = skill.execute(
        {
            "action": "fetch_via_geo",
            "url": "http://169.254.169.254/latest/meta-data/",
        }
    )
    print("   SSRF Target Attempt: http://169.254.169.254/latest/meta-data/")
    print(f"   Outcome Status: {ssrf_res['status']}")
    print(f"   Rejection Reason: {ssrf_res['error']}")
    print("=" * 75)
    print("Geo IP rotator demonstration completed successfully.")


if __name__ == "__main__":
    main()

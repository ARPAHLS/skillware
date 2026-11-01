# Networking Agent Skills

Skills that provide deterministic, enterprise-grade transport, egress routing, and connectivity middleware for host agent loops.

This hub is the documentation landing page for Skillware **networking** agent skills. Runtime bundles stay at `skills/networking/<skill_name>/` with stable registry IDs `networking/<skill_name>` — do not rename those folders for search indexing.

[Skill Library](../README.md) · [Glossary](../../glossary.md) · [Sitemap](../../sitemap.md) · [Agent loops](../../usage/agent_loops.md)

## Catalog

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Geo IP Rotator](geo_ip_rotator.md)** | `networking/geo_ip_rotator` | `0.1.0` (31 Oct 2026) | [@bd-c3](https://github.com/bd-c3) ([@ARPAHLS](https://github.com/ARPAHLS)) | Geographic egress proxy routing, multi-region web inspection, and anti-blocking gateway for AI agents. |

## Roadmap for the Networking Category

1. **`networking/geo_ip_rotator` (This Skill):** Egress proxy rotation, multi-region web inspection, and residential/ISP anti-blocking routing.
2. **`networking/wireguard_tunnel_gate` (Planned):** Ephemeral private WireGuard/Tailscale mesh connectivity for enterprise intranets and VPCs.
3. **`networking/dns_health_resolver` (Planned):** Split-horizon DNS probing, DNSSEC validation, and DoH (DNS-over-HTTPS) resolution.
4. **`networking/tls_cert_inspector` (Planned):** Cipher suite auditing, certificate chain verification, and SSL expiry monitoring.

## Typical host pipelines

- Targeted jurisdiction web retrieval: `networking/geo_ip_rotator` (action `fetch_via_geo`).
- Global pricing and regional compliance comparison: `networking/geo_ip_rotator` (action `compare_regions`).
- Pre-flight egress verification and sticky identity: `networking/geo_ip_rotator` (action `resolve_egress`).
- Supplying authenticated proxy middleware to downstream parsing: `networking/geo_ip_rotator` (action `get_proxy_context`) → `data_engineering/semantic_web_proxy` → `security/prompt_injection_firewall`.

## Load by registry ID

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("networking/geo_ip_rotator")
skill = bundle["class"]()
```

See the [Skill library](../README.md) for every category, and [install extras](../../usage/install_extras.md) for per-skill pip extras.

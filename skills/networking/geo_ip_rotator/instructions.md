# Geo IP Rotator Directive

## When to invoke

Invoke `networking/geo_ip_rotator` when an autonomous agent needs to:
- Retrieve public web resources, regulatory notices, pricing pages, or corporate filings from specific geographical egress locations (e.g., United Kingdom, European Union, Japan, United States).
- Overcome datacenter ASN IP bans (Cloudflare, Akamai, AWS/GCP blocking) by routing egress traffic through residential or mobile network nodes.
- Inspect and compare web content, localized currency, pricing variances, and cookie consent variations across 2 to 5 international jurisdictions simultaneously (`compare_regions`).
- Verify exit node metadata (confirmed egress IP, country, ASN, ISP, latency) prior to initiating long-running web tasks (`resolve_egress`).
- Generate structured, authenticated proxy dictionaries formatted for downstream HTTP clients (`requests`, `httpx`, `aiohttp`, `playwright`, `curl`) used by other skills (`get_proxy_context`).

## When NOT to invoke

- Do not invoke to access internal corporate network resources, private subnets (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16), loopback endpoints (127.0.0.1, localhost), or cloud instance metadata (169.254.169.254); the skill enforces strict pre-flight SSRF blocking and will reject these destinations with `ssrf_blocked`.
- Do not invoke for high-throughput video/binary streaming exceeding 10 MB.
- Do not invoke to circumvent lawful digital rights management or perform denial-of-service testing.

## Operational Parameters

- `action`: Capability selector:
  - `fetch_via_geo`: Single-region targeted request through proxy tunnel.
  - `compare_regions`: Concurrent multi-country web inspection and delta analysis.
  - `resolve_egress`: Exit node probing and verification without contacting external target URL.
  - `get_proxy_context`: Formats ephemeral proxy configuration for downstream libraries.
  - `list_supported_regions`: Catalog of supported regional countries and network pools.
- `url`: Target public http or https destination URL.
- `country`: Two-letter ISO country code (e.g. `GB`, `DE`, `JP`, `US`, `FR`, `CA`, `AU`, `BR`, `IN`, `SG`, `NL`, `CH`, `KR`, `SE`, `ZA`, `AE`).
- `city`: Optional localized city (e.g. `London`, `Tokyo`, `Frankfurt`, `New York`).
- `network_type`: `residential` (best for anti-bot bypass), `datacenter` (low latency), or `mobile`.
- `session_id`: Alphanumeric token for sticky session persistence across multiple turns.
- `regions`: List of 2 to 5 ISO country codes for `compare_regions` (e.g. `["US", "GB", "DE", "JP"]`).
- `format`: Downstream client format in `get_proxy_context` (`requests`, `httpx`, `aiohttp`, `playwright`, `urllib`, `curl`, `dict`).
- `jurisdiction_fence`: Optional enterprise policy dict (`allow_eea_only: true`, `blocked_countries: [...]`, `allowed_countries: [...]`).

## Interpreting Status Envelopes

- `ready`: Request or inspection succeeded. Inspect `egress` for confirmed exit IP/ASN and `response` for HTTP body, status code, and headers.
- `ssrf_blocked`: The requested target or redirect hop resolved to a prohibited internal, private, loopback, or cloud metadata address.
- `circuit_broken`: Target exit nodes encountered persistent timeouts or 5xx gateway failures. Consult `agent_hint` for retry or failover suggestions.
- `error`: Invalid parameters, unsupported actions, or response exceeded payload bounds (`max_bytes`).

## Cross-Skill Chaining

1. Invoke `networking/geo_ip_rotator` with action `get_proxy_context` to acquire a targeted regional proxy dictionary.
2. Forward the returned `proxies` dictionary into `data_engineering/semantic_web_proxy` or `office/web_form_mapper` to conduct region-specific content extraction or document completion.
3. Pass extracted textual payloads into `security/prompt_injection_firewall` before feeding external content into host model context.

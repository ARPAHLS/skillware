# Geo IP Rotator Skill

**ID**: `networking/geo_ip_rotator`  
**Issuer**: [@bd-c3](https://github.com/bd-c3) ([@ARPAHLS](https://github.com/ARPAHLS))  
<!-- skill-doc-meta:begin -->
- **Version**: `0.1.0` — 31 Oct 2026
- **Tier**: `core`
- **Shape**: `middleware`
- **Target**: `software`
- **Tags**: `networking`, `proxy`, `geo_ip`, `egress`, `routing`, `multi_region`, `anti_blocking`, `ssrf_guard`
<!-- skill-doc-meta:end -->
<!-- skill-intent:begin -->
**Solves:** Geographic egress proxy routing, multi-region web inspection, and anti-blocking gateway for AI agents.
**Works with:** Gemini, Claude, OpenAI, DeepSeek, Ollama, and Bedrock-compatible host loops.
**Runtime:** Model agnostic with pluggable commercial/private proxy adapters and deterministic offline mock mode.
<!-- skill-intent:end -->

**Recommended install:** `pip install "skillware[networking_geo_ip_rotator]"`. See [Install extras](../../usage/install_extras.md).  
[Skill Library](../README.md) · [Networking](README.md) · [Glossary](../../glossary.md) · [Testing](../../TESTING.md)

A deterministic, enterprise-grade egress networking skill that manages geographic IP proxy routing for autonomous agents. Overcomes datacenter ASN blacklisting and regional geo-fences by routing agent HTTP requests through specific countries, cities, and residential networks, while enforcing strict SSRF guardrails and data sovereignty compliance.

## Capabilities

* **Targeted Geo Egress (`fetch_via_geo`)**: Route HTTP/HTTPS requests through residential, datacenter, or mobile proxy exit nodes in target ISO countries (`GB`, `DE`, `JP`, `US`, `FR`, etc.) or specific metropolitan cities.
* **Multi-Region Inspection (`compare_regions`)**: Concurrently inspects a single target URL across 2 to 5 distinct global jurisdictions and computes side-by-side variance in status codes, detected currencies, localized prices, path redirects, and cookie consent banners.
* **Exit Node Probing (`resolve_egress`)**: Verifies current exit IP, ASN, ISP, country, and regulatory jurisdiction without contacting external target URLs.
* **Downstream Proxy Provider (`get_proxy_context`)**: Emits structured proxy dictionaries formatted for downstream Python libraries (`requests`, `httpx`, `aiohttp`, `playwright`, `curl`, `urllib`).
* **Supported Regions Inventory (`list_supported_regions`)**: Inspects backend proxy pool capabilities filtered by continent or country.
* **Strict SSRF Guardrails**: Rejects loopback, private RFC 1918 subnets, link-local metadata (169.254.169.254), internal domains, and validates every redirect hop before dialing.
* **Data Sovereignty Auditing**: Classifies governing data protection regimes (EU GDPR, UK GDPR, APPI Japan, CCPA, PDPA) and emits verifiable SHA-256 cryptographic audit receipts.

## Bundle layout

The skill is self-contained in `skills/networking/geo_ip_rotator/`. [Skill anatomy](../../introduction.md#skill-anatomy). Vocabulary: [glossary](../../glossary.md). **Contract** — see Manifest Details above. **Assurance** — `test_skill.py` in the bundle.

### Directive (`instructions.md`)
The directive provides operational guidance for host models to select actions, format regional targeting parameters, configure sticky sessions, and inspect structured envelopes.

### Effect (`skill.py`, `engine.py`, `ssrf.py`, `providers.py`, `sovereignty.py`)
* **SSRF Guard**: Pre-flight DNS resolution and IP address validation.
* **Streaming Engine**: Bounded chunked streaming enforcing a mandatory `max_bytes` ceiling.
* **Provider Adapters**: Format profiles for BrightData, Oxylabs, Smartproxy, IPRoyal, and generic gateways.
* **Deterministic Mock Engine**: Offline simulation of authentic multi-region exit nodes for hermetic CI and testing.

## Integration Guide

### Environment Variables

Configure optional upstream proxy credentials in your `.env` file (or pass hermetically via host secrets). When credentials are omitted, the skill operates in **Deterministic Mock Mode**:

```bash
# Optional upstream proxy endpoint (HTTP, HTTPS, or SOCKS5)
PROXY_SERVICE_URL="http://pr.brightdata.com:22225"
PROXY_USERNAME="lum-customer-hl_12345"
PROXY_PASSWORD="your_proxy_password"
PROXY_PROVIDER="brightdata"
```

## Usage Examples

Guides: [Usage index](../../usage/README.md) · [Agent loops](../../usage/agent_loops.md) · [API keys](../../usage/api_keys.md).

Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].GeoIpRotatorSkill()` also works.

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("networking/geo_ip_rotator")
skill = bundle["class"]()

# Fetch UK notice through London residential egress
result = skill.execute({
    "action": "fetch_via_geo",
    "url": "https://service.gov.uk/regional-notice",
    "country": "GB",
    "city": "London",
    "network_type": "residential",
})
print("Egress IP:", result["egress"]["ip"])
print("HTTP Status:", result["response"]["status_code"])
print("Jurisdiction:", result["sovereignty"]["jurisdiction_code"])

# Concurrently compare pricing across 4 jurisdictions
comparison = skill.execute({
    "action": "compare_regions",
    "url": "https://example-saas.com/pricing",
    "regions": ["US", "GB", "DE", "JP"],
})
print("Detected Currencies:", comparison["variance_detected"]["currency_variance"])
```

### Gemini

```python
import os
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("networking/geo_ip_rotator")
skill = bundle["class"]()
client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
tool_name = SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"])
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Compare how our pricing page renders in the US, Germany, and Japan.",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call and part.function_call.name == tool_name:
        result = skill.execute(dict(part.function_call.args))
        print("Comparison Status:", result["status"])
```

### Claude

```python
import os
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("networking/geo_ip_rotator")
skill = bundle["class"]()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    system=bundle["instructions"],
    tools=tools,
    messages=[{"role": "user", "content": "Fetch the UK statutory filing via London residential egress."}],
)
for block in response.content:
    if block.type == "tool_use" and block.name == bundle["manifest"]["name"]:
        result = skill.execute(block.input)
        print("Egress IP:", result["egress"]["ip"])
```

### OpenAI

```python
import os
import json
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("networking/geo_ip_rotator")
skill = bundle["class"]()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
tools = [SkillLoader.to_openai_tool(bundle)]
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Resolve exit node details for Tokyo residential network."}],
    tools=tools,
)
msg = response.choices[0].message
if msg.tool_calls:
    for call in msg.tool_calls:
        if call.function.name == bundle["manifest"]["name"]:
            args = json.loads(call.function.arguments)
            result = skill.execute(args)
            print("Exit Node:", result["egress"]["ip"])
```

### DeepSeek

```python
import os
import json
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("networking/geo_ip_rotator")
skill = bundle["class"]()
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
tools = [SkillLoader.to_openai_tool(bundle)]
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "Get proxy context for Germany checkout session."}],
    tools=tools,
)
msg = response.choices[0].message
if msg.tool_calls:
    call = msg.tool_calls[0]
    args = json.loads(call.function.arguments)
    result = skill.execute(args)
    print("Proxies:", result["proxies"])
```

### Ollama

```python
import os
import ollama
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("networking/geo_ip_rotator")
skill = bundle["class"]()
tool = SkillLoader.to_ollama_tool(bundle)

response = ollama.chat(
    model="llama3.1",
    messages=[{"role": "user", "content": "List supported countries in Europe."}],
    tools=[tool],
)
if response.message.tool_calls:
    for call in response.message.tool_calls:
        result = skill.execute(call.function.arguments)
        print("Supported Countries:", result["total_countries"])
```

## Constitution & Enterprise Security Rules

1. **Strict SSRF Guardrails (Rule 1)**: Even when operating over proxy tunnels, the skill enforces strict pre-flight URL resolution. All loopback (127.0.0.1, localhost), link-local (169.254.169.254 AWS metadata), RFC 1918 private subnets, and internal service mesh names are rejected immediately with `ssrf_blocked`.
2. **Credential Isolation (Rule 2)**: Proxy authentication credentials are resolved hermetically via `self.credential()` and never logged, echoed in outputs, or stored on disk.
3. **Payload Bounds & Streaming (Rule 3)**: Responses are streamed with a mandatory `max_bytes` ceiling (default 5 MB, hard limit 10 MB) to prevent out-of-memory crashes on bloated binaries.
4. **Fallback & Circuit Breaking (Rule 4)**: If an exit node experiences a timeout or 5xx gateway failure, the skill gracefully retries against an alternative node or emits a structured `circuit_broken` status with an actionable `agent_hint`.
5. **Data Sovereignty Compliance (Rule 5)**: All egress responses are cryptographically hashed and classified by legal data protection regime (GDPR, UK GDPR, APPI) to guarantee sovereign compliance.

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`networking/geo_ip_rotator`](https://github.com/ARPAHLS/skillware/tree/main/skills/networking/geo_ip_rotator)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`bc9f072`](https://github.com/ARPAHLS/skillware/commit/bc9f07237) | feat(networking): add geo_ip_rotator skill and networking category (#437) | 31 Oct 2026 | `0.1.0` | [@bd-c3](https://github.com/bd-c3) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

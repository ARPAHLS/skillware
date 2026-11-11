# RPC Health Probe

**ID**: `monitoring/rpc_health_probe`  
**Issuer**: [@Hendobox](https://github.com/Hendobox) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
- **Version**: `0.1.0` — 8 Nov 2026
- **Tier**: `core`
- **Shape**: `atomic`
- **Target**: `software`
- **Tags**: `web3`, `rpc`, `latency`, `health`, `evm`
<!-- skill-doc-meta:end -->
<!-- skill-intent:begin -->
**Solves:** Probe operator EVM JSON-RPC endpoints for chain ID, latency, and optional sync lag before a host trades.
**Works with:** Gemini, Claude, OpenAI, DeepSeek, Ollama, and Bedrock-compatible host loops.
**Runtime:** Operator RPC URLs via env / `evm.yaml` (`skillware.core.evm_config`). Optional `REFERENCE_RPC_URL_<CHAIN>`.
<!-- skill-intent:end -->

**Recommended install:** `pip install "skillware[monitoring_rpc_health_probe]"`. See [Install extras](../../usage/install_extras.md).

[Skill Library](../README.md) · [Monitoring hub](README.md) · [Glossary](../../glossary.md) · [Testing](../../TESTING.md)

Read-only **EVM JSON-RPC health probe**. Calls `eth_chainId` and `eth_blockNumber`, measures round-trip latency, optionally compares block height to a same-chain reference, and returns `healthy` / `degraded` / `unhealthy` with reasons. **No transactions.** Hosts should gate `defi/evm_tx_handler` on `all_healthy`.

## Capabilities

| Action | Description |
|--------|-------------|
| `probe` | Probe one or more endpoints; return per-row status plus `all_healthy` |

## Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| Chain `rpc_env` from operator EVM config (e.g. `BASE_RPC_URL`) | For configured chains | Target RPC URL when `url` / `url_env` are omitted |
| `REFERENCE_RPC_URL_<CHAIN>` | No | Optional same-chain reference for lag (e.g. `REFERENCE_RPC_URL_BASE`) |

Endpoints may also pass explicit `url` / `reference_url` (useful in tests). See [API keys for skills](../../usage/api_keys.md) and [EVM operator config](../../usage/evm_operator_config.md).

## Agent notes

- **`all_healthy`**: only `true` when every row has `status: healthy`. Fail closed otherwise.
- **Chain identity**: `eth_chainId` must match `resolve_chain(chain).chain_id`. Two endpoints agreeing on height while both on the wrong chain is still unhealthy.
- **Lag honesty**: without a usable same-chain reference, `block_lag` is `null` and `lag_status` is `unchecked` — not zero.
- **Chaining (host-side):** `monitoring/rpc_health_probe` → optional `finance/wallet_screening` / `defi/token_security_scanner` → `defi/evm_tx_handler` preview/execute.

## Bundle layout

The skill lives in `skills/monitoring/rpc_health_probe/`. Roles: [Skill anatomy](../../introduction.md#skill-anatomy). **Contract** — `manifest.yaml`. **Assurance** — `test_skill.py` (mocked HTTP; no live RPC in CI).

### Effect (`skill.py`)

JSON-RPC probe over `requests`, chain config via `skillware.core.evm_config`.

### Directive (`instructions.md`)

When to probe, how to read `all_healthy` / `reasons` / lag fields.

## Usage Examples

Guides: [Usage index](../../usage/README.md) · [Agent loops](../../usage/agent_loops.md) · [API keys](../../usage/api_keys.md).

Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].RpcHealthProbeSkill()` also works.

Sample user message: *Probe Base RPC health before I swap.*

```python
USER_MESSAGE = (
    "Probe the Base RPC endpoint before trading. "
    "Use action probe with endpoints including chain base."
)
```

### Gemini

```python
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/rpc_health_probe")
skill = bundle["class"]()
client = genai.Client()
gemini_tool = SkillLoader.to_gemini_tool(bundle)
response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents=USER_MESSAGE,
    config=types.GenerateContentConfig(
        tools=[gemini_tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call:
        result = skill.execute(dict(part.function_call.args))
        print(result["all_healthy"], result["results"])
```

### Claude

```python
import os

import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/rpc_health_probe")
skill = bundle["class"]()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    system=bundle["instructions"],
    tools=tools,
    messages=[{"role": "user", "content": USER_MESSAGE}],
)
for block in response.content:
    if block.type == "tool_use":
        result = skill.execute(dict(block.input))
        print(result["all_healthy"], result["results"])
```

### OpenAI

```python
import json
import os

from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/rpc_health_probe")
skill = bundle["class"]()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
tools = [SkillLoader.to_openai_tool(bundle)]
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": USER_MESSAGE},
    ],
    tools=tools,
)
msg = response.choices[0].message
if msg.tool_calls:
    args = json.loads(msg.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result["all_healthy"], result["results"])
```

### DeepSeek

```python
import json
import os

from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/rpc_health_probe")
skill = bundle["class"]()
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
tools = [SkillLoader.to_openai_tool(bundle)]
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": USER_MESSAGE},
    ],
    tools=tools,
)
msg = response.choices[0].message
if msg.tool_calls:
    args = json.loads(msg.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result["all_healthy"], result["results"])
```

### Ollama

```python
import json
import urllib.request

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/rpc_health_probe")
skill = bundle["class"]()
# Prompt-mode: ask the local model to emit JSON args, then execute locally.
args = {"action": "probe", "endpoints": [{"chain": "base"}]}
result = skill.execute(args)
print(json.dumps(result, indent=2))
```

## Data Schema

```json
{
  "status": "ok",
  "all_healthy": true,
  "results": [
    {
      "chain": "base",
      "healthy": true,
      "status": "healthy",
      "latency_ms": 142,
      "block": 12345678,
      "chain_id": 8453,
      "expected_chain_id": 8453,
      "block_lag": null,
      "lag_status": "unchecked",
      "reasons": [],
      "endpoint": "https://mainnet.base.org"
    }
  ]
}
```

## Limitations

- EVM JSON-RPC HTTP only (no Solana, no websocket subscriptions).
- No live RPC calls in CI; assurance uses mocked HTTP.
- Reference lag requires a same-chain reference; mismatched reference chain IDs are unusable for lag.
- Not a paid SLA monitor.

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`monitoring/rpc_health_probe`](https://github.com/ARPAHLS/skillware/tree/main/skills/monitoring/rpc_health_probe)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`a705ab0`](https://github.com/ARPAHLS/skillware/commit/a705ab0796c278ffed4694c7e5287f45312df0bc) | feat(monitoring): add rpc_health_probe v0.1 (#459) (#472) | 11 Nov 2026 | `0.1.0` | [@Hendobox](https://github.com/Hendobox) |
<!-- skill-history:end -->

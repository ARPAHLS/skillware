# Token Security Scanner

**ID**: `defi/token_security_scanner`  
**Issuer**: [@Hendobox](https://github.com/Hendobox) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
**Version**: `0.1.0` — 19 Sep 2026
<!-- skill-doc-meta:end -->

**Recommended install:** `pip install "skillware[defi_token_security_scanner]"`. See [Install extras](../usage/install_extras.md).

[Skill Library](README.md) · [Testing](../TESTING.md)

Read-only **ERC-20 / LP token** safety report for agents. Calls the [GoPlus Token Security API](https://docs.gopluslabs.io/), normalizes honeypot/tax/ownership/proxy/mint signals into a stable JSON envelope, and never signs or swaps. Use **before** `defi/evm_tx_handler` preview/execute.

## Capabilities

| Action | Description |
|--------|-------------|
| `scan` | Fetch GoPlus signals for `{chain, contract}` → `risk_tier` + `signals` |
| `supported_chains` | List bundled chain slugs and GoPlus chain IDs |

## Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `GOPLUS_APP_KEY` | No | Optional Bearer token for higher limits / authenticated GoPlus access. Free permissionless Token Security calls work without it. |

No private keys. No wallet address required. See [API keys for skills](../usage/api_keys.md).

## Agent notes

- **`risk_tier`**: `critical` / `high` → refuse trade; `medium` → human confirm; `low` → still not financial advice; `unknown` → missing signals.
- **`null` signals** mean unknown (common for closed-source or proxy contracts) — do not treat as safe.
- **Chain coverage** varies; always surface `warnings`.
- **Chaining (host-side):** `scan` → optional `finance/wallet_screening` on large holders → `defi/evm_tx_handler` preview. Holder screening is out of scope for v0.1.

## Bundle layout

The skill lives in `skills/defi/token_security_scanner/`. Roles: [Skill anatomy](../introduction.md#skill-anatomy). **Contract** — `manifest.yaml`. **Assurance** — `test_skill.py` in the bundle.

### Effect (`skill.py`)

Action dispatch, GoPlus HTTP client, `"0"`/`"1"` flag normalization, deterministic `risk_tier`.

### Directive (`instructions.md`)

When to call `scan`, how to interpret tiers, constitution reminders.

### Corpus

- `data/chains.yaml` — slug → GoPlus `chain_id`
- `fixtures/` — recorded GoPlus JSON for CI (no live network)

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [API keys](../usage/api_keys.md).

Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].ClassName()` also works.

Sample user message: *“Is this Base token safe to buy?”* → `scan` with chain + contract → explain `risk_tier` / `signals`.

### Direct execute

```python
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/token_security_scanner")
skill = bundle["class"]()

report = skill.execute(
    {
        "action": "scan",
        "chain": "base",
        "contract": "0x4ed4e862860bed51a9570b96d89af5e1b0efefed",
    }
)
print(report["risk_tier"], report["signals"])
```

### Gemini

```python
import google.genai as genai
from google.genai import types

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/token_security_scanner")
skill = bundle["class"]()
client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
tool_name = SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"])

response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents=(
        "Scan Base contract 0x4ed4e862860bed51a9570b96d89af5e1b0efefed "
        "for honeypot and tax risk before I buy."
    ),
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call and part.function_call.name == tool_name:
        result = skill.execute(dict(part.function_call.args))
        print(result.get("risk_tier"), result.get("status"))
```

### Claude

```python
import os
import anthropic

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/token_security_scanner")
skill = bundle["class"]()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]

response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    system=bundle["instructions"],
    tools=tools,
    messages=[
        {
            "role": "user",
            "content": (
                "Scan Base contract 0x4ed4e862860bed51a9570b96d89af5e1b0efefed "
                "for token security risk."
            ),
        }
    ],
)
for block in response.content:
    if block.type == "tool_use":
        result = skill.execute(dict(block.input))
        print(result.get("risk_tier"), result.get("status"))
```

### OpenAI

```python
import json
import os
from openai import OpenAI

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/token_security_scanner")
skill = bundle["class"]()
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {
            "role": "user",
            "content": (
                "Scan Base contract 0x4ed4e862860bed51a9570b96d89af5e1b0efefed "
                "for honeypot risk."
            ),
        },
    ],
    tools=[openai_tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result.get("risk_tier"), result.get("status"))
```

### DeepSeek

```python
import json
import os
from openai import OpenAI

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/token_security_scanner")
skill = bundle["class"]()
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {
            "role": "user",
            "content": (
                "Scan Base contract 0x4ed4e862860bed51a9570b96d89af5e1b0efefed "
                "for token security risk."
            ),
        },
    ],
    tools=[deepseek_tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result.get("risk_tier"), result.get("status"))
```

### Ollama (prompt mode)

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("defi/token_security_scanner")
skill = bundle["class"]()

# Prompt-mode hosts parse the model reply into execute args, then:
result = skill.execute(
    {
        "action": "scan",
        "chain": "base",
        "contract": "0x4ed4e862860bed51a9570b96d89af5e1b0efefed",
    }
)
print(result.get("risk_tier"), result.get("status"))
```

### Offline tests

```bash
pytest skills/defi/token_security_scanner/test_skill.py -q
```

## Limitations (v0.1)

- EVM Token Security only (no Solana / NFT collections / MEV simulation).
- Single provider (GoPlus); no DexScreener market chrome.
- Does not replace a professional audit or live Chainalysis/TRM feeds.

<!-- skill-history:begin -->
## Skill history

| Version | Date | Notes |
| :--- | :--- | :--- |
| `0.1.0` | 19 Sep 2026 | Initial release — GoPlus `scan` / `supported_chains`, fixture-backed tests (#365). |
<!-- skill-history:end -->

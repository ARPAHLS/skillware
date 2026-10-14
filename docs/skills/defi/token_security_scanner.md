# Token Security Scanner

**ID**: `defi/token_security_scanner`  
**Issuer**: [@Hendobox](https://github.com/Hendobox) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
**Version**: `0.2.0`
<!-- skill-doc-meta:end -->
<!-- skill-intent:begin -->
**Solves:** Vet an ERC-20 / LP contract for honeypot, tax, ownership, and related risk before an agent trades.
**Works with:** Gemini, Claude, OpenAI, DeepSeek, Ollama, and Bedrock-compatible host loops.
**Runtime:** Optional `GOPLUS_APP_KEY`; chain slugs from shared EVM operator config (no RPC required for GoPlus scan).
<!-- skill-intent:end -->

**Recommended install:** `pip install "skillware[defi_token_security_scanner]"`. See [Install extras](../../usage/install_extras.md).

[Skill Library](../README.md) · [DeFi hub](README.md) · [Glossary](../../glossary.md) · [Testing](../../TESTING.md)

Read-only **ERC-20 / LP token** safety report for agents. Calls the [GoPlus Token Security API](https://docs.gopluslabs.io/), normalizes honeypot/tax/ownership/proxy/mint signals into a stable JSON envelope, and never signs or swaps. Use **before** `defi/evm_tx_handler` preview/execute.

## Capabilities

| Action | Description |
|--------|-------------|
| `scan` | Fetch GoPlus signals for `{chain, contract}` or `{chain, token}` → `risk_tier`, `policy_action`, `signals` |
| `scan_batch` | Up to 5 sequential scans plus `worst_risk_tier` |
| `supported_chains` | Enabled chain slugs, with `goplus_supported` true or false |

## Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `GOPLUS_APP_KEY` | No | Optional Bearer token for higher limits / authenticated GoPlus access. Free permissionless Token Security calls work without it. |
| `TOKEN_SCAN_POLICY_PATH` | No | Operator policy YAML. Otherwise `~/.config/skillware/token_scan_policy.yaml`, then the bundled `enterprise_default` profile. |

No private keys. No wallet address required. See [API keys for skills](../../usage/api_keys.md).

## Agent notes

- **`policy_action`**: `block` refuses the trade, `flag` needs a human, `allow` may continue. Default profile blocks `critical`, `high`, and `unknown`.
- **`risk_tier`**: still returned. Hosts should gate on `policy_action` so an operator file can change thresholds without a new host script.
- **`null` signals** mean unknown (common for closed-source or proxy contracts) — do not treat as safe.
- **Chain coverage** varies; always surface `warnings`.
- **Chaining (host-side):** suggested pre-trade path — optional `security/drainer_pattern_guard` (when shipped) → `scan` → `defi/evm_reader` → `defi/evm_tx_handler` preview/execute. Optional holder EOAs → `finance/wallet_screening`. Tokens stay in operator `evm.tokens`, not the address book.
- **Chains:** enabled slugs from operator EVM config (`skillware evm`); add further GoPlus-supported networks via `skillware evm chain add` (see [EVM operator config](../../usage/evm_operator_config.md)).

## Bundle layout

The skill lives in `skills/defi/token_security_scanner/`. Roles: [Skill anatomy](../../introduction.md#skill-anatomy). **Contract** — `manifest.yaml`. **Assurance** — `test_skill.py` in the bundle.

### Effect (`skill.py`)

Action dispatch, GoPlus HTTP client, `"0"`/`"1"` flag normalization, deterministic `risk_tier`.

### Directive (`instructions.md`)

When to call `scan`, how to interpret tiers, constitution reminders.

### Corpus

- Chain slugs / `chain_id` from shared [`skillware.core.evm_config`](../../usage/evm_operator_config.md) (no per-bundle `chains.yaml`)
- `data/default_policy.yaml` — `enterprise_default` thresholds. Operators override with `token_scan_policy.yaml`
- `data/goplus_chain_ids.yaml` — chain IDs GoPlus Token Security accepts
- `fixtures/` — recorded GoPlus JSON for CI (no live network)

## Usage Examples

Guides: [Usage index](../../usage/README.md) · [Agent loops](../../usage/agent_loops.md) · [API keys](../../usage/api_keys.md).

Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].ClassName()` also works.

Sample user message: *“Is this Base token safe to buy?”* → `scan` with chain + contract → explain `risk_tier` / `signals`.

### Host-side pre-trade gate (chain into `evm_tx_handler`)

Skills stay atomic — the **host** owns `scan → gate → quote/preview`. Fail closed when
`status` is not `ok` or `policy_action` is `block`. `flag` needs a person. Do not
treat a missing honeypot signal as “low risk.”

```python
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
scanner = SkillLoader.load_skill("defi/token_security_scanner")["class"]()
evm = SkillLoader.load_skill("defi/evm_tx_handler")["class"]()

token_contract = "0x4ed4e862860bed51a9570b96d89af5e1b0efefed"
report = scanner.execute(
    {"action": "scan", "chain": "base", "contract": token_contract}
)

if report.get("status") != "ok" or report.get("policy_action") == "block":
    print(
        "Blocked pre-trade:",
        report.get("risk_tier"),
        report.get("contract_errors"),
        report.get("warnings"),
    )
elif report.get("policy_action") == "flag":
    print("Needs confirmation:", report.get("risk_tier"), report.get("contract_errors"))
else:
    # Host proceeds only after a clean scan — quote/preview, then HITL confirm.
    preview = evm.execute(
        {
            "action": "preview",
            "intent": {
                "side": "buy",
                "chain": "base",
                "target_asset": "degen",
                "spend_asset": "eth",
                "amount": 0.05,
                "amount_kind": "spend_in",
            },
        }
    )
    print(preview.get("status"), preview.get("preview"))
```

Optional: after a clean scan, screen large holder EOAs with `finance/wallet_screening`
before preview. Do not bind `confirmed: true` across a changed chain/token/amount —
re-preview if the intent drifts.

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

## Limitations (v0.2)

- EVM Token Security only (no Solana / NFT collections / MEV simulation).
- Single provider (GoPlus); no second-source quorum.
- `scan_batch` is sequential and capped at 5. One retry on HTTP 429 or 5xx, then fail closed.
- A chain can be enabled in EVM config and still be `goplus_supported: false`.
- Does not replace a professional audit or live Chainalysis/TRM feeds.

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`defi/token_security_scanner`](https://github.com/ARPAHLS/skillware/tree/main/skills/defi/token_security_scanner)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`e14bcab`](https://github.com/ARPAHLS/skillware/commit/e14bcab69b2218e0a78e9b81ba363e3e5afca9b9) | feat(token_security_scanner): add operator policy and policy_action | 14 Oct 2026 | `0.2.0` | [@Hendobox](https://github.com/Hendobox) |
| [`e90bbce`](https://github.com/ARPAHLS/skillware/commit/e90bbceadb360772cbe1f6cff16a9ec96c90a225) | feat(defi): token_security_scanner v0.1 (GoPlus read-only) (#368) | 26 Sep 2026 | `0.1.0` | [@Hendobox](https://github.com/Hendobox) |
<!-- skill-history:end -->

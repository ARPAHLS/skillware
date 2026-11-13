# Ephemeral Wallet

**ID**: `finance/ephemeral_wallet`  
**Issuer**: [@Hendobox](https://github.com/Hendobox) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
- **Version**: `0.1.0` — 11 Nov 2026
- **Tier**: `core`
- **Shape**: `workflow`
- **Target**: `software`
- **Tags**: `payments`, `x402`, `agent-wallet`, `web3`, `finance`
<!-- skill-doc-meta:end -->
<!-- skill-intent:begin -->
**Solves:** Spend-capped, short-lived agent payment sessions for x402-shaped HTTP micropayments from a dedicated agent wallet (not card PANs).
**Works with:** Gemini, Claude, OpenAI, DeepSeek, Ollama, and Bedrock-compatible host loops.
**Runtime:** Mock settlement in v0.1 (no live chain in CI). Optional CDP env names reserved for live settle (PR2). Optional `EPHEMERAL_WALLET_SESSION_DIR` for JSONL durability.
<!-- skill-intent:end -->

**Recommended install:** `pip install "skillware[finance_ephemeral_wallet]"`. See [Install extras](../../usage/install_extras.md).

[Skill Library](../README.md) · [Finance hub](README.md) · [Glossary](../../glossary.md) · [Testing](../../TESTING.md)

Thin **agent payment session** skill: `create_session` → `status` / `pay` / `revoke`. v0.1 uses a **mock x402 provider** so hosts can wire the action loop offline. Live CDP + x402 settle is PR2. Cap / TTL / revoke are **soft in-process policy** until funded-to-cap enforcement.

## Capabilities

| Action | Description |
|--------|-------------|
| `create_session` | Open a session with soft `spend_cap_usd` + `ttl_seconds`; returns `session_id` |
| `status` | Remaining soft budget, expiry, revoke flag, last payment refs |
| `pay` | Debit soft counter and return mock receipt refs for a URL |
| `revoke` | Expire the session; further `pay` fails closed |

## Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `CDP_API_KEY_ID` | For live (PR2) | CDP auth |
| `CDP_API_KEY_SECRET` | For live (PR2) | CDP auth |
| `CDP_WALLET_SECRET` | For live (PR2) | Dedicated agent wallet secret |
| `EPHEMERAL_WALLET_NETWORK` | No | Default `base-sepolia` |
| `EPHEMERAL_WALLET_FACILITATOR_URL` | No | Reserved for live facilitator |
| `EPHEMERAL_WALLET_SESSION_DIR` | No | Append-only `sessions.jsonl` / `payments.jsonl` (fail closed if unwritable) |
| `EPHEMERAL_WALLET_MOCK` | No | Default `1` (mock). `0` requests live and hits `missing_config` / PR1 refuse |

Non-secret defaults: `config.yaml.example` (`default_spend_cap_usd`, `default_ttl_seconds`, `network`). Secrets never in YAML or tool args. See [API keys for skills](../../usage/api_keys.md).

## Agent notes

- Pass **`session_id`** from `create_session` on every later call (host-held across turns).
- **`status` other than `ready` / `confirmed`**: halt automated spend.
- **`remaining_usd`**: display counter — not a hard on-chain bound in v0.1.
- **Never** echo private keys, CDP secrets, or PANs/CVVs.
- Boundary: x402-shaped session pay only — swaps/transfers → `defi/evm_tx_handler`.
- Why not Issuing/PANs in v1: secret risk + KYC; x402 + CDP is the locked open path (#41 / #272).

## Bundle layout

The skill lives in `skills/finance/ephemeral_wallet/`. Roles: [Skill anatomy](../../introduction.md#skill-anatomy). **Contract** — `manifest.yaml`. **Assurance** — `test_skill.py` (mocked provider; no live Base / facilitator in CI).

### Effect (`skill.py`)

Session store + `MockX402Provider` behind a small provider boundary.

### Directive (`instructions.md`)

When to open a session, how to gate on status codes, soft-policy honesty.

## Usage Examples

Guides: [Usage index](../../usage/README.md) · [Agent loops](../../usage/agent_loops.md) · [API keys](../../usage/api_keys.md).

Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].EphemeralWalletSkill()` also works.

Sample user message: *Open a $5 Base Sepolia payment session for two hours, then pay a URL.*

```python
USER_MESSAGE = (
    "Create an ephemeral wallet session with spend_cap_usd 5 and ttl_seconds 7200, "
    "then pay https://api.example.com/v1/resource for 0.5 USD."
)
```

### Gemini

```python
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/ephemeral_wallet")
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
        print(result["status"], result.get("session_id"), result.get("remaining_usd"))
```

### Claude

```python
import os

import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/ephemeral_wallet")
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
        print(result["status"], result.get("session_id"), result.get("remaining_usd"))
```

### OpenAI

```python
import json
import os

from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/ephemeral_wallet")
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
    print(result["status"], result.get("session_id"), result.get("remaining_usd"))
```

### DeepSeek

```python
import json
import os

from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/ephemeral_wallet")
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
    print(result["status"], result.get("session_id"), result.get("remaining_usd"))
```

### Ollama

```python
import json

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/ephemeral_wallet")
skill = bundle["class"]()
# Prompt-mode: ask the local model to emit JSON args, then execute locally.
created = skill.execute(
    {"action": "create_session", "spend_cap_usd": 5.0, "ttl_seconds": 7200}
)
paid = skill.execute(
    {
        "action": "pay",
        "session_id": created["session_id"],
        "url": "https://api.example.com/v1/resource",
        "amount_usd": 0.5,
    }
)
print(json.dumps({"created": created, "paid": paid}, indent=2))
```

## Data Schema

**`create_session`**

```json
{
  "status": "ready",
  "session_id": "ews_…",
  "spend_cap_usd": 5.0,
  "remaining_usd": 5.0,
  "expires_at": "2026-11-11T16:00:00Z",
  "network": "base-sepolia",
  "wallet_address": "0x1111111111111111111111111111111111111111",
  "settlement": "mock",
  "agent_hint": "Pass session_id on later status/pay/revoke. No secrets in this payload."
}
```

**`pay` (mock)**

```json
{
  "status": "confirmed",
  "session_id": "ews_…",
  "remaining_usd": 4.5,
  "payment": {
    "url": "https://api.example.com/v1/resource",
    "amount_usd": 0.5,
    "network": "base-sepolia",
    "tx_ref": "mock_tx_…",
    "receipt_ref": "mock_rcpt_…"
  },
  "settlement": "mock"
}
```

Errors use structured `status` (`missing_config` | `expired` | `revoked` | `over_cap` | `error`) plus `agent_hint`. Never keys / PANs.

## Limitations

- v0.1 settlement is **mocked** — no live Base / facilitator / CDP in CI.
- Cap / TTL / revoke are soft in-process policy until funded-to-cap (PR2).
- Session memory is process-local unless `EPHEMERAL_WALLET_SESSION_DIR` is set.
- Not Stripe Issuing / virtual-card PANs (deferred adapter).
- Not a general EVM transfer/swap skill.

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`finance/ephemeral_wallet`](https://github.com/ARPAHLS/skillware/tree/main/skills/finance/ephemeral_wallet)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| `TBD` | feat(finance): add ephemeral_wallet v0.1 skeleton (#41 PR1) | 11 Nov 2026 | `0.1.0` | [@Hendobox](https://github.com/Hendobox) |
<!-- skill-history:end -->

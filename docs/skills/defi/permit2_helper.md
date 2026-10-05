# Permit2 Helper

**ID**: `defi/permit2_helper`  
**Issuer**: [@Achalnawal2745](https://github.com/Achalnawal2745) ([@ARPAHLS](https://github.com/ARPAHLS))  
<!-- skill-doc-meta:begin -->
**Version**: `0.1.0`
<!-- skill-doc-meta:end -->
<!-- skill-intent:begin -->
**Solves:** Build, validate, and hash EIP-712 typed data payloads for Uniswap Permit2 allowances and signature transfers without mangling domains, nonces, or spenders.  
**Works with:** Gemini, Claude, OpenAI, DeepSeek, Ollama, and Bedrock-compatible host loops.  
**Runtime:** Model agnostic; RPC URLs resolved via shared EVM operator config (operator `evm.yaml` + `.env`) for optional on-chain nonce reads.  
<!-- skill-intent:end -->

**Recommended install:** `pip install "skillware[defi_permit2_helper]"`. See [Install extras](../../usage/install_extras.md).

[Skill Library](../README.md) · [DeFi hub](README.md) · [Glossary](../../glossary.md) · [Testing](../../TESTING.md)

Constructs and verifies EIP-712 typed data payloads for Uniswap Permit2 (`0x000000000022D473030F116dDEE9F6B43aC78BA3`). Does not hold private keys or sign transactions in v0.1; returns clean structured data and 32-byte signing digests ready for wallets or host signing agents.

## Capabilities

| Action | Description | Key Inputs |
|--------|-------------|------------|
| `build_permit2` | Build standard EIP-712 PermitSingle or PermitTransferFrom typed data with signing digest | `chain`, `token`, `spender`, `amount`, `nonce`, `deadline` |
| `validate_typed_data` | Validate an EIP-712 typed data payload for domain integrity, expiration, and expected parameters | `typed_data`, `expected_chain`, `expected_spender` |
| `hash_typed_data` | Compute the 32-byte EIP-712 digest (hash) of any Permit2 typed data mapping | `typed_data` |
| `read_nonce` | Read current on-chain Permit2 allowance, expiration, and nonce via RPC | `chain`, `owner`, `token`, `spender` |

## Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `ETHEREUM_RPC_URL` | No | JSON-RPC URL for Ethereum mainnet nonce reads. |
| `BASE_RPC_URL` | No | JSON-RPC URL for Base nonce reads. |
| `ARBITRUM_RPC_URL` | No | JSON-RPC URL for Arbitrum One nonce reads. |

All RPC URLs are dynamically resolved through `skillware.core.evm_config`. Offline payload building, validation, and hashing require no network connection or RPC endpoints.

## Agent notes

- **Fail-Closed on Unlimited Approvals:** Permits for `type(uint160).max` or `type(uint256).max` fail closed by default to protect user funds from infinite drain risk. The host must pass `allow_unlimited: true` to permit maximum allowances.
- **Spender Verification:** In `validate_typed_data`, pass `expected_spender` to ensure untrusted payloads cannot redirect allowances to unauthorized addresses.
- **Router Aliases:** The `spender` argument supports router aliases like `router_v2` which automatically resolve to the configured router address in `evm.yaml`.
- **Chaining (host-side):** Pairs upstream with [`defi/evm_reader`](evm_reader.md) (check current balances and allowances) and [`defi/evm_tx_handler`](evm_tx_handler.md) (execute swaps after Permit2 signatures are acquired).

## Bundle layout

The skill lives in `skills/defi/permit2_helper/`. Roles: [Skill anatomy](../../introduction.md#skill-anatomy). **Contract** — `manifest.yaml`. **Assurance** — `test_skill.py`.

### Effect (`skill.py`)

Handles action dispatch, address normalization, parameter verification, and EIP-712 encoding.

### Schemas (`constants.py`)

Canonical Permit2 contract address, EIP-712 type dictionaries, known router labels, and bit limits.

## Usage Examples

### Gemini

```python
import os
from google import genai
from google.genai import types

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/permit2_helper")
skill = bundle["class"]()
client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
tool_name = SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"])

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Build a Permit2 payload for 100 USDC to router_v2 on ethereum.",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call and part.function_call.name == tool_name:
        result = skill.execute(**dict(part.function_call.args))
        print(result.get("digest"), result.get("status"))
```

### Claude

```python
import os
import anthropic

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/permit2_helper")
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
            "content": "Build a Permit2 payload for 100 USDC to router_v2 on ethereum.",
        }
    ],
)
for block in response.content:
    if block.type == "tool_use":
        result = skill.execute(**dict(block.input))
        print(result.get("digest"), result.get("status"))
```

### OpenAI

```python
import json
import os
from openai import OpenAI

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/permit2_helper")
skill = bundle["class"]()
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {
            "role": "user",
            "content": "Build a Permit2 payload for 100 USDC to router_v2 on ethereum.",
        },
    ],
    tools=[openai_tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(**args)
    print(result.get("digest"), result.get("status"))
```

### DeepSeek

```python
import json
import os
from openai import OpenAI

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/permit2_helper")
skill = bundle["class"]()
deepseek_tool = SkillLoader.to_openai_tool(bundle)
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
            "content": "Build a Permit2 payload for 100 USDC to router_v2 on ethereum.",
        },
    ],
    tools=[deepseek_tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(**args)
    print(result.get("digest"), result.get("status"))
```

### Ollama

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("defi/permit2_helper")
skill = bundle["class"]()

# Prompt-mode hosts parse the model reply into execute args, then:
result = skill.execute(
    action="build_permit2",
    chain="ethereum",
    token="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
    spender="0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45",
    amount=100000000,
    nonce=0,
    deadline=1735689600,
)
print(result.get("digest"), result.get("status"))
```

## Limitations (v0.1)

- Does not sign or broadcast on-chain transactions directly (payloads are signed by the host wallet).
- Legacy ERC-2612 permits with custom contract domains are out of scope (targeted for v0.2).

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`defi/permit2_helper`](https://github.com/ARPAHLS/skillware/tree/main/skills/defi/permit2_helper)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| `HEAD` | feat(defi): add permit2_helper skill for EIP-712 Permit2 typed data (#400) | 05 Oct 2026 | `0.1.0` | [@Achalnawal2745](https://github.com/Achalnawal2745) |
<!-- skill-history:end -->

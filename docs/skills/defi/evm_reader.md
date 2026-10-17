# EVM Chain Reader

**ID**: `defi/evm_reader`  
**Issuer**: [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))  
<!-- skill-doc-meta:begin -->
**Version**: `0.1.0`
<!-- skill-doc-meta:end -->
<!-- skill-intent:begin -->
**Solves:** Read-only EVM chain queries: token metadata, balances, allowances, allowlisted contract view calls, Multicall3 batch reads, and address book contact resolution without signing.  
**Works with:** Gemini, Claude, OpenAI, DeepSeek, Ollama, and Bedrock-compatible host loops.  
**Runtime:** RPC URLs resolved via shared EVM operator config (operator `evm.yaml` + `.env`); central address book (`public_0x`).  
<!-- skill-intent:end -->

**Recommended install:** `pip install "skillware[defi_evm_reader]"`. See [Install extras](../../usage/install_extras.md).

[Skill Library](../README.md) · [DeFi hub](README.md) · [Glossary](../../glossary.md) · [Testing](../../TESTING.md)

Read-only EVM state plane for agent loops. Queries ERC-20 and ERC-721 token balances, allowances, metadata, arbitrary allowlisted view calls, and Multicall3 batches. Pairs with `defi/evm_tx_handler` for read-only checks and never requires or accepts private keys.

## Capabilities

| Action | Description | Key Inputs |
|--------|-------------|------------|
| `erc20_metadata` | Fetch ERC-20 token name, symbol, decimals, and total_supply | `chain`, `contract` (or `token`) |
| `erc20_balance` | Query formatted and raw ERC-20 token balance | `chain`, `contract`, `holder` |
| `erc20_allowance` | Query spender allowance granted by token owner | `chain`, `contract`, `owner`, `spender` |
| `erc721_metadata` | Fetch NFT collection name, symbol, and total supply | `chain`, `contract` |
| `erc721_balance` | Query count of NFTs owned by holder | `chain`, `contract`, `holder` |
| `erc721_owner_of` | Query owner of specific NFT token ID | `chain`, `contract`, `token_id` |
| `call_view` | Execute allowlisted view function (ERC-20/721, Uni V2 reserves, Chainlink feeds) | `chain`, `contract`, `method`, `abi_preset`, `args` |
| `multicall` | Batch execute view calls via Multicall3 (`tryAggregate`) | `chain`, `calls` |
| `resolve_holder` | Resolve contact ID, alias, or display name to `public_0x` via address book | `holder` |

## Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `ETHEREUM_RPC_URL` | No | JSON-RPC URL for Ethereum mainnet queries. |
| `BASE_RPC_URL` | No | JSON-RPC URL for Base queries. |
| `ARBITRUM_RPC_URL` | No | JSON-RPC URL for Arbitrum One queries. |
| `MEGAETH_RPC_URL` | No | JSON-RPC URL for MegaETH queries. |
| `ARC_RPC_URL` | No | JSON-RPC URL for Circle Arc queries. |

All RPC URLs are dynamically resolved through `skillware.core.evm_config`. Operators can configure custom networks and endpoints in `evm.yaml`. No private keys or wallet credentials are ever required.

## Agent notes

- **Read-Only Guarantee:** This skill has no signing capability and requires no private keys.
- **Address Book Integration:** When `holder`, `owner`, or `spender` is provided as a human name or alias (e.g. `alice`), the skill queries `addressbook.yaml`. If multiple contacts match, it safely returns `status: "needs_input"` with candidate disambiguation info.
- **EIP-55 Checksumming:** All EVM addresses in outputs are validated and normalized to EIP-55 checksum format.
- **Token Shortcuts:** Configured tokens in operator `evm.yaml` (such as `usdc` on Ethereum or `degen` on Base) can be passed directly as the `contract` or `token` argument.
- **Rate-Limited Multicall:** Multicall batches are capped at 50 calls per invocation to protect node throughput.
- **Chaining (host-side):** Upstream to [`defi/evm_tx_handler`](evm_tx_handler.md) (balance/allowance checks before trade execution) or downstream from [`finance/wallet_screening`](../finance/wallet_screening.md) (read on-chain balances of screened addresses) and [`defi/token_security_scanner`](token_security_scanner.md) (verify token metadata and decimals after security checks). See [DeFi hub](README.md#typical-host-pipelines) and [Skill chaining](../../usage/skill_chaining.md).

## Bundle layout

The skill lives in `skills/defi/evm_reader/`. Roles: [Skill anatomy](../../introduction.md#skill-anatomy). **Contract** — `manifest.yaml`. **Assurance** — `test_skill.py`.

### Effect (`skill.py`)

Handles action dispatch, Web3 RPC calls, address normalization, address book resolution, and Multicall3 decoding.

### Presets (`abis.py`)

Bundled standard ABIs for ERC-20, ERC-721, ERC-1155, ERC-4626, Uniswap V2 pairs, Chainlink feeds, Ownable, AccessControl, and Multicall3.

## Usage Examples

See [examples/README.md](../../../examples/README.md) and [`examples/evm_reader_demo.py`](../../../examples/evm_reader_demo.py) for a runnable script demonstrating offline mock reads and live RPC queries.

### Gemini

```python
import os
from google import genai
from google.genai import types

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/evm_reader")
skill = bundle["class"]()
client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
tool_name = SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"])

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Check USDC balance for alice on ethereum.",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call and part.function_call.name == tool_name:
        result = skill.execute(**dict(part.function_call.args))
        print(result.get("balance"), result.get("status"))
```

### Claude

```python
import os
import anthropic

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/evm_reader")
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
            "content": "Check USDC balance for alice on ethereum.",
        }
    ],
)
for block in response.content:
    if block.type == "tool_use":
        result = skill.execute(**dict(block.input))
        print(result.get("balance"), result.get("status"))
```

### OpenAI

```python
import json
import os
from openai import OpenAI

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/evm_reader")
skill = bundle["class"]()
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {
            "role": "user",
            "content": "Check USDC balance for alice on ethereum.",
        },
    ],
    tools=[openai_tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(**args)
    print(result.get("balance"), result.get("status"))
```

### DeepSeek

```python
import json
import os
from openai import OpenAI

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/evm_reader")
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
            "content": "Check USDC balance for alice on ethereum.",
        },
    ],
    tools=[deepseek_tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(**args)
    print(result.get("balance"), result.get("status"))
```

### Ollama

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("defi/evm_reader")
skill = bundle["class"]()

# Prompt-mode hosts parse the model reply into execute args, then:
result = skill.execute(
    action="erc20_balance",
    chain="ethereum",
    contract="usdc",
    holder="alice",
)
print(result.get("balance"), result.get("status"))
```

## Limitations (v0.1)

- Read-only queries only (no transaction broadcasting or wallet signing).
- Does not index historical logs; queries current state via `eth_call`.
- Custom ABI uploads outside the allowlisted presets are out of scope for v0.1.

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`defi/evm_reader`](https://github.com/ARPAHLS/skillware/tree/main/skills/defi/evm_reader)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`5b20254`](https://github.com/ARPAHLS/skillware/commit/5b20254b492673288ed29b30313c15523f7cfadf) | feat(defi): add evm_reader skill v0.1.0 for read-only EVM chain queries (#367) (#394) | 29 Sep 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
<!-- skill-history:end -->

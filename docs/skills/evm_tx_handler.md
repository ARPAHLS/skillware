# EVM Transaction Handler

**ID**: `defi/evm_tx_handler`  
**Issuer**: [@Hendobox](https://github.com/Hendobox) ([@ARPAHLS](https://github.com/ARPAHLS))

**Recommended install:** `pip install "skillware[defi_evm_tx_handler]"`. See [Install extras](../usage/install_extras.md).

[Skill Library](README.md) · [Testing](../TESTING.md)

Structured EVM operations for a **dedicated agent wallet**: resolve trade intent, quote Uniswap V2 swaps, preview outcomes, execute swaps, and send native/ERC20 transfers on Ethereum and Base.

## Capabilities

| Action | Description |
|--------|-------------|
| `resolve` | Merge intent with config and YAML registries; surface missing fields |
| `quote` / `preview` | On-chain Uni V2 quote (buy/sell); optional CoinGecko USD in preview |
| `execute` | Approve (if needed) + Uni V2 swap; **re-quotes on-chain at broadcast** |
| `transfer` | Sign and send native or ERC20 (with optional confirmation gate) |
| `balances` | Wallet balances for registered tokens |
| `wallet_info` | Address, supported chains, preferences (no secrets) |
| `update_preferences` | Persist allowed keys to `config.yaml` |

## Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `AGENT_WALLET_PRIVATE_KEY` | Yes (for signing) | **Dedicated agent wallet only** — hex private key in `.env`, never in tool args or YAML |
| `ETHEREUM_RPC_URL` | If using `ethereum` | JSON-RPC |
| `BASE_RPC_URL` | If using `base` | JSON-RPC |
| `COINGECKO_API_KEY` | No | USD preview and `max_trade_usd` enforcement |

### Dedicated agent wallet (required for signing)

1. Create a **new wallet** used only for this agent (limited funds).
2. Add the private key to `.env` as `AGENT_WALLET_PRIVATE_KEY` (or the name in `private_key_env` inside `config.yaml`).
3. Load `.env` via `skillware.core.env.load_env_file()` before calling the skill.
4. **Never** use a personal, treasury, or exchange hot wallet. **Never** pass the key in chat or tool arguments.

If the key is missing, the skill returns `status: missing_config` with setup guidance (see `setup` in the JSON and [API keys for skills](../usage/api_keys.md)).

Copy `skills/defi/evm_tx_handler/config.yaml.example` to `config.yaml` in the same folder for long-term defaults.

## Agent notes

- **Preview drift:** `execute` builds a fresh on-chain quote at broadcast; amounts may differ from the last preview.
- **Quote before confirm:** Call `quote` / `preview` immediately before user approval and `execute`.
- **ERC20 two-step:** Swaps may require `approve` then `swap` (see `approve_tx_hash` in the response).
- **Balances:** Insufficient funds return `status: insufficient_balance` with `agent_hint` before any transaction is sent.

## Registry data

- `data/chains.yaml` — chain IDs, RPC env keys, explorers, Uni V2 routers  
- `data/tokens.yaml` — symbol → contract per chain  
- `data/addressbook.yaml` — label → address (replace placeholders before mainnet use)

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [API keys](../usage/api_keys.md).


Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].ClassName()` also works.

Sample user message: *“Buy 10 DEGEN on Base with USDC”* → `resolve` → `quote` → `preview` → user confirms → `execute` with `confirmed: true`.

### Runnable examples

See [examples/README.md](../../examples/README.md).

| Provider | Script |
| :--- | :--- |
| Gemini | `examples/gemini_evm_tx_handler.py` |
| Claude | `examples/claude_evm_tx_handler.py` |

**Demo mode (no live keys):** `EVM_TX_HANDLER_EXAMPLE_DEMO=1 python examples/gemini_evm_tx_handler.py`

### Gemini

```python
import os
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/evm_tx_handler")
skill = bundle["class"]()
client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)

intent = {
    "side": "buy",
    "chain": "base",
    "target_asset": "degen",
    "spend_asset": "usdc",
    "amount": 10,
    "amount_kind": "target_out",
}

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Resolve and quote a buy of 10 DEGEN on Base with USDC.",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)
# On function_call, match SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"]) (defi_evm_tx_handler):
# skill.execute({"action": ..., "intent": ...})
# After preview + user approval: skill.execute({"action": "execute", "intent": intent, "confirmed": True})
```

### Claude

```python
import os
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/evm_tx_handler")
skill = bundle["class"]()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]

# On tool_use, match name against bundle["manifest"]["name"] (defi/evm_tx_handler):
# skill.execute(tool_use.input)
# execute example:
# skill.execute({"action": "execute", "intent": intent, "confirmed": True})
```

### OpenAI

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/evm_tx_handler")
skill = bundle["class"]()
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# Match tool_call.function.name to openai_tool["function"]["name"] (defi_evm_tx_handler)
```

### DeepSeek

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("defi/evm_tx_handler")
skill = bundle["class"]()
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
# Match tool_call.function.name to deepseek_tool["function"]["name"] (defi_evm_tx_handler)
```

### Ollama

`SkillLoader.to_ollama_prompt(bundle)`; match `"tool": "defi/evm_tx_handler"`. See [Ollama usage](../usage/ollama.md).

## Limitations

- Uniswap V2 only; Ethereum + Base.  
- No cross-chain bridges or aggregators.  
- Create and fund the agent wallet outside the skill; key only in `.env`.

## Security

- Fail closed on missing RPC, registry entries, missing wallet key, or USD price when `max_trade_usd` is set.  
- `confirm_before_send` blocks execute/transfer until `confirmed: true`.  
- Not financial or legal advice; agents can mis-parse NL — always preview.
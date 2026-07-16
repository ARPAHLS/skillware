# Token Limiter

**Domain:** `monitoring`
**Skill ID:** `monitoring/token_limiter`
**Issuer:** [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))

**Recommended install:** `pip install "skillware[monitoring_token_limiter]"`. See [Install extras](../usage/install_extras.md).
[Skill Library](README.md) · [Testing](../TESTING.md)

A deterministic **token budget gate** for autonomous agent loops. After each model turn, the host passes cumulative token usage; the skill returns `CONTINUE`, `WARN`, or `FORCE_TERMINATE`. The host loop must stop when the action is `FORCE_TERMINATE`.

This skill does **not** kill processes, cancel provider sessions, or call billing APIs. It returns a structured decision the orchestrator acts on.

> **Budget disclaimer:** This skill provides an operational budget signal only. It is not billing authority, financial advice, or a guarantee that spend is within budget. A `CONTINUE` result does not approve further spend; the host loop must track token usage from your provider or tokenizer and act on `FORCE_TERMINATE`. Cost estimates use bundled list prices and may differ from invoices.

## Capabilities

- **Hard token ceiling**: Terminates (signals termination) when cumulative tokens reach `max_allowed_tokens`.
- **Soft warning threshold**: Default 80% utilization returns `WARN` before the hard limit.
- **Indicative cost estimates**: Optional `model_id` maps to bundled list prices in `data/model_pricing.json`.
- **Idempotent retries**: Optional `turn_id` caches the decision for the same turn metrics.
- **ROI scaffold (v2)**: Accepts `roi_value_usd`, `expected_outcome`, and `outcome_delivered` for future outcome-aware gates. **Not enforced in v1.**

## Internal Architecture

The skill lives in `skills/monitoring/token_limiter/`.

### The Body (`skill.py` + `budget.py`)

Pure Python evaluation. Loads pricing data at init, tracks an in-memory turn cache for idempotent retries, and returns JSON-serializable payloads. No network calls.

| action | Purpose |
|--------|---------|
| `check` (default) | Evaluate cumulative token usage against limits |
| `reset` | Clear cached turn results for a `task_id` |

### The Mind (`instructions.md`)

Tells the host agent when to call the tool, that cumulative counts are required, and that `FORCE_TERMINATE` means stop the loop immediately.

## Integration Guide

### Environment

No skill-specific environment variables. The host loop supplies token counts from provider usage metadata.

Configure agent keys per [API keys for skills](../usage/api_keys.md) when running provider loop examples.

## Cost metrics

Indicative USD rates live in `skills/monitoring/token_limiter/data/model_pricing.json`. They are **not** invoice-grade. Refresh the file when public list prices change.

| Model ID | Input USD / 1M | Output USD / 1M |
| :--- | ---: | ---: |
| `gpt-4o` | 2.50 | 10.00 |
| `gpt-4o-mini` | 0.15 | 0.60 |
| `claude-3-5-sonnet-latest` | 3.00 | 15.00 |
| `claude-3-5-haiku-latest` | 0.80 | 4.00 |
| `gemini-2.5-flash` | 0.15 | 0.60 |
| `gemini-2.5-flash-lite` | 0.075 | 0.30 |
| `deepseek-chat` | 0.27 | 1.10 |
| Unknown models | Fallback blended 5.00 USD / 1M | |

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md). No skill-specific API keys.


Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].ClassName()` also works.

Sample user message: *Check whether task `scrape_amazon_listings_101` should continue; it has used 125000 tokens with a 100000 limit.*

### Runnable examples

| Script | Provider | Env vars |
| :--- | :--- | :--- |
| [`token_limiter_loop.py`](../../examples/token_limiter_loop.py) | Local execute | None |
| [`gemini_token_limiter.py`](../../examples/gemini_token_limiter.py) | Gemini | Optional `GOOGLE_API_KEY` for Phase 2 |
| [`claude_token_limiter.py`](../../examples/claude_token_limiter.py) | Claude | Optional `ANTHROPIC_API_KEY` for Phase 2 |

Phase 1 in the provider scripts runs the deterministic local loop without API keys. Phase 2 calls the live model when the provider key is set.

See [examples/README.md](../../examples/README.md) and [Agent loops](../usage/agent_loops.md).

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("monitoring/token_limiter")
skill = bundle["class"]()
result = skill.execute({
    "task_id": "scrape_amazon_listings_101",
    "current_token_count": 125_000,
    "max_allowed_tokens": 100_000,
    "model_id": "gpt-4o",
})
# result["action"] == "FORCE_TERMINATE"
print(result["reason"])
```

### Gemini

```python
import os
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/token_limiter")
skill = bundle["class"]()
client = genai.Client()
gemini_tool = SkillLoader.to_gemini_tool(bundle)
response = client.models.generate_content(
    model="gemini-2.5-flash-lite",
    contents=(
        "Check task scrape_amazon_listings_101: 125000 tokens used, limit 100000."
    ),
    config=types.GenerateContentConfig(
        tools=[gemini_tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call:
        result = skill.execute(dict(part.function_call.args))
        print(result["action"], result["reason"])
```

### Claude

```python
import os
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/token_limiter")
skill = bundle["class"]()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
response = client.messages.create(
    model="claude-3-5-haiku-latest",
    max_tokens=1024,
    system=bundle["instructions"],
    tools=tools,
    messages=[{
        "role": "user",
        "content": (
            "Check task scrape_amazon_listings_101: 125000 tokens used, limit 100000."
        ),
    }],
)
for block in response.content:
    if block.type == "tool_use":
        result = skill.execute(dict(block.input))
        print(result["action"], result["reason"])
```

### OpenAI

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/token_limiter")
skill = bundle["class"]()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
tool = SkillLoader.to_openai_tool(bundle)
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {
            "role": "user",
            "content": (
                "Check task scrape_amazon_listings_101: 125000 tokens used, limit 100000."
            ),
        },
    ],
    tools=[tool],
)
message = response.choices[0].message
if message.tool_calls:
    import json
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result["action"], result["reason"])
```

### DeepSeek

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("monitoring/token_limiter")
skill = bundle["class"]()
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
tool = SkillLoader.to_deepseek_tool(bundle)
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {
            "role": "user",
            "content": (
                "Check task scrape_amazon_listings_101: 125000 tokens used, limit 100000."
            ),
        },
    ],
    tools=[tool],
)
message = response.choices[0].message
if message.tool_calls:
    import json
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result["action"], result["reason"])
```

### Ollama (prompt mode)

```python
import json
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("monitoring/token_limiter")
skill = bundle["class"]()
prompt = (
    "You may call tools as JSON blocks.\n"
    f"Tool: {bundle['manifest']['name']}\n"
    f"Instructions:\n{bundle['instructions']}\n"
    "User: Check task scrape_amazon_listings_101 with 125000 tokens and limit 100000."
)
print(prompt)
# When the model emits JSON tool args, pass them to execute:
result = skill.execute({
    "task_id": "scrape_amazon_listings_101",
    "current_token_count": 125_000,
    "max_allowed_tokens": 100_000,
})
print(json.dumps(result, indent=2))
```

## Limitations

- **Provider-agnostic integration**: Works with any agent loop (local Ollama, cloud APIs, custom orchestrators) as long as the host passes cumulative `current_token_count`; the skill does not read provider usage APIs.
- **Not billing authority**: Budget decisions are heuristic signals based on counts you supply and optional indicative pricing. They do not replace provider dashboards, invoices, or finance controls.
- Cost figures are estimates from bundled list prices, not billing records.
- ROI fields are scaffold-only in v1; only token limits trigger `FORCE_TERMINATE`.
- Turn cache is in-memory per skill instance; restart the process to clear all cache.

---

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own budgets, token accounting, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.
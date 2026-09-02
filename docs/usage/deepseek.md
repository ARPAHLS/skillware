# Integration Guide: DeepSeek

Skillware supports DeepSeek chat models via `SkillLoader.to_deepseek_tool()`. Use the official `openai` Python SDK pointed at the DeepSeek API base URL.

This adapter is **separate** from `to_openai_tool()` even though the wire format is similar. Do not substitute one for the other in application code.

Set `DEEPSEEK_API_KEY` for the agent loop. Skills that call other APIs during `execute()` may need additional variables; see [API keys for skills](api_keys.md) and the skill's catalog page.

---

## Quick snippet

```python
import os

from openai import OpenAI

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()

bundle = SkillLoader.load_skill("finance/wallet_screening")
tool = SkillLoader.to_deepseek_tool(bundle)

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
# Pass bundle["instructions"] as the system message when you start the chat.
```

---

## How it works

### 1. Schema adaptation

`to_deepseek_tool()` returns the same structural tool object used by OpenAI-compatible APIs:

```json
{
  "type": "function",
  "function": {
    "name": "...",
    "description": "...",
    "parameters": { }
  }
}
```

Parameters come directly from the skill manifest JSON Schema.

### 2. Function name sanitization

DeepSeek applies the same function-name rules as other OpenAI-compatible tool APIs. Manifest IDs with slashes are normalized (for example `compliance/tos_evaluator` becomes `compliance_tos_evaluator`).

Match `tool_call.function.name` to `tool["function"]["name"]` from `to_deepseek_tool()`, not the raw manifest `name` string.

### 3. System message (Directive)

Pass `bundle["instructions"]` as the `system` role content so the model knows when to call the skill.

### 4. Tool calling loop

Use `client.chat.completions.create` with `tools=[deepseek_tool]`, handle `tool_calls`, run `skill.execute(...)`, append `tool` messages, and repeat.

See `examples/deepseek_tos_evaluator.py`.

---

## Complete example (manual loop)

```python
import json
import os

from openai import OpenAI

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()

bundle = SkillLoader.load_skill("compliance/tos_evaluator")
skill = bundle["class"]()
# Or: skill = bundle["module"].TOSEvaluatorSkill()

deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
tool_name = deepseek_tool["function"]["name"]

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
messages = [
    {"role": "system", "content": bundle["instructions"]},
    {
        "role": "user",
        "content": "Check whether automated crawling is allowed for https://example.com/docs.",
    },
]

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=messages,
    tools=[deepseek_tool],
)

while response.choices[0].message.tool_calls:
    assistant_message = response.choices[0].message
    tool_call = assistant_message.tool_calls[0]

    if tool_call.function.name != tool_name:
        break

    args = json.loads(tool_call.function.arguments)
    result = skill.execute(args)

    messages.append(assistant_message)
    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(result),
        }
    )

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        tools=[deepseek_tool],
    )

print(response.choices[0].message.content)
```

---

## Related documents

- [API keys for skills](api_keys.md)
- [Usage: OpenAI](openai.md) (separate adapter for ChatGPT)
- [Usage: Gemini](gemini.md)
- [Usage: Claude](claude.md)
- [Skill library](../skills/README.md)

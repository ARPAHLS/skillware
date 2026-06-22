# Integration Guide: OpenAI (ChatGPT)

Skillware supports OpenAI Chat Completions tool calling via `SkillLoader.to_openai_tool()`. Use the official `openai` Python SDK.

For agent credentials, set `OPENAI_API_KEY` (see [API keys for skills](api_keys.md) for local and CI setup). Skills that call external APIs during `execute()` may require additional variables documented on each skill page.

---

## Quick snippet

```python
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader
from openai import OpenAI

load_env_file()

bundle = SkillLoader.load_skill("finance/wallet_screening")
tool = SkillLoader.to_openai_tool(bundle)

client = OpenAI()
# Pass bundle["instructions"] as the system message when you start the chat.
```

---

## How it works

### 1. Schema adaptation

`manifest.yaml` stores parameters as standard JSON Schema (`type`, `properties`, `required`). `to_openai_tool()` wraps them in OpenAI's tool shape:

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

No type-case conversion is required (unlike Gemini).

### 2. Function name sanitization

OpenAI function names must match `[a-zA-Z0-9_-]` and are limited to 64 characters. Manifest IDs with slashes are normalized automatically:

| Manifest `name` | OpenAI `function.name` |
| :--- | :--- |
| `compliance/tos_evaluator` | `compliance_tos_evaluator` |
| `finance/wallet_screening` | `finance_wallet_screening` |

In your tool loop, compare `tool_call.function.name` to `tool["function"]["name"]` from `to_openai_tool()`, not necessarily the raw manifest string.

### 3. System message (the Mind)

Pass `bundle["instructions"]` as the `system` role content (or equivalent in your orchestration layer). That teaches the model when and how to invoke the skill, not only what parameters exist.

### 4. Tool calling loop

OpenAI returns `tool_calls` on the assistant message. You execute `skill.execute(...)`, append the assistant message and a `tool` role message with the result, then call `chat.completions.create` again until the model responds without tools.

See `examples/openai_tos_evaluator.py` for a full loop with `compliance/tos_evaluator`.

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
SkillClass = bundle["module"].TOSEvaluatorSkill
skill = SkillClass()

openai_tool = SkillLoader.to_openai_tool(bundle)
tool_name = openai_tool["function"]["name"]

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
messages = [
    {"role": "system", "content": bundle["instructions"]},
    {
        "role": "user",
        "content": "Check whether automated crawling is allowed for https://example.com/docs.",
    },
]

response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages,
    tools=[openai_tool],
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
        model="gpt-4o",
        messages=messages,
        tools=[openai_tool],
    )

print(response.choices[0].message.content)
```

---

## Related documents

- [API keys for skills](api_keys.md)
- [Usage: DeepSeek](deepseek.md) (separate adapter)
- [Usage: Gemini](gemini.md)
- [Usage: Claude](claude.md)
- [Usage: Ollama](ollama.md) (separate prompt-based integration)
- [Skill library](../skills/README.md)

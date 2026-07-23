# OpenAI-compatible model hosts

Many model hosts accept the OpenAI Chat Completions `tools` schema. With those
hosts, use `SkillLoader.to_openai_tool()` and configure the OpenAI client with
the host's API key and `base_url`. A separate Skillware adapter is not needed
just because the model or vendor name is different.

Compatibility is host- and model-specific. Before relying on a model, confirm
that its current documentation says it supports Chat Completions tool calling,
then use the model ID published by that host.

## Choose the adapter

| Situation | Skillware adapter | Guide |
| :--- | :--- | :--- |
| OpenAI or a host that accepts the OpenAI `tools` schema | `to_openai_tool()` | This guide and [OpenAI](openai.md) |
| DeepSeek's first-party API | `to_deepseek_tool()` | [DeepSeek](deepseek.md) |
| Gemini or Claude's native tool API | `to_gemini_tool()` or `to_claude_tool()` | [Gemini](gemini.md) or [Claude](claude.md) |
| Ollama prompt mode, without OpenAI-style tool calling | `to_ollama_prompt()` | [Ollama](ollama.md) |

Use a provider-specific adapter when the provider's schema differs. Do not add
one `to_*_tool()` method per OpenAI-compatible vendor.

## Client pattern

This Groq example changes only the credential, base URL, and model passed to
the standard OpenAI client:

```python
import os

from openai import OpenAI

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()

bundle = SkillLoader.load_skill("compliance/tos_evaluator")
tool = SkillLoader.to_openai_tool(bundle)

client = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)

response = client.chat.completions.create(
    model="<groq-model-id-with-tool-use>",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": "Check https://example.com/docs."},
    ],
    tools=[tool],
)
```

Handle `response.choices[0].message.tool_calls`, execute the skill, and return
the result exactly as in the [shared agent loop](agent_loops.md).

For a complete runnable Groq loop (load skill, call host, `execute()`, return
tool result), see [`examples/openai_compatible_host.py`](../../examples/openai_compatible_host.py).

## Common hosts

The endpoints below are the providers' documented general OpenAI-compatible
base URLs. Provider plans, regional endpoints, model IDs, and feature support
can change, so follow the linked provider documentation for current details.

| Host | `base_url` | Typical key variable | Notes |
| :--- | :--- | :--- | :--- |
| [Kimi / Moonshot](https://platform.kimi.ai/docs/api/chat) | `https://api.moonshot.ai/v1` | `MOONSHOT_API_KEY` | Chat Completions supports function tools; select a current Kimi model with tool use. |
| [Z.AI GLM](https://docs.z.ai/guides/develop/openai/python) | `https://api.z.ai/api/paas/v4/` | `ZAI_API_KEY` | Use the general API endpoint; the Coding Plan has a separate endpoint and use case. |
| [Groq](https://console.groq.com/docs/openai) | `https://api.groq.com/openai/v1` | `GROQ_API_KEY` | Use a model that the Groq model catalog marks for tool use. |
| [Mistral](https://docs.mistral.ai/resources/migration-guides) | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` | The OpenAI-compatible path uses Mistral model IDs. |
| [Together AI](https://docs.together.ai/docs/inference/openai-compatibility) | `https://api.together.ai/v1` | `TOGETHER_API_KEY` | Model IDs commonly use a `provider/model` form. |
| [Fireworks AI](https://docs.fireworks.ai/tools-sdks/openai-compatibility) | `https://api.fireworks.ai/inference/v1` | `FIREWORKS_API_KEY` | Use a Fireworks model or deployment ID that supports tools. |
| [OpenRouter](https://openrouter.ai/docs/quickstart) | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | This is a multi-model gateway; tool support depends on the routed model and provider. |
| [vLLM](https://docs.vllm.ai/en/latest/serving/online_serving/openai_compatible_server/) | `http://localhost:8000/v1` | Operator-defined | The server may require a configured token; the served model must support an appropriate chat template and tools. |
| [LiteLLM proxy](https://docs.litellm.ai/) | `http://localhost:4000` | Operator-defined | Use the proxy key and model alias configured by the proxy operator. |

Never commit API keys. Load them from the environment as described in
[API keys for skills](api_keys.md).

## Local-server boundary

An OpenAI-compatible route does not guarantee compatible tool behavior. For a
local vLLM or LiteLLM deployment, verify the server's tool-calling configuration
and the selected model before sending `tools=[tool]`. If the local runtime only
supports an instruction prompt, use the [Ollama prompt-mode guide](ollama.md)
instead of treating it as structured tool calling.

## Related documents

- [Runnable example: `openai_compatible_host.py`](../../examples/openai_compatible_host.py)
- [Usage: OpenAI](openai.md)
- [Usage: DeepSeek](deepseek.md)
- [Shared agent loops](agent_loops.md)
- [API keys for skills](api_keys.md)
- [Usage guides index](README.md)

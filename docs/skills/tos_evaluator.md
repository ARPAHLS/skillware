# Terms of Service Evaluator

**Domain:** `compliance`
**Skill ID:** `compliance/tos_evaluator`
**Issuer:** [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))

[Skill Library](README.md) · [Testing](../TESTING.md)

A local-first compliance guardrail that checks whether an intended automated action appears permissible on a target website. It evaluates `robots.txt`, discovers candidate legal pages, extracts relevant clauses, and can optionally use a low-cost LLM to interpret ambiguous policy language.

## What It Checks

1. `robots.txt` rules for the exact target URL and user-agent.
2. Likely Terms, Legal, Acceptable Use, and API policy pages on the same site.
3. Clauses related to scraping, crawling, indexing, monitoring, downloading, and API-only access.
4. Optional LLM-backed clause review when local heuristics cannot confidently classify the policy language.

## Manifest Details

**Parameters Schema:**
* `target_url` (string): Full URL the agent intends to access.
* `intended_action` (string): Natural-language action such as `scrape pricing data` or `index docs`.
* `user_agent` (string, optional): User-agent used for `robots.txt` checks.
* `fetch_mode` (string, optional): `lightweight` or `deep`.
* `use_llm_evaluator` (boolean, optional): Enables optional clause interpretation for low-confidence cases.
* `llm_provider` (string, optional): Provider name for the optional evaluator.
* `llm_model` (string, optional): Model name such as `gemini-2.5-flash-lite`.
* `assume_authenticated_session` (boolean, optional): Helps represent paid or logged-in usage contexts.
* `max_terms_pages` (integer, optional): Caps discovery breadth.

**Outputs Schema:**
* `is_safe_to_proceed` (boolean): Whether the action was approved.
* `confidence_score` (number): Confidence in the verdict.
* `verdict` (string): `SAFE`, `UNSAFE`, `CAUTION`, or `INSUFFICIENT_EVIDENCE`.
* `reason` (string): Short explanation of the verdict.
* `robots_assessment` (object): Structured `robots.txt` result.
* `tos_assessment` (object): Structured policy discovery and clause result.
* `llm_assessment` (object): Optional evaluator result.
* `evidence` (array): Supporting snippets and sources.

## Verdict Semantics

* `SAFE`: strong evidence suggests the requested action is allowed, and `robots.txt` does not block it.
* `UNSAFE`: `robots.txt` blocks the path or discovered policy text explicitly restricts the automation.
* `CAUTION`: the site may allow access, but only with conditions such as API usage, permission, or strict rate limits.
* `INSUFFICIENT_EVIDENCE`: the evaluator could not find enough trustworthy evidence to safely approve the action.

## Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `GOOGLE_API_KEY` | No | Optional LLM clause evaluator when `use_llm_evaluator` is enabled with a Gemini provider |

Configure values per [API keys for skills](../usage/api_keys.md). The core policy checks do not require a cloud API key.

## Example Usage (Direct)

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("compliance/tos_evaluator")
TOSEvaluatorSkill = bundle["module"].TOSEvaluatorSkill
skill = TOSEvaluatorSkill()

result = skill.execute(
    {
        "target_url": "https://hackernoon.com/tagged/ai",
        "intended_action": "crawl tagged article pages for research indexing",
        "use_llm_evaluator": True,
        "llm_provider": "gemini",
        "llm_model": "gemini-2.5-flash-lite",
    }
)

print(result["verdict"])
print(result["reason"])
```

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [API keys](../usage/api_keys.md) (optional `GOOGLE_API_KEY` for the LLM evaluator path).

Sample user message: *Before crawling https://example.com/docs, check if automated indexing is allowed.*

| Provider | Reference script |
| :--- | :--- |
| Gemini | `examples/gemini_tos_evaluator.py` |
| Claude | `examples/claude_tos_evaluator.py` |
| OpenAI | `examples/openai_tos_evaluator.py` |
| DeepSeek | `examples/deepseek_tos_evaluator.py` |
| Ollama | `examples/ollama_tos_evaluator.py` |

### Gemini

```python
import os
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("compliance/tos_evaluator")
skill = bundle["module"].TOSEvaluatorSkill()
tool = SkillLoader.to_gemini_tool(bundle)
client = genai.Client()
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Check whether crawling https://example.com/docs is allowed.",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call:
        result = skill.execute(dict(part.function_call.args))
        follow_up = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                "Use this tool result to answer the original request.",
                {
                    "function_response": {
                        "name": part.function_call.name,
                        "response": {"result": result},
                    }
                },
            ],
            config=types.GenerateContentConfig(
                tools=[tool],
                system_instruction=bundle["instructions"],
            ),
        )
        print(follow_up.text)
```

### Claude

```python
import os
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("compliance/tos_evaluator")
skill = bundle["module"].TOSEvaluatorSkill()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
# messages.create(..., system=bundle["instructions"], tools=tools)
# On tool_use: skill.execute(tool_use.input), reply with tool_result
```

### OpenAI

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("compliance/tos_evaluator")
skill = bundle["module"].TOSEvaluatorSkill()
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# chat.completions.create(model="gpt-4o", tools=[openai_tool], ...)
# Match tool_call.function.name to openai_tool["function"]["name"] (compliance_tos_evaluator)
```

### DeepSeek

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("compliance/tos_evaluator")
skill = bundle["module"].TOSEvaluatorSkill()
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
# chat.completions.create(model="deepseek-chat", tools=[deepseek_tool], ...)
```

### Ollama

Prompt-based tool calling. Pull a model such as `gemma3` or `qwen3.5`, then see `examples/ollama_tos_evaluator.py` and [Ollama usage](../usage/ollama.md).

## Notes

This skill is a practical operational safeguard, not legal counsel. If the result is `CAUTION` or `INSUFFICIENT_EVIDENCE`, the safe default is manual review or an official API/developer integration path.

To run tests specifically for this skill:

```bash
pytest tests/skills/compliance/test_tos_evaluator.py
pytest skills/compliance/tos_evaluator/test_skill.py
```

---

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

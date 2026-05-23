# Prompt Token Rewriter

**Domain:** `optimization`
**Skill ID:** `optimization/prompt_rewriter`
**Issuer:** [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))

[Skill Library](README.md) · [Testing](../TESTING.md)

A powerful middleware skill that acts as a deterministic compression logic gate for agents. It ingests a massive, bloated prompt or conversation history and "rewrites" it to use fewer tokens while aggressively retaining 100% of the semantic meaning and instructions.

This is critical for complex agents facing strict token constraints or high LLM API costs.

## Manifest Details

**Parameters Schema:**
*   `raw_text` (string): The bloated, repetitive prompt or extensive conversation history to compress.
*   `compression_aggression` (string): The level of compression: 'low', 'medium', or 'high'.

**Outputs Schema:**
*   `compressed_text` (string): The aggressively shortened prompt retaining semantic constraints.
*   `original_tokens` (integer): The approximate original length.
*   `new_tokens` (integer): The approximate new length.
*   `tokens_saved` (integer): The absolute number of tokens removed.

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md). No skill-specific API keys.

Sample user message: *Compress this prompt before the main model call: "Hello, could you please make sure to read this documentation..."*

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("optimization/prompt_rewriter")
rewriter = bundle["module"].PromptRewriter()
result = rewriter.execute({
    "raw_text": "Hello, could you please make sure to read this documentation...",
    "compression_aggression": "high",
})
print(result["compressed_text"])
```

### Gemini

```python
import os
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("optimization/prompt_rewriter")
skill = bundle["module"].PromptRewriter()
client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Rewrite this support prompt for a concise, policy-safe assistant.",
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
bundle = SkillLoader.load_skill("optimization/prompt_rewriter")
skill = bundle["module"].PromptRewriter()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
# On tool_use (name optimization/prompt_rewriter): skill.execute(tool_use.input)
```

### OpenAI

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("optimization/prompt_rewriter")
skill = bundle["module"].PromptRewriter()
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# Match tool_call.function.name to openai_tool["function"]["name"] (optimization_prompt_rewriter)
```

### DeepSeek

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("optimization/prompt_rewriter")
skill = bundle["module"].PromptRewriter()
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
```

### Ollama

`SkillLoader.to_ollama_prompt(bundle)`; match `"tool": "optimization/prompt_rewriter"`. See [Ollama usage](../usage/ollama.md).

## Maintenance

To run tests specifically for this skill:
```bash
pytest tests/skills/optimization/test_prompt_rewriter.py
```

---

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

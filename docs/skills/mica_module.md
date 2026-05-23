# MiCA Module Skill

**ID**: `compliance/mica_module`
**Issuer**: [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))

[Skill Library](README.md) · [Testing](../TESTING.md)

A highly specialized, localized RAG (Retrieval-Augmented Generation) and policy enforcement engine for the Markets in Crypto-Assets (MiCA) regulation. It ensures any agent using it can understand, query, and enforce the entirety of MiCA with granular precision, acting as a strict compliance firewall.

## Capabilities

*   **Self-Contained Local RAG**: Ships with the full MiCA regulation mapped into a structured `mica_corpus.json` file. It relies on a fast semantic router to prevent overwhelming the parent agent's context window.
*   **Incremental Fetching**: Only pulls precisely the Articles and legal text necessary based on the User's query intent.
*   **Optional Model Swappable Evaluator**: Includes a built-in evaluation loop to review the context and score potential responses for regulatory holes. This node operates entirely independently and the model can be dynamically swapped based on user preference.
*   **Policy Firewall**: Evaluates intent against the regulation before the parent agent generates an external answer, labeling requests as `APPROVED`, `CAUTION`, or `HIGH_RISK_DETECTED`.

## Internal Architecture

The skill is self-contained in `skills/compliance/mica_module/`.

### 1. The Mind (`instructions.md`)
The system prompt teaches the main Agent to:
*   Use a **Pure Cognitive Workflow**: The agent recognizes the MiCA skill via its manifest and determines when statutory context is needed.
*   Formatting: Invokes the skill via a JSON block in the dialogue stream.
*   **Traceability**: Explicitly cites the Article numbers (e.g., Article 59) found in the RAG context.

### 2. The Body (`skill.py` & `mica_corpus.json`)
*   **In-Memory Caching**: The 1MB corpus is cached on the first run, delivering subsequent RAG lookups in **~1.7ms**.
*   **Weighted Surgical Router**: Instead of a "shotgun" match, the router uses a weighted scoring system (Mentions > Keywords > collisions) and throttles retrieval to the **Top 10** most relevant Articles to prevent context window asphyxiation.

## Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `GOOGLE_API_KEY` | Yes (evaluator / Gemini paths) | Google Generative AI used by the built-in evaluator and RAG flows |

Configure values per [API keys for skills](../usage/api_keys.md).

## Arguments

| Argument | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `user_prompt` | string | Yes | - | The user's query regarding crypto-assets, e-money licenses, or MiCA rules. |
| `run_evaluator` | boolean | No | `false` | Triggers the built-in Gemini evaluator node to grade the RAG context and flag regulatory holes. Adds a secondary API call. |
| `evaluator_model` | string | No | `gemini-2.5-flash-lite` | The Gemini model used by the evaluator node. Can be swapped for a faster or more capable model without changing any other part of the skill. |

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [API keys](../usage/api_keys.md).

| Provider | Reference script |
| :--- | :--- |
| Gemini / RAG | `examples/mica_rag_flow.py` |
| Claude | `examples/mica_claude_flow.py` |
| Ollama | `examples/mica_ollama_flow.py` |

Sample user message: *Can I issue a stablecoin backed by physical art under an e-money license?*

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("compliance/mica_module")
skill = bundle["module"].MiCAModuleSkill()
result = skill.execute({
    "user_prompt": "Can I issue a stablecoin backed by physical art under an e-money license?",
    "run_evaluator": True,
    "evaluator_model": "gemini-2.5-flash",
})
print(result["policy_status"])
```

### Gemini

```python
import os
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("compliance/mica_module")
skill = bundle["module"].MiCAModuleSkill()
client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Check whether this stablecoin disclosure aligns with MiCA expectations.",
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
bundle = SkillLoader.load_skill("compliance/mica_module")
skill = bundle["module"].MiCAModuleSkill()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
# See examples/mica_claude_flow.py for the full loop
```

### OpenAI

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("compliance/mica_module")
skill = bundle["module"].MiCAModuleSkill()
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# Match tool_call.function.name (compliance_mica_module)
```

### DeepSeek

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("compliance/mica_module")
skill = bundle["module"].MiCAModuleSkill()
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
```

### Ollama

`SkillLoader.to_ollama_prompt(bundle)`; match `"tool": "compliance/mica_module"`. See `examples/mica_ollama_flow.py` and [Ollama usage](../usage/ollama.md).

## Data Schema Output

The skill returns a strictly formatted JSON context block that Parent Agents incorporate sequentially into their memory.

```json
{
  "retrieved_sections": [
    "Title III | Article 16: Authorization requirements"
  ],
  "policy_status": "HIGH_RISK_DETECTED",
  "gemini_evaluator_feedback": {
    "grade": "B-",
    "holes_found": "The setup failed to mention the absolute requirement of publishing a white paper.",
    "suggestion": "Revise the answer to explicitly state that an e-money license is insufficient without a crypto-asset white paper."
  },
  "final_context_for_agent": "Output the revised answer integrating the following requirement: [White paper publication under Article 16]."
}
```

---

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

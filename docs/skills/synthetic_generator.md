# Synthetic Data Generator Skill

**Domain:** `data_engineering`
**Skill ID:** `data_engineering/synthetic_generator`
**Issuer:** [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))

[Skill Library](README.md) · [Testing](../TESTING.md)

A specialized data engineering capability that combats "model collapse" by generating high-entropy, highly structured synthetic data intentionally designed to fine-tune other models.

## Capabilities

*   **Model Agnosticism**: Supports dynamic internal LLM configuration, letting the user trigger generation via Ollama (local), Google Gemini, or Anthropic Claude.
*   **Combinatorial Entropy Injection**: Designed to explicitly seek out edge-case personas via the `diversity_prompt`, significantly raising the variance of training data.
*   **Zero-Dependency Evaluation Heuristic**: Employs built-in `zlib` string compression ratios to calculate a dynamic entropy score, allowing the coordinating agent to reject low-entropy boilerplate data instantly.

## Internal Architecture

The skill is located in `skills/data_engineering/synthetic_generator/`.

### 1. The Mind (`instructions.md`)
The system instructions emphasize boundary-pushing data generation. It prohibits standard AI tropes and enforces schema obedience.

### 2. The Body (`skill.py`)
*   **Data Generation**: The skill handles invoking the LLM behind the scenes, using the configured provider and isolating the `temperature` specifically for the data generation task so the primary coordinating agent doesn't need to run at high temperature.
*   **Validation**: Attempts to automatically parse out code blocks to extract standard JSON object arrays.
*   **Entropy Scoring**: Converts text sequences into `zlib` compressed bytes. A poor compression ratio implies high lexical variance (less repetitive syntax).

## Integration Guide

### Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `GOOGLE_API_KEY` | When `model_provider` is `gemini` | Google Generative AI for generation |
| `ANTHROPIC_API_KEY` | When `model_provider` is `anthropic` | Anthropic API for generation |
| (none) | When `model_provider` is `ollama` | Uses local Ollama on the default port |

Configure values per [API keys for skills](../usage/api_keys.md). Internal generation uses `model_provider` (`gemini`, `anthropic`, or `ollama`); that is separate from which agent hosts the skill.

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [API keys](../usage/api_keys.md).

Sample user message: *Generate five high-entropy medical coding dispute samples with dual-insurance edge cases.*

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("data_engineering/synthetic_generator")
skill = bundle["module"].SyntheticGeneratorSkill()
result = skill.execute({
    "domain": "medical_coding_disputes",
    "num_samples": 5,
    "entropy_temperature": 0.9,
    "diversity_prompt": "Dual-insurance coverage overlaps.",
    "model_provider": "gemini",
})
print(result["entropy_score"], result["samples_generated"])
```

### Gemini

```python
import os
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/synthetic_generator")
skill = bundle["module"].SyntheticGeneratorSkill()
client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Generate 25 synthetic customer support rows with no real PII.",
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
bundle = SkillLoader.load_skill("data_engineering/synthetic_generator")
skill = bundle["module"].SyntheticGeneratorSkill()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
# On tool_use (name data_engineering/synthetic_generator): skill.execute(tool_use.input)
```

### OpenAI

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/synthetic_generator")
skill = bundle["module"].SyntheticGeneratorSkill()
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# Match tool_call.function.name (data_engineering_synthetic_generator)
```

### DeepSeek

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("data_engineering/synthetic_generator")
skill = bundle["module"].SyntheticGeneratorSkill()
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
```

### Ollama

`SkillLoader.to_ollama_prompt(bundle)`; match `"tool": "data_engineering/synthetic_generator"`. See [Ollama usage](../usage/ollama.md).

## Data Schema

The skill constructs a response validating the pipeline and containing the raw samples.

```json
{
  "samples": [
    {
      "instruction": "Resolve the coding dispute for CPT 99291...",
      "input": "Patient A admitted with BlueCross and Medicare...",
      "output": "Since primary is exhausted..."
    }
  ],
  "entropy_score": 0.88,
  "status": "success",
  "provider_used": "gemini",
  "samples_generated": 1
}
```

## Limitations

*   **Structure Consistency**: If the LLM generates improperly formatted JSON (despite the strict prompt), the parsing step may fail, requiring the agent to retry the skill execution.
*   **Heuristic Entropy**: The `zlib` entropy score evaluates lexical byte-variance, not semantic variance. It serves as a guardrail against robotic boilerplate repetition but is not mathematically bulletproof.

---

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

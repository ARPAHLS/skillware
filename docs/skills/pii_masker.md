# PII Masker

**ID**: `compliance/pii_masker`
**Issuer**: [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))
**Category**: Compliance

[Skill Library](README.md) · [Testing](../TESTING.md)

High-precision, local PII (Personally Identifiable Information) detection and redaction using the `micro-f1-mask` model. This skill acts as a "Privacy Firewall" at the edge, scrubbing sensitive data before it reaches high-latency cloud models.

> [!WARNING]
> **Disclaimer**: This skill and the underlying base model are provided for **demonstration and proof-of-concept purposes only**. 
> Reaching production-grade 95%+ enterprise accuracy requires architectural optimizations, hard-negative mining, and dataset-specific fine-tuning. Full implementation of the `micro-f1-mask` privacy middleware should only happen after you rigorously fine-tune and test it exclusively with your own proprietary data structures.
> Visit the core project repository for training orchestration and full middleware execution: [github.com/arpahls/micro-f1-mask](https://github.com/arpahls/micro-f1-mask)

## How It Works

Agentic workflows inherently risk leaking sensitive user data (names, physical addresses, emails, crypto wallets, etc.) to external LLM providers. This skill solves this by utilizing a local [Ollama](https://ollama.com/) instance hosting the `arpacorp/micro-f1-mask` edge model. 

1. **Contextual Recognition**: Unlike rigid regex patterns, the 270M parameter model is trained to recognize syntactic structure and distinguish between generic information (e.g. "a specific date") and genuine PII (e.g. "a birth date").
2. **Local Execution**: The text is evaluated entirely on your local node, ensuring that raw unencrypted data never touches the external internet.

## Prerequisites

- **Local Inference Support**: This skill uses the `requests` library to communicate entirely locally.
- **Ollama**: You must have [Ollama](https://ollama.com/) running.
- **Model**: You must pull the base privacy edge model before utilizing this skill:
  ```bash
  ollama run arpacorp/micro-f1-mask
  ```
*(Note for full-cycle setups: While Redis is a strict prerequisite for running the full standalone FastAPI bridge of the `micro-f1-mask` repository, it is **not** a prerequisite for invoking this specific `skillware` skill, as this skill performs the stateless scrubbing pass only.)*

## Integration & Full Cycle Nuances

Currently, this `pii_masker` skill functions primarily as a **Forward-Pass Scrubber** (Phase A). 
When an agent calls this skill on a block of text, the skill returns a sanitized string with identifying markers (e.g., `[PERSON_1]`).

**Stateless Design**: By default, this specific Skillware component is stateless. It performs the LLM call and tokenizes the output, but it *does not* automatically preserve the mapping in a local vault (like Redis). 
For a complete End-to-End Enterprise integration (The "Full Cycle" ➔ Mask ➔ Send to Cloud ➔ Get Response ➔ Unmask), external developers should either:
- **Option A (Full Middleware Proxy):** Stand up the full standalone FastAPI bridge + Redis vault provided at the [micro-f1-mask repo](https://github.com/arpahls/micro-f1-mask) and point the agent's network traffic entirely through it.
- **Option B (Stateful Agent Logic):** Build custom logic within the calling agent that parses the detected entities returned from this skill's `metadata`, preserves them in its own internal session database or memory variables, invokes the cloud API, and strings-replaces the tags back onto the cloud response. For understanding how state/vault recovery works conceptually during this reconstruction phase, review the core project's dedicated [API Reference & Lifecycle Architecture](https://github.com/ARPAHLS/micro-f1-mask/blob/main/docs/API.md).

## Arguments

| Argument | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `text` | string | Yes | - | The raw, sensitive input string. |
| `mode` | string | No | `mask` | Options: `mask` (e.g., `[PERSON]`), `redact` (e.g., `XXXX`), or `remove` (removes the token entirely). |
| `ollama_url` | string | No | `http://localhost:11434` | The URL for your local Ollama instance running the model. |

## Supported Entity Types
The `micro-f1-mask` model detects a variety of entities, including but not limited to:
- Names (`[PERSON]`)
- Emails (`[EMAIL]`)
- Phone Numbers (`[PHONE]`)
- Physical Addresses (`[ADDRESS]`)
- Crypto Wallets (`[CRYPTO_ADDRESS]`)
- Identification Numbers (SSN, Passports, etc.)

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md). Skill execution uses local Ollama (`arpacorp/micro-f1-mask`); no cloud agent key required for the masker itself.

Reference flow: `examples/pii_guardrail_flow.py`.

Sample user message: *Mask PII in: "Hello John Doe, your wallet 0xabc123 has been verified."*

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("compliance/pii_masker")
skill = bundle["module"].PIIMaskerSkill()
result = skill.execute({
    "text": "Hello John Doe, your wallet 0xabc123 has been verified.",
    "mode": "mask",
})
print(result["sanitized_text"])
```

### Gemini

```python
import os
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("compliance/pii_masker")
skill = bundle["module"].PIIMaskerSkill()
client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Mask PII before summarizing: Jane Doe, jane@example.com, +1-555-0100.",
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
bundle = SkillLoader.load_skill("compliance/pii_masker")
skill = bundle["module"].PIIMaskerSkill()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
# On tool_use (name compliance/pii_masker): skill.execute(tool_use.input)
```

### OpenAI

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("compliance/pii_masker")
skill = bundle["module"].PIIMaskerSkill()
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# Match tool_call.function.name (compliance_pii_masker)
```

### DeepSeek

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("compliance/pii_masker")
skill = bundle["module"].PIIMaskerSkill()
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
```

### Ollama

`SkillLoader.to_ollama_prompt(bundle)`; match `"tool": "compliance/pii_masker"`. Ensure `ollama run arpacorp/micro-f1-mask` is available. See [Ollama usage](../usage/ollama.md).

### Sample output (mask mode)

```json
{
  "sanitized_text": "Hello [PERSON_1], your wallet [CRYPTO_ADDRESS] has been verified.",
  "metadata": {
    "detected_entities": ["PERSON", "CRYPTO_ADDRESS"],
    "entity_count": 2,
    "security_level": "local-only",
    "model": "arpacorp/micro-f1-mask"
  }
}
```

---

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

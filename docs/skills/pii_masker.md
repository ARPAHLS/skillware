# PII Masker

**ID**: `compliance/pii_masker`
**Issuer**: [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
**Version**: `0.1.0` — 20 Jul 2026
<!-- skill-doc-meta:end -->

**Recommended install:** `pip install "skillware[compliance_pii_masker]"`. See [Install extras](../usage/install_extras.md).
**Category**: Compliance

[Skill Library](README.md) · [Testing](../TESTING.md)

High-precision, local PII (Personally Identifiable Information) detection and redaction using the `micro-f1-mask` model. This skill acts as a "Privacy Firewall" at the edge, scrubbing sensitive data before it reaches high-latency cloud models.

> **Skill chains:** Run on untrusted text before downstream skills — see [Skill chaining](../usage/skill_chaining.md) and `examples/pii_guardrail_flow.py`.

> [!WARNING]
> **Disclaimer**: This skill and the underlying base model are provided for **demonstration and proof-of-concept purposes only**. 
> Reaching production-grade 95%+ enterprise accuracy requires architectural optimizations, hard-negative mining, and dataset-specific fine-tuning. Full implementation of the `micro-f1-mask` privacy middleware should only happen after you rigorously fine-tune and test it exclusively with your own proprietary data structures.
> Visit the core project repository for training orchestration and full middleware execution: [github.com/arpahls/micro-f1-mask](https://github.com/arpahls/micro-f1-mask)

## Bundle layout

The skill lives in `skills/compliance/pii_masker/`. [Skill anatomy](../introduction.md#skill-anatomy). **Contract** — manifest in the bundle. **Directive** — `instructions.md`. **Effect** — `skill.py`. **Assurance** — `test_skill.py`.

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


Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].ClassName()` also works.

### Runnable examples

See [examples/README.md](../../examples/README.md) for the current runnable-script inventory. The dedicated runnable example for this skill is `examples/pii_guardrail_flow.py`, which demonstrates the local execute path rather than a full provider loop.

Sample user message: *Mask PII in: "Hello John Doe, your wallet 0xabc123 has been verified."*

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("compliance/pii_masker")
skill = bundle["class"]()
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
skill = bundle["class"]()
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
skill = bundle["class"]()
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
skill = bundle["class"]()
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
skill = bundle["class"]()
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

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`compliance/pii_masker`](https://github.com/ARPAHLS/skillware/tree/main/skills/compliance/pii_masker)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`12fbd1a`](https://github.com/ARPAHLS/skillware/commit/12fbd1a11bdf66250008afc59df7048935eafc73) | docs: adopt Skill anatomy vocabulary on catalog page (#319) | 1 Sep 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`812ec7e`](https://github.com/ARPAHLS/skillware/commit/812ec7e) | Add card ui_schema validation guard and fix drift (#199) (#260) | 20 Jul 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`bca8181`](https://github.com/ARPAHLS/skillware/commit/bca8181) | Add category and per-skill pip extras with manifest sync (#236). (#256) | 16 Jul 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`0d550d0`](https://github.com/ARPAHLS/skillware/commit/0d550d0) | docs: sweep vision, bundle class usage, and README Mermaid | 8 Jul 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`0f81d1f`](https://github.com/ARPAHLS/skillware/commit/0f81d1f) | Backfill bundle tests for six registry skills missing test_skill.py. | 10 Jun 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`14807be`](https://github.com/ARPAHLS/skillware/commit/14807be) | style: format codebase with Black (#153) | 3 Jun 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`5b68b78`](https://github.com/ARPAHLS/skillware/commit/5b68b78) | Feat/issue 93 cli visual redesign (#129) | 26 May 2026 | `0.1.0` | [@rizzoMartin](https://github.com/rizzoMartin) |
| [`52cce29`](https://github.com/ARPAHLS/skillware/commit/52cce29) | docs: clarify runnable examples across skill pages (#121) | 24 May 2026 | `0.1.0` | [@narutamaaurum](https://github.com/narutamaaurum) |
| [`a3a7ac8`](https://github.com/ARPAHLS/skillware/commit/a3a7ac8) | docs: update Gemini snippets to google-genai (#92) | 23 May 2026 | `0.1.0` | [@kunal-9090](https://github.com/kunal-9090) |
| [`cca7334`](https://github.com/ARPAHLS/skillware/commit/cca7334) | docs: skill docs revamp — remove emojis, add breadcrumbs, fix index, add missing sections (closes #52) (#82) | 21 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`5b18e21`](https://github.com/ARPAHLS/skillware/commit/5b18e21) | Document per-skill usage examples across providers. | 17 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`f800f41`](https://github.com/ARPAHLS/skillware/commit/f800f41) | Add skill issuer attribution across registry and docs. | 17 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`e658e7e`](https://github.com/ARPAHLS/skillware/commit/e658e7e) | docs: update enterprise disclaimer heading and scope to ARPA catalog skills only | 16 May 2026 | `0.1.0` | [@shaansatsangi](https://github.com/shaansatsangi) |
| [`891f5cc`](https://github.com/ARPAHLS/skillware/commit/891f5cc) | docs: add standard enterprise disclaimer to all skill documentation pages (#59) | 16 May 2026 | `0.1.0` | [@shaansatsangi](https://github.com/shaansatsangi) |
| [`8b598bc`](https://github.com/ARPAHLS/skillware/commit/8b598bc) | feat(compliance): add pii_masker skill using micro-f1-mask | 9 Apr 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

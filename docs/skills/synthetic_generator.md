# Synthetic Data Generator Skill

**Domain:** `data_engineering`
**Skill ID:** `data_engineering/synthetic_generator`
**Issuer:** [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
**Version**: `0.1.0` — 16 Jul 2026
<!-- skill-doc-meta:end -->

**Recommended install:** `pip install "skillware[data_engineering_synthetic_generator]"`. See [Install extras](../usage/install_extras.md).
[Skill Library](README.md) · [Testing](../TESTING.md)

A specialized data engineering capability that combats "model collapse" by generating high-entropy, highly structured synthetic data intentionally designed to fine-tune other models.

## Capabilities

*   **Model Agnosticism**: Supports dynamic internal LLM configuration, letting the user trigger generation via Ollama (local), Google Gemini, or Anthropic Claude.
*   **Combinatorial Entropy Injection**: Designed to explicitly seek out edge-case personas via the `diversity_prompt`, significantly raising the variance of training data.
*   **Zero-Dependency Evaluation Heuristic**: Employs built-in `zlib` string compression ratios to calculate a dynamic entropy score, allowing the coordinating agent to reject low-entropy boilerplate data instantly.

## Bundle layout

The skill is located in `skills/data_engineering/synthetic_generator/`. [Skill anatomy](../introduction.md#skill-anatomy). **Contract** — see Manifest Details above. **Assurance** — `test_skill.py` in the bundle.

### Directive (`instructions.md`)
The system instructions emphasize boundary-pushing data generation. It prohibits standard AI tropes and enforces schema obedience.

### Effect (`skill.py`)
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


Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].ClassName()` also works.

Sample user message: *Generate five high-entropy medical coding dispute samples with dual-insurance edge cases.*

### Runnable examples

See [examples/README.md](../../examples/README.md) for the current runnable-script inventory. The dedicated runnable example for this skill is `examples/build_dataset_demo.py`, which uses the skill's local execute path while configuring the internal generator with a Gemini backend.

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("data_engineering/synthetic_generator")
skill = bundle["class"]()
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
skill = bundle["class"]()
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
skill = bundle["class"]()
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
skill = bundle["class"]()
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
skill = bundle["class"]()
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

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`data_engineering/synthetic_generator`](https://github.com/ARPAHLS/skillware/tree/main/skills/data_engineering/synthetic_generator)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`f158fd8`](https://github.com/ARPAHLS/skillware/commit/f158fd844ca2a586ae87d286ffa12d619a999ebf) | docs: adopt Skill anatomy vocabulary on catalog page (#319) | 1 Sep 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`bca8181`](https://github.com/ARPAHLS/skillware/commit/bca8181) | Add category and per-skill pip extras with manifest sync (#236). (#256) | 16 Jul 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`0d550d0`](https://github.com/ARPAHLS/skillware/commit/0d550d0) | docs: sweep vision, bundle class usage, and README Mermaid | 8 Jul 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`0f81d1f`](https://github.com/ARPAHLS/skillware/commit/0f81d1f) | Backfill bundle tests for six registry skills missing test_skill.py. | 10 Jun 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`14807be`](https://github.com/ARPAHLS/skillware/commit/14807be) | style: format codebase with Black (#153) | 3 Jun 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`5b68b78`](https://github.com/ARPAHLS/skillware/commit/5b68b78) | Feat/issue 93 cli visual redesign (#129) | 26 May 2026 | `0.1.0` | [@rizzoMartin](https://github.com/rizzoMartin) |
| [`52cce29`](https://github.com/ARPAHLS/skillware/commit/52cce29) | docs: clarify runnable examples across skill pages (#121) | 24 May 2026 | `0.1.0` | [@narutamaaurum](https://github.com/narutamaaurum) |
| [`7ddedb2`](https://github.com/ARPAHLS/skillware/commit/7ddedb2) | feat: migrate from google-generativeai to google-genai SDK (#97) | 23 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`a3a7ac8`](https://github.com/ARPAHLS/skillware/commit/a3a7ac8) | docs: update Gemini snippets to google-genai (#92) | 23 May 2026 | `0.1.0` | [@kunal-9090](https://github.com/kunal-9090) |
| [`cca7334`](https://github.com/ARPAHLS/skillware/commit/cca7334) | docs: skill docs revamp — remove emojis, add breadcrumbs, fix index, add missing sections (closes #52) (#82) | 21 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`e465dc4`](https://github.com/ARPAHLS/skillware/commit/e465dc4) | Fix skill path resolution and PyPI skill packaging. (#79) | 18 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`5b18e21`](https://github.com/ARPAHLS/skillware/commit/5b18e21) | Document per-skill usage examples across providers. | 17 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`39487f8`](https://github.com/ARPAHLS/skillware/commit/39487f8) | Add generic API keys guide for skills requiring external calls. | 17 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`f800f41`](https://github.com/ARPAHLS/skillware/commit/f800f41) | Add skill issuer attribution across registry and docs. | 17 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`e658e7e`](https://github.com/ARPAHLS/skillware/commit/e658e7e) | docs: update enterprise disclaimer heading and scope to ARPA catalog skills only | 16 May 2026 | `0.1.0` | [@shaansatsangi](https://github.com/shaansatsangi) |
| [`891f5cc`](https://github.com/ARPAHLS/skillware/commit/891f5cc) | docs: add standard enterprise disclaimer to all skill documentation pages (#59) | 16 May 2026 | `0.1.0` | [@shaansatsangi](https://github.com/shaansatsangi) |
| [`3ca49b6`](https://github.com/ARPAHLS/skillware/commit/3ca49b6) | chore: fix flake8 linting errors and bump version to 0.2.2 | 3 Apr 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`8f8a963`](https://github.com/ARPAHLS/skillware/commit/8f8a963) | feat: implement high-entropy synthetic data generator skill (Issue #22) | 3 Apr 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

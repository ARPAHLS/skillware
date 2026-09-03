# Prompt Token Rewriter

**Domain:** `optimization`
**Skill ID:** `optimization/prompt_rewriter`
**Issuer:** [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
**Version**: `0.1.0` — 16 Jul 2026
<!-- skill-doc-meta:end -->

**Recommended install:** `pip install "skillware[optimization_prompt_rewriter]"`. See [Install extras](../usage/install_extras.md).
[Skill Library](README.md) · [Testing](../TESTING.md)

A powerful middleware skill that acts as a deterministic compression logic gate for agents. It ingests a massive, bloated prompt or conversation history and "rewrites" it to use fewer tokens while aggressively retaining 100% of the semantic meaning and instructions.

This is critical for complex agents facing strict token constraints or high LLM API costs.

Often follows [`security/prompt_injection_firewall`](prompt_injection_firewall.md) in a chain when text is safe — see [Skill chaining](../usage/skill_chaining.md).

## Bundle layout

The skill lives in `skills/optimization/prompt_rewriter/`. [Skill anatomy](../introduction.md#skill-anatomy). **Contract** — see Manifest Details below. **Directive** — `instructions.md`. **Effect** — `skill.py`. **Assurance** — `test_skill.py`.

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


Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].ClassName()` also works.

Sample user message: *Compress this prompt before the main model call: "Hello, could you please make sure to read this documentation..."*

### Runnable examples

See [examples/README.md](../../examples/README.md) for the current runnable-script inventory. The dedicated runnable example for this skill is `examples/prompt_compression_demo.py`; the provider sections below are catalog snippets rather than separate checked-in loop scripts.

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("optimization/prompt_rewriter")
rewriter = bundle["class"]()
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
skill = bundle["class"]()
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
skill = bundle["class"]()
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
skill = bundle["class"]()
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
skill = bundle["class"]()
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

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`optimization/prompt_rewriter`](https://github.com/ARPAHLS/skillware/tree/main/skills/optimization/prompt_rewriter)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`12fbd1a`](https://github.com/ARPAHLS/skillware/commit/12fbd1a11bdf66250008afc59df7048935eafc73) | docs: adopt Skill anatomy vocabulary on catalog page (#319) | 1 Sep 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
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
| [`5ea39b2`](https://github.com/ARPAHLS/skillware/commit/5ea39b2) | chore: Fix linting errors for CI | 23 Mar 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`84b7113`](https://github.com/ARPAHLS/skillware/commit/84b7113) | docs: remove redundant skill README and emphasize docs/skills/ documentation | 21 Mar 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`12a3f8f`](https://github.com/ARPAHLS/skillware/commit/12a3f8f) | feat: align prompt rewriter with skillware standards and fix lints | 21 Mar 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`c434341`](https://github.com/ARPAHLS/skillware/commit/c434341) | feat: add prompt rewriter skill and optimization category | 21 Mar 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

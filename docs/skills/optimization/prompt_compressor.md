# Prompt Compressor

**Domain:** `optimization`
**Skill ID:** `optimization/prompt_compressor`
**Issuer:** [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
- **Version**: `1.0.0` — 20 Nov 2026
- **Tier**: `core`
- **Shape**: `middleware`
- **Target**: `software`
- **Tags**: `prompt_engineering`, `compression`, `refinement`, `llm`, `token_optimization`, `prompt_caching`, `rule_deduplication`
<!-- skill-doc-meta:end -->
<!-- skill-intent:begin -->
**Solves:** Compress oversized prompts and conversation histories while retaining meaning so host agents spend fewer tokens.
**Works with:** Gemini, Claude, OpenAI, DeepSeek, Ollama, and Bedrock-compatible host loops.
**Runtime:** Offline. No API keys.
<!-- skill-intent:end -->

> **Migration:** This skill was previously `optimization/prompt_rewriter`. The old ID still loads through a deprecated alias in `skillware/core/loader.py`, and the legacy modes `low` / `medium` / `high` still work but emit a `DeprecationWarning`. See [#436](https://github.com/ARPAHLS/skillware/issues/436).

**Recommended install:** `pip install "skillware[optimization_prompt_compressor]"`. See [Install extras](../../usage/install_extras.md).
[Skill Library](../README.md) · [Optimization](README.md) · [Testing](../../TESTING.md)

A middleware skill that acts as a deterministic compression gate for agents. It compresses bloated prompts and conversation histories into fewer tokens, analyzes how much of a prompt is structural versus semantic, and deduplicates overlapping instruction rules. Lossless, balanced, and cache-optimized modes preserve meaning; aggressive mode is lossy and is flagged as such in the result.

This is critical for complex agents facing strict token constraints or high LLM API costs.

Often follows [`security/prompt_injection_firewall`](../security/prompt_injection_firewall.md) in a chain when text is safe — see [Skill chaining](../../usage/skill_chaining.md). For large documents, run [`optimization/context_optimizer`](context_optimizer.md) first to select relevant spans extractively, then optionally compress with this skill.

## Bundle layout

The skill lives in `skills/optimization/prompt_compressor/`. [Skill anatomy](../../introduction.md#skill-anatomy). Vocabulary: [glossary](../../glossary.md). **Contract** — see Manifest Details below. **Directive** — `instructions.md`. **Effect** — `skill.py`. **Assurance** — `test_skill.py`.

## Manifest Details

**Actions** (`action`, default `compress_prompt`): `compress_prompt`, `analyze_prompt_density`, `deduplicate_rules`.

**Parameters Schema:**
*   `action` (string): Operation to perform. Default `compress_prompt`.
*   `text` (string): Prompt text to compress or analyze. `raw_text` is accepted as an alias for `compress_prompt`.
*   `mode` (string): `lossless`, `balanced` (default), `aggressive` (lossy), or `cache_optimized`. `cache_optimized` keeps leading `<system>...</system>` / `[SYSTEM]...[/SYSTEM]` blocks verbatim as a stable cache prefix and compresses the rest like `balanced`; a warning is returned if no system block is found or it is not at the start. Deprecated aliases: `low` → `lossless`, `medium` → `balanced`, `high` → `aggressive`. `compression_aggression` is accepted as an alias for the `mode` parameter.
*   `target_tokens` (integer, optional): Token budget. Compression escalates through stronger stages until it is met (`lossless` → `balanced` → `aggressive`; `balanced`/`cache_optimized` → `aggressive`), keeping the best result.
*   `preserve_prefix_chars` (integer, optional): Leading characters to leave untouched. When greater than 0, it takes precedence over `cache_optimized`: `<system>` / `[SYSTEM]` block detection is skipped and no cache-related warnings are emitted. Use `cache_optimized` alone for tagged system blocks, or `preserve_prefix_chars` alone for a fixed-length prefix.
*   `protect_code_blocks` (boolean, default `true`): Keep fenced code blocks and inline code spans verbatim.
*   `protect_templates` (boolean, default `true`): Keep `{placeholders}`, `{{...}}`, `${...}`, and XML/HTML-style tags verbatim.
*   `rules` (array of strings, or newline-delimited string): Rules to deduplicate.
*   `combine_negatives` (boolean, default `true`): Group "Do not..." / "Never..." rules at the end.

URLs and email addresses are always kept verbatim.

**Outputs Schema:**
*   `compress_prompt`: `status`, `compressed_text`, `original_tokens`, `compressed_tokens`, `tokens_saved`, `reduction_percentage`, `protected_blocks_count`, `agent_hint` (`mode_used`, `target_tokens`, `stages_applied`, `target_met`, `warnings`, `lossy`, `deprecated_mode`).
*   `analyze_prompt_density`: `status`, `total_tokens`, `structural_tokens`, `semantic_tokens`, `information_density`, `potential_savings` (per mode).
*   `deduplicate_rules`: `status`, `deduplicated_rules`, `original_rule_count`, `final_rule_count`, `tokens_saved`.
*   On validation failure: `status: "error"` and `error`.

## Usage Examples

Guides: [Usage index](../../usage/README.md) · [Agent loops](../../usage/agent_loops.md). No skill-specific API keys.


Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].ClassName()` also works.

Sample user message: *Compress this prompt before the main model call: "Hello, could you please make sure to read this documentation..."*

### Runnable examples

See [examples/README.md](../../../examples/README.md) for the current runnable-script inventory. The dedicated runnable example for this skill is `examples/prompt_compression_demo.py`; the provider sections below are catalog snippets rather than separate checked-in loop scripts.

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("optimization/prompt_compressor")
compressor = bundle["class"]()
result = compressor.execute({
    "text": "Hello, could you please make sure to read this documentation...",
    "mode": "aggressive",
})
print(result.get('compressed_text', result))
```

### Gemini

```python
import os
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("optimization/prompt_compressor")
skill = bundle["class"]()
client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents="Compress this prompt before the main model call: 'Hello, could you please make sure to read this documentation...'",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call:
        result = skill.execute(dict(part.function_call.args))
        follow_up = client.models.generate_content(
            model="gemini-3.5-flash",
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
bundle = SkillLoader.load_skill("optimization/prompt_compressor")
skill = bundle["class"]()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    system=bundle["instructions"],
    tools=tools,
    messages=[{"role": "user", "content": "Compress this prompt before the main model call: 'Hello, could you please make sure to read this documentation...'"}],
)
for block in response.content:
    if block.type == "tool_use":
        result = skill.execute(dict(block.input))
        print(result.get('compressed_text', result))
```

### OpenAI

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("optimization/prompt_compressor")
skill = bundle["class"]()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
tool = SkillLoader.to_openai_tool(bundle)
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": "Compress this prompt before the main model call: 'Hello, could you please make sure to read this documentation...'"},
    ],
    tools=[tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result.get('compressed_text', result))

```

### DeepSeek

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("optimization/prompt_compressor")
skill = bundle["class"]()
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
tool = SkillLoader.to_deepseek_tool(bundle)
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": "Compress this prompt before the main model call: 'Hello, could you please make sure to read this documentation...'"},
    ],
    tools=[tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result.get('compressed_text', result))
```

### Ollama (prompt mode)

```python
import json
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("optimization/prompt_compressor")
skill = bundle["class"]()
prompt = (
    "You may call tools as JSON blocks.\n"
    f"Tool: {bundle['manifest']['name']}\n"
    f"Instructions:\n{bundle['instructions']}\n"
    f"User: Compress this prompt before the main model call: 'Hello, could you please make sure to read this documentation...'"
)
print(prompt)
result = skill.execute({
    "text": "Hello, could you please make sure to read this documentation...",
    "mode": "aggressive",
})
print(json.dumps(result, indent=2))
```

## Maintenance

To run tests specifically for this skill:
```bash
pytest tests/skills/optimization/test_prompt_compressor.py
```

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`optimization/prompt_compressor`](https://github.com/ARPAHLS/skillware/tree/main/skills/optimization/prompt_compressor)).

| Commit                                                                                            | Description                                                                                                                                                              | Date | Version | Contributors |
|:--------------------------------------------------------------------------------------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------| :--- | :--- | :--- |
| TBD                                                                                               | feat(optimization): prompt_compressor v1.0.0 with lossless/balanced/aggressive/cache_optimized modes, target_tokens, analyze_prompt_density and deduplicate_rules (#504) | 23 Nov 2026 | `1.0.0` | [@isouvikdas](https://github.com/isouvikdas) |
| [`05e3f04`](https://github.com/ARPAHLS/skillware/commit/05e3f04874cb8928afeea2844a8ad021667da3a0) | feat(catalog): backfill Manifest v2 taxonomy and establish tag governance policy (#440)                                                                                  | 19 Oct 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`3d36648`](https://github.com/ARPAHLS/skillware/commit/3d366482cb3f659c0e6a5580b7336b20063010fa) | feat(core): shared BaseSkill.load_manifest_from_dir() helper and stub skill migration (#203) (#383)                                                                      | 5 Oct 2026 | `0.1.0` | [@Achalnawal2745](https://github.com/Achalnawal2745) |
| [`0ab59cc`](https://github.com/ARPAHLS/skillware/commit/0ab59ccfa5b2fabd438114980aba063367418f0d) | feat(optimization): add context_optimizer for query-aware extractive selection (#44) (#357)                                                                              | 16 Sep 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`790787d`](https://github.com/ARPAHLS/skillware/commit/790787d0e72262ddfeb26f747f880012ca2b1ca6) | docs: five-provider Usage Examples guard and catalog loop backfill (#347)                                                                                                | 10 Sep 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`12fbd1a`](https://github.com/ARPAHLS/skillware/commit/12fbd1a11bdf66250008afc59df7048935eafc73) | docs: adopt Skill anatomy vocabulary on catalog page (#319)                                                                                                              | 1 Sep 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`bca8181`](https://github.com/ARPAHLS/skillware/commit/bca8181)                                  | Add category and per-skill pip extras with manifest sync (#236). (#256)                                                                                                  | 16 Jul 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`0d550d0`](https://github.com/ARPAHLS/skillware/commit/0d550d0)                                  | docs: sweep vision, bundle class usage, and README Mermaid                                                                                                               | 8 Jul 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`0f81d1f`](https://github.com/ARPAHLS/skillware/commit/0f81d1f)                                  | Backfill bundle tests for six registry skills missing test_skill.py.                                                                                                     | 10 Jun 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`14807be`](https://github.com/ARPAHLS/skillware/commit/14807be)                                  | style: format codebase with Black (#153)                                                                                                                                 | 3 Jun 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`5b68b78`](https://github.com/ARPAHLS/skillware/commit/5b68b78)                                  | Feat/issue 93 cli visual redesign (#129)                                                                                                                                 | 26 May 2026 | `0.1.0` | [@rizzoMartin](https://github.com/rizzoMartin) |
| [`52cce29`](https://github.com/ARPAHLS/skillware/commit/52cce29)                                  | docs: clarify runnable examples across skill pages (#121)                                                                                                                | 24 May 2026 | `0.1.0` | [@narutamaaurum](https://github.com/narutamaaurum) |
| [`a3a7ac8`](https://github.com/ARPAHLS/skillware/commit/a3a7ac8)                                  | docs: update Gemini snippets to google-genai (#92)                                                                                                                       | 23 May 2026 | `0.1.0` | [@kunal-9090](https://github.com/kunal-9090) |
| [`cca7334`](https://github.com/ARPAHLS/skillware/commit/cca7334)                                  | docs: skill docs revamp — remove emojis, add breadcrumbs, fix index, add missing sections (closes #52) (#82)                                                             | 21 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`5b18e21`](https://github.com/ARPAHLS/skillware/commit/5b18e21)                                  | Document per-skill usage examples across providers.                                                                                                                      | 17 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`f800f41`](https://github.com/ARPAHLS/skillware/commit/f800f41)                                  | Add skill issuer attribution across registry and docs.                                                                                                                   | 17 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`e658e7e`](https://github.com/ARPAHLS/skillware/commit/e658e7e)                                  | docs: update enterprise disclaimer heading and scope to ARPA catalog skills only                                                                                         | 16 May 2026 | `0.1.0` | [@shaansatsangi](https://github.com/shaansatsangi) |
| [`891f5cc`](https://github.com/ARPAHLS/skillware/commit/891f5cc)                                  | docs: add standard enterprise disclaimer to all skill documentation pages (#59)                                                                                          | 16 May 2026 | `0.1.0` | [@shaansatsangi](https://github.com/shaansatsangi) |
| [`5ea39b2`](https://github.com/ARPAHLS/skillware/commit/5ea39b2)                                  | chore: Fix linting errors for CI                                                                                                                                         | 23 Mar 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`84b7113`](https://github.com/ARPAHLS/skillware/commit/84b7113)                                  | docs: remove redundant skill README and emphasize docs/skills/ documentation                                                                                             | 21 Mar 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`12a3f8f`](https://github.com/ARPAHLS/skillware/commit/12a3f8f)                                  | feat: align prompt rewriter with skillware standards and fix lints                                                                                                       | 21 Mar 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`c434341`](https://github.com/ARPAHLS/skillware/commit/c434341)                                  | feat: add prompt rewriter skill and optimization category                                                                                                                | 21 Mar 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

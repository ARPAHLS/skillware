# Context Window Optimizer

**Domain:** `optimization`
**Skill ID:** `optimization/context_optimizer`
**Issuer:** [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
**Version**: `0.1.1` — 20 Sep 2026
<!-- skill-doc-meta:end -->

**Recommended install:** `pip install "skillware[optimization_context_optimizer]"`. See [Install extras](../usage/install_extras.md).

[Skill Library](README.md) · [Testing](../TESTING.md)

Query-aware **extractive** context selection for large documents. The skill chunks `document_text`, scores each span against `agent_goal` with local `fastembed` embeddings, and returns only the highest-relevance source text up to `max_tokens_return` — a mini-RAG cycle **without paraphrase**.

Use this **before** the main LLM when a document is far larger than the task needs. Pair with [`optimization/prompt_rewriter`](prompt_rewriter.md) **after** selection when the chosen spans still need compression. Do **not** confuse with the rewriter: the optimizer **selects** verbatim spans; the rewriter **compresses** text.

For untrusted documents, chain [`security/prompt_injection_firewall`](prompt_injection_firewall.md) first — see [Skill chaining](../usage/skill_chaining.md).

## Capabilities

- **Local embeddings**: `fastembed` with `BAAI/bge-small-en-v1.5` (~50 MB, cached after first use). No API key in `execute()`.
- **Extractive-only**: `optimized_context` is verbatim from `document_text` (constitution enforced).
- **Traceability**: `chunks_selected` reports index, cosine score, byte offsets, and previews.
- **Chunk strategies**: `paragraph` (default), `sentence`, or `fixed_chars` with overlap for dense corpora.
- **Fail closed**: `empty_result` when no chunk meets `min_score`; no fabricated filler text.
- **Budget passthrough**: Documents already under `max_tokens_return` return verbatim with `0%` reduction.

## Bundle layout

The skill lives in `skills/optimization/context_optimizer/`. [Skill anatomy](../introduction.md#skill-anatomy). **Contract** — see Manifest Details below. **Directive** — `instructions.md`. **Effect** — `skill.py`. **Assurance** — `test_skill.py`.

## Manifest Details

**Parameters Schema:**
*   `document_text` (string): Full source document (plain text or Markdown).
*   `agent_goal` (string): Natural-language description of what the host agent needs from the document.
*   `max_tokens_return` (integer, default `2000`): Approximate token budget for `optimized_context` (chars/4 heuristic).
*   `min_score` (number, default `0.35`): Minimum cosine similarity for a chunk to be eligible.
*   `chunk_strategy` (string): `paragraph` | `sentence` | `fixed_chars`.
*   `chunk_size_chars` / `chunk_overlap_chars`: Tuning for `fixed_chars` strategy.

**Outputs Schema:**
*   `status`: `ready` | `empty_result` | `error`
*   `optimized_context`: Extractive concatenation of selected chunks.
*   `reduction_percentage`: Estimated reduction vs full document.
*   `chunks_selected`: Traceability rows (index, score, offsets, preview).
*   `agent_hint`: Host guidance (e.g. chain firewall, lower `min_score`).

## Integration Guide

### Dependencies

```bash
pip install "skillware[optimization_context_optimizer]"
```

On first use, `fastembed` downloads the embedding model to a local cache.

### Environment

No skill-specific API keys. Optional provider keys only when wiring `optimized_context` into Gemini, Claude, or other hosts (see Usage Examples).

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md).

Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].ClassName()` also works.

Sample user message: *From this 500-page policy, find jurisdiction clauses for data handling and pass only relevant sections to the main model.*

### Runnable examples

See [examples/README.md](../../examples/README.md). Offline: `examples/context_optimizer_demo.py`, `examples/context_optimizer_chain_demo.py` (firewall → optimizer). Optional live loops: `examples/context_optimizer_gemini_loop.py` (`CONTEXT_OPTIMIZER_GEMINI_LIVE=1`), `examples/context_optimizer_claude_loop.py` (`CONTEXT_OPTIMIZER_CLAUDE_LIVE=1`).

### Direct execute

```python
from pathlib import Path
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("optimization/context_optimizer")
skill = bundle["class"]()
document = Path("skills/optimization/context_optimizer/data/sample_policy.txt").read_text(encoding="utf-8")

result = skill.execute({
    "document_text": document,
    "agent_goal": "Find jurisdiction clauses for data handling.",
    "max_tokens_return": 250,
    "min_score": 0.45,
})
print(result["status"])
print(result["optimized_context"])
print(result["reduction_percentage"])
print(result["chunks_selected"])
```

### SkillContext chain (firewall → optimizer)

```python
from skillware import SkillContext

ctx = SkillContext(skills=[
    "security/prompt_injection_firewall",
    "optimization/context_optimizer",
])
raw = open("policy.txt", encoding="utf-8").read()
fw = ctx.execute("security/prompt_injection_firewall", {
    "source_text": raw,
    "input_mode": "plain",
    "sensitivity": "balanced",
})
if not fw.get("is_safe"):
    raise RuntimeError("Untrusted document blocked by firewall")

opt = ctx.execute("optimization/context_optimizer", {
    "document_text": fw["sanitized_text"],
    "agent_goal": "jurisdiction and cross-border data handling",
    "max_tokens_return": 250,
    "min_score": 0.45,
})
print(opt["optimized_context"])
```

### Gemini

```python
import os
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("optimization/context_optimizer")
skill = bundle["class"]()
client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents="Select jurisdiction-relevant sections from the attached policy for data handling.",
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
                "Answer using ONLY optimized_context from the tool result.",
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
bundle = SkillLoader.load_skill("optimization/context_optimizer")
skill = bundle["class"]()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    system=bundle["instructions"],
    tools=tools,
    messages=[{
        "role": "user",
        "content": "Extract jurisdiction clauses for data handling from the policy text I will provide.",
    }],
)
for block in response.content:
    if block.type == "tool_use":
        result = skill.execute(dict(block.input))
        print(result["optimized_context"])
```

### OpenAI

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("optimization/context_optimizer")
skill = bundle["class"]()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
tool = SkillLoader.to_openai_tool(bundle)
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": "Select jurisdiction-relevant policy sections for data handling."},
    ],
    tools=[tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result["optimized_context"])
```

### DeepSeek

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("optimization/context_optimizer")
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
        {"role": "user", "content": "Select jurisdiction-relevant policy sections for data handling."},
    ],
    tools=[tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result["optimized_context"])
```

### Ollama (prompt mode)

```python
import json
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("optimization/context_optimizer")
skill = bundle["class"]()
prompt = (
    "You may call tools as JSON blocks.\n"
    f"Tool: {bundle['manifest']['name']}\n"
    f"Instructions:\n{bundle['instructions']}\n"
    f"User: Select jurisdiction clauses for data handling from the policy."
)
print(prompt)
result = skill.execute({
    "document_text": "Section 1 Marketing...\n\nSection 9 Jurisdiction and GDPR data handling...",
    "agent_goal": "jurisdiction data handling",
    "max_tokens_return": 500,
})
print(json.dumps(result, indent=2))
```

## Maintenance

```bash
pytest skills/optimization/context_optimizer/test_skill.py
pytest tests/skills/optimization/test_context_optimizer.py
```

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`optimization/context_optimizer`](https://github.com/ARPAHLS/skillware/tree/main/skills/optimization/context_optimizer)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`0ab59cc`](https://github.com/ARPAHLS/skillware/commit/0ab59ccfa5b2fabd438114980aba063367418f0d) | feat(optimization): add context_optimizer for query-aware extractive selection (#44) (#357) | 16 Sep 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

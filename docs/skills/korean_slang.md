# Korean Slang

**Domain:** `linguistics`
**Skill ID:** `linguistics/korean_slang`
**Issuer:** [@bd-c3](https://github.com/bd-c3) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
**Version**: `0.1.0` — 19 Sep 2026
<!-- skill-doc-meta:end -->
**Recommended install:** `pip install "skillware[linguistics_korean_slang]"`. See [Install extras](../usage/install_extras.md).

[Skill Library](README.md) · [Testing](../TESTING.md)

Deterministic **Korean Gen-Z slang lexicon** for host agents that need to understand or speak modern internet Korean. `execute()` is a pure function: longest-first matching over a curated September 2026 pack, template-based `suggest()`, and constitution filters for slurs and appearance-policing slang. No network. No model calls.

This is the v1 answer to [issue #34](https://github.com/ARPAHLS/skillware/issues/34) (preferred id `linguistics/korean_slang`, not `korean_pack_26_S`). The pack is small and honest: unmatched 줄임말 stay unmatched.

> **Skill chains:** Often after `security/prompt_injection_firewall` when the Korean text arrived from an untrusted comment field — see [Skill chaining](../usage/skill_chaining.md).

> **Language disclaimer:** This skill is a curated snapshot, not a native speaker and not a living social network. Slang dating, regional use, and irony can still be wrong. A Korean-native review of the data pack is expected at PR time.

## Capabilities

- **interpret** (default): gloss incoming Korean / Konglish / jamo chat. Returns the issue contract fields `translation`, `slang_breakdown`, `nuance`, `formality`.
- **suggest**: peer-register lines from templates, gated by `audience` (`peers`, `mixed`, `work`, `elders`). Elders get polite Korean, not 반말 slang.
- **lookup**: exact surface, alias, or romanization.
- **Constitution**: blocked substrings are omitted from glosses and never generated. Vulgar items (`존나`, `존맛탱`) are interpreted but not suggested unless `vulgar_ok` is true.

## Bundle layout

The skill lives in `skills/linguistics/korean_slang/`. Roles: [Skill anatomy](../introduction.md#skill-anatomy) and the [glossary](../glossary.md). **Contract** — see Manifest Details below. **Assurance** — `test_skill.py` in the bundle.

### Effect (`skill.py` + `lexicon.py`)

Pure Python. Loads `kb/` once per process, matches compact Hangul (spaces ignored), applies jamo/latin boundaries, and fills templates. Identical input returns identical JSON.

### Directive (`instructions.md`)

When to call interpret vs suggest, honorific gates, and how to talk about unmatched or caution terms.

### Corpus (`kb/`)

| File | Role |
| :--- | :--- |
| `entries.json` | Curated slang entries (surfaces, aliases, romanization, intents, safety flags) |
| `generation.json` | Intent aliases and audience-scoped templates |
| `constitution.json` | Blocked substrings the skill will not gloss or generate |
| `pack_meta.json` | Snapshot id `2026-09` and public sources used to seed the pack |

## Manifest Details

**Parameters Schema:**
* `text` (string): Korean, Konglish, or English. Required for `interpret` and `lookup`.
* `context` (string, optional): Situational note appended to `nuance`.
* `action` (string, optional): `interpret` (default), `suggest`, or `lookup`.
* `intent` (string, optional): Generation bucket for `suggest` (`praise`, `food`, `work`, `tired`, `annoyed`, `agree`, `greeting`, `bye`, `thanks`, `workout`, `weekend`, `dating`, `fandom`, `competence`).
* `audience` (string, optional): `peers` (default), `mixed`, `work`, or `elders`.
* `include_romanization` (boolean, optional): Attach romanization on hits.
* `max_hits` (integer, optional): 1–50, default 12.
* `vulgar_ok` (boolean, optional): Allow vulgar-marked items in `suggest()`. Default false.

**Outputs Schema:**
* `status` (string): `ok` or `error`.
* `action` (string): Echoed action.
* `translation` (string or null): English gloss, or generated Korean for `suggest`.
* `slang_breakdown` (object): Surface → short explanation.
* `nuance` (string): Socio-linguistic note.
* `formality` (string): `Informal / Slang`, `Informal / Vulgar`, `Informal / Caution`, `Polite`, `Work-safe`, `unknown`, or `blocked`.
* `hit_count` (integer): Hits or suggestion count.

Contract violations return `{"status": "error", "error": {"code", "detail"}}`. Closed codes: `EMPTY_TEXT`, `UNKNOWN_ACTION`, `UNKNOWN_AUDIENCE`, `INVALID_MAX_HITS`, `NEED_TEXT_OR_INTENT`, `NO_SUGGESTIONS`, `PACK_FAILURE`.

## Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| *(none)* | — | Offline pack; `execute()` does not read secrets |

Configure agent keys per [API keys for skills](../usage/api_keys.md) only when running provider loop examples.

## Example Usage (Direct)

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("linguistics/korean_slang")
skill = bundle["class"]()
result = skill.execute(
    {
        "text": "요즘 완전 폼 미쳤다",
        "context": "A comment on a YouTube video about a popular singer.",
    }
)
print(result["translation"], result["formality"])
print(result["slang_breakdown"])
```

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [Skill chaining](../usage/skill_chaining.md). No skill-specific API keys. See [Install extras](../usage/install_extras.md).

Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].KoreanSlangSkill()` also works.

Sample user message: *What does 요즘 완전 폼 미쳤다 mean on a YouTube comment about a singer?*

### Runnable examples

| Script | Provider | Env vars |
| :--- | :--- | :--- |
| [`korean_slang_demo.py`](../../examples/korean_slang_demo.py) | Local execute | None |
| [`korean_slang_stress_sim.py`](../../scripts/korean_slang_stress_sim.py) | Local execute (maintainer harness) | None |

### Gemini

```python
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("linguistics/korean_slang")
skill = bundle["class"]()
tool = SkillLoader.to_gemini_tool(bundle)
client = genai.Client()
response = client.models.generate_content(
    model="gemini-3.5-flash-lite",
    contents=(
        "What does 요즘 완전 폼 미쳤다 mean on a YouTube comment about a singer?"
    ),
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call:
        result = skill.execute(dict(part.function_call.args))
        print(result["translation"], result["formality"])
```

### Claude

```python
import os
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("linguistics/korean_slang")
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
        "content": (
            "What does 요즘 완전 폼 미쳤다 mean on a YouTube comment about a singer?"
        ),
    }],
)
for block in response.content:
    if block.type == "tool_use":
        result = skill.execute(dict(block.input))
        print(result["translation"], result["formality"])
```

### OpenAI

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("linguistics/korean_slang")
skill = bundle["class"]()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
tool = SkillLoader.to_openai_tool(bundle)
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {
            "role": "user",
            "content": (
                "What does 요즘 완전 폼 미쳤다 mean on a YouTube comment about a singer?"
            ),
        },
    ],
    tools=[tool],
)
message = response.choices[0].message
if message.tool_calls:
    import json
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result["translation"], result["formality"])
```

### DeepSeek

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("linguistics/korean_slang")
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
        {
            "role": "user",
            "content": (
                "What does 요즘 완전 폼 미쳤다 mean on a YouTube comment about a singer?"
            ),
        },
    ],
    tools=[tool],
)
message = response.choices[0].message
if message.tool_calls:
    import json
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result["translation"], result["formality"])
```

### Ollama (prompt mode)

```python
import json
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("linguistics/korean_slang")
skill = bundle["class"]()
prompt = (
    "You may call tools as JSON blocks.\n"
    f"Tool: {bundle['manifest']['name']}\n"
    f"Instructions:\n{bundle['instructions']}\n"
    "User: What does 요즘 완전 폼 미쳤다 mean on a YouTube comment about a singer?"
)
print(prompt)
# When the model emits JSON tool args, pass them to execute:
result = skill.execute({
    "text": "요즘 완전 폼 미쳤다",
    "context": "A comment on a YouTube video about a popular singer.",
    "action": "interpret",
})
print(json.dumps(result, indent=2, ensure_ascii=False))
```

## Limitations

- **Not an LLM translator.** Unseen slang returns `unmatched`. Do not invent 줄임말 expansions.
- **Snapshot dated 2026-09.** Internet Korean moves faster than a registry pack.
- **Register gates are coarse.** `elders` suppresses slang; it does not implement a full 존댓말 grammar engine.
- **Blocked list is not exhaustive.** New slurs will appear; the constitution is a floor, not a hate-speech classifier.
- **Romanization is a lookup aid**, not official Revised Romanization for every vowel nuance.

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`linguistics/korean_slang`](https://github.com/ARPAHLS/skillware/tree/main/skills/linguistics/korean_slang)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`91d8124`](https://github.com/ARPAHLS/skillware/commit/91d812478546b048590c88bc615bb4b0aaec7628) | feat(linguistics): add korean_slang offline Gen-Z pack (#34) (#369) | 19 Sep 2026 | `0.1.0` | [@bd-c3](https://github.com/bd-c3) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

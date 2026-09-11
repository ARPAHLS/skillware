# Deck Builder

**ID**: `creative/deck_builder`  
**Issuer**: [@tusharjamunkar](https://github.com/tusharjamunkar) ([@ARPAHLS](https://github.com/ARPAHLS))  
<!-- skill-doc-meta:begin -->
**Version**: `0.2.0` — 4 Sep 2026
<!-- skill-doc-meta:end -->

**Recommended install:** `pip install "skillware[creative_deck_builder]"`. See [Install extras](../usage/install_extras.md).  
**Category**: Creative

[Skill Library](README.md) · [Testing](../TESTING.md)

Deterministic, offline assembly of Microsoft PowerPoint (`.pptx`) presentations from structured JSON deck specifications. Supports 13 slide layouts (title, section, bullets, two-column, image, image with caption, quote, table, chart, timeline, metrics, comparison, blank), smart image placeholders, `fit` policies, presentation quality linting (`lint_deck`), archetype outline generation (`suggest_outline`), custom theme token overrides, speaker notes, and pre-flight validation.

## Capabilities

- **Deterministic Assembly**: Generates standard editable `.pptx` documents without remote network calls or image generation APIs.
- **13 Layout Types**: Supports cover titles, section headers, bullet lists, two-column comparisons, images, image captions, pull-quotes, tables, native OpenXML charts (bar, line, pie), milestone timelines, KPI metric cards, comparative matrices, and blank canvases.
- **Smart Image Engine & Placeholders**: Normalizes images via Pillow (EXIF orientation, CMYK to RGB) with configurable `fit` policies (`contain`, `cover`, `crop_center`, `stretch`) and neutral offline placeholders (`hero`, `logo`, `icon`, `chart_backdrop`, `headshot`).
- **Quality Gates (`lint_deck`)**: Heuristic deck scoring (0–100) assessing bullet density, text length caps, image alt tags, orphan bullets, and visual monotony.
- **Archetype Outlines (`suggest_outline`)**: Offline template outline generator for `investor_pitch`, `technical_brief`, `quarterly_review`, `product_launch`, and `training_workshop`.
- **Pre-flight Validation (`validate_spec`)**: Validates JSON specifications against strict JSON Schema and flags soft-limit warnings (e.g. text truncations, missing assets) before writing to disk.
- **Widescreen 16:9 Templates**: Bundles 3 distinct master templates (`pitch_v1`, `corporate_v1`, `minimal_v1`) with configurable font and accent color tokens.
- **Inspection (`inspect`)**: Examines existing `.pptx` files and extracts slide counts, layout hints, titles, and speaker notes presence.

## Actions

| Action | Parameters | Description |
| :--- | :--- | :--- |
| `validate_spec` *(default)* | `deck_spec`, `strict` *(optional)* | Validates `deck_spec` against JSON schema and business rules without writing files. |
| `render` | `deck_spec`, `output_path`, `template_id` *(optional)*, `theme` *(optional)*, `strict` *(optional)* | Assembles slides, applies theme tokens, inserts images/charts, writes `.pptx` to disk. |
| `inspect` | `input_path` | Reads an existing `.pptx` presentation and returns slide counts, titles, layout names, and notes presence. |
| `list_templates` | *(none)* | Enumerates bundled template IDs, names, descriptions, and aspect ratios. |
| `lint_deck` | `deck_spec`, `min_score` *(optional)*, `strict_a11y` *(optional)* | Analyzes deck specification for presentation design and accessibility best practices. |
| `suggest_outline` | `archetype`, `topic` *(optional)*, `constraints` *(optional)* | Generates a structured slide outline and skeleton `deck_spec` for an archetype. |

## Slide Layouts

| Type | Description | Key Fields |
| :--- | :--- | :--- |
| `title` | Cover slide | `title`, `subtitle`, optional `image`, optional `speaker_notes` |
| `section` | Section divider | `title`, optional `subtitle`, optional `speaker_notes` |
| `bullets` | Bulleted takeaways | `title`, `bullets` (array of strings; >120 chars emits warning), `speaker_notes` |
| `two_column` | Comparison / two-panel layout | `title`, `left` (text/bullets), `right` (text/bullets), `speaker_notes` |
| `image` | Visual showcase | `title`, `image` (path, base64, or placeholder_id), optional `caption`, `speaker_notes` |
| `image_caption` | Image with side text | `title`, `image`, `body` (explanatory text), `speaker_notes` |
| `quote` | Pull quote | `quote`, `attribution`, `speaker_notes` |
| `table` | Tabular data grid | `title`, `columns`, `rows`, `speaker_notes` |
| `chart` | Data visualization | `title`, `chart` (`kind`: `bar`/`line`/`pie`, `categories`, `series`), `speaker_notes` |
| `timeline` | Milestone roadmap | `title`, `items` (array of `{date, title, description, status}`), `speaker_notes` |
| `metrics` | KPI big numbers | `title`, `metrics` (array of `{value, label, delta, trend}`), `speaker_notes` |
| `comparison` | Comparative cards | `title`, `left`, `right` (or `columns`), `speaker_notes` |
| `blank` | Clean canvas | optional `speaker_notes` |

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md)

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("creative/deck_builder")
skill = bundle["class"]()

spec = {
    "title": "Quarterly Briefing",
    "template_id": "pitch_v1",
    "slides": [
        {"type": "title", "title": "Quarterly Briefing", "subtitle": "Executive Overview"},
        {"type": "bullets", "title": "Highlights", "bullets": ["Revenue up 24%", "Shipped 12 skills"]},
    ],
}

# Pre-flight validation
val = skill.execute({"action": "validate_spec", "deck_spec": spec})
print("Valid:", val["valid"])

# Render presentation
result = skill.execute({"action": "render", "deck_spec": spec, "output_path": "briefing.pptx"})
print("Rendered:", result["output_path"], result["slide_count"], "slides")
```

### Gemini

```python
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("creative/deck_builder")
skill = bundle["class"]()
tool = SkillLoader.to_gemini_tool(bundle)
client = genai.Client()
response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents="Assemble a deck specification into a presentation.",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call:
        result = skill.execute(dict(part.function_call.args))
        print(result.get("valid"), result.get("output_path"), result.get("slide_count"))
```

### Claude

```python
import os
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("creative/deck_builder")
skill = bundle["class"]()
tool = SkillLoader.to_claude_tool(bundle)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    system=bundle["instructions"],
    tools=[tool],
    messages=[{"role": "user", "content": "Assemble a 5-slide investor pitch deck for our AI platform."}],
)
for block in response.content:
    if block.type == "tool_use":
        result = skill.execute(dict(block.input))
        print(result.get("valid"), result.get("output_path"), result.get("slide_count"))
```

### OpenAI

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("creative/deck_builder")
skill = bundle["class"]()
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": "Build a quarterly review presentation with a revenue chart."},
    ],
    tools=[openai_tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result.get("valid"), result.get("output_path"), result.get("slide_count"))
```

### DeepSeek

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("creative/deck_builder")
skill = bundle["class"]()
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": "Validate and render a technical architecture deck."},
    ],
    tools=[deepseek_tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result.get("valid"), result.get("output_path"), result.get("slide_count"))
```

### Ollama (prompt mode)

```python
import json
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("creative/deck_builder")
skill = bundle["class"]()
deck_spec = {
    "title": "Quarterly Briefing",
    "template_id": "pitch_v1",
    "slides": [
        {"type": "title", "title": "Quarterly Briefing", "subtitle": "Executive Overview"},
    ],
}
prompt = (
    "You may call tools as JSON blocks.\n"
    f"Tool: {bundle['manifest']['name']}\n"
    f"Instructions:\n{bundle['instructions']}\n"
    "User: Validate this deck spec before rendering."
)
print(prompt)
result = skill.execute({"action": "validate_spec", "deck_spec": deck_spec})
print(json.dumps(result, indent=2))
```

### Skill Chaining (with `creative/bg_remover`)

Compose with other skills using host orchestration or `SkillContext` (see [Skill chaining](../usage/skill_chaining.md)). For example, bootstrap an archetype outline, remove backgrounds from brand logos with [`creative/bg_remover`](bg_remover.md), evaluate deck quality gates (`lint_deck`), and assemble the final presentation (see full runnable script in [`examples/deck_builder_chain_demo.py`](../../examples/deck_builder_chain_demo.py)):

```python
from skillware import SkillContext

ctx = SkillContext(skills=["creative/bg_remover", "creative/deck_builder"])

# Step 1: Suggest outline via archetype
outline = ctx.execute(
    "creative/deck_builder",
    {
        "action": "suggest_outline",
        "archetype": "product_launch",
        "topic": "Skillware Autonomous Runtime",
        "constraints": ["no pricing"],
    },
)
deck_spec = outline["deck_spec_skeleton"]

# Step 2: Strip background from brand mark
bg_res = ctx.execute("creative/bg_remover", {"input_path": "assets/raw_logo.png"})
deck_spec["slides"][0]["image"] = {
    "base64": bg_res["image_base64"],
    "mime_type": "image/png",
    "fit": "contain",
}

# Step 3: Run presentation quality linting
lint_res = ctx.execute("creative/deck_builder", {"action": "lint_deck", "deck_spec": deck_spec, "min_score": 80})
assert lint_res["passed"] is True, f"Quality gate failed: score={lint_res['score']}"

# Step 4: Render final presentation
render_res = ctx.execute(
    "creative/deck_builder",
    {"action": "render", "deck_spec": deck_spec, "output_path": "launch_deck.pptx"},
)
print("Rendered:", render_res["output_path"], "with", render_res["slide_count"], "slides (score:", lint_res["score"], ")")
```

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`creative/deck_builder`](https://github.com/ARPAHLS/skillware/tree/main/skills/creative/deck_builder)).

| Commit | Description | Date | Version | Contributors |
| [`8c0f64f`](https://github.com/ARPAHLS/skillware/commit/8c0f64f) | feat(creative): deck_builder v0.2.0 baseline — placeholders, quality linting, archetypes, and new layouts (#336) | 4 Sep 2026 | `0.2.0` | [@tusharjamunkar](https://github.com/tusharjamunkar) |
| [`1903f30`](https://github.com/ARPAHLS/skillware/commit/1903f30f32bd75567270058f3b255452d8bddd97) | feat(creative): add deck_builder skill for deterministic PPTX assembly (#276) (#331) | 4 Sep 2026 | `0.1.0` | [@tusharjamunkar](https://github.com/tusharjamunkar) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.
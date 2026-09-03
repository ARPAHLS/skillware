# Deck Builder

**ID**: `creative/deck_builder`  
**Issuer**: [@tusharjamunkar](https://github.com/tusharjamunkar) ([@ARPAHLS](https://github.com/ARPAHLS))  
<!-- skill-doc-meta:begin -->
**Version**: `0.1.0`
<!-- skill-doc-meta:end -->

**Recommended install:** `pip install "skillware[creative_deck_builder]"`. See [Install extras](../usage/install_extras.md).  
**Category**: Creative

[Skill Library](README.md) · [Testing](../TESTING.md)

Deterministic, offline assembly of Microsoft PowerPoint (`.pptx`) presentations from structured JSON deck specifications. Supports multi-slide layouts (title, section, bullets, two-column, image, image with caption, quote, table, chart, blank), custom theme token overrides, speaker notes, and pre-flight validation.

## Capabilities

- **Deterministic Assembly**: Generates standard editable `.pptx` documents without remote network calls or image generation APIs.
- **10 Layout Types**: Supports cover titles, section headers, bullet lists, two-column comparisons, images, image captions, pull-quotes, tables, native OpenXML charts (bar, line, pie), and blank canvases.
- **Pre-flight Validation (`validate_spec`)**: Validates JSON specifications against strict JSON Schema and flags soft-limit warnings (e.g. text truncations, missing assets) before writing to disk.
- **Widescreen 16:9 Templates**: Bundles 3 distinct master templates (`pitch_v1`, `corporate_v1`, `minimal_v1`) with configurable font and accent color tokens.
- **Inspection (`inspect`)**: Examines existing `.pptx` files and extracts slide counts, layout hints, titles, and speaker notes presence.
- **Asset Normalization**: Ingests local file paths or Base64 image payloads with Pillow validation and directory traversal defenses.

## Actions

| Action | Parameters | Description |
| :--- | :--- | :--- |
| `validate_spec` *(default)* | `deck_spec`, `strict` *(optional)* | Validates `deck_spec` against JSON schema and business rules without writing files. |
| `render` | `deck_spec`, `output_path`, `template_id` *(optional)*, `theme` *(optional)*, `strict` *(optional)* | Assembles slides, applies theme tokens, inserts images/charts, writes `.pptx` to disk. |
| `inspect` | `input_path` | Reads an existing `.pptx` presentation and returns slide counts, titles, layout names, and notes presence. |
| `list_templates` | *(none)* | Enumerates bundled template IDs, names, descriptions, and aspect ratios. |

## Slide Layouts

| Type | Description | Key Fields |
| :--- | :--- | :--- |
| `title` | Cover slide | `title`, `subtitle`, optional `image`, optional `speaker_notes` |
| `section` | Section divider | `title`, optional `subtitle`, optional `speaker_notes` |
| `bullets` | Bulleted takeaways | `title`, `bullets` (array of strings; >120 chars emits warning), `speaker_notes` |
| `two_column` | Comparison / two-panel layout | `title`, `left` (text/bullets), `right` (text/bullets), `speaker_notes` |
| `image` | Visual showcase | `title`, `image` (path or base64), optional `caption`, `speaker_notes` |
| `image_caption` | Image with side text | `title`, `image`, `body` (explanatory text), `speaker_notes` |
| `quote` | Pull quote | `quote`, `attribution`, `speaker_notes` |
| `table` | Tabular data grid | `title`, `columns`, `rows`, `speaker_notes` |
| `chart` | Data visualization | `title`, `chart` (`kind`: `bar`/`line`/`pie`, `categories`, `series`), `speaker_notes` |
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

### Claude (Anthropic Tool Use)

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
    model="claude-3-7-sonnet-20250219",
    max_tokens=1024,
    tools=[tool],
    messages=[{"role": "user", "content": "Assemble a 5-slide investor pitch deck for our AI platform."}],
)
```

### OpenAI (Function Calling)

```python
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
    model="gpt-4o",
    tools=[openai_tool],
    messages=[{"role": "user", "content": "Build a quarterly review presentation with a revenue chart."}],
)
```

### DeepSeek

```python
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
    tools=[deepseek_tool],
    messages=[{"role": "user", "content": "Validate and render a technical architecture deck."}],
)
```

### Ollama (Local LLMs)

Prompt-based tool calling or system prompt injection. Pull a model such as `gemma3` or `qwen3.5`, then follow [Ollama usage](../usage/ollama.md):

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("creative/deck_builder")
system_tool_prompt = SkillLoader.to_ollama_prompt(bundle)
```

### Gemini

```python
import os
import google.genai as genai
from skillware.core.loader import SkillLoader
from skillware.core.env import load_env_file

load_env_file()
bundle = SkillLoader.load_skill("creative/deck_builder")
tool = SkillLoader.to_gemini_tool(bundle)
skill = bundle["class"]()
client = genai.Client(api_key=os.environ["GOOGLE_API_KEY"])

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Assemble a deck specification into a presentation.",
    config=genai.types.GenerateContentConfig(tools=[tool]),
)
```

### Skill Chaining (with `creative/bg_remover`)

Compose with other skills using host orchestration or `SkillContext` (see [Skill chaining](../usage/skill_chaining.md)). For example, remove backgrounds from brand logos or product photos with [`creative/bg_remover`](bg_remover.md) before passing the transparent PNG into `creative/deck_builder`:

```python
from skillware import SkillContext

ctx = SkillContext(skills=["creative/bg_remover", "creative/deck_builder"])

# Step 1: Strip background from raw logo or product image
bg_res = ctx.execute("creative/bg_remover", {"input_path": "assets/raw_logo.jpg"})

# Step 2: Assemble presentation using the transparent PNG
deck_spec = {
    "title": "Product Launch",
    "template_id": "pitch_v1",
    "slides": [
        {
            "type": "title",
            "title": "Autonomous Infrastructure",
            "subtitle": "Q4 Executive Review",
            "image": {"base64": bg_res["image_base64"], "mime_type": "image/png"},
        },
        {
            "type": "bullets",
            "title": "Highlights",
            "bullets": ["100% offline assembly", "Deterministic slide layout"],
        },
    ],
}
render_res = ctx.execute(
    "creative/deck_builder",
    {"action": "render", "deck_spec": deck_spec, "output_path": "launch_deck.pptx"},
)
print("Rendered:", render_res["output_path"], "with", render_res["slide_count"], "slides")
```

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`creative/deck_builder`](https://github.com/ARPAHLS/skillware/tree/main/skills/creative/deck_builder)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`0db53ba`](https://github.com/ARPAHLS/skillware/commit/0db53ba) | feat(creative): add deck_builder skill for deterministic PPTX assembly (#276) | 4 Sep 2026 | 0.1.0 | [@tusharjamunkar](https://github.com/tusharjamunkar) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.
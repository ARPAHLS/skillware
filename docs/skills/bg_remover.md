# Background Remover

**ID**: `creative/bg_remover`
**Issuer**: [@AyushSrivastava1818](https://github.com/AyushSrivastava1818)

**Recommended install:** `pip install "skillware[creative_bg_remover]"`. See [Install extras](../usage/install_extras.md).
**Category**: Creative

[Skill Library](README.md) · [Testing](../TESTING.md)

Deterministic, local background removal for still images using [rembg](https://github.com/danielgatis/rembg). Accepts Base64 image data or local file paths and returns transparent PNG output. No cloud credentials are required for the skill itself; provider API keys are only needed for the agent integration examples below.

## Capabilities

- Removes image backgrounds locally using `rembg`
- Accepts Base64 images or local file paths
- Produces transparent PNG output with width and height metadata
- Supports configurable `model` and optional `alpha_matting`
- Works offline after the initial ONNX model download

## Dependencies and first run

Two-step cost for operators:

1. **Install runtime packages** — `pip install "skillware[creative_bg_remover]"` (or `pip install "skillware[creative]"` for the whole category).
2. **First `execute()`** — downloads the selected ONNX model (~176 MB for `isnet-general-use`) to the rembg cache (`~/.u2net/` on Linux/macOS, `%USERPROFILE%\.u2net\` on Windows). Later runs reuse the cache and are much faster.

Unit tests mock `rembg` and do not download ONNX models in CI.

## Integration Guide

### Environment

This skill does not require API keys or cloud credentials.

```bash
pip install "skillware[creative_bg_remover]"
```

Provider API keys are only required when using the provider integration examples below.

## Input Parameters

| Parameter | Required | Description |
| :--- | :---: | :--- |
| `image` | No* | Base64-encoded still image (preferred for chat/upload handoff) |
| `input_path` | No* | Absolute or relative path to a local still image file |
| `output_path` | No | Optional path to write PNG; if omitted, use `image_base64` from the result |
| `model` | No | rembg model (`isnet-general-use`, `u2net`, `u2net_human_seg`, `silueta`; default `isnet-general-use`) |
| `alpha_matting` | No | Enable alpha matting when supported by the installed rembg version |

\* One of `image` or `input_path` is required. If both are sent, `image` wins.

## Model selection

| Use case | Suggested `model` | Notes |
| :--- | :--- | :--- |
| Products, logos, general scenes (default) | `isnet-general-use` | Best default for most requests |
| People, portraits, human subjects | `u2net_human_seg` | Prefer when the subject is a person |
| Legacy / simple scenes | `u2net` or `silueta` | Optional fallback models |
| Hair, fur, glass, fine edges | any model + `alpha_matting: true` | Slower; use when edge quality matters |

Agent routing details live in `skills/creative/bg_remover/instructions.md`.

## Output Schema

| Field | Description |
| :--- | :--- |
| `success` | `true` when processing completed; `false` on validation or runtime errors |
| `image_base64` | Base64-encoded transparent PNG (always set on success) |
| `mime_type` | Output MIME type (`image/png`) |
| `output_path` | Echo of the requested output path when provided |
| `width` | Output image width in pixels |
| `height` | Output image height in pixels |
| `model_used` | rembg model used for processing |
| `error` | Human-readable error message when `success` is `false` |
| `error_code` | `INVALID_INPUT`, `MISSING_DEPENDENCY`, or `PROCESSING_FAILED` |

## Input scenarios

| Scenario | Example payload |
| :--- | :--- |
| Chat / upload / attachment handoff | `{"image": "<base64>"}` |
| Local file | `{"input_path": "/path/to/product.png"}` |
| Save to disk | `{"input_path": "product.png", "output_path": "product_no_bg.png"}` |
| URL (agent pre-step) | Agent downloads `https://example.com/photo.jpg` → temp file, then `{"input_path": "/tmp/photo.jpg", "output_path": "/tmp/photo_no_bg.png"}` |

## Output scenarios

| Scenario | Agent behavior |
| :--- | :--- |
| User wants a file on disk | Set `output_path`; prefer `{stem}_no_bg.png` beside the source unless the user specifies otherwise |
| Chat / API only | Omit `output_path`; decode or display `image_base64` |
| Save next to original | Same directory, new filename (e.g. `1223_no_bg.png`); do not overwrite the source unless asked |

## Cloud storage workflows

The skill does not call cloud APIs. The host agent downloads objects to temp files, invokes the skill locally, then uploads results.

| Provider | Workflow |
| :--- | :--- |
| **AWS S3** | GetObject → `/tmp/in.png` → `execute({input_path, output_path})` → PutObject from `output_path` |
| **Google Cloud Storage** | Download object → temp file → `execute({input_path, output_path})` → upload PNG |
| **Azure Blob** | Download blob → temp file → `execute({input_path, output_path})` → upload PNG |
| **Cloudflare R2** | Download object → temp file → `execute({input_path, output_path})` → upload PNG |

Example execute payload after download:

```json
{
  "input_path": "/tmp/input.png",
  "output_path": "/tmp/output.png"
}
```

## Internal Architecture

The skill lives in `skills/creative/bg_remover/`.

### The Mind (`instructions.md`)

Skill instructions: when to invoke, input/output conventions, URL and cloud pre-steps, model selection, and error codes.

### The Body (`skill.py`)

Lazy-imports `rembg` and Pillow, runs `new_session` + `remove`, and returns structured JSON with transparent PNG bytes.

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [API keys](../usage/api_keys.md)

Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].ClassName()` also works.

### Runnable examples

See [examples/README.md](../../examples/README.md) for the current runnable-script inventory. There is no dedicated runnable example for this skill yet; the Claude, OpenAI, and DeepSeek sections below are **catalog snippets only** (same pattern as [PDF Form Filler](pdf_form_filler.md)).

Sample user request:

> Remove the background from `product.png` and save the transparent PNG as `product_no_bg.png`.

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("creative/bg_remover")
skill = bundle["class"]()

result = skill.execute({
    "input_path": "product.png",
    "output_path": "product_no_bg.png",
})
print(result)
```

### Gemini

```python
import google.genai as genai
from google.genai import types

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()

bundle = SkillLoader.load_skill("creative/bg_remover")
skill = bundle["class"]()

client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
tool_name = SkillLoader._sanitize_gemini_tool_name(
    bundle["manifest"]["name"]
)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=(
        "Remove the background from product.png and save the result "
        "as product_no_bg.png."
    ),
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)

for part in response.candidates[0].content.parts:
    if part.function_call and part.function_call.name == tool_name:
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

Catalog snippets only — no dedicated runnable example yet.

```python
import os
import anthropic

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()

bundle = SkillLoader.load_skill("creative/bg_remover")
skill = bundle["class"]()

client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
)

tools = [SkillLoader.to_claude_tool(bundle)]

# On tool_use:
# result = skill.execute(tool_use.input)
# Return the tool result to Claude.
```

### OpenAI

Catalog snippets only — no dedicated runnable example yet.

```python
import os
from openai import OpenAI

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()

bundle = SkillLoader.load_skill("creative/bg_remover")
skill = bundle["class"]()

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

tool = SkillLoader.to_openai_tool(bundle)

# Match tool_call.function.name and execute:
# result = skill.execute(args)
```

### DeepSeek

Catalog snippets only — no dedicated runnable example yet.

```python
import os
from openai import OpenAI

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()

bundle = SkillLoader.load_skill("creative/bg_remover")
skill = bundle["class"]()

client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

tool = SkillLoader.to_deepseek_tool(bundle)

# Match tool_call.function.name and execute:
# result = skill.execute(args)
```

### Ollama (prompt mode)

```python
import json

from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("creative/bg_remover")
skill = bundle["class"]()

prompt = SkillLoader.to_ollama_prompt(bundle)

print(prompt)
print("User: Remove the background from product.png and save it as product_no_bg.png.")

# When the model emits JSON tool arguments,
# pass them to execute():

result = skill.execute({
    "input_path": "product.png",
    "output_path": "product_no_bg.png",
})

print(json.dumps(result, indent=2))
```

## Limitations

- Still images only (no video or batch folder processing)
- First execution downloads the selected ONNX model
- Output quality depends on the selected `rembg` model
- The skill does not fetch URLs or cloud objects directly

---

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own workflows and image-processing requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

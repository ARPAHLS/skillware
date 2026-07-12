# Background Remover

**Domain:** `creative`
**Skill ID:** `creative/bg_remover`
**Issuer:** [@AyushSrivastava1818](https://github.com/AyushSrivastava1818)

[Skill Library](README.md) · [Testing](../TESTING.md)

## Overview

`creative/bg_remover` is a deterministic image-processing skill that removes the background from still images locally using `rembg`. It accepts Base64 image data or local image paths and produces transparent PNG output without requiring cloud services after the initial ONNX model download.

## Capabilities

- Removes image backgrounds locally using `rembg`
- Accepts Base64 images or local file paths
- Produces transparent PNG output
- Supports optional `alpha_matting`
- Works completely offline after the initial ONNX model download

## Integration Guide

### Environment

This skill does not require API keys or cloud credentials.

Install runtime dependencies:

```bash
pip install rembg pillow onnxruntime

The first execution downloads the selected ONNX model (approximately 176 MB). Once cached, subsequent executions are fully offline.

Provider API keys are only required when using the provider integration examples below.

```

## Input Parameters

| Parameter | Required | Description |
| :--- | :---: | :--- |
| `image` | No | Base64-encoded input image |
| `input_path` | No | Local input image path |
| `output_path` | No | Local output PNG path |
| `model` | No | Optional rembg model |
| `alpha_matting` | No | Enable alpha matting if supported |

## Output Schema

| Field | Description |
| :--- | :--- |
| `success` | Indicates whether processing completed successfully |
| `image_base64` | Base64-encoded PNG when `output_path` is not provided |
| `mime_type` | Output MIME type (`image/png`) |
| `width` | Output image width |
| `height` | Output image height |
| `model_used` | rembg model used for processing |

## Input and Output Recipes

### Base64 input

```json
{
  "image": "<base64>"
}
```

### Local file input

```json
{
  "input_path": "input.png"
}
```

### Save output locally

```json
{
  "input_path": "input.png",
  "output_path": "output.png"
}
```

## Data Schema

```json
{
  "success": true,
  "image_base64": "<base64_png>",
  "mime_type": "image/png",
  "width": 1024,
  "height": 768,
  "model_used": "u2net"
}
```

## Internal Architecture

The skill lives in `skills/creative/bg_remover/`.

### The Mind (`instructions.md`)

Guides the host agent on when to invoke the skill, accepted inputs, and expected output.

### The Body (`skill.py`)

Processes still images locally using `rembg`, supports Base64 and file-based workflows, and returns transparent PNG output.

## Cloud Storage Recipes

### AWS S3

Download the source image from S3 to a local temporary file, execute the skill using `input_path`, then upload the generated PNG from `output_path` back to S3.

```json
{
  "input_path": "/tmp/input.png",
  "output_path": "/tmp/output.png"
}
```

### Google Cloud Storage

Download the object from GCS, process it locally with `input_path`, then upload the generated PNG.

```json
{
  "input_path": "/tmp/input.png",
  "output_path": "/tmp/output.png"
}
```

### Azure Blob Storage

Download the blob to local storage before invoking the skill and upload the generated PNG afterwards.

```json
{
  "input_path": "/tmp/input.png",
  "output_path": "/tmp/output.png"
}
```

### Cloudflare R2

Download the object locally, invoke the skill, then upload the resulting transparent PNG back to the bucket.

```json
{
  "input_path": "/tmp/input.png",
  "output_path": "/tmp/output.png"
}
```

## Notes

- Runs completely offline after the required model is available.
- The first execution downloads the required ONNX model (approximately 176 MB). Later executions reuse the cached model and work completely offline.
- Unit tests mock `rembg` and do not download ONNX models.
- The optional `model` and `alpha_matting` parameters are forwarded to `rembg` when supported by the installed version.

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [API keys](../usage/api_keys.md)

Use `bundle["class"]()` in the snippets below.

### Runnable examples

See [examples/README.md](../../examples/README.md) for the current runnable provider examples.

Sample user request:

> Remove the background from `product.png` and save the transparent PNG.

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("creative/bg_remover")
skill = bundle["class"]()

result = skill.execute({
    "input_path": "product.png",
    "output_path": "product_no_bg.png",
})
```

print(result)

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

- Supports still images only.
- Video processing is not supported.
- Batch processing is not supported.
- The first execution downloads the selected ONNX model.
- Output quality depends on the selected `rembg` model.

---

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own workflows and image-processing requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.
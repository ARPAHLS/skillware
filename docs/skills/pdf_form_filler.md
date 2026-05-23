# PDF Form Filler Skill

**ID**: `office/pdf_form_filler`
**Issuer**: [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))

[Skill Library](README.md) · [Testing](../TESTING.md)

A productivity skill that fills AcroForm-based PDFs by mapping natural language instructions to detected form fields using semantic understanding.

## Capabilities

*   **Smart Field Detection**: Automatically identifies text fields, checkboxes, radio buttons, and dropdowns in standard PDFs.
*   **Semantic Mapping**: Uses an internal LLM (Claude) to understand user instructions (e.g., "Sign me up for the newsletter") and map them to the correct field (e.g., `checkbox_subscribe_newsletter`).
*   **Context Awareness**: Extracts nearby text labels to ensure accurate mapping, even if field names are obscure (e.g., `field_123` vs label "First Name").
*   **Type Safety**: Automatically converts values to the correct format (booleans for checkboxes, specific options for dropdowns).

## Internal Architecture

The skill is self-contained in `skills/office/pdf_form_filler/`.

### 1. The Mind (`instructions.md`)
The system prompt teaches the internal mapping engine to:
*   Analyze the provided "User Instructions".
*   Review the list of "Detected Fields" (ID, Type, Context, Options).
*   Output a strict JSON mapping of `Field ID -> Value`.
*   Handle ambiguities by preferring precision over guessing.

### 2. The Body (`skill.py` & `utils.py`)
*   **PDF Processing**: Uses `PyMuPDF` (fitz) for high-fidelity rendering and widget manipulation.
*   **LLM Integration**: Wraps the Anthropic SDK to perform the semantic reasoning step.
*   **Validation**: Ensures values match the field type (e.g., selecting a valid option from a dropdown).

## Integration Guide

### Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `ANTHROPIC_API_KEY` | Yes | Claude API for semantic field mapping |

Configure values per [API keys for skills](../usage/api_keys.md).

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [API keys](../usage/api_keys.md).

| Provider | Reference script |
| :--- | :--- |
| Gemini | `examples/gemini_pdf_form_filler.py` |
| Claude | `examples/claude_pdf_form_filler.py` |

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("office/pdf_form_filler")
filler = bundle["module"].PDFFormFillerSkill()
result = filler.execute({
    "pdf_path": "/absolute/path/to/form.pdf",
    "instructions": "Name: John Doe. Check the terms of service box.",
})
print(result["output_path"])
```

### Gemini

```python
import os
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("office/pdf_form_filler")
skill = bundle["module"].PDFFormFillerSkill()
client = genai.Client()
# User: "Fill /path/to/form.pdf — name John Doe, check the terms box."
tool = SkillLoader.to_gemini_tool(bundle)
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Fill /path/to/form.pdf — name John Doe, check the terms box.",
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
bundle = SkillLoader.load_skill("office/pdf_form_filler")
skill = bundle["module"].PDFFormFillerSkill()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
# On tool_use (name pdf_form_filler): skill.execute(tool_use.input), return tool_result
```

### OpenAI

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("office/pdf_form_filler")
skill = bundle["module"].PDFFormFillerSkill()
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# Match tool_call.function.name to openai_tool["function"]["name"] (pdf_form_filler)
```

### DeepSeek

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("office/pdf_form_filler")
skill = bundle["module"].PDFFormFillerSkill()
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
```

### Ollama

`SkillLoader.to_ollama_prompt(bundle)`; match `"tool": "pdf_form_filler"`. See [Ollama usage](../usage/ollama.md).

## Data Schema

The skill returns a JSON object with the result of the operation.

```json
{
  "status": "success",
  "output_path": "/path/to/form_filled.pdf",
  "filled_fields": [
    "page0_full_name",
    "page0_terms_check"
  ],
  "message": "Successfully filled 2 fields."
}
```

## Limitations

*   **AcroForms Only**: Does not support XFA forms or non-interactive "flat" PDFs.
*   **LLM Dependency**: Requires an active internet connection and valid API key for the semantic mapping step.

---

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

# PDF Form Filler Skill

**ID**: `office/pdf_form_filler`
**Issuer**: [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
**Version**: `0.1.0` — 16 Jul 2026
<!-- skill-doc-meta:end -->

**Recommended install:** `pip install "skillware[office_pdf_form_filler]"`. See [Install extras](../usage/install_extras.md).
[Skill Library](README.md) · [Testing](../TESTING.md)

A productivity skill that fills AcroForm-based PDFs by mapping natural language instructions to detected form fields using semantic understanding.

## Capabilities

*   **Smart Field Detection**: Automatically identifies text fields, checkboxes, radio buttons, and dropdowns in standard PDFs.
*   **Semantic Mapping**: Uses an internal LLM (Claude) to understand user instructions (e.g., "Sign me up for the newsletter") and map them to the correct field (e.g., `checkbox_subscribe_newsletter`).
*   **Context Awareness**: Extracts nearby text labels to ensure accurate mapping, even if field names are obscure (e.g., `field_123` vs label "First Name").
*   **Type Safety**: Automatically converts values to the correct format (booleans for checkboxes, specific options for dropdowns).

## Bundle layout

The skill is self-contained in `skills/office/pdf_form_filler/`. [Skill anatomy](../introduction.md#skill-anatomy). **Contract** — see Manifest Details above. **Assurance** — `test_skill.py` in the bundle.

### Directive (`instructions.md`)
The system prompt teaches the internal mapping engine to:
*   Analyze the provided "User Instructions".
*   Review the list of "Detected Fields" (ID, Type, Context, Options).
*   Output a strict JSON mapping of `Field ID -> Value`.
*   Handle ambiguities by preferring precision over guessing.

### Effect (`skill.py` & `utils.py`)
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


Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].ClassName()` also works.

### Runnable examples

See [examples/README.md](../../examples/README.md) for the current runnable-script inventory. The dedicated runnable scripts today are `examples/gemini_pdf_form_filler.py` and `examples/claude_pdf_form_filler.py`. The OpenAI, DeepSeek, and Ollama sections below are catalog snippets only unless separate runnable examples are added later.

| Provider | Reference script |
| :--- | :--- |
| Gemini | `examples/gemini_pdf_form_filler.py` |
| Claude | `examples/claude_pdf_form_filler.py` |

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("office/pdf_form_filler")
filler = bundle["class"]()
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
skill = bundle["class"]()
client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
tool_name = SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"])
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Fill /path/to/form.pdf — name John Doe, check the terms box.",
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
bundle = SkillLoader.load_skill("office/pdf_form_filler")
skill = bundle["class"]()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
# On tool_use, match name against bundle["manifest"]["name"] (office/pdf_form_filler):
# skill.execute(tool_use.input), return tool_result
```

### OpenAI

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("office/pdf_form_filler")
skill = bundle["class"]()
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# Match tool_call.function.name to openai_tool["function"]["name"] (office_pdf_form_filler)
```

### DeepSeek

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("office/pdf_form_filler")
skill = bundle["class"]()
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
# Match tool_call.function.name to deepseek_tool["function"]["name"] (office_pdf_form_filler)
```

### Ollama

`SkillLoader.to_ollama_prompt(bundle)`; match `"tool": "office/pdf_form_filler"`. See [Ollama usage](../usage/ollama.md).

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

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`office/pdf_form_filler`](https://github.com/ARPAHLS/skillware/tree/main/skills/office/pdf_form_filler)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`f158fd8`](https://github.com/ARPAHLS/skillware/commit/f158fd844ca2a586ae87d286ffa12d619a999ebf) | docs: adopt Skill anatomy vocabulary on catalog page (#319) | 1 Sep 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`bca8181`](https://github.com/ARPAHLS/skillware/commit/bca8181) | Add category and per-skill pip extras with manifest sync (#236). (#256) | 16 Jul 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`4814478`](https://github.com/ARPAHLS/skillware/commit/4814478) | Fix: to_gemini_tool to return types.Tool object. Fixes #223 (#229) | 10 Jul 2026 | `0.1.0` | [@Areen-09](https://github.com/Areen-09) |
| [`0d550d0`](https://github.com/ARPAHLS/skillware/commit/0d550d0) | docs: sweep vision, bundle class usage, and README Mermaid | 8 Jul 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`91bef48`](https://github.com/ARPAHLS/skillware/commit/91bef48) | docs: document manifest ID alignment and provider tool names (#201) | 1 Jul 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`673e227`](https://github.com/ARPAHLS/skillware/commit/673e227) | fix: align pdf_form_filler and evm_tx_handler manifest names with registry paths | 1 Jul 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`0f81d1f`](https://github.com/ARPAHLS/skillware/commit/0f81d1f) | Backfill bundle tests for six registry skills missing test_skill.py. | 10 Jun 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`5b68b78`](https://github.com/ARPAHLS/skillware/commit/5b68b78) | Feat/issue 93 cli visual redesign (#129) | 26 May 2026 | `0.1.0` | [@rizzoMartin](https://github.com/rizzoMartin) |
| [`52cce29`](https://github.com/ARPAHLS/skillware/commit/52cce29) | docs: clarify runnable examples across skill pages (#121) | 24 May 2026 | `0.1.0` | [@narutamaaurum](https://github.com/narutamaaurum) |
| [`a3a7ac8`](https://github.com/ARPAHLS/skillware/commit/a3a7ac8) | docs: update Gemini snippets to google-genai (#92) | 23 May 2026 | `0.1.0` | [@kunal-9090](https://github.com/kunal-9090) |
| [`cca7334`](https://github.com/ARPAHLS/skillware/commit/cca7334) | docs: skill docs revamp — remove emojis, add breadcrumbs, fix index, add missing sections (closes #52) (#82) | 21 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`e465dc4`](https://github.com/ARPAHLS/skillware/commit/e465dc4) | Fix skill path resolution and PyPI skill packaging. (#79) | 18 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`5b18e21`](https://github.com/ARPAHLS/skillware/commit/5b18e21) | Document per-skill usage examples across providers. | 17 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`39487f8`](https://github.com/ARPAHLS/skillware/commit/39487f8) | Add generic API keys guide for skills requiring external calls. | 17 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`f800f41`](https://github.com/ARPAHLS/skillware/commit/f800f41) | Add skill issuer attribution across registry and docs. | 17 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`e658e7e`](https://github.com/ARPAHLS/skillware/commit/e658e7e) | docs: update enterprise disclaimer heading and scope to ARPA catalog skills only | 16 May 2026 | `0.1.0` | [@shaansatsangi](https://github.com/shaansatsangi) |
| [`891f5cc`](https://github.com/ARPAHLS/skillware/commit/891f5cc) | docs: add standard enterprise disclaimer to all skill documentation pages (#59) | 16 May 2026 | `0.1.0` | [@shaansatsangi](https://github.com/shaansatsangi) |
| [`b6b8180`](https://github.com/ARPAHLS/skillware/commit/b6b8180) | feat: Make Skillware pip-installable and add release workflow (closes #7) | 15 Feb 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`3838724`](https://github.com/ARPAHLS/skillware/commit/3838724) | feat: Add automated testing and strict linting (closes #8) | 15 Feb 2026 | `—` | [@rosspeili](https://github.com/rosspeili) |
| [`34e966c`](https://github.com/ARPAHLS/skillware/commit/34e966c) | feat(skills): add pdf_form_filler skill (Fixes #4) | 15 Feb 2026 | `—` | [@rosspeili](https://github.com/rosspeili) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

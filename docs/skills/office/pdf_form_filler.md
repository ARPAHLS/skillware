# PDF Form Filler Skill

**ID**: `office/pdf_form_filler`
**Issuer**: [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
**Version**: `0.1.2` — 16 Oct 2026
<!-- skill-doc-meta:end -->
<!-- skill-intent:begin -->
**Solves:** Inspect, validate, and fill AcroForm PDFs deterministically with XFA guards, radio group handling, and vector flattening.
**Works with:** Gemini, Claude, OpenAI, DeepSeek, Ollama, and Bedrock-compatible host loops.
**Runtime:** 100% offline local Python execution with PyMuPDF. No mandatory external API keys required.
<!-- skill-intent:end -->

**Recommended install:** `pip install "skillware[office_pdf_form_filler]"`. See [Install extras](../../usage/install_extras.md).
[Skill Library](../README.md) · [Office](README.md) · [Testing](../../TESTING.md)

A deterministic productivity skill that inspects, validates, and fills AcroForm-based PDFs using structured multi-action dispatch, XFA dynamic form guards, and vector flattening.

## Capabilities

*   **Multi-Action Protocol**: Discrete actions (`inspect`, `validate`, `fill`) giving host models full visibility and control over field discovery and form filling.
*   **XFA Dynamic Form Guard**: Early detection and graceful error handling for unsupported Adobe LiveCycle dynamic forms.
*   **Radio Button Group Normalization**: Accurately aggregates shared-name radio widgets, mapping on-state export values and nearby labels without field collision.
*   **Confirmation Safety Gate**: Enforces explicit operator confirmation (`confirmed: true`) before persisting edits to disk.
*   **Tamper-Proof Flattening**: Optional vector baking (`flatten: true`) converts interactive form fields into permanent page graphics for formal compliance submissions.

## Bundle layout

The skill is self-contained in `skills/office/pdf_form_filler/`. [Skill anatomy](../../introduction.md#skill-anatomy). Vocabulary: [glossary](../../glossary.md). **Contract** — see Manifest Details above. **Assurance** — `test_skill.py` in the bundle.

### Directive (`instructions.md`)
The directive provides operational guidance for host models to:
*   Inspect form fields and radio options (`action: "inspect"`).
*   Validate proposed edits against field types and export values (`action: "validate"`).
*   Enforce confirmation gates and optional flattening (`action: "fill"`).

### Effect (`skill.py` & `utils.py`)
*   **PDF Processing**: Uses `PyMuPDF` (fitz) for high-fidelity widget manipulation, radio button state resolution, and document flattening.
*   **Host Agnostic**: Operates 100% deterministically without internal LLM calls or vendor lock-in.
*   **Safety Guards**: Detects dynamic XFA forms and prevents unauthorized overwrites.

## Integration Guide

### Environment

None. This skill operates entirely deterministically and locally on PDF byte streams; no provider API keys or external services are required.

## Usage Examples

Guides: [Usage index](../../usage/README.md) · [Agent loops](../../usage/agent_loops.md) · [API keys](../../usage/api_keys.md).


Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].ClassName()` also works.

### Runnable examples

See [examples/README.md](../../../examples/README.md) for the current runnable-script inventory. The dedicated runnable scripts today are `examples/gemini_pdf_form_filler.py` and `examples/claude_pdf_form_filler.py`. The OpenAI, DeepSeek, and Ollama sections below are catalog snippets only unless separate runnable examples are added later.

| Provider | Reference script |
| :--- | :--- |
| Gemini | `examples/gemini_pdf_form_filler.py` |
| Claude | `examples/claude_pdf_form_filler.py` |

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("office/pdf_form_filler")
filler = bundle["class"]()

# Step 1: Inspect PDF form fields and radio options
inspect_res = filler.execute({
    "action": "inspect",
    "pdf_path": "/absolute/path/to/form.pdf",
})
print(f"Detected {inspect_res['field_count']} fields across {inspect_res['page_count']} page(s).")

# Step 2: Validate proposed edits against AcroForm constraints
edits = {
    "page0_full_name": "Jane Doe",
    "page0_agree_terms": True,
    "page0_tax_class": "Individual",
}
valid_res = filler.execute({
    "action": "validate",
    "pdf_path": "/absolute/path/to/form.pdf",
    "edits": edits,
})
assert valid_res["valid"] is True

# Step 3: Fill with confirmation gate and vector flattening
fill_res = filler.execute({
    "action": "fill",
    "pdf_path": "/absolute/path/to/form.pdf",
    "edits": edits,
    "confirmed": True,
    "flatten": True,
})
print("Filled PDF saved to:", fill_res["output_path"])
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
    model="gemini-3.5-flash",
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
bundle = SkillLoader.load_skill("office/pdf_form_filler")
skill = bundle["class"]()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
response = client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=1024,
    system=bundle["instructions"],
    tools=tools,
    messages=[{"role": "user", "content": "Fill the W-9 PDF at forms/w9.pdf with vendor details."}],
)
for block in response.content:
    if block.type == "tool_use":
        result = skill.execute(dict(block.input))
        print(result["status"])
```

### OpenAI

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("office/pdf_form_filler")
skill = bundle["class"]()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
tool = SkillLoader.to_openai_tool(bundle)
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": "Fill the W-9 PDF at forms/w9.pdf with vendor details."},
    ],
    tools=[tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result["status"])
```
### DeepSeek

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("office/pdf_form_filler")
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
        {"role": "user", "content": "Fill the W-9 PDF at forms/w9.pdf with vendor details."},
    ],
    tools=[tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result["status"])
```
### Ollama (prompt mode)

```python
import json
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("office/pdf_form_filler")
skill = bundle["class"]()
prompt = (
    "You may call tools as JSON blocks.\n"
    f"Tool: {bundle['manifest']['name']}\n"
    f"Instructions:\n{bundle['instructions']}\n"
    f"User: Fill the W-9 PDF at forms/w9.pdf with vendor details."
)
print(prompt)
result = skill.execute({
    "action": "fill",
    "pdf_path": "forms/w9.pdf",
    "field_values": {"name": "Acme Corp"},
})
print(json.dumps(result, indent=2))
```
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

*   **AcroForms Only**: Does not support dynamic XFA forms; returns explicit `unsupported_xfa_form` error for LiveCycle forms.
*   **Interactive Confirmation**: Modifying files requires explicit `confirmed: true`.

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`office/pdf_form_filler`](https://github.com/ARPAHLS/skillware/tree/main/skills/office/pdf_form_filler)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`f5942a8`](https://github.com/ARPAHLS/skillware/commit/f5942a89f01b95cbc240cdd73d7f8a6e452f2664) | Refactor into host-agnostic deterministic engine with multi-action dispatch, XFA guard, and radio groups (#403) | 16 Oct 2026 | `0.1.2` | [@rosspeili](https://github.com/rosspeili) |
| [`42df736`](https://github.com/ARPAHLS/skillware/commit/42df736318a4ee8fbf4c40bcfe1d3f3f00994fbc) | Fix pdf_form_filler helper imports without mutating sys.path (#399) | 30 Sep 2026 | `0.1.1` | [@Bdysj](https://github.com/Bdysj) |
| [`790787d`](https://github.com/ARPAHLS/skillware/commit/790787d0e72262ddfeb26f747f880012ca2b1ca6) | docs: five-provider Usage Examples guard and catalog loop backfill (#347) | 10 Sep 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
| [`12fbd1a`](https://github.com/ARPAHLS/skillware/commit/12fbd1a11bdf66250008afc59df7048935eafc73) | docs: adopt Skill anatomy vocabulary on catalog page (#319) | 1 Sep 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
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

# Agent loops with Skillware

Every integration follows the same execution pattern:

1. `bundle = SkillLoader.load_skill("<category>/<skill_name>")`
2. `skill = bundle["module"].<SkillClass>()`
3. Adapt `bundle` for the model (`to_gemini_tool`, `to_claude_tool`, etc.).
4. Pass `bundle["instructions"]` as system context.
5. On tool call, `result = skill.execute(arguments)` and return JSON to the model.

Provider guides contain full API details. Skill pages contain copy-paste examples with skill-specific paths and sample user messages.

---

## Tool name matching

| Adapter | Match tool calls using |
| :--- | :--- |
| Gemini | `manifest["name"]` (may include slashes, e.g. `compliance/tos_evaluator`) |
| Claude | `manifest["name"]` |
| OpenAI | `to_openai_tool(bundle)["function"]["name"]` (sanitized, e.g. `compliance_tos_evaluator`) |
| DeepSeek | `to_deepseek_tool(bundle)["function"]["name"]` (same sanitization rules) |
| Ollama (prompt) | `"tool"` field in the JSON block the model emits |

---

## Minimal execute (no LLM)

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("compliance/tos_evaluator")
SkillClass = bundle["module"].TOSEvaluatorSkill
result = SkillClass().execute(
    {
        "target_url": "https://example.com",
        "intended_action": "crawl documentation for research",
    }
)
print(result)
```

---

## Reference scripts

Full runnable loops live under `examples/` where listed. See the
[examples index](../../examples/README.md) for script filenames, skill IDs,
provider extras, required environment variables, and skills that do not yet
have runnable examples. Gemini reference scripts use the `google-genai` SDK
(`import google.genai`). All [skill catalog pages](../skills/README.md)
include compact **Usage Examples** per provider.

| Skill | Gemini | Claude | OpenAI | DeepSeek | Ollama |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `compliance/tos_evaluator` | `gemini_tos_evaluator.py` | `claude_tos_evaluator.py` | `openai_tos_evaluator.py` | `deepseek_tos_evaluator.py` | `ollama_tos_evaluator.py` |
| `finance/wallet_screening` | `gemini_wallet_check.py` | `claude_wallet_check.py` | (catalog page) | (catalog page) | (catalog page) |
| `office/pdf_form_filler` | `gemini_pdf_form_filler.py` | `claude_pdf_form_filler.py` | (catalog page) | (catalog page) | (catalog page) |
| `compliance/mica_module` | `mica_rag_flow.py` | `mica_claude_flow.py` | (catalog page) | (catalog page) | `mica_ollama_flow.py` |
| `compliance/pii_masker` | (catalog page) | (catalog page) | (catalog page) | (catalog page) | (catalog page) |
| Other skills | (catalog page) | (catalog page) | (catalog page) | (catalog page) | (catalog page) |

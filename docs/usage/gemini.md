# Integration Guide: Google Gemini

Skillware provides first-class support for Google's Gemini models via the `google-genai` SDK.

## ⚡ Quick Snippet

```python
from skillware.core.loader import SkillLoader
import google.genai as genai

# Load & Convert
skill = SkillLoader.load_skill("finance/wallet_screening")
tool = SkillLoader.to_gemini_tool(skill)

# Initialize the google-genai client
client = genai.Client()

# Pass tool and skill['instructions'] through GenerateContentConfig when calling
# client.models.generate_content(...).
```

## 🔍 How It Works

Gemini uses `FunctionDeclaration` objects (defined in Protobuf) to describe tools to the model.

### 1. Type Conversion
The `manifest.yaml` uses standard JSON Schema types (lowercase `string`, `object`).
Gemini requires Protobuf types (uppercase `STRING`, `OBJECT`).

`SkillLoader.to_gemini_tool()` handles this conversion automatically. It recursively walks your parameter schema and ensures it is compatible with Gemini's backend.

### 2. Context Injection
Gemini 1.5+ supports `system_instruction`. Skillware leverages this to inject the "Mind" of the skill (`instructions.md`).

This is crucial. Without `system_instruction`, the model knows it *has* a tool, but it doesn't know the nuanced strategy of *when* to use it. By injecting the instructions, you effectively fine-tune the model's behavior for that specific capability during the session.

### 3. Function Calling Loop
Gemini supports `enable_automatic_function_calling=True`.

*   **Automatic**: The SDK handles the loop. It calls your python function and sends the result back.
*   **Manual**: You receive a `Part` with `function_call`. You must execute the logic and send back a `FunctionResponse`.

## 🛠️ Advanced: Manual Execution Loop

If you need granular control (e.g., to sanitize inputs or show progress bars), use the manual loop:

```python
response = chat.send_message("Scan wallet...")

for part in response.parts:
    if fn := part.function_call:
        print(f"Model wants to call {fn.name} with {fn.args}")

        # 1. Execute Logic
        result = my_skill.execute(dict(fn.args))

        # 2. Send Result
        chat.send_message(
            genai.prototypes.Part(
                function_response=genai.prototypes.FunctionResponse(
                    name=fn.name,
                    response={'result': result}
                )
            )
        )
```
*(Note: As of Gemini SDK v0.8+, the exact import for `FunctionResponse` may vary. Using a dictionary structure is often more robust.)*

## 🔗 Skill Chaining (Middleware)

Skillware's modular design allows treating skills as deterministic offline logic blocks. For example, you can seamlessly chain the **Prompt Token Rewriter** to optimize context before hitting the LLM:

```python
# Load the middleware skill
rewriter = SkillLoader.load_skill("optimization/prompt_rewriter")
sys_prompt = "You are a very helpful assistant serving a bank..."

# Use python logic offline before starting the chat session
optimized_ctx_result = rewriter['module'].PromptRewriter().execute({
    "raw_text": sys_prompt,
    "compression_aggression": "high"
})

response = client.models.generate_content(
    model='gemini-2.5-flash',
    contents="Summarize the optimized context.",
)
```

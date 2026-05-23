# Integration Guide: Google Gemini

Skillware provides first-class support for Google's Gemini models via the `google-genai` SDK.

## ⚡ Quick Snippet

```python
import os
from skillware.core.loader import SkillLoader
import google.genai as genai
from google.genai import types

# Load & Convert
skill = SkillLoader.load_skill("finance/wallet_screening")
skill_instance = skill["module"].WalletScreeningSkill(
    config={"ETHERSCAN_API_KEY": os.environ.get("ETHERSCAN_API_KEY")}
)
tool = SkillLoader.to_gemini_tool(skill)

# Initialize the google-genai client
client = genai.Client()

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Screen wallet 0xd8dA... for risks.",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=skill["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call:
        result = skill_instance.execute(dict(part.function_call.args))
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
                system_instruction=skill["instructions"],
            ),
        )
        print(follow_up.text)
    else:
        print(part.text)
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
The `google-genai` SDK returns model parts that can include `function_call` requests.
In a manual Skillware loop, execute the matching local skill with `skill.execute(dict(part.function_call.args))`, then send a `function_response` back to Gemini so the model can produce the final answer.
If you use an automatic-calling helper in your own app, keep the same boundary: Skillware executes locally, and the tool result is returned to the model before you show a final response.

## 🛠️ Advanced: Manual Execution Loop

If you need granular control (e.g., to sanitize inputs or show progress bars), use the manual loop:

```python
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Scan wallet 0xd8dA... for risks.",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=skill["instructions"],
    ),
)

for part in response.candidates[0].content.parts:
    if fn := part.function_call:
        print(f"Model wants to call {fn.name} with {fn.args}")

        # 1. Execute Logic
        result = skill_instance.execute(dict(fn.args))

        # 2. Send Result
        follow_up = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                "Use this tool result to answer the original request.",
                {"function_response": {"name": fn.name, "response": {"result": result}}},
            ],
            config=types.GenerateContentConfig(
                tools=[tool],
                system_instruction=skill["instructions"],
            ),
        )
```

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
    config=types.GenerateContentConfig(
        system_instruction=optimized_ctx_result["compressed_text"],
    ),
)
```

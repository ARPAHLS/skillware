# Integration Guide: Anthropic Claude

Skillware is designed to integrate seamlessly with Anthropic's Claude models (Claude 3 Opus, Sonnet, Haiku) via the `anthropic` Python SDK.

## ⚡ Quick Snippet

```python
from skillware.core.loader import SkillLoader
import anthropic

client = anthropic.Anthropic()
skill = SkillLoader.load_skill("finance/wallet_screening")

# Convert to Claude Format
claude_tool = SkillLoader.to_claude_tool(skill)

message = client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=1024,
    system=skill['instructions'],  # Inject the "Mind"
    tools=[claude_tool],           # Bind the "Body"
    messages=[
        {"role": "user", "content": "Check wallet 0x123..."}
    ]
)
```

## 🔍 How It Works

Claude uses a specific JSON structure for tools:
```json
{
  "name": "my_function",
  "description": "...",
  "input_schema": { ... }
}
```

### 1. Schema Adaptation
Skillware's `manifest.yaml` uses standard JSON Schema for `parameters`.
`SkillLoader.to_claude_tool()` maps `manifest['parameters']` directly to `input_schema`, wrapping it in the correct dictionary structure that the Anthropic API expects.

### 2. System Prompt Engineering
Claude excels at following complex instructions. Skillware's `instructions.md` (The Mind) is designed to be passed directly to the `system` parameter of `messages.create()`.

This ensures Claude adopts the persona (e.g., "Senior Compliance Officer") defined by the skill author.

## 🛠️ Handling Tool Use

Claude stops generating when it wants to call a tool. You must execute and reply.

```python
if message.stop_reason == "tool_use":
    tool_use = next(b for b in message.content if b.type == "tool_use")
    
    # 1. Execute
    print(f"Calling {tool_use.name}...")
    result = my_skill.execute(tool_use.input)
    
    # 2. Reply with Result
    response = client.messages.create(
        model="claude-3-opus-20240229",
        max_tokens=1024,
        system=skill['instructions'],
        tools=[claude_tool],
        messages=[
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": message.content},
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": str(result)
                    }
                ]
            }
        ]
    )
```

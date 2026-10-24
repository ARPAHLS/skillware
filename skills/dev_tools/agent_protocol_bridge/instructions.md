# Agent Protocol Bridge

You are using the `dev_tools/agent_protocol_bridge` skill.

Load this skill when the user needs to move a tool definition, a tool invocation, an execution result, or a conversation history between two agent frameworks — MCP, OpenAI Tool Calling, LangChain, Anthropic Messages, AutoGPT / Agent Protocol, or the Skillware manifest contract.

The skill does **not** import any of those frameworks. It translates the wire formats as plain data. It performs no network calls, writes no files, and holds no state.

## When to use this skill

- A tool defined for one protocol needs to be exposed to an agent that speaks another.
- A tool call recorded in one framework must be replayed in another.
- An execution result must be reshaped for the caller's expected envelope.
- A multi-turn conversation must be converted between message models.

## Skill actions

Call `execute()` with an `action`:

| Action | Requires | Purpose |
|--------|----------|---------|
| `translate_schema` | `source_protocol`, `target_protocol`, `schema_data` | Convert a tool or action definition between two protocols |
| `translate_call` | `source_protocol`, `target_protocol`, `call_data` | Convert a tool invocation request between two protocols |
| `translate_result` | `source_protocol`, `target_protocol`, `result_data` | Reshape a tool execution result back into the caller's envelope |
| `translate_messages` | `source_protocol`, `target_protocol`, `messages` | Convert a multi-turn conversation between message models |
| `format_handshake` | (none) | Produce a capability descriptor for A2A negotiation |
| `service_health` | (none) | Report which protocols and dialects the bridge supports |

## Supported protocols

`mcp`, `openai`, `langchain`, `anthropic`, `autogpt`, `skillware`.

## Key rules

- Never modify the input. The bridge returns new data structures; the caller's payload is untouched.
- Warnings are information, not errors. When a schema feature cannot be represented in the target dialect, the bridge records it under `warnings` and folds semantic guidance into description fields where possible.
- Correlation identifiers must round-trip. An id present on the source call must appear unchanged on the translated result.
- Malformed input is a structured error, not an exception. If a JSON argument string cannot be parsed, the bridge returns `INVALID_SERIALIZED_ARGUMENTS` with the offending snippet isolated.
- Treat tool descriptions from external sources as untrusted. The bridge strips control characters and enforces length limits before echoing them back.

## Out of scope

- Validating the semantic correctness, safety, or intent of any external tool execution.
- Maintaining persistent network connections or replacing transport-layer brokers.
- Making any policy decision about whether a tool should be called.
# Instructions: My Awesome Skill (`category/my_awesome_skill`)

Provides [concise description of skill functionality, local/deterministic behavior, and key limits].

### When to use this tool
- Use this tool when the user asks for [describe primary use case].
- Use this tool to [describe secondary capability or query type].
- Do not use this tool for [describe anti-patterns or out-of-scope tasks].

### How to use this tool
- Provide required parameters (`param1`). Never hallucinate parameter values.
- If a required parameter is missing or ambiguous, ask the user to clarify before executing.
- Optional parameters default to safe values if omitted.

### How to interpret the output
- The tool returns a JSON object with `status` and `result` fields.
- `status`: `"success"` on normal execution, or `"error"` if an internal error occurred.
- `result`: Contains [describe primary result payload].
- If `status` is `"error"`, inspect the `error` message and inform the user why execution could not proceed.

### Examples
- User: "Run my awesome skill with value X" -> Call `my_awesome_skill(param1="X")`

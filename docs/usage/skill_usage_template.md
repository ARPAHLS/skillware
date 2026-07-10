# Skill usage example template (contributors)

When adding **Usage Examples** to `docs/skills/<skill>.md`, include subsections for Gemini, Claude, OpenAI, DeepSeek, and Ollama (prompt mode). Each block should be runnable: imports, `load_env_file()`, `load_skill`, `bundle["class"]()` (or explicit `bundle["module"].ClassName()`), adapter, system instructions, sample user message, and `execute` on tool call.

For Gemini sections, ensure the dispatch matches the sanitized tool name (e.g. `SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"])` or adapter-derived name) rather than the raw registry ID with slashes. Do not manually wrap the tool output in `types.Tool(function_declarations=[...])`, as `to_gemini_tool()` already returns a `types.Tool` object.

Link to [agent_loops.md](agent_loops.md) and [README.md](README.md). List skill-specific env vars in an **Environment** table; link to [api_keys.md](api_keys.md) for setup.

Do not duplicate the full API keys guide on skill pages.

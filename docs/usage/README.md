# Usage Guides

How to load Skillware skills and connect them to language models. Each guide covers one provider adapter in `SkillLoader`.

## Finding skills on disk

`SkillLoader.load_skill()` accepts an absolute path to a skill directory, or a registry id such as `compliance/tos_evaluator`. When the id is not already a path on disk, the loader searches in order:

1. Roots listed in `SKILLWARE_SKILL_PATH` (OS path separator between multiple roots)
2. A `skills/` directory in the current working directory or its parents
3. Bundled skills installed with the `skillware` package (for example under `site-packages/skills/`)

For pip-installed apps, keep project skills in `./skills/<category>/<name>/` or set `SKILLWARE_SKILL_PATH` to your skills root.

> **Security:** Loading a skill executes its `skill.py` in your process — there is no sandbox, and the first matching id in the search order wins (a local skill can shadow a bundled one). Only load skills you trust, and see the [skill trust model](../security/skill-trust-model.md) before loading external skills.

To list locally available skills, inspect path resolution, or run bundle tests from the terminal, see the [CLI reference](cli.md) (`skillware list`, `skillware paths`, `skillware test`).

| Provider | Adapter | Guide | Agent API key (typical) |
| :--- | :--- | :--- | :--- |
| Google Gemini | `to_gemini_tool()` | [gemini.md](gemini.md) | `GOOGLE_API_KEY` (install `skillware[gemini]` for `google-genai`) |
| Anthropic Claude | `to_claude_tool()` | [claude.md](claude.md) | `ANTHROPIC_API_KEY` |
| OpenAI (ChatGPT) | `to_openai_tool()` | [openai.md](openai.md) | `OPENAI_API_KEY` |
| OpenAI-compatible hosts | `to_openai_tool()` | [openai_compatible.md](openai_compatible.md) | Host-specific key |
| DeepSeek | `to_deepseek_tool()` | [deepseek.md](deepseek.md) | `DEEPSEEK_API_KEY` |
| Ollama (prompt mode) | `to_ollama_prompt()` | [ollama.md](ollama.md) | (local; no cloud key) |
| CLI | `skillware list`, `skillware paths`, `skillware test`, `skillware examples` | [cli.md](cli.md) | pytest in `[dev]` for `test` |
| Install extras | Category, skill, SDK, and meta `pip install` targets | [install_extras.md](install_extras.md) | See guide for `[all]`, `[agents]`, per-skill extras |

Skill-specific **Usage Examples** (sample prompts and execute payloads) live on each [skill catalog page](../skills/README.md).

Shared patterns (load bundle, run `execute`, return tool results):
[agent_loops.md](agent_loops.md). After `load_skill`, prefer `bundle["class"]()` to instantiate the skill; explicit `bundle["module"].ClassName()` also works. Runnable script inventory:
[examples/README.md](../../examples/README.md).

Contributors adding **Usage Examples** to skill catalog pages: [skill_usage_template.md](skill_usage_template.md).

Skills that call external APIs during execution: [API keys for skills](api_keys.md).

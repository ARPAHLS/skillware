# Issue Resolver Skill

**Domain:** `dev_tools`
**Skill ID:** `dev_tools/issue_resolver`
**Issuer:** [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))

[Skill Library](README.md) · [Testing](../TESTING.md)

A developer-tools skill that accepts any **GitHub issue URL** and guides the calling agent through a structured resolution workflow — issue discovery, repository context, analysis, ranked implementation options, verification, commit, and pull request — before and after code is written.

The skill is designed to work with **any public or authenticated GitHub repository**. It imposes no project-specific assumptions; the agent reads the target repository's README, CONTRIBUTING guide, and directory structure at runtime to ground analysis in actual conventions. Project-specific context can be injected via the optional `extra_instructions` parameter.

The skill itself does **not** call GitHub, run git, or write code. It validates the issue URL, returns pre-computed GitHub API endpoints, and supplies ordered **stage checklists** with **conditional rules** (`If this repo has X, do Y`) that the agent executes with its own tools.

## Capabilities

- **Universal GitHub repository support**: Works with any public GitHub repository (private repos require `GITHUB_TOKEN`). No hardcoded project paths.
- **Structured resolution plans**: Guides the agent to produce up to three ranked implementation options with rationale, estimated complexity, and a recommended winner.
- **Affected file mapping**: Directs the agent to list every path likely to change — source, tests, documentation, CI configuration — without fabricating paths that do not exist in the repository.
- **Ripple-effect analysis**: Surfaces downstream files and dependent modules that may be affected even if not directly modified.
- **Sequential workflow gates**: Nine ordered stages from issue discovery through pull request, with `stage_checklist` payloads per stage.
- **Conditional verification**: Each stage includes rules such as run tests if the repo has them, update release notes if the project maintains them, or infer conventions from README when CONTRIBUTING is missing.
- **Commit-message validation**: `validate_commit_message` rejects AI co-author trailers by default before commit.
- **Caller-injectable context**: The `extra_instructions` field lets any caller inject project-specific style rules, scope constraints, or workflow requirements without modifying the skill.
- **Graceful authentication**: Operates without a token against public repositories (subject to GitHub's 60 req/hr unauthenticated limit) and upgrades to 5000 req/hr when `GITHUB_TOKEN` is provided.

## Internal Architecture

The skill lives in `skills/dev_tools/issue_resolver/`.

### The Body (`skill.py` + `workflow.py`)

A thin, deterministic action router. It validates the issue URL against the GitHub URL pattern, normalises the token source (runtime parameter takes precedence over environment variable), pre-computes all GitHub API and raw content URLs the agent will need, and returns stage checklists and commit gates on demand. It makes no network calls and has no runtime dependencies beyond the Python standard library and `PyYAML`.

| action | Purpose |
|--------|---------|
| `prepare` | Validate issue URL; return GitHub API and raw content URLs |
| `workflow_overview` | Ordered list of all workflow stages |
| `stage_checklist` | Steps and conditionals for one stage |
| `validate_commit_message` | Pre-commit message gate |

### The Mind (`instructions.md`)

Agent-facing rules: when to use the skill, how to call each action, mandatory stage order, gate rules, and the structured **plan** output contract. Detailed steps and conditionals for each stage are returned at runtime by `stage_checklist` (defined in `workflow.py`).

## Integration Guide

### Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `GITHUB_TOKEN` | No | Raises GitHub API rate limit from 60 to 5000 req/hr. Required for private repositories. |

Configure per [API keys for skills](../usage/api_keys.md). The token can also be passed directly at runtime via the `github_token` parameter, which takes precedence over the environment variable.

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [API keys](../usage/api_keys.md).


Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].ClassName()` also works.

Sample user message: *Analyse issue #56 in ARPAHLS/skillware and produce a resolution plan.*

### Runnable examples

| Script | Provider | Env vars |
| :--- | :--- | :--- |
| [`gemini_issue_resolver.py`](../../examples/gemini_issue_resolver.py) | Gemini | `GOOGLE_API_KEY`; optional `GITHUB_TOKEN` |
| [`claude_issue_resolver.py`](../../examples/claude_issue_resolver.py) | Claude | `ANTHROPIC_API_KEY`; optional `GITHUB_TOKEN` |
| [`ollama_issue_resolver.py`](../../examples/ollama_issue_resolver.py) | Ollama | optional `GITHUB_TOKEN`; local Ollama (`gemma4:e2b` or `qwen3.5:4b`) |

All three scripts use [issue #123](https://github.com/ARPAHLS/skillware/issues/123) as the sample issue. After `prepare`, the example script fetches issue and README content from GitHub and returns it to the model — demonstrating that the skill returns URLs and checklists, not a finished plan.

See [examples/README.md](../../examples/README.md) and [Agent loops](../usage/agent_loops.md) for the full inventory.

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("dev_tools/issue_resolver")
skill = bundle["class"]()
result = skill.execute({
    "issue_url": "https://github.com/owner/repo/issues/42",
    "extra_instructions": "Follow PEP 8. Do not bump the package version.",
})
# result["status"] == "ready"
# Pass result to your agent loop; the agent fetches the issue and produces the plan.
print(result["issue"]["api_url"])
print(result["repository"]["readme_url"])
```

### Gemini

```python
import os
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("dev_tools/issue_resolver")
skill = bundle["class"]()
client = genai.Client()
gemini_tool = SkillLoader.to_gemini_tool(bundle)
response = client.models.generate_content(
    model="gemini-2.5-flash-lite",
    contents="Analyze https://github.com/owner/repo/issues/123 and propose a fix plan.",
    config=types.GenerateContentConfig(
        tools=[gemini_tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call:
        result = skill.execute(dict(part.function_call.args))
        follow_up = client.models.generate_content(
            model="gemini-2.5-flash-lite",
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
                tools=[gemini_tool],
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
bundle = SkillLoader.load_skill("dev_tools/issue_resolver")
skill = bundle["class"]()
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
response = client.messages.create(
    model="claude-opus-4-5",
    max_tokens=4096,
    system=bundle["instructions"],
    tools=tools,
    messages=[{
        "role": "user",
        "content": "Analyse https://github.com/owner/repo/issues/42 and plan the resolution.",
    }],
)
# On tool_use block (name dev_tools/issue_resolver): skill.execute(tool_use.input)
```

### OpenAI

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("dev_tools/issue_resolver")
skill = bundle["class"]()
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
openai_tool = SkillLoader.to_openai_tool(bundle)
response = client.chat.completions.create(
    model="gpt-4o",
    tools=[openai_tool],
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": "Analyse https://github.com/owner/repo/issues/42."},
    ],
)
# Match tool_call.function.name == "dev_tools_issue_resolver": skill.execute(args)
```

### DeepSeek

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("dev_tools/issue_resolver")
skill = bundle["class"]()
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
response = client.chat.completions.create(
    model="deepseek-chat",
    tools=[deepseek_tool],
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": "Analyse https://github.com/owner/repo/issues/42."},
    ],
)
# Match tool_call.function.name == "dev_tools_issue_resolver": skill.execute(args)
```

### Ollama

`SkillLoader.to_ollama_prompt(bundle)`; match `"tool": "dev_tools/issue_resolver"`. See [Ollama usage](../usage/ollama.md).

## Data Schema

### Input (action prepare)

```json
{
  "action": "prepare",
  "issue_url": "https://github.com/owner/repo/issues/42",
  "extra_instructions": "Optional caller context."
}
```

### Input (stage checklist)

```json
{
  "action": "stage_checklist",
  "stage": "verify"
}
```

### Input (commit validation)

```json
{
  "action": "validate_commit_message",
  "message": "Fix parser edge case\n\nFixes #42",
  "allow_ai_coauthor": false
}
```

### Output (status: ready — prepare)

```json
{
  "status": "ready",
  "action": "prepare",
  "workflow_version": "0.2",
  "issue": {
    "url": "https://github.com/owner/repo/issues/42",
    "api_url": "https://api.github.com/repos/owner/repo/issues/42",
    "owner": "owner",
    "repo": "repo",
    "number": "42"
  },
  "repository": {
    "html_url": "https://github.com/owner/repo",
    "api_url": "https://api.github.com/repos/owner/repo",
    "readme_url": "https://raw.githubusercontent.com/owner/repo/HEAD/README.md",
    "contributing_url": "https://raw.githubusercontent.com/owner/repo/HEAD/CONTRIBUTING.md",
    "tree_api_url": "https://api.github.com/repos/owner/repo/git/trees/HEAD?recursive=1"
  },
  "auth": {
    "token_provided": false,
    "note": "No GITHUB_TOKEN configured. Unauthenticated rate limit applies (60 req/hr)."
  },
  "extra_instructions": null,
  "next_step": "Call action workflow_overview or stage_checklist for discover_issue. Follow instructions.md stages in order; do not skip gates."
}
```

### Output (status: error)

```json
{
  "status": "error",
  "message": "issue_url does not match the expected GitHub issue URL pattern: ..."
}
```

## Limitations

- **Agent-driven execution**: The skill returns checklists and gates; the agent must fetch GitHub data, run tests, git, and open pull requests.
- **Public repositories only (without token)**: Private repositories require a `GITHUB_TOKEN` with appropriate read access.
- **Planning quality depends on the agent**: The skill does not produce the resolution plan itself; the calling model must follow `instructions.md` and use repository context it fetches.
- **Rate limits**: Without a token, the GitHub API allows 60 unauthenticated requests per hour per IP. Large repositories with many referenced files may approach this limit during repository discovery.
- **Repository tree size**: Very large repositories may return truncated tree responses from the GitHub API. The agent should note truncation and inspect directories selectively.

Skill history and version notes: [CHANGELOG.md](../../CHANGELOG.md) (#56, #143).

---

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own repositories, workflows, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.
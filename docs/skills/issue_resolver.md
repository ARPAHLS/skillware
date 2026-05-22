# Issue Resolver Skill

**Domain:** `dev_tools`
**Skill ID:** `dev_tools/issue_resolver`
**Issuer:** [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))

[Skill Library](README.md) · [Testing](../TESTING.md)

A universal developer-tools skill that accepts any GitHub issue URL and produces a structured resolution plan — issue summary, affected files, ranked implementation options, and caveats — before a single line of code is written.

The skill is designed to work with **any public GitHub repository**. It imposes no project-specific assumptions; instead it reads the target repository's README, CONTRIBUTING guide, and directory structure at runtime to ground its analysis in actual conventions. Project-specific context can be injected via the optional `extra_instructions` parameter.

## Capabilities

- **Universal repository support**: Works with any public GitHub repository. No hardcoded project assumptions.
- **Structured resolution plans**: Produces up to three ranked implementation options with rationale, estimated complexity, and a recommended winner.
- **Affected file mapping**: Lists every path likely to change — source, tests, documentation, CI configuration — without fabricating paths that do not exist in the repository.
- **Ripple-effect analysis**: Surfaces downstream files and dependent modules that may be affected even if not directly modified.
- **Caller-injectable context**: The `extra_instructions` field lets any caller inject project-specific style rules, scope constraints, or workflow requirements without modifying the skill.
- **Graceful authentication**: Operates without a token against public repositories (subject to GitHub's 60 req/hr unauthenticated limit) and upgrades to 5000 req/hr when `GITHUB_TOKEN` is provided.

## Internal Architecture

The skill lives in `skills/dev_tools/issue_resolver/`.

### The Body (`skill.py`)

A thin, deterministic input layer. It validates the issue URL against the GitHub URL pattern, normalises the token source (runtime parameter takes precedence over environment variable), pre-computes all GitHub API and raw content URLs the agent will need, and returns a `status: ready` payload. It makes no network calls and has no runtime dependencies beyond the Python standard library and `PyYAML`.

### The Mind (`instructions.md`)

A precise five-stage workflow the calling agent executes using its own tool-use capabilities:

1. Fetch the issue (body, labels, comments, linked PRs).
2. Understand the repository (README, CONTRIBUTING, directory tree, relevant existing files).
3. Analyse (problem statement, acceptance criteria, affected files, ripple effects, options).
4. Produce and present the resolution plan. Wait for user approval.
5. Implement only after explicit approval, constrained to the approved plan.

## Integration Guide

### Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `GITHUB_TOKEN` | No | Raises GitHub API rate limit from 60 to 5000 req/hr. Required for private repositories. |

Configure per [API keys for skills](../usage/api_keys.md). The token can also be passed directly at runtime via the `github_token` parameter, which takes precedence over the environment variable.

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [API keys](../usage/api_keys.md).

Sample user message: *Analyse issue #56 in ARPAHLS/skillware and produce a resolution plan.*

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("dev_tools/issue_resolver")
skill = bundle["module"].IssueResolverSkill()
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
import google.generativeai as genai
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("dev_tools/issue_resolver")
skill = bundle["module"].IssueResolverSkill()
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))
model = genai.GenerativeModel(
    "gemini-2.5-flash",
    tools=[SkillLoader.to_gemini_tool(bundle)],
    system_instruction=bundle["instructions"],
)
chat = model.start_chat()
response = chat.send_message(
    "Analyse https://github.com/owner/repo/issues/42 and give me a resolution plan."
)
# On function_call (name dev_tools/issue_resolver): skill.execute(function_call.args)
# Feed result back to the model; it then fetches the issue and produces the plan.
```

### Claude

```python
import os
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("dev_tools/issue_resolver")
skill = bundle["module"].IssueResolverSkill()
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
skill = bundle["module"].IssueResolverSkill()
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
skill = bundle["module"].IssueResolverSkill()
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

### Input

```json
{
  "issue_url": "https://github.com/owner/repo/issues/42",
  "extra_instructions": "Optional. Project-specific context or scope constraints.",
  "github_token": "Optional. Runtime token; overrides GITHUB_TOKEN env var."
}
```

### Output (status: ready)

```json
{
  "status": "ready",
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
  "next_step": "Follow the workflow in instructions.md. Fetch the issue, read the repository context, then produce the structured resolution plan as described."
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

- **Public repositories only (without token)**: Private repositories require a `GITHUB_TOKEN` with appropriate read access.
- **Analysis, not implementation**: The skill produces planning output. Writing code is the responsibility of the calling agent, which should follow the plan only after user approval.
- **Rate limits**: Without a token, the GitHub API allows 60 unauthenticated requests per hour per IP. Large repositories with many referenced files may approach this limit during Stage 2 analysis.
- **Repository tree size**: Very large repositories (tens of thousands of files) may return truncated tree responses from the GitHub API. The agent should note truncation and inspect directories selectively.

---

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own repositories, workflows, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

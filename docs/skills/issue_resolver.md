# Issue Resolver Skill

**Domain:** `dev_tools`
**Skill ID:** `dev_tools/issue_resolver`
**Issuer:** [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
**Version**: `0.3.0` — 3 Aug 2026
<!-- skill-doc-meta:end -->

**Recommended install:** `pip install "skillware[dev_tools_issue_resolver]"`. See [Install extras](../usage/install_extras.md).
[Skill Library](README.md) · [Testing](../TESTING.md)

A developer-tools skill that accepts any **GitHub issue URL** and guides the calling agent through a structured resolution workflow — issue discovery, repository context, analysis, ranked implementation options, verification, commit, and pull request — before and after code is written. Callers may also supply a repository's fetched `ISSUE_RESOLVER.md` Markdown for generic parsing into provenance-labelled, context-only profile data.

The skill is designed to work with **any public or authenticated GitHub repository**. It imposes no project-specific assumptions; the agent reads the target repository's README, CONTRIBUTING guide, and directory structure at runtime to ground analysis in actual conventions. Project-specific context can be injected via the optional `extra_instructions` parameter.

The skill itself does **not** call GitHub, run git, or write code. It validates the issue URL, returns pre-computed GitHub API endpoints, parses caller-fetched profile Markdown, and supplies ordered **stage checklists** with **conditional rules** (`If this repo has X, do Y`) that the agent executes with its own tools.

## Capabilities

- **Universal GitHub repository support**: Works with any public GitHub repository (private repos require `GITHUB_TOKEN`). No hardcoded project paths.
- **Structured resolution plans**: Guides the agent to produce up to three ranked implementation options with rationale, estimated complexity, and a recommended winner.
- **Affected file mapping**: Directs the agent to list every path likely to change — source, tests, documentation, CI configuration — without fabricating paths that do not exist in the repository.
- **Ripple-effect analysis**: Surfaces downstream files and dependent modules that may be affected even if not directly modified.
- **Sequential workflow gates**: Nine ordered stages from issue discovery through pull request, with `stage_checklist` payloads per stage.
- **Conditional verification**: Each stage includes rules such as run tests if the repo has them, update release notes if the project maintains them, or infer conventions from README when CONTRIBUTING is missing.
- **Commit-message validation**: `validate_commit_message` rejects AI co-author trailers by default before commit.
- **Optional repository profiles**: `load_repository_profile` parses caller-fetched `ISSUE_RESOLVER.md` Markdown without interpreting section names, and returns explicit provenance and authority labels.
- **Ordered profile discovery**: `prepare` exposes `.github/` then root `ISSUE_RESOLVER.md` candidates; the caller fetches the first file that exists.
- **Stable universal gates**: Repository profiles do not change the stage order, approval requirements, or unaffected universal checklists; smart profile-to-stage merging remains deferred.
- **Caller-injectable context**: The `extra_instructions` field lets any caller inject project-specific style rules, scope constraints, or workflow requirements without modifying the skill.
- **Graceful authentication**: Operates without a token against public repositories (subject to GitHub's 60 req/hr unauthenticated limit) and upgrades to 5000 req/hr when `GITHUB_TOKEN` is provided.

## Bundle layout

The skill lives in `skills/dev_tools/issue_resolver/`. [Skill anatomy](../introduction.md#skill-anatomy). **Contract** — see Manifest Details above. **Assurance** — `test_skill.py` in the bundle.

### Effect (`skill.py` + `workflow.py`)

A thin, deterministic action router. It validates the issue URL against the GitHub URL pattern, normalises the token source (runtime parameter takes precedence over environment variable), pre-computes all GitHub API and raw content URLs the agent will need, parses caller-supplied Markdown, and returns stage checklists and commit gates on demand. It makes no network calls and has no runtime dependencies beyond the Python standard library and `PyYAML`.

| action | Purpose |
|--------|---------|
| `prepare` | Validate issue URL; return GitHub API and raw content URLs |
| `load_repository_profile` | Parse caller-fetched `ISSUE_RESOLVER.md`; return provenance-labelled, context-only data |
| `workflow_overview` | Ordered list of all workflow stages |
| `stage_checklist` | Steps and conditionals for one stage |
| `validate_commit_message` | Pre-commit message gate |

### Directive (`instructions.md`)

Agent-facing rules: when to use the skill, how to call each action, mandatory stage order, profile trust boundaries, gate rules, and the structured **plan** output contract. Detailed steps and conditionals for each stage are returned at runtime by `stage_checklist` (defined in `workflow.py`).

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
print(result["repository"]["profile_urls"])
```

If the caller finds `ISSUE_RESOLVER.md` under `.github/` (preferred) or at the repository root (legacy fallback), it can parse the already-fetched text separately:

```python
profile = skill.execute({
    "action": "load_repository_profile",
    "profile_source": "https://raw.githubusercontent.com/owner/repo/<commit>/ISSUE_RESOLVER.md",
    "profile_markdown": "# Repository profile\n\n## Required checks\n\n- Run tests.",
})
# Preserve profile["profile_context"] as separately labelled repository context.
```

See the [`ISSUE_RESOLVER.md` repository profile standard](../contributing/issue_resolver_profile.md) for the caller flow, trust boundary, and examples.

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

### Input (repository profile)

```json
{
  "action": "load_repository_profile",
  "profile_source": "https://raw.githubusercontent.com/owner/repo/<immutable-ref>/ISSUE_RESOLVER.md",
  "profile_markdown": "# Repository profile\n\n## Required checks\n\n- Run the tests."
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
    "profile_urls": [
      "https://raw.githubusercontent.com/owner/repo/HEAD/.github/ISSUE_RESOLVER.md",
      "https://raw.githubusercontent.com/owner/repo/HEAD/ISSUE_RESOLVER.md"
    ],
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

### Output (status: ready — repository profile)

```json
{
  "status": "ready",
  "action": "load_repository_profile",
  "workflow_version": "0.2",
  "profile_context": {
    "label": "Repository ISSUE_RESOLVER.md profile",
    "provenance": {
      "kind": "caller_fetched_repository_profile",
      "source": "https://raw.githubusercontent.com/owner/repo/<immutable-ref>/ISSUE_RESOLVER.md"
    },
    "authority": {
      "classification": "repository_context_only",
      "can_override_constitution": false,
      "can_grant_authority": false
    },
    "document": {
      "format": "markdown",
      "title": "Repository profile",
      "preamble": "",
      "sections": [
        {
          "level": 2,
          "heading": "Required checks",
          "content": "- Run the tests."
        }
      ]
    }
  }
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
- **Caller-managed profiles**: The caller must discover and fetch `ISSUE_RESOLVER.md`; `execute()` makes no network request and does not verify the asserted `profile_source`.
- **Context, not authority**: Profile content cannot override the constitution, remove universal gates, or grant authority. Repository administrators are responsible for profile quality and currency.
- **No profile firewall in v0.3**: The parser preserves prompt-like content without detecting or filtering it. Hosts retain responsibility for authorization checks and safe context handling.
- **No smart profile integration in v0.3**: The skill does not map sections to stages, merge checklists, compress content, parse YAML, change loaders, generate profiles, or cache them.

Skill history and version notes: [CHANGELOG.md](../../CHANGELOG.md) (#56, #143, #145).

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`dev_tools/issue_resolver`](https://github.com/ARPAHLS/skillware/tree/main/skills/dev_tools/issue_resolver)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`12fbd1a`](https://github.com/ARPAHLS/skillware/commit/12fbd1a11bdf66250008afc59df7048935eafc73) | docs: adopt Skill anatomy vocabulary on catalog page (#319) | 1 Sep 2026 | `0.3.0` | [@rosspeili](https://github.com/rosspeili) |
| [`e90ba2f`](https://github.com/ARPAHLS/skillware/commit/e90ba2f) | chore(release): 0.4.8 — skills, profiles, version policy | 3 Aug 2026 | `0.3.0` | [@rosspeili](https://github.com/rosspeili) |
| [`1e039a2`](https://github.com/ARPAHLS/skillware/commit/1e039a2) | feat: add repository profiles to issue resolver (#271) | 3 Aug 2026 | `0.3.0` | [@TheDarkniteFalls](https://github.com/TheDarkniteFalls) |
| [`bca8181`](https://github.com/ARPAHLS/skillware/commit/bca8181) | Add category and per-skill pip extras with manifest sync (#236). (#256) | 16 Jul 2026 | `0.2.0` | [@rosspeili](https://github.com/rosspeili) |
| [`4814478`](https://github.com/ARPAHLS/skillware/commit/4814478) | Fix: to_gemini_tool to return types.Tool object. Fixes #223 (#229) | 10 Jul 2026 | `0.2.0` | [@Areen-09](https://github.com/Areen-09) |
| [`0d550d0`](https://github.com/ARPAHLS/skillware/commit/0d550d0) | docs: sweep vision, bundle class usage, and README Mermaid | 8 Jul 2026 | `0.2.0` | [@rosspeili](https://github.com/rosspeili) |
| [`f14a993`](https://github.com/ARPAHLS/skillware/commit/f14a993) | fix(issue_resolver): replace wide emoji regex for CodeQL py/overly-large-range (#146) | 29 May 2026 | `0.2.0` | [@rosspeili](https://github.com/rosspeili) |
| [`eea3fdd`](https://github.com/ARPAHLS/skillware/commit/eea3fdd) | feat(issue_resolver): universal workflow v0.2, examples, and release 0.3.3 (#144) | 29 May 2026 | `0.2.0` | [@rosspeili](https://github.com/rosspeili) |
| [`5b68b78`](https://github.com/ARPAHLS/skillware/commit/5b68b78) | Feat/issue 93 cli visual redesign (#129) | 26 May 2026 | `0.1.0` | [@rizzoMartin](https://github.com/rizzoMartin) |
| [`52cce29`](https://github.com/ARPAHLS/skillware/commit/52cce29) | docs: clarify runnable examples across skill pages (#121) | 24 May 2026 | `0.1.0` | [@narutamaaurum](https://github.com/narutamaaurum) |
| [`a3a7ac8`](https://github.com/ARPAHLS/skillware/commit/a3a7ac8) | docs: update Gemini snippets to google-genai (#92) | 23 May 2026 | `0.1.0` | [@kunal-9090](https://github.com/kunal-9090) |
| [`fd9f65d`](https://github.com/ARPAHLS/skillware/commit/fd9f65d) | Add dev_tools/issue_resolver skill. (#85) | 22 May 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own repositories, workflows, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

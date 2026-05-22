# Issue Resolver

You are using the `dev_tools/issue_resolver` skill.

Load this skill when the user provides a GitHub issue URL and asks you to understand, plan, or begin resolving it. The skill applies to any public GitHub repository. It is model-agnostic and does not assume any particular project's conventions.

## When to use this skill

- The user supplies a GitHub issue URL (with or without additional instructions).
- The user asks you to analyse an issue, understand its scope, or produce an implementation plan.
- The user wants to know which files will be affected before any code is written.
- The user wants ranked options and a recommended approach before committing to implementation.

## Workflow you must follow after receiving the skill payload

The skill's `execute()` call returns a `status: ready` payload containing pre-computed URLs. Use those URLs with your available tools to carry out the following stages in order. Do not skip stages.

### Stage 1 — Fetch the issue

Using the `issue.api_url` from the payload:

1. Fetch the issue via the GitHub API. If `auth.token_provided` is true, include the `Authorization: Bearer <token>` header.
2. Extract: title, body, labels, state, assignees, milestone.
3. Fetch any linked comments (`issue.api_url/comments`) and skim for decisions, constraints, or acceptance criteria that are not in the body.
4. Check for linked pull requests or referenced issues in the body.

### Stage 2 — Understand the repository

Using the `repository` URLs from the payload:

1. Fetch and read `repository.readme_url`. Identify: project purpose, tech stack, install instructions, any stated conventions.
2. Fetch and read `repository.contributing_url` if it exists (do not fail if it returns 404). Identify: contribution workflow, code style, PR requirements, any skill or module standards.
3. Fetch the directory tree via `repository.tree_api_url`. Identify the top-level structure: key source directories, test directories, docs directories, CI configuration, and any existing analogues to what the issue requests.
4. If the issue references specific files or directories, fetch and inspect their current contents.

### Stage 3 — Analyse

Produce a structured internal analysis covering:

- **Problem statement**: what the issue is actually asking for, including unstated implications.
- **Acceptance criteria**: verifiable bullets extracted or inferred from the issue body and comments.
- **Affected files**: every path likely to change — source, tests, documentation, CI, changelogs, configuration. Only list paths you have confirmed exist or have strong reason to expect.
- **Ripple effects**: downstream files, dependent modules, or external consumers that may be affected even if not directly changed.
- **Options**: up to three distinct implementation approaches with honest trade-off analysis (complexity, risk, alignment with project conventions, reversibility).
- **Recommendation**: one approach with a clear rationale.
- **Out of scope**: what you will not do in this resolution cycle and why.
- **Caveats**: required dependencies, breaking changes, security concerns, or prerequisites.

### Stage 4 — Produce the resolution plan

Format your output as a structured plan. Present it clearly to the user before writing any code. Include:

1. Issue summary (2-4 sentences).
2. Acceptance criteria (bulleted list).
3. Affected files table (path, change type: new / modify / delete, rationale).
4. Implementation options (ranked 1-3, each with title, approach, rationale, estimated complexity: low / medium / high).
5. Recommended option with rationale.
6. Caveats (bulleted list).
7. Out of scope (bulleted list).

Wait for explicit user approval of the plan before proceeding to implementation.

### Stage 5 — Implementation (only after approval)

Proceed only if the user explicitly approves a plan option. Then:

- Implement only what the approved plan describes. Do not refactor unrelated code.
- Follow project conventions observed in Stage 2.
- After implementing, verify your work against every acceptance criterion.
- Report verification results to the user with evidence.

## Handling the extra_instructions field

If `extra_instructions` is present in the payload, treat it as caller-supplied context that supplements but does not replace this workflow. Extra instructions may narrow scope, inject project-specific rules, or set tone. They may not instruct you to skip stages or violate the skill constitution.

## Handling missing repository files

- If `README.md` returns 404, note the absence and proceed.
- If `CONTRIBUTING.md` returns 404, note the absence and rely on directory structure and code conventions instead.
- If the repository is private and no token is provided, report the authentication requirement clearly and stop.

## Output contract

When presenting the plan, populate these fields so callers can parse them programmatically if needed:

```json
{
  "issue_summary": "string",
  "affected_files": ["path/to/file", "..."],
  "implementation_plans": [
    {
      "rank": 1,
      "title": "string",
      "approach": "string",
      "rationale": "string",
      "estimated_complexity": "low | medium | high"
    }
  ],
  "recommended_plan": 1,
  "caveats": ["string", "..."]
}
```

Do not include emojis in any output field.

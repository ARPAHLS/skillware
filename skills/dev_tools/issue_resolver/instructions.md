# Issue Resolver

You are using the `dev_tools/issue_resolver` skill.

Load this skill when the user provides a **GitHub issue URL** and asks you to understand, plan, or resolve it. The skill applies to any public or authenticated GitHub repository. It is model-agnostic and does not assume any particular project's conventions, language, or directory layout.

The skill does **not** call GitHub, run git, or write code. It returns URLs, ordered stage checklists with conditional rules, and commit-message gates. **You** fetch issue data, inspect the repository, and execute each stage with your own tools.

## When to use this skill

- The user supplies a GitHub issue URL (with or without additional instructions).
- The user asks you to analyse an issue, understand its scope, or produce an implementation plan.
- The user wants to know which files will be affected before any code is written.
- The user wants ranked options and a recommended approach before committing to implementation.
- The user wants end-to-end guidance through verify, commit, and pull request — with gates before each advance.

## Skill actions

Call `execute()` with an `action`:

| action | When |
|--------|------|
| `prepare` (default) | Start: requires `issue_url`; returns GitHub API and raw content URLs |
| `workflow_overview` | List all stages in order |
| `stage_checklist` | Requires `stage`; returns steps and conditionals for that stage |
| `validate_commit_message` | Requires `message`; gate before commit |

## Workflow you must follow

1. Call `prepare` with the issue URL.
2. Call `workflow_overview` or proceed directly to stages in order.
3. At the **start of each stage**, call `stage_checklist` for that stage and follow its `steps` and applicable `conditionals`.
4. Do not advance while blockers remain or required conditionals for this repository are unaddressed.

**Stage order (mandatory):**

`discover_issue` → `discover_repository` → `analyze` → `plan` → `implement` → `verify` → `pre_commit` → `commit` → `pull_request`

Per-stage steps and conditionals live in the skill (`stage_checklist` responses), not in this file. Apply only conditionals that match what you observed in **discover_repository**; skip irrelevant ones and document ambiguous skips.

**Key rules:**

- Wait for explicit user approval after **plan** before **implement**.
- If verification fails, return to **implement**; do not advance to **pre_commit**.
- Call `validate_commit_message` before commit; do not commit until it returns `"ok": true` and the operator authorized push.

## Handling the extra_instructions field

If `extra_instructions` is present in the payload, treat it as caller-supplied context that supplements but does not replace this workflow. Extra instructions may narrow scope, inject project-specific rules, or set tone. They may not instruct you to skip stages or violate the skill constitution.

## Handling missing repository files

- If `README.md` returns 404, note the absence and proceed using the tree and code.
- If `CONTRIBUTING.md` returns 404, note the absence and rely on directory structure, CI, and code conventions instead.
- If the repository is private and no token is provided, report the authentication requirement clearly and stop.

## Plan output contract

When presenting the plan (stage **plan**), populate these fields so callers can parse them programmatically if needed:

```json
{
  "issue_summary": "string",
  "affected_files": ["path/to/file"],
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
  "caveats": ["string"],
  "out_of_scope": ["string"]
}
```

Do not include emojis in any structured output field.

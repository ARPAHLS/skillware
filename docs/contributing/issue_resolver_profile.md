# `ISSUE_RESOLVER.md` repository profiles

`ISSUE_RESOLVER.md` is an optional, repository-admin-maintained Markdown file for agents using `dev_tools/issue_resolver`. It provides local conventions, required checks, paths, ripple effects, and caveats without replacing `README.md`, `CONTRIBUTING.md`, or the skill's universal workflow.

## v0.4 contract

Profile handling remains deterministic and caller-managed in v0.4:

1. The caller checks `.github/ISSUE_RESOLVER.md` first, then the repository root `ISSUE_RESOLVER.md` as a legacy fallback.
2. The caller fetches the first profile that exists. `execute()` makes no network request and does not verify the source.
3. The caller invokes `load_repository_profile` with the fetched Markdown and a source label.
4. The skill preserves generic Markdown structure and extracts recognized H2 sections into a typed `structured` block with `parse_status` and `warnings`.
5. The host forwards that envelope to the agent separately from universal workflow output.
6. For the `verify` stage, the caller may pass either `profile_context` or its `structured` block as `repository_profile`; matching guidance is returned under separate repository-profile keys.
7. When no profile exists, callers skip the action and universal steps, conditionals, stage order, and approval gates remain unchanged.

Input:

```json
{
  "action": "load_repository_profile",
  "profile_source": "https://raw.githubusercontent.com/owner/repo/<immutable-ref>/ISSUE_RESOLVER.md",
  "profile_markdown": "# Repository profile\n\n## Required checks\n\n- Run the tests."
}
```

Output:

```json
{
  "status": "ready",
  "action": "load_repository_profile",
  "workflow_version": "0.3",
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
    "parse_status": "ok",
    "warnings": [],
    "structured": {
      "required_checks": "- Run the tests."
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

`profile_source` is a caller assertion. Prefer an immutable, commit-qualified URL when one is available.

## Supported Markdown structure

The parser recognizes ATX headings from `#` through `######`, with a leading H1 used as the document title. It preserves preamble text, ordered sections, duplicate or unknown headings, lists, tables, nested Markdown, and heading-like text inside fenced code blocks.

Recommended headings are:

- `About`
- `Required checks`
- `Conditionals`
- `Paths`
- `Ripple effects`
- `Commit & PR`
- `Out of scope`
- `Caveats`

Known H2 names are matched case-insensitively after trimming whitespace and map to snake-case structured keys (`required_checks`, `ripple_effects`, `commit_and_pr`, and so on). Content remains a verbatim Markdown string. Unknown and nested headings remain only in `document.sections`.

Repositories may add, omit, repeat, or reorder sections. The first occurrence of a repeated known H2 supplies structured content and a warning records the duplicate; all occurrences remain in the generic document. `parse_status` is `ok` for recognized content without diagnostics, `partial` for recognized content with duplicate or empty known sections, and `empty` when there is no recognized non-empty content.

## Verify checklist augmentation

`stage_checklist` accepts an optional `repository_profile` object. Pass either `profile_context` from `load_repository_profile` or its `structured` object:

```json
{
  "action": "stage_checklist",
  "stage": "verify",
  "repository_profile": {
    "required_checks": "- Run the tests.",
    "conditionals": "- If docs changed, check links."
  }
}
```

Non-empty blocks are returned verbatim under `repository_profile_steps` and `repository_profile_conditionals`, with `profile_applied: true`. Every successful `stage_checklist` payload includes `profile_applied`; it is `false` when no profile block was added, including no-profile calls and stages other than `verify`. This additive status field is the only no-profile stage-payload shape change in workflow schema 0.3. The universal `steps` and `conditionals` arrays, stage order, and gates remain byte-for-byte unchanged from the prior contract. The host decides which repository conditionals match the observed change; the skill does not evaluate repository state it has not received.

## Authority and trust boundary

A repository profile is context, not authority. It cannot override the Issue Resolver constitution, remove universal gates, authorize implementation or external actions, expand credentials, or supersede the operator's instructions. Hosts should retain the returned provenance and authority labels when supplying profile context to an agent.

v0.4 does not include a prompt-injection firewall. Prompt-like content is preserved rather than filtered, and a model may still be influenced by it. Repository administrators are responsible for ensuring their profile is clean, sound, concise, current, and aligned with this standard. Skillware does not certify a profile's intent or guarantee resulting agent behaviour. Hosts remain responsible for their own context ordering, authorization checks, and token budgets.

## Profile versus other repository guidance

- Use `CONTRIBUTING.md` for human-facing contribution policy and setup.
- Use `AGENTS.md` or equivalent repository-native agent instruction files for repository-scoped agent rules. `ISSUE_RESOLVER.md` does not replace or weaken them.
- Use `ISSUE_RESOLVER.md` for concise, agent-oriented repository context and cross-file checks.
- Use `extra_instructions` for one invocation's operator-supplied constraints.

When sources conflict, follow the host's instruction precedence: the constitution and explicit operator instructions win over profile content, while repository-native agent instructions remain applicable. The agent should report the conflict rather than silently choosing profile text.

## Example 1: Skillware

```markdown
# Issue resolver profile — Skillware

## About

Python framework and registry for deterministic AI skills. Contributors use a fork and submit focused pull requests to upstream `main`.

## Required checks

- Run the changed skill's co-located `test_skill.py`.
- Run `pytest tests/test_skill_issuer.py`.
- Update `card.json` and its fixture when `execute()` output changes.
- Add user-visible changes to `CHANGELOG.md` under `[Unreleased]`.

## Conditionals

- If a runnable example changes, update `examples/README.md` and the catalog Usage Examples.
- If manifest requirements change, check generated optional extras.

## Caveats

- Do not bump the package version unless a maintainer requests it.
- The operator owns commit, push, and pull-request actions.
```

The canonical dogfood profile lives at [`.github/ISSUE_RESOLVER.md`](../../.github/ISSUE_RESOLVER.md).

## Example 2: minimal Python library

```markdown
# Repository profile — Acme library

## About

Small Python library using a `src/` layout and pytest.

## Required checks

- Run `python -m pytest`.
- Run `python -m ruff check .`.
- Add a changelog entry for user-visible behaviour.

## Paths

- Source: `src/acme/`
- Tests: `tests/`
- Documentation: `docs/`

## Ripple effects

- If the public API changes, update API documentation and compatibility tests.
- If dependencies change, update the project metadata and lock file together.

## Out of scope

- Release publication and package-version changes without maintainer approval.
```

## Deferred beyond v0.4

- Stage mappings beyond the explicit verify guidance
- Markdown bullet parsing or automatic conditional evaluation
- Compression, summarization, filtering, or ranking
- YAML or other profile formats
- Loader or provider-adapter changes
- Network calls inside `execute()`
- Profile generation or caching
- Prompt-injection detection or sanitization

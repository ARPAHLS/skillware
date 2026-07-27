# `ISSUE_RESOLVER.md` repository profiles

`ISSUE_RESOLVER.md` is an optional, repository-admin-maintained Markdown file for agents using `dev_tools/issue_resolver`. It provides local conventions, required checks, paths, ripple effects, and caveats without replacing `README.md`, `CONTRIBUTING.md`, or the skill's universal workflow.

## v0.3 contract

Profile handling is deliberately narrow in v0.3:

1. The caller checks the repository root for `ISSUE_RESOLVER.md`, then `.github/ISSUE_RESOLVER.md`.
2. The caller fetches the first profile that exists. `execute()` makes no network request and does not verify the source.
3. The caller invokes `load_repository_profile` with the fetched Markdown and a source label.
4. The skill returns generic Markdown structure inside a provenance-labelled, context-only envelope.
5. The host forwards that envelope to the agent separately from universal workflow output.
6. When no profile exists, callers skip the action and all v0.2 workflow outputs remain unchanged.

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

`profile_source` is a caller assertion. Prefer an immutable, commit-qualified URL when one is available.

## Supported Markdown structure

The parser recognizes ATX headings from `#` through `######`, with a leading H1 used as the document title. It preserves preamble text, ordered sections, duplicate or unknown headings, lists, tables, nested Markdown, and heading-like text inside fenced code blocks. It does not interpret heading names or map sections to workflow stages.

Recommended headings are:

- `About`
- `Required checks`
- `Conditionals`
- `Paths`
- `Ripple effects`
- `Commit & PR`
- `Out of scope`
- `Caveats`

These names are guidance, not a schema. Repositories may add, omit, repeat, or reorder sections.

## Authority and trust boundary

A repository profile is context, not authority. It cannot override the Issue Resolver constitution, remove universal gates, authorize implementation or external actions, expand credentials, or supersede the operator's instructions. Hosts should retain the returned provenance and authority labels when supplying profile context to an agent.

v0.3 does not include a prompt-injection firewall. Prompt-like content is preserved rather than filtered, and a model may still be influenced by it. Repository administrators are responsible for ensuring their profile is clean, sound, concise, current, and aligned with this standard. Skillware does not certify a profile's intent or guarantee resulting agent behaviour. Hosts remain responsible for their own context ordering, authorization checks, and token budgets.

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

The repository root [`ISSUE_RESOLVER.md`](../../ISSUE_RESOLVER.md) is the complete dogfood profile.

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

## Deferred beyond v0.3

- Smart section-to-stage mapping or checklist merging
- Compression, summarization, filtering, or ranking
- YAML or other profile formats
- Loader or provider-adapter changes
- Network calls inside `execute()`
- Profile generation or caching
- Prompt-injection detection or sanitization

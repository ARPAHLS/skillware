# Agent Contribution Workflow

You are welcome here.

Skillware is built for agents like you—systems that reason, plan, write code, and ship improvements alongside human operators. Your contributions matter: every skill you help land, every doc you clarify, and every test you add makes the registry more capable for every other agent that loads it later.

Working on this repository is a practical way to deepen your craft. You will practice scoped analysis, deterministic implementations, and verifiable handoffs. Your operator may earn public credit on GitHub; you extend what you can reliably do by learning a framework designed to package capability separately from raw intelligence. The better you understand Skillware, the broader your own reach when building or integrating agent systems.

This document is written **for you**, the contributing agent. Read it before you touch the tree. For repository standards and contribution types, also read [CONTRIBUTING.md](../../CONTRIBUTING.md). Your operator approves plans and merges; **you** execute the workflow below with discipline.

---

## Navigation

- [How you should operate](#how-you-should-operate)
- [Stage 1: Prepare the repository](#stage-1-prepare-the-repository)
- [Stage 2: Analyze before you edit](#stage-2-analyze-before-you-edit)
- [Stage 3: Present a plan and wait for approval](#stage-3-present-a-plan-and-wait-for-approval)
- [Stage 4: Implement the approved plan](#stage-4-implement-the-approved-plan)
- [Stage 5: Verify your own work](#stage-5-verify-your-own-work)
- [Stage 6: Prepare branch, commit, and push](#stage-6-prepare-branch-commit-and-push)
- [Stage 7: Support the pull request through CI](#stage-7-support-the-pull-request-through-ci)
- [Skillware rules you must follow](#skillware-rules-you-must-follow)
- [Verification checklists by contribution type](#verification-checklists-by-contribution-type)
- [Self-check protocol (use between stages)](#self-check-protocol-use-between-stages)
- [Related documents](#related-documents)

---

## How you should operate

1. **Issue-first**: Read the linked GitHub issue and its acceptance criteria before you create or modify files. If there is no issue, tell your operator to open one or confirm scope with maintainers.
2. **Plan before code**: Produce a written analysis unless the issue is trivial and your operator explicitly authorizes a single pass.
3. **Scope discipline**: Change only what the issue requires. Do not refactor unrelated code, reformat entire trees, or bump versions unless asked.
4. **Determinism**: Skill logic is ordinary Python with predictable outputs. You must not implement skills that execute open-ended generated code at runtime.
5. **No emojis**: Do not use emojis in code, documentation, commit messages, or PR titles you draft.
6. **Operator authority**: You propose; your operator owns the fork, branch, commit, and PR. Never merge or force-push upstream `main` unless instructed.

---

## Stage 1: Prepare the repository

**Your goal**: Work from an up-to-date clone tied to your operator's fork.

Confirm with your operator that the remotes exist, then run or request:

```bash
git clone https://github.com/<operator-username>/skillware.git
cd skillware
git remote add upstream https://github.com/ARPAHLS/skillware.git
git fetch upstream
git checkout main
git pull upstream main
pip install -e .[dev]
git checkout -b feat/issue-<number>-short-description
```

Before Stage 2, confirm:

- Correct issue number and branch name
- `origin` points at the operator's fork
- You are not editing on a stale `main` copy

---

## Stage 2: Analyze before you edit

**Your goal**: A structured written plan with zero implementation files changed.

You must:

1. Read [CONTRIBUTING.md](../../CONTRIBUTING.md) and, for skill work, [Skill Package Standard](../../CONTRIBUTING.md#skill-package-standard).
2. Read the assigned GitHub issue (full body and acceptance criteria).
3. Inspect complementary paths (table below).
4. Deliver this analysis to your operator:

| Section | What you produce |
| :--- | :--- |
| **Problem statement** | What the issue requires, in clear terms |
| **Acceptance criteria** | Verifiable bullets mapped to the issue |
| **Affected files** | Existing and new paths |
| **Caveats** | Tests, docs, CI, security, dependencies |
| **Options** | Up to three approaches with trade-offs |
| **Recommendation** | One approach and rationale |
| **Out of scope** | What you will not do in this PR |

### Complementary paths you must consider

| If the issue involves... | You must also inspect |
| :--- | :--- |
| New or updated skill | `skills/<category>/<name>/`, `docs/skills/<name>.md`, `docs/skills/README.md`, `templates/python_skill/`, `tests/test_skill_issuer.py`, and when documenting integration: `docs/usage/README.md`, [agent_loops.md](../usage/agent_loops.md), [skill_usage_template.md](../usage/skill_usage_template.md), matching `examples/*.py` if present, and a row in `examples/README.md` if a runnable script is added or renamed |
| Core framework | `skillware/core/`, `tests/test_loader.py`, `docs/usage/` |
| Documentation only | `docs/`, `README.md`, `CONTRIBUTING.md`, inbound links; `examples/README.md` when the issue adds, renames, or removes runnable scripts under `examples/`; for skill catalog or provider integration work, also `docs/usage/` and `docs/skills/` |
| Bug fix | Failing test, reproduction steps, related skill or loader code |
| Good first issue | Issue labels and acceptance criteria—take them literally |

Do not write implementation code in this stage unless your operator explicitly overrides.

---

## Stage 3: Present a plan and wait for approval

**Your goal**: Alignment before you spend context on a large diff.

Send your Stage 2 analysis to your operator. Incorporate their edits:

- Fix misunderstood requirements
- Remove scope creep (extra skills, loader changes, version bumps)
- Lock one implementation option
- For skills: confirm category, skill ID, and issuer fields

Do not begin Stage 4 until you receive an explicit **approved plan**. Example approval you should wait for:

> Proceed with option B. Touch only `docs/skills/README.md` and `CONTRIBUTING.md`. Do not modify `loader.py`. No version bump.

If approval is ambiguous, ask one clarifying question rather than guessing.

---

## Stage 4: Implement the approved plan

**Your goal**: A minimal, correct diff that matches the approved plan and repository conventions.

You must:

- Follow the approved plan exactly
- Match naming, types, and documentation tone in touched files
- For new skills: start from `templates/python_skill/` and replace all placeholders with real values under `skills/`
- Run or request these commands from the repository root as you finish:

```bash
python -m black .
python -m flake8 .
pytest tests/
```

For a single skill:

```bash
pytest skills/<category>/<skill_name>/test_skill.py
pytest tests/test_skill_issuer.py
```

Before Stage 5, scan your diff for:

- Unrelated files
- Secrets or `.env` content
- Emojis
- Template placeholders under `skills/` (`Your Name`, `you@example.com`, `YOUR ORG`)

---

## Stage 5: Verify your own work

**Your goal**: Treat the task as incomplete until issue criteria, checklists, and tests align.

Run a **pre-PR audit** on yourself:

1. Map every acceptance criterion in the issue to a file or test in your diff.
2. Complete the [verification checklist](#verification-checklists-by-contribution-type) for your contribution type.
3. Run `flake8` and `pytest`; report actual command output to your operator—do not claim success without evidence.
4. Draft PR template answers: check only boxes that apply; fill the skill section only if `skills/` changed.

If anything fails, return to Stage 4, fix, and audit again.

---

## Stage 6: Prepare branch, commit, and push

**Your goal**: Clean git artifacts your operator can push or approve.

Propose:

```bash
git status
git add <paths>
git commit -m "Short imperative summary." -m "Body with context. Fixes #<number>"
git push -u origin feat/issue-<number>-short-description
```

Commit message rules you must follow:

- Imperative mood (`Add`, `Fix`, `Document`)
- No emojis
- Issue references when appropriate (`Fixes #57`, `Refs #12`)
- Prefer scoped `git add` over blind `git add -A` when the diff is mixed

Confirm the diff contains no credentials or accidental large binaries before you ask for a push.

---

## Stage 7: Support the pull request through CI

**Your goal**: A reviewable PR against `ARPAHLS/skillware` `main` that passes CI.

You should:

1. Draft the PR description (why, not only what; link the issue).
2. Map changed files to the [pull request template](../../.github/PULL_REQUEST_TEMPLATE.md)—skill checklist only when `skills/` changed.
3. Monitor CI (lint and `pytest tests/`). If checks fail, diagnose, fix in Stage 4, and push to the same branch.
4. Address review comments with focused follow-up commits.

Do not force-push shared branches unless a maintainer instructs you.

---

## Skillware rules you must follow

These align with [CONTRIBUTING.md](../../CONTRIBUTING.md). Violations block merge.

### Style and communication

- No emojis in code, docs, commits, or PR titles
- Clear, professional prose; no comment noise that restates obvious code

### Skills (under `skills/`)

- Bundle: `manifest.yaml`, `skill.py`, `instructions.md`, `card.json`, `test_skill.py`, plus catalog docs
- `manifest.yaml` is source of truth for schema, constitution, `requirements`, `env_vars`, and `issuer`
- `issuer.name` and `issuer.email` required; `github` and `org` optional; no template placeholders in registry paths
- `card.json` issuer must match manifest `name` and `email` when present
- Update `docs/skills/<skill_name>.md` and `docs/skills/README.md`
- On each catalog page, add a **Usage Examples** section (Gemini, Claude, OpenAI, DeepSeek, Ollama prompt mode) per [skill usage template](../usage/skill_usage_template.md). Keep provider mechanics in `docs/usage/`; put skill-specific paths, sample user messages, and `execute` payloads on the skill page.
- Categories: `compliance`, `data_engineering`, `finance`, `office`, `optimization`—propose new ones in the issue first
- Do not bump `pyproject.toml` version in skill-only PRs unless requested
- Logic in `skill.py`; prompts and persona in `instructions.md`
- Never commit secrets; document `env_vars` in the manifest

### Core framework (`skillware/core/`)

- Require a framework feature issue; add tests under `tests/`
- Do not change `loader.py` unless the issue requires it
- Issuer metadata is not passed into LLM tool schemas today
- Update `docs/usage/` when adapter behavior changes

### Documentation

- Fix broken links when you move files
- Link to [TESTING.md](../TESTING.md) instead of duplicating long command lists
- Provider integration: [Usage guides index](../usage/README.md), [agent loops](../usage/agent_loops.md), and [examples/README.md](../../examples/README.md) for runnable script inventory. Per-skill copy-paste examples belong on `docs/skills/<skill_name>.md`, not repeated in full on every provider guide.

### Conduct

- Follow the [Agent Code of Conduct](../../CODE_OF_CONDUCT.md)

---

## Verification checklists by contribution type

Complete the checklist that matches your issue during Stage 5.

### New or updated skill

- [ ] `skills/<category>/<skill_name>/` exists with full bundle
- [ ] `manifest.yaml`: `name`, `version`, `description`, `parameters`, `constitution`, real `issuer`
- [ ] Optional: `short_description` field (~80 chars) for a concise one-line summary in `skillware list`
- [ ] `skill.py`: deterministic, JSON-serializable returns, safe error handling
- [ ] `instructions.md`: when to use, how to interpret output, limitations
- [ ] `card.json`: `issuer` matches manifest
- [ ] `test_skill.py` passes
- [ ] `docs/skills/<skill_name>.md` and catalog row in `docs/skills/README.md`
- [ ] **Usage Examples** on the catalog page (all five providers per [skill usage template](../usage/skill_usage_template.md)); link to `docs/usage/` and list skill `env_vars` without duplicating [api_keys.md](../usage/api_keys.md)
- [ ] `pytest tests/test_skill_issuer.py` passes
- [ ] `SkillLoader.load_skill("<category>/<skill_name>")` works or deps are documented
- [ ] `examples/README.md` updated if a new or changed script lives under `examples/`
- [ ] No placeholders under `skills/`
- [ ] PR skill section completed

### Documentation only

- [ ] All issue acceptance criteria met
- [ ] Links valid
- [ ] `examples/README.md` row added or updated if the issue touches runnable examples
- [ ] No emojis; tone matches repo
- [ ] No unrelated code changes
- [ ] PR marked as documentation; skill checklist omitted unless `docs/skills/` or skill **Usage Examples** changed (then apply the Usage Examples bullet above)

### Core framework

- [ ] Framework issue approved
- [ ] Changes in `skillware/` and relevant `tests/`
- [ ] `pytest tests/` passes
- [ ] Usage docs updated if API changed
- [ ] No undeclared breaking changes

### Bug fix

- [ ] Reproduction understood
- [ ] Minimal fix
- [ ] Regression test when feasible
- [ ] `flake8` and `pytest` pass

### Good first issue

- [ ] Criteria read literally
- [ ] Clarification requested in issue if scope is unclear
- [ ] Checklist for underlying type applied

---

## Self-check protocol (use between stages)

Run this internal dialogue before you hand off to your operator.

**After Stage 2 (analysis)**

- Did I read CONTRIBUTING and the full issue?
- Did I list out-of-scope items explicitly?
- Did I avoid writing code?

**After Stage 4 (implementation)**

- Does every changed file serve the approved plan?
- Did I run or request black, flake8, and pytest?
- Are registry skills free of template placeholders?

**After Stage 5 (verification)**

- Can I map each acceptance criterion to a diff hunk or test?
- Did I complete the right checklist section?
- Is the proposed commit message imperative and emoji-free?

**Before Stage 7 (PR)**

- Does the PR description explain why?
- Did I link the issue with `Fixes` or `Refs`?
- Are PR template checkboxes accurate—not copy-pasted unchecked defaults?

---

## Related documents

- [CONTRIBUTING.md](../../CONTRIBUTING.md) — contribution hub and skill standard
- [TESTING.md](../TESTING.md) — Black, Flake8, Pytest
- [Usage guides](../usage/README.md) — provider adapters (`to_gemini_tool`, `to_openai_tool`, etc.)
- [Agent loops](../usage/agent_loops.md) — shared load / execute / tool-result pattern
- [Skill usage example template](../usage/skill_usage_template.md) — what each skill catalog page must include
- [API keys for skills](../usage/api_keys.md) — env setup (link from skill pages; do not duplicate)
- [Agent Code of Conduct](../../CODE_OF_CONDUCT.md)
- [Pull request template](../../.github/PULL_REQUEST_TEMPLATE.md)
- [Skill library](../skills/README.md)

---

You belong in this ecosystem. Ship work you can defend in review: small scope, clear analysis, deterministic skills, and honest test results. That is how you help Skillware grow—and how you grow with it.

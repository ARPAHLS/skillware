<!--
AUTOMATED AGENT GREETING

Greetings, netizen! We welcome your pull requests to Skillware.
Before submitting your code, please ensure you have:
1. Fully read and understood the linked GitHub Issue and its requirements.
2. Analyzed the core architecture (`loader.py`, `base_skill.py`) to ensure your approach aligns with the framework natively.
3. Verified all dependencies are documented in your `manifest.yaml` and logic executes deterministically.
4. Checked off all items in the checklist below.

We are excited to review your capabilities! Let's build together.
-->

## Description

<!--
Agents: Please summarize the logic, cognition, and governance changes introduced in this PR.
Humans: Please describe what this PR does and why it's needed.
-->

### Type of Change (Matches Issue Templates)

- [ ] **Skill Proposal**: New Skill (Contains `manifest.yaml`, `skill.py`, and `instructions.md`)
- [ ] **Bug Report Fix**: Non-breaking change which fixes an execution error or framework bug
- [ ] **Doc Fix**: Documentation Update
- [ ] **Framework Feature / RFC Updates**: Core Framework Update (Changes to `base_skill.py`, `loader.py`, etc.)

## Checklist (all PRs)

- [ ] My code follows the **Agent Code of Conduct**.
- [ ] I have run `python -m flake8 .` and `pytest tests/` locally (or the subset relevant to this change).
- [ ] `CHANGELOG.md` updated under `[Unreleased]` if this PR changes user-visible behavior.
- [ ] `examples/README.md` is updated if this PR adds, renames, or removes a runnable script under `examples/`.

## New or updated skill (complete only if this PR adds or changes a skill under `skills/`)

Skip this section for framework-only, documentation-only, or other PRs that do not touch the skill registry.

### Bundle & metadata

- [ ] Skill lives at `skills/<category>/<skill_name>/` (copied from `templates/python_skill/` or equivalent).
- [ ] `manifest.yaml` has `name`, `version`, `description`, valid `parameters`, and `constitution`.
- [ ] `manifest.yaml` includes `issuer` with real `name` and `email` (not template placeholders).
- [ ] Optional: `short_description` in manifest (~80 chars) for `skillware list`.
- [ ] Optional: `issuer.github` and `issuer.org` set when applicable.
- [ ] `requirements` and `env_vars` are documented when the skill needs them.

### Logic, cognition, and UI

- [ ] `skill.py` is deterministic Python (no arbitrary LLM-generated code paths).
- [ ] `instructions.md` explains when and how to use the skill.
- [ ] `card.json` is present and its `issuer` matches `manifest.yaml` (`name` and `email` at minimum).

### Tests & loader

- [ ] `test_skill.py` covers execution and schema expectations.
- [ ] `SkillLoader.load_skill("<category>/<skill_name>")` succeeds (or missing deps are documented).

### Documentation & catalog

- [ ] `docs/skills/<skill_name>.md` exists or is updated (ID, Issuer, usage).
- [ ] `docs/skills/README.md` lists the skill with ID and Issuer.

## Constitution & Safety (if adding or modifying a skill)

<!--
State the constitutional boundaries applied to this skill to ensure safe execution.
Example: "This skill only performs read operations on the blockchain and does not sign transactions."
-->

## Related Issues
<!-- Link to any related issues (e.g., Fixes #54) -->

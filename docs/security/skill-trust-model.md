# Skill Trust Model & Operator Security

This page explains how Skillware resolves and executes skills on disk, and how you should reason about trusting them.

**None of these tiers are sandboxed today.** Loading a skill runs its Python in your host process. Trust in Skillware is based on provenance — where a skill came from and who reviewed it — not on runtime isolation. Nothing described below prevents a skill from doing anything your own process can do. Read this page before loading skills you did not write.

## 1. Executive summary

When you load a skill, Skillware executes that skill's skill.py in your host process. Import runs the module's top-level code immediately, and from that point the skill's code has the same reach your process has: the full filesystem and every environment variable in os.environ, including secrets and API keys.

There is no isolation, no permission boundary, and no capability restriction around this execution. SkillLoader checks that a skill's declared requirements are importable, but it does not inspect, restrict, or sandbox what the code does. So the real decision each time you load a skill is: am I willing to hand this code my machine and my secrets?

The trust tiers in this document describe how much you should trust a skill's origin. They are not isolation levels. To be explicit: none of them are sandboxed today.

## 2. How skills are resolved on disk

When you pass a registry id (for example finance/wallet_screening) rather than a path that already exists, the loader searches a fixed set of roots and uses the first match it finds, in this order:

1. SKILLWARE_SKILL_PATH — one or more roots, separated by your OS path separator.
2. ./skills/ in the current working directory, and its parent directories — the loader walks up to six levels of parents looking for a skills/ directory.
3. Bundled skills shipped inside the installed skillware package (for example under site-packages/skills/).

If you pass a path that already points at a skill directory (absolute or relative to the current directory), the loader uses it directly and skips the search entirely.

### Shadowing

Because the search stops at the first matching id, a skill earlier in the order shadows any skill with the same id later in the order. If a finance/wallet_screening exists under SKILLWARE_SKILL_PATH or in a local ./skills/, it is loaded instead of the bundled, maintainer-reviewed copy of the same id — and the bundled copy never runs.

Run `skillware paths` to see which roots are active and which IDs shadow bundled registry skills.

The practical consequence: placing a skill with the same id as an official one, anywhere earlier in the search order, silently replaces the official skill. Shadowing is a normal feature of the resolution order, but it means the id you ask for does not by itself tell you which code will run — the location does.

### Flat vs registry layout

A private, local skill can live either in registry layout (`<skill_root>/<category>/<skill_name>/`) or in a flat layout (`<skill_root>/<skill_name>/`). Both load. One practical wrinkle: `skillware list` only discovers the two-level registry layout, so a flat skill loads fine but does not appear in `list`. If a local skill loads but is missing from `list`, a flat layout is usually why.

## 3. Provenance tiers

A skill's tier describes where it came from and who reviewed it, which is the basis for how much you should trust it. It does not describe runtime isolation. All tiers execute the same way, in your host process.

| Tier | Where it comes from | Reviewed by | Basis for trust | Sandboxed? |
| :--- | :--- | :--- | :--- | :--- |
| **Bundled registry** | Shipped in the skillware wheel (site-packages/skills/) | Maintainers, via pull-request review | Public review before it ships | No |
| **Project-local** | ./skills/ in your project (cwd or a parent) | You / your team | You put it there | No |
| **External** | SKILLWARE_SKILL_PATH or an absolute path | No one, until you review it | Treat as untrusted until read | No |

**Bundled registry.** These ship inside the package and go through maintainer pull-request review before release. This is the most trustworthy origin, but review is not isolation: a bundled skill still runs unsandboxed in your process.

**Project-local.** Skills in your project's ./skills/ (or a parent's). Trust here is simply trust in you and your team — you are responsible for the code you place there.

**External.** Skills loaded from SKILLWARE_SKILL_PATH or an absolute path. This is third-party code you did not write and no one has reviewed for you. Treat it as untrusted until you have read it yourself.

## 4. constitution is guidance, not isolation

A skill's manifest.yaml can declare a constitution — a set of natural-language rules such as "use a dedicated wallet only," "never pass private keys in tool arguments," or "fail closed on missing confirmation." For example, defi/evm_tx_handler declares a constitution covering dedicated wallets, secret handling, and fail-closed behavior.

A constitution guides the agent (the LLM calling the skill). It does not constrain skill.py. Nothing in the loader enforces a constitution at the Python level — code that ignores every rule in the constitution loads and runs exactly the same. The constitution is a prompt-level norm, not a process-level boundary.

The same distinction applies to other manifest fields. Declaring env_vars documents which variables a skill expects; it does not limit what the code can read. The loader's requirements check confirms that declared packages are importable; it does not inspect what the code does with them. In short:

| constitution / manifest does | It does not |
| :--- | :--- |
| Tell the agent how the skill should be used | Sandbox or restrict skill.py |
| Document expected env vars and dependencies | Limit which env vars or files the code can access |
| Set norms reviewers and agents can rely on | Enforce those norms at runtime |

## 5. Concrete flows

Three common setups and what to watch for in each.

**pip-only agent.** You pip install skillware and use only bundled skills (Bundled). Origin trust is highest here — the skills were reviewed before shipping — but execution is still unsandboxed: a bundled skill runs in your process with full access like any other. The risk is lower because of review, not because of isolation.

**Development with ./skills/.** You keep project skills in ./skills/ (Project). Two things to keep in mind: trust rests on whoever on your team wrote the code, and shadowing applies — a local skill with the same id as a bundled one replaces it. Check that you are not unintentionally overriding an official skill with a local id.

**External path.** You point SKILLWARE_SKILL_PATH at a third-party skills directory (External). This is the highest-risk case: unreviewed code runs in your process with access to your entire os.environ. Because a skill can read environment variables and make network calls, a malicious or careless external skill could read your API keys or secrets and send them elsewhere — nothing in the loader prevents this. Only load external skills you have read.

## 6. Operator checklist

Because there is no default isolation, these precautions are on you, the operator — the loader does not do them for you:

- Read external (External) skills before you load them. Do not run third-party skill code you have not looked at.
- Use dedicated, least-privilege API keys for agent work. Any loaded skill can read every variable in os.environ, so do not expose production or personal full-access keys.
- Do not run untrusted skills on a machine that holds production secrets.
- Watch for shadowing: confirm a local ./skills/ id is not unintentionally overriding a bundled skill.
- When running skills you do not fully trust, run them in a minimal or containerized environment. This is your own isolation, outside Skillware — the loader provides none.

## 7. Where this is going

This document describes the current state (Phase 0): an honest account of how loading works today, with no isolation. Isolation and trust controls are being discussed in follow-up work:

- #110 — Phase 1: operator warnings and a trust flag for remote/external code.
- #111 and #39 — scoped secrets, so skills see only the environment they need.
- #112–#114 — research into stronger isolation (for example WASM or container-based sandboxing).
- #17 — the parent Security Sandboxing RFC, which remains the decision record for this area.

Until those land, treat every tier as unsandboxed and trust skills by their provenance.

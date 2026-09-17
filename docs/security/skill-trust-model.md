# Skill Trust Model & Operator Security

How Skillware loads skills, how you run them with confidence, and where to look when something is not the bundled default.

Most operators: `pip install skillware`, copy `.env`, run `skillware doctor`, load bundled skills, execute. The sections below add detail when you use project skills, external paths, or multi-skill hosts.

---

## 1. What you can rely on today

| Layer | What it gives you |
| :--- | :--- |
| **Bundled registry** | Maintainer-reviewed skills in the wheel — Contract, Effect, Directive, Assurance, and Presentation in every bundle |
| **Manifest contract** | Declared `env_vars`, `requirements`, `constitution`, and `issuer` — documented before you run |
| **Load-time checks** | Import/version validation for declared `requirements` before `skill.py` executes |
| **Credentials (#39)** | `BaseSkill.credential()` (config first, `.env` fallback); hosts inject via [secret providers](../usage/api_keys.md#secret-managers) without polluting global `os.environ` |
| **CLI readiness** | `skillware doctor` (deps, import, **ENVS**), `skillware paths` / `paths shadows` (tiers and shadowing), `skillware test` (Assurance) |
| **Multi-skill hosts** | `SkillContext` discovery with tier labels, shadow warnings, and optional `secret_provider` per session |

Skills run in your Python process — the same model as importing a local library. Skillware focuses on **clear provenance**, **declared credentials**, and **operator tooling** so you know what runs and whether it is ready.

---

## 2. How skills are resolved

Pass a registry id (for example `finance/wallet_screening`) or an absolute path to a skill directory.

**Default (no config file):**

1. `SKILLWARE_SKILL_PATH` — one or more roots (OS path separator between entries)
2. `./skills/` in the current working directory and its parents (up to six levels)
3. Bundled skills inside the installed `skillware` package (`site-packages/skills/`)

**With config (`.skillware.yaml` or global `config.yaml`):** resolution follows `resolution.order` (default: **project → external → bundled**). Persist private roots under `paths.external`; set `paths.project` to `auto` or an explicit directory. Bundled registry skills are always included. See `skillware config show` and [CLI config](../usage/cli.md#skillware-config).

An absolute or cwd-relative path to a skill directory skips search and loads that folder directly.

### Shadowing

Search stops at the **first** matching id. A project or external skill with the same id as a bundled one **replaces** the bundled copy for that process.

Inspect active roots and conflicts:

```bash
skillware paths
skillware paths shadows   # summary only
```

`SkillContext` also appends shadow warnings to `ctx.warnings` when it discovers overlapping ids.

### Flat vs registry layout

Registry layout: `<root>/<category>/<skill_name>/`. Flat layout: `<root>/<skill_name>/`. Both load. `skillware list` only discovers registry layout — a flat skill may load but not appear in `list`.

---

## 3. Provenance tiers

The tier describes **who reviewed the origin**, not a runtime sandbox.

| Tier | Source | Reviewed by | Recommended for |
| :--- | :--- | :--- | :--- |
| **Bundled** | Shipped in the `skillware` wheel | Maintainers (pull-request review) | Default — production agents and tutorials |
| **Project** | `./skills/` in your repo (cwd or parent) | You / your team | Private extensions and overrides |
| **External** | `SKILLWARE_SKILL_PATH` or absolute path | You, when you adopt it | Private registries, pinned forks, experiments |

**Bundled** — reviewed before release, documented `env_vars`, registry Assurance tests, and `credential()` for declared keys.

**Project** — your code; same secret-provider patterns as production when multiple skills share a process.

**External** — pin versions (commit or copy) when you depend on them; re-check on update. Skillware loads the code; maintenance and review are between you and the skill author (see identity RFC #234).

**Support:** bundled skill or loader issues → this repository. Issues inside an external skill → that skill's maintainer.

---

## 4. Manifest, constitution, and Assurance

Every registry bundle follows [skill anatomy](../introduction.md#skill-anatomy):

- **Contract** (`manifest.yaml`) — name, version, parameters, `env_vars`, `requirements`, `constitution`, `issuer`
- **Effect** (`skill.py`) — deterministic `execute()`; bundled skills use `credential()` for declared keys
- **Directive** (`instructions.md`) — when and how the host agent should call the skill
- **Assurance** (`test_skill.py`) — offline pytest; run locally with `skillware test <id>` or `pytest skills/`

**Constitution** — agent-facing rules in Contract (dedicated wallets, confirm-before-send, no secret logging). Reviewers and operators rely on them; bundled skills are written to honor them.

**`env_vars`** — exact credential names the skill expects. `skillware doctor` reports missing **required** keys in the **ENVS** column. Hosts inject values via `SkillLoader.resolve_env_vars()` or `SkillContext(secret_provider=...)`.

**`requirements`** — optional dependencies checked at load (importable; version pins enforced when declared).

---

## 5. Credentials and production hosts

**Local development:** copy `.env.example` → `.env`, optionally `load_env_file()`, construct skills normally — `credential()` falls back to `os.environ`.

**Production:** inject manifest keys through a [secret provider](../usage/api_keys.md#secret-managers):

```python
from skillware import SkillContext
from skillware.core.secrets import MappingSecretProvider

ctx = SkillContext(
    skills=["office/gmail_handler"],
    secret_provider=MappingSecretProvider({
        "GMAIL_ADDRESS": "...",
        "GMAIL_APP_PASSWORD": "...",
    }),
)
ctx.execute("office/gmail_handler", {"action": "mailbox_status"})
```

- `MappingSecretProvider(dict)` — values already fetched (Vault, K8s, cloud secret store)
- `CallableSecretProvider(fetcher)` — callback per key (STS, workload identity)
- `EnvSecretProvider()` — read from `os.environ` after `load_env_file()`
- Custom `get(key)` — full control (ephemeral tokens)

With a provider set, `SkillContext.execute()` re-resolves credentials each call — short-lived tokens work. Use one context (or provider) per tenant.

Demo: [`examples/secret_provider_demo.py`](../../examples/secret_provider_demo.py).

---

## 6. Multi-skill sessions and chains

[`SkillContext`](../usage/skill_chaining.md#skillcontext--discovery-filters) discovers skills by id, category, or root filter; labels each id with its tier in brief lines; surfaces shadow conflicts in `warnings`; and exposes `tools(provider)` for Gemini, Claude, OpenAI, DeepSeek, Bedrock, and Ollama.

Named **chains** (`skillware chain …`) run ordered steps with optional `when:` skips — useful for guardrails (sanitize → mask PII → call model) without ad-hoc orchestration code.

When mixing bundled and local skills, run `skillware paths shadows` once during setup.

---

## 7. Untrusted inputs

Some skills consume **third-party content** (web pages, email, attachments). Bundled skills mark risky payloads (for example `untrusted_content: true` on Gmail read/download) so agents treat them as data, not instructions.

Recommended defense chain for browser agents:

1. **`security/deceptive_ui_guard`** — scan page HTML before clicks or checkout
2. **`security/prompt_injection_firewall`** — scan text before it enters the model context

Compose with [`SkillContext`](../usage/skill_chaining.md) or explicit `execute()` calls at the trust boundary. See skill catalog pages for chaining examples (`gmail_handler`, `semantic_web_proxy`, `pii_masker`).

Instruction-only packs (markdown the agent reads, no `skill.py` execute) still affect agent behavior — apply the same provenance judgment as executable skills when the source is external.

---

## 8. Common setups

**pip-only agent (recommended).** Install skillware, use bundled skills, `.env` locally or secret providers in production. Run `skillware doctor` before going live.

**Project `./skills/`.** Add team skills under `./skills/<category>/<name>/`. Check `skillware paths shadows` so a local id is not accidentally overriding a bundled skill.

**External path.** Point `SKILLWARE_SKILL_PATH` at a private tree; pin versions; use secret providers for production keys.

**Enterprise cloud.** Model credentials (Bedrock IAM, Azure SP, Vertex ADC) are separate from skill `env_vars` — see [enterprise cloud](../usage/enterprise_cloud.md).

---

## 9. Operator checklist

- Start with **bundled** skills; run **`skillware doctor`**
- Use **dedicated, least-privilege keys** (agent mailbox, scoped API tokens)
- In production, prefer **secret providers** over exporting keys to `os.environ`
- Run **`skillware paths shadows`** when adding project or external skills
- Pin and re-read **external** skills when you update them
- Chain **security skills** at untrusted-input boundaries when agents browse or read mail

---

## 10. Roadmap

**Shipped (#39):** host-injected credentials, `credential()` on bundled skills, doctor **ENVS** checks.

**Planned:**

- #110 — operator warnings and a trust flag for remote/external code
- #111 — tighter scoped-secret enforcement
- #112–#114 — stronger isolation research (WASM, containers)
- #17 — parent Security Sandboxing RFC

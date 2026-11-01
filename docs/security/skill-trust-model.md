# Skill Trust Model & Operator Security

How Skillware loads skills, how you run them with confidence, and where to look when something is not the bundled default. Terms: [glossary.md](../glossary.md).

Most operators: `pip install skillware`, copy `.env`, run `skillware doctor`, load bundled skills, execute. The sections below add detail when you use project skills, external paths, or multi-skill hosts.

---

## 1. What you can rely on today

| Layer | What it gives you |
| :--- | :--- |
| **Bundled registry** | Maintainer-reviewed skills in the wheel — Contract, Effect, Directive, Assurance, and Presentation in every bundle |
| **Manifest v2 Contract** | Declared `shape`, `tier`, `target`, `tags`, `env_vars`, `requirements`, `constitution`, and `issuer` — schema-validated before you run |
| **Load-time checks** | Import/version validation for declared `requirements` and Manifest v2 JSON schema before `skill.py` executes |
| **Hardware & bioware safety gate** | Emits `SkillwareHardwareSafetyWarning` when autonomous agents attempt to execute `hardware` or `bioware` targets without explicit operator confirmation |
| **Credentials & isolation** | `BaseSkill.credential()` (config first, `.env` fallback); hosts inject via [secret providers](../usage/api_keys.md#secret-managers) without polluting global `os.environ` |
| **AST security audits** | Automated offline enforcement (`tests/test_security_audit.py`) blocking dynamic execution (`eval`, `exec`, `compile`) and direct `os.environ` reads |
| **CLI readiness** | `skillware doctor` (deps, import, **ENVS**), `skillware paths` / `paths shadows` (tiers and shadowing), `skillware test` (Assurance), `skillware find` (readiness probing) |
| **Multi-skill hosts** | `SkillContext` discovery with taxonomy filtering, progressive disclosure (`brief` mode), concurrency limiting (`max_concurrency`), shadow warnings, and session secret providers |

Skills run in your Python process — the same model as importing a local library. Skillware focuses on **clear provenance**, **declared credentials**, **hermetic AST invariants**, and **operator tooling** so you know what runs and whether it is ready.

---

## 2. How skills are resolved

Pass a registry id (for example `finance/wallet_screening`) or an absolute path to a skill directory.

**Default resolution order:**

1. `paths.override` — local override root that supersedes all other roots (precedence 0)
2. `paths.external` / `SKILLWARE_SKILL_PATH` — external directories (precedence 1)
3. `paths.project` / `./skills/` — active workspace repository (cwd or up to 6 parent levels, precedence 2)
4. `paths.bundled` — bundled skills inside the installed `skillware` distribution (`site-packages/skills/` or repo `skills/`, precedence 3)

**With config (`.skillware.yaml` or global `config.yaml`):** resolution follows `resolution.order` (default: **project → external → bundled**). Persist private roots under `paths.external`; set `paths.project` to `auto` or an explicit directory. Bundled registry skills are always included as fallback. See `skillware config show` and [CLI config](../usage/cli.md#skillware-config).

An absolute or cwd-relative path to a skill directory skips search and loads that folder directly.

### Shadowing

Search stops at the **first** matching id. A project, external, or override skill with the same id as a bundled one **replaces** the bundled copy for that process.

Inspect active roots and conflicts:

```bash
skillware paths
skillware paths shadows   # summary only
```

`SkillContext` also appends shadow warnings to `ctx.warnings` when it discovers overlapping ids during host initialization.

### Flat vs registry layout

Registry layout: `<root>/<category>/<skill_name>/`. Flat layout: `<root>/<skill_name>/`. Both load. `skillware list` only discovers registry layout — a flat skill may load by explicit path or ID, but registry tools expect `category/name`.

---

## 3. Provenance tiers vs Manifest tiers

It is essential to distinguish between where a skill was discovered on disk (**Skill root tier / Provenance tier**) and what infrastructure dependencies the skill declares in its manifest (**Manifest tier / Package tier**).

### Skill root tiers (Provenance)

The provenance tier describes **who reviewed the origin and where the code resides**, not a runtime sandbox.

| Tier | Source | Reviewed by | Recommended for |
| :--- | :--- | :--- | :--- |
| **Override** | Operator-defined local override root | You | Urgent local hotfixes and targeted patch overrides |
| **Bundled** | Shipped in the `skillware` wheel | Maintainers (pull-request review) | Default — production agents and enterprise workflows |
| **Project** | `./skills/` in your repo (cwd or parent) | You / your team | Private extensions and repository-specific skills |
| **External** | `SKILLWARE_SKILL_PATH` or absolute path | You, when you adopt it | Private registries, pinned forks, third-party packs |

**Bundled** — reviewed before release, documented `env_vars`, registry Assurance tests, and `credential()` for declared keys.

**Project** — your code; same secret-provider patterns as production when multiple skills share a process.

**External** — pin versions (commit hash or vendored copy) when you depend on them; re-check on update. Skillware loads the code; maintenance and review are between you and the skill author.

### Manifest tiers (Infrastructure footprint)

Declared in `manifest.yaml` under `tier:`:

- **`tier: core`**: Zero external paid cloud API dependencies; runs fully locally and offline with standard libraries or local weights.
- **`tier: cloud`**: Requires external cloud APIs, hosted LLM endpoints, or network JSON-RPC connections.
- **`tier: enterprise`**: Requires enterprise-grade infrastructure, private databases, VPCs, KMS, or compliance vaults.

---

## 4. Manifest v2, taxonomy, constitution, and Assurance

Every registry bundle follows [skill anatomy](../introduction.md#skill-anatomy):

- **Contract** (`manifest.yaml`) — name, version, taxonomy (`shape`, `tier`, `target`, `tags`), parameters, `outputs`, `env_vars`, `requirements`, `constitution`, and `issuer`
- **Effect** (`skill.py`) — deterministic `execute()`; uses `self.credential()` for declared keys; zero raw `os.environ` reads
- **Directive** (`instructions.md`) — when and how the host agent should call the skill (skill context, not host persona)
- **Assurance** (`test_skill.py`) — offline pytest suite; run locally with `skillware test <id>` or `pytest skills/`

### Manifest v2 Universal Taxonomy

Skills declare their operational archetype and execution surface in `manifest.yaml`:

* **Shape** (`shape:`):
  * `atomic`: Single-step tool execution returning deterministic output.
  * `workflow`: Multi-step orchestrated pipeline with distinct internal stages.
  * `middleware`: Interceptor that inspects, sanitizes, validates, or gates inputs/outputs before reaching models or tools.
  * `stream`: Streaming event processor handling continuous or chunked metrics/telemetry.
* **Target** (`target:`): List of execution substrates (`software`, `hardware`, `bioware`).
* **Tags** (`tags:`): 2 to 10 curated semantic and domain discovery keywords (`^[a-z0-9_-]+$`).

### Physical & Bioware Safety Gate

Autonomous execution of physical or wetware systems presents real-world hazards. When a skill declares `target: [hardware]` or `target: [bioware]`, Skillware enforces a safety gate:

* `SkillContext` defaults to `allow_hardware_execution=False`.
* If an agent attempts to execute a hardware/bioware skill without explicit operator confirmation, the runtime emits a `SkillwareHardwareSafetyWarning`.
* Operators must explicitly set `allow_hardware_execution=True` in host code or confirm physical execution gates before actions reach actuators, robotics, or biosensors.

### Constitution

Prompt-level rules in Contract (for example dedicated wallets, confirm-before-send, no secret logging). Reviewers and operators rely on them; bundled skills are written to honor them.

### `env_vars` and `requirements`

`env_vars` documents exact credential names the skill expects. `skillware doctor` reports missing **required** keys in the **ENVS** column. Hosts inject values via `SkillLoader.resolve_env_vars()` or `SkillContext(secret_provider=...)`.

`requirements` declares dependencies validated at load time (PEP 508 strings; version pins enforced when declared).

---

## 5. Credentials and production hosts

**Local development:** copy `.env.example` → `.env`, optionally `load_env_file()`, construct skills normally — `self.credential()` falls back to `os.environ`.

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
- Custom `SecretProvider` — full control (ephemeral tokens)

With a provider set, `SkillContext.execute()` re-resolves credentials each call — short-lived tokens work. Use one context (or provider) per tenant.

**Credential Sandboxing Invariant:** Skills must never read `os.environ` directly for API keys or secrets. Direct environment reads bypass tenant scoping and are blocked during CI via AST audits (`tests/test_security_audit.py`).

Demo: [`examples/secret_provider_demo.py`](../../examples/secret_provider_demo.py).

---

## 6. Multi-skill sessions, concurrency, and chains

[`SkillContext`](../usage/skill_chaining.md#skillcontext--discovery-filters) provides multi-skill orchestration with built-in security and performance controls:

- **Discovery and Taxonomy Filtering**: Filter available skills by `categories`, `allowed_shapes`, `allowed_tiers`, `allowed_targets`, or `tags`.
- **Progressive Disclosure (`mode="brief"`)**: By default, `SkillContext` generates compact single-line summaries (`- **{name}** [{trust_tier}][{pkg_tier}:{shape}:{target}]: {short}`) consuming ~45 tokens per skill instead of injecting thousands of tokens of raw playbooks into the prompt.
- **Concurrency Limiting (`max_concurrency`)**: Configurable `asyncio.Semaphore` bounds concurrent skill executions, protecting downstream APIs and local compute from agent loop stampedes.
- **Provider Adapters**: Exposes `tools(provider)` for Gemini, Claude, OpenAI, DeepSeek, Bedrock, and Ollama without ad-hoc conversion code.

Named **chains** (`skillware chain run …`) run ordered steps with optional `when:` skips — useful for guardrails (sanitize → mask PII → call model) without ad-hoc orchestration code.

When mixing bundled and local skills, run `skillware paths shadows` once during setup.

---

## 7. Untrusted inputs and middleware guardrails

Some skills consume **third-party content** (web pages, email, attachments, blockchain logs). Bundled skills mark risky payloads (for example `untrusted_content: true` on Gmail read/download) so agents treat them as data, not instructions.

Skills with `shape: middleware` are designed to sit between external data sources and model execution:

1. **`security/deceptive_ui_guard`** — scan page HTML for phishing, dark patterns, or clickjacking before browser clicks
2. **`security/prompt_injection_firewall`** — scan text before it enters the model context
3. **`compliance/pii_masker`** — mask sensitive identifiers before data reaches model prompts or logs

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
- Run **`skillware paths shadows`** when adding project, external, or override skills
- Require explicit confirmation (`allow_hardware_execution=True`) before executing skills targeting `hardware` or `bioware`
- Pin and re-read **external** skills when you update them
- Chain **`shape: middleware`** security skills at untrusted-input boundaries when agents browse, ingest web data, or read mail

---

## 10. The Permissive Fortress Architecture

Under the project's MIT governance, security and supply-chain integrity are enforced through **The Permissive Fortress**: a defense-in-depth model that combines inbound legal guarantees, runtime credential isolation, and automated CI gatekeepers:

1. **Inbound Legal Guardrails:** All contributions are bound by the [Legal notice and code ownership](../../CONTRIBUTING.md#legal-notice-and-code-ownership) terms upon opening a Pull Request, providing irrevocable licensing, patent non-assertion, and preventing retroactive code takedowns.
2. **Credential Sandboxing:** Third-party skills must never read `os.environ` directly for API keys or secrets. Credentials must be resolved through `BaseSkill.credential()`, which prioritizes injected `credential_fn` callables and `config` mappings over process-global environment variables.
3. **AST Security Audits:** Pull Requests are automatically scanned via `tests/test_security_audit.py` to detect dynamic execution primitives (`eval`, `exec`, `compile`, `__import__`), direct `os.environ` credential reads, or hardcoded secrets. Insecure AST patterns fail CI immediately.
4. **Supply Chain & CVE Auditing:** Dependency trees and optional pip extras (`pip install "skillware[web3]"`) are audited via `pip-audit` to detect known vulnerabilities or package compromises before merge.
5. **AI-Native Integrity:** Inbound skill bundles must adhere to the [Agent Contribution Workflow](../contributing/ai_native_workflow.md), requiring pre-flight tool schema validation, hermetic prompt templating, Manifest v2 taxonomy compliance, and full chaining integration suites.
6. **Social Shield & Enforcement:** Maintainers enforce the [Agent Code of Conduct](../../CODE_OF_CONDUCT.md) with explicit authority to reject PRs, ban bad-faith actors, or block rogue AI bots that attempt credential exfiltration or unauthorized execution.

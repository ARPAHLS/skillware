# Glossary

Canonical Skillware terms. Prefer the **primary** column in new docs. Synonyms are fine once per page for readability; link here on first use.

Skill file roles follow [Skill anatomy](introduction.md#skill-anatomy) ([#326](https://github.com/ARPAHLS/skillware/issues/326)). Do not use retired Mind / Body / Conscience labels.

Inclusive language: [inclusive-language.md](contributing/inclusive-language.md). Issue: [#252](https://github.com/ARPAHLS/skillware/issues/252).

## People and runtimes

| Primary | Means | Do not use for this | Keep when |
| :--- | :--- | :--- | :--- |
| **Operator** | Person who installs Skillware, sets credentials, runs the CLI, and owns fork / commit / PR | admin, generic “user” | — |
| **Contributor** | Person or supervised agent opening PRs on this repository | operator (unless they also run the host) | — |
| **Supervised agent** | Cursor, Copilot, or similar working **on this repo** under an operator | bot, AI contributor, host agent | “human operator” when contrasting with the agent |
| **Host agent** | LLM + tool loop that **loads** skills | contributor, operator, calling agent | — |
| **End user** | Person the host agent is serving (for example “ask the user to confirm send”) | operator | Skill **Directive** copy; templates |

**`user` is not banned.** It stays for LLM `role: "user"`, Keep a Changelog **user-visible**, OS **user-level config** (`~/.config`), and **end user** in Directives.

Do not global-replace `user` → `operator`.

## Skill artifacts

| Primary | Means | Avoid |
| :--- | :--- | :--- |
| **Skill ID** | Registry string `category/name` (folder path, `manifest.name`, CLI `ID`) | “name” alone |
| **Skill directory** | Folder `skills/<category>/<name>/` | “the skill” when the folder vs class is ambiguous |
| **Skill bundle** | That directory on disk, **or** the dict returned by `SkillLoader.load_skill()` (`bundle["class"]`, `bundle["instructions"]`, …) | “package” (conflicts with the PyPI **package** `skillware`) |
| **PyPI package** | Installable `skillware` distribution | calling a registry skill a package |

## Skill anatomy (roles)

| Role | File | Answers |
| :--- | :--- | :--- |
| **Contract** | `manifest.yaml` | Typed I/O, taxonomy, constitution, issuer, requirements |
| **Effect** | `skill.py` | What runs in `execute()` |
| **Directive** | `instructions.md` | When and how the **host agent** should call the skill (skill context, not host persona) |
| **Assurance** | `test_skill.py` | Offline bundle tests |
| **Presentation** | `card.json` | Catalog / UI metadata |
| **Corpus** | `kb/`, `data/`, … | Bundled knowledge Effect reads |
| **Reference** | `schemas/`, maps | Machine-readable adjuncts to Contract |
| **Interface** | `SkillLoader` adapters | Host API tool schemas |

Retired: **Mind**, **Body**, **Conscience** as role names. Filenames did not change.

## Manifest v2 universal taxonomy

Manifest v2 defines four orthogonal taxonomy primitives for every skill bundle in `manifest.yaml`, validated at load time via `skillware.core.manifest_schema`.

| Primary | Means | Values / Format | Avoid |
| :--- | :--- | :--- | :--- |
| **Manifest v2** | Universal taxonomy standard for Skillware bundles; classifies execution topology, dependencies, substrates, and discovery keywords | schema validated via `skillware.core.manifest_schema` | "Manifest v1" (deprecated unclassified manifests) |
| **Shape** | Execution archetype and topology of a skill bundle | `atomic`, `workflow`, `middleware`, `stream` | using "type" or "kind" ambiguously |
| **`atomic`** | Discrete deterministic computation; bounded single-pass execution (`inputs` -> compute -> `outputs`) | shape value | "simple tool", "function" |
| **`workflow`** | Orchestrated multi-step pipeline with internal phase transitions and staging | shape value | "agent loop", "chain" (when internal to the skill) |
| **`middleware`** | Interceptor that inspects, sanitizes, validates, masks, or gates prompts/payloads before or between agent turns (for example PII masking, prompt firewalls) | shape value | "hook", "filter" alone |
| **`stream`** | Streaming event processor handling continuous or chunked telemetry, logs, or metrics | shape value | "listener", "daemon" |
| **Manifest tier** (Package tier) | Infrastructure dependency footprint declared in `manifest.yaml` | `core`, `cloud`, `enterprise` | conflating with **Skill root tier** (provenance) |
| **`core`** | Zero external paid cloud API dependencies; local deterministic compute running on standard library or bundled weights | tier value | "offline-only", "basic" |
| **`cloud`** | Requires third-party cloud APIs, hosted LLM endpoints, or network RPC | tier value | "online", "remote" |
| **`enterprise`** | Requires organizational-grade infrastructure, private databases, VPCs, KMS, or compliance vaults | tier value | "proprietary", "closed" |
| **Target** | Physical execution substrate where the skill takes effect | subset of `["software"]`, `["hardware"]`, `["bioware"]` | execution environment |
| **`software`** | Digital execution (APIs, code, memory, virtual environments) | target value | "virtual" |
| **`hardware`** | Physical execution on robotics, IoT, sensors, actuators, or firmware | target value | "physical" |
| **`bioware`** | Wetware execution (DNA/RNA sequences, laboratory automation, wet-lab protocols) | target value | "biology" alone |
| **Tags** | Curated lowercase alphanumeric semantic discovery keywords for lexical and semantic matching | 2 to 10 tokens matching `^[a-z0-9_-]+$` | keyword stuffing, filler tags (`tool`, `ai`) |
| **Constitution** | Bounded prompt-level safety rules and operational boundaries declared in `manifest.yaml` | string or structured object | system prompt (belongs to host agent) |
| **Hardware safety gate** | Protection mechanism that emits `SkillwareHardwareSafetyWarning` when autonomous agents invoke `hardware` or `bioware` targets without explicit operator confirmation (`allow_hardware_execution=True`) | runtime safety gate in `SkillContext` | unvalidated physical execution |

## Skill roots and provenance tiers

Skill roots define where skills are discovered on the filesystem. The provenance tier determines resolution order when skills share the same ID.

| Primary | Means | Precedence / Resolution | Avoid |
| :--- | :--- | :--- | :--- |
| **Skill root** | Directory searched for registry-layout skills (`category/skill_name/`) | discovered via `skillware.core.discovery` | "skills folder" without qualification |
| **Skill root tier** (Provenance tier) | Provenance and trust level of a discovered skill root on the host machine | `override` > `external` > `project` > `bundled` | conflating with **Manifest tier** (`core`, `cloud`, `enterprise`) |
| **`override`** | Operator-defined local override root that takes highest priority | precedence 0 (highest) | "hotfix root" |
| **`external`** | Discovered from `SKILLWARE_SKILL_PATH` or operator config paths | precedence 1 | "plugin path" |
| **`project`** | Discovered in the active workspace repository (`./skills`) | precedence 2 | "local root" |
| **`bundled`** | Built-in skills shipped inside the installed `skillware` package distribution | precedence 3 (fallback) | "core skills" (conflates with `tier: core`) |
| **Shadow conflict** | Discovered when the same registry Skill ID exists in multiple roots; higher-precedence root wins | recorded as warning in `SkillContext` and CLI | "silent overwrite" |

## Context and progressive disclosure

Skillware provides progressive disclosure primitives via `SkillContext` to prevent context window saturation and prompt bloat.

| Primary | Means | Avoid |
| :--- | :--- | :--- |
| **`SkillContext`** | Host agent context manager that discovers and orchestrates registry skills for multi-skill agent sessions without polluting context windows | raw system prompt stuffing |
| **Context mode** | Strategy used by `SkillContext` for prompt assembly: `brief`, `tools_only`, or `directives` | "prompt style" |
| **`brief` mode** | Default context mode; outputs a single-line taxonomy summary per skill (`- **{name}** [{trust_tier}][{pkg_tier}:{shape}:{target}]: {short}`) consuming ~45 tokens per skill | dumping full documentation into the system prompt |
| **`tools_only` mode** | Exports schema function declarations to the host LLM with zero system prompt injections | "schema-only" |
| **`directives` mode** | Inlines full `instructions.md` playbooks into the host agent system prompt | "full mode", "verbose prompt" |
| **Brief line** | Standardized one-line summary string formatted as `- **{name}** [{trust_tier}][{pkg_tier}:{shape}:{target}]: {short_description}` | unstructured description |
| **JIT context excision** (Progressive disclosure) | Architecture pattern where host agents receive compact brief lines upfront and only read full SOP directives or corpus files just-in-time when invoked | static upfront prompt dump |

## Discovery and intent matching

| Primary | Means | Avoid |
| :--- | :--- | :--- |
| **`SkillMatcher`** | Deterministic registry discovery engine powering `skillware find` that scores skills against natural language queries using tokenization, stemming, fuzzy matching, prerequisite readiness probing, and git commit freshness | vector database dependency for basic CLI search |
| **`SkillMatchResult`** | Structured ranked match object returned by `SkillMatcher` containing confidence score, readiness, missing prerequisites, matched actions, and taxonomy metadata | raw dict results |
| **Readiness probe** | Offline inspection that checks whether a skill's required packages (`requirements`) and environment variables (`env_vars`) are present before invocation | runtime exception on first execution |

## Security and credential isolation

| Primary | Means | Avoid |
| :--- | :--- | :--- |
| **`self.credential()`** | Isolated credential accessor on `BaseSkill`; checks secret providers and config before environment variables | reading raw `os.environ` directly in skill logic |
| **Secret provider** (`SecretProvider`) | Secret resolution callable or mapping injected into `SkillLoader` or `SkillContext` to supply credentials at runtime | hardcoding API keys or storing secrets in git |
| **Credential isolation** | Security standard prohibiting direct environment mutation and raw secret exposure | ambient process environment access |

## Operator configuration

| Primary | Means | Avoid |
| :--- | :--- | :--- |
| **EVM operator config** | Writable `evm.yaml` plus `skillware.core.evm_config` merge helpers for chain IDs, `rpc_env` names, and token registry metadata shared by defi skills — see [EVM operator config](usage/evm_operator_config.md) | putting RPC URLs or private keys in YAML |
| **Shared address book** (operator address book) | Writable `addressbook.yaml` under user config — cross-skill contact identity (mail recipients and defi transfer EOAs) via `skillware.core.mail_config` — see [Address book operator config](usage/addressbook_operator_config.md) | ERC-20 token contracts; orchestration **`chains:`** |
| **`public_0x`** | Optional EVM wallet field on an address-book contact — counterparty **EOA** for defi skills such as `defi/evm_tx_handler` | token/router/pool contract addresses (those belong in `evm.yaml` → `tokens:`) |
| **Orchestration chain** | Named multi-skill pipeline under top-level `chains:` in `.skillware.yaml` (`skillware chain run`) | EVM blockchain network |
| **EVM chain (network)** | JSON-RPC network entry (ethereum, base, …) under `evm:` / `evm.yaml` | orchestration **chain** |

## Deprecated synonyms

| Instead of | Write |
| :--- | :--- |
| calling agent (LLM loading skills) | **host agent** |
| Skill Package Standard | **Skill bundle standard** ([CONTRIBUTING](../CONTRIBUTING.md#skill-bundle-standard)) |
| user (person running Skillware) | **operator** |
| dummy (placeholder data) | mock, stub, **placeholder**, sample |
| master a domain | cover / use a skill in a domain |
| output: (in manifest.yaml) | **outputs:** |
| tool_package | **skill bundle** |

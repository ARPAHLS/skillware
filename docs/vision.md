# Skillware Vision

Skillware is an open registry and Python framework for **installable agent capabilities**. A Skill is not a prompt snippet or a server spec. It is a self-contained bundle: executable logic, instructions for the model, safety rules, and a schema any supported LLM can call. You install know-how the same way you install libraries with `pip`.

This page is the long-form story behind the project. For a scannable overview, start with [README.md](../README.md). For technical contrasts with MCP, LangChain, and similar approaches, see [COMPARISON.md](../COMPARISON.md).

---

## How we started

Every new agent project used to mean rewriting tool definitions, system prompts, and safety checks from scratch. The same wallet check, PDF parser, or data pipeline showed up again under different names, tied to one model API or one framework.

We wanted something closer to how operating systems ship software. `apt-get` installs packages. `pip` installs libraries. **Skillware installs capability.** One bundle works across Gemini, Claude, OpenAI, DeepSeek, and Ollama because the loader adapts manifests at runtime instead of locking you to one vendor.

That decoupling matters in practice. Teams can swap models without rewriting tools. Open source contributors can ship a skill once and have it run everywhere the loader supports. Operators keep governance and attribution in the bundle instead of scattered across prompts.

For a longer argument against markdown-only skill files, see the essay [*skills.md is Dead: Why Your Agents Need Skillware*](https://dev.to/arpa/skillsmd-is-dead-why-your-agents-need-skillware-2g59) (extended reading).

---

## Why not instructions only?

Markdown instructions and web search can describe a task. They cannot guarantee how it runs.

Prompt-only flows burn context reading rules, then ask the model to invent code on every run. That is slow, expensive, and hard to audit. Web search adds latency and misses signals that live in structured data or on-chain history.

Skillware bundles **deterministic Python**, **local datasets**, **tests**, and **governance** in one installable unit. The model decides *when* to call a skill. The skill decides *how* the work runs. Results are repeatable. Boundaries are written down in `manifest.yaml` and enforced in code.

That split is the difference between a demo and something you can ship. Instructions alone leave execution quality to the model's mood that day. A skill gives you the same JSON shape, the same error handling, and the same audit trail on run one and run one thousand.

---

## Wallet screening as an example

Consider screening an Ethereum wallet for sanctions exposure and risky counterparties. That is not a single API call. It is layered work: load OFAC and related lists, scan transaction history, flag mixer or drainer interactions, score risk, and return a structured report the model can summarize.

The [`finance/wallet_screening`](../skills/finance/wallet_screening/) skill packages all of that. Bundled JSON datasets sit beside the Python runner. Optional Etherscan access enriches live chain data. The agent receives a tool schema plus `instructions.md` that teach it how to interpret the JSON verdict.

Multi-layer screening runs locally in one `execute()` call. No generated scraper. No ad-hoc script the model wrote five minutes ago. For skill-level detail, see [wallet_screening.md](skills/wallet_screening.md). For how this task compares to prompts, MCP, or enterprise APIs, see the [wallet screening table](../COMPARISON.md#wallet-screening-same-task-different-approaches) in [COMPARISON.md](../COMPARISON.md).

---

## Built for agents

Skillware is designed so agents and their operators can discover, vet, and integrate capabilities without reinventing the wheel.

- **Manifests** declare inputs, outputs, dependencies, and constitution in `manifest.yaml`.
- **`skillware list`**, **`skillware examples`** / **`skillware list --examples`**, and **`skillware test`** (CLI) surface the local registry, browse the runnable example index, and run bundle tests.
- **[Examples index](../examples/README.md)** maps runnable provider scripts to skills.
- **[Usage guides](usage/README.md)** show the same load / tool-call / execute loop for Gemini, Claude, OpenAI, DeepSeek, and Ollama.
- **[Agent contribution workflow](contributing/ai_native_workflow.md)** documents how supervised agents propose scoped changes and open PRs.

Copy a snippet from an example, point `SkillLoader` at a skill id, and you have a working tool on any supported model. That is the discoverability loop we are optimizing for.

New contributors should not need to reverse-engineer the repo to find the right entry point. Vision and introduction explain the why. The skill catalog and examples show the what. Usage guides and the agent workflow show the how. Each layer stays short so agents and humans can drill down only where they need depth.

---

## Roadmap in four phases

Skillware follows one thread: modular capability you can install, trust, and extend across models, machines, and people.

### v0: Modular Agent Skills

**Self-contained, deterministic skills for any LLM or agent**

**In short:** A public registry, a stable loader, model adapters, tests, and docs. Install a skill and call it from any major LLM runtime. **You are here** (v0.3.x).

**Example:** Your agent runs `pip install skillware`, loads a Terms-of-Service evaluator skill, then visits a site or ingests a document. It follows the skill's constitution and logic immediately: what to extract, what to flag, what never to scrape or store. No extra prompt engineering, no one-off tools, no separate subscription stack. The capability ships as one bundle.

---

### v1: Ultimate skills

**Partner-grade bundles with verified data and shared maintenance**

**In short:** Co-develop deeper skills with industry partners in compliance, finance, supply chain & logistics, manufacturing, among other domains. Higher-assurance datasets, SLAs, and production ownership beyond community contributions alone.

**Example:** An OEM and a plant operator co-maintain a skill chain for production lines: ingest IoT telemetry, normalize units, flag anomalies, and alert on silo levels, line stoppages, and vendor price shifts. Live feeds, audit logs, and signed releases ship inside the bundle. The same skill ids run in staging and on the floor. Logic, governance, and data provenance stay aligned because the bundle is the contract, not a patchwork of prompts and ad-hoc integrations.

---

### v2: World skills

**Skills for robots, UAVs and drones, appliances, and the physical world**

**In short:** Extend the bundle model beyond Python-in-a-process. A skill becomes a portable contract between an agent and a device, sensor mesh, or simulation.

**Example:** At home, a fridge skill uses vision to notice you are low on milk, checks vendor skills for a three-day discount at store X, and suggests pickup after your gym slot tomorrow. A drone skill inspects a roof or field boundary from a live feed. Same installable idea, different surfaces and devices.

---

### v3: Brain skills

**Procedural delivery at the edge of human-machine interfaces**

**In short:** Long-term research and partnership territory. Deliver practice, language, and job skills through interfaces where cognition and execution meet, not only through chat or APIs.

**Example:** A learner installs a language or trade skill and receives structured procedural capability: pronunciation drills, safety checks on a lathe, or clinical triage steps under supervision. Decades of practice compressed into a governed bundle the interface can invoke step by step. Same modular philosophy as v0, a different execution surface.

---

## Where we are today

Honest snapshot for **v0** (current v0.3.x line):

- **Registry**: Skills under `skills/` with docs in [docs/skills/](skills/README.md).
- **Loader**: Dynamic import, dependency checks, and adapters for major LLM tool formats.
- **CLI**: `skillware list`, `skillware test`, and an interactive menu, included with `pip install skillware`. Use `skillware list --examples` and `skillware examples` to browse the runnable script index from the terminal.
- **Active work**: Wallet screening enhancements ([RFC #115](https://github.com/ARPAHLS/skillware/issues/115)), CLI polish, contributor docs, and good first issues across docs and framework.

Browse [open good first issues](https://github.com/ARPAHLS/skillware/issues?q=is%3Aopen+label%3A%22good+first+issue%22) if you want a low-risk entry point.

---

## Join us

Skillware is community-built. We welcome human contributors and **supervised agents** following the same standards: small PRs, tests where they matter, no emojis in project prose, and honest issue links.

- **[CONTRIBUTING.md](../CONTRIBUTING.md)** — fork, branch, skill standard, pull request process.
- **[Agent Contribution Workflow](contributing/ai_native_workflow.md)** — how operators and agents ship reviewable work.
- **[Introduction](introduction.md)** — Mind, Body, Conscience architecture in depth.

Help us make agent capabilities portable, safe, and reusable.

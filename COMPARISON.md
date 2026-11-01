# Comparison: Skillware vs. Alternatives

Skillware is a Python framework and curated capability registry that decouples **Effect**, **Directive**, and **Contract** into self-contained, installable modules called **Skills**. For the project mission and roadmap, see [docs/vision.md](docs/vision.md). For empirical benchmarks across 23 frontier and open-weight models, see the [Skillware-Bench repository](https://github.com/ARPAHLS/skillware-bench).

This document provides a comprehensive technical comparison between Skillware and alternative approaches for equipping AI agents with tools and domain capabilities, including:
- **Prompt-only & File formats**: Agent Skills (`SKILL.md`), Antigravity IDE skills, and unconstrained code-generation prompts.
- **Tool transport protocols**: Model Context Protocol (MCP).
- **Agent orchestration frameworks**: LangChain Tools, Microsoft AutoGen, CrewAI, and Microsoft Semantic Kernel.

---

## Wallet Screening: One Task, Five Approaches

To ground the architectural trade-offs, consider a concrete enterprise task: **screening an Ethereum wallet for sanctions, mixer interactions, and illicit counterparties** before an autonomous agent executes a transaction:

| Approach | Latency | Token Cost | Accuracy & Determinism | Security & Blast Radius | Setup & Maintenance |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Skillware** (`finance/wallet_screening`) | **< 1.0 s** (offline) / **< 3.5 s** (full) | **Zero logic tokens** (fixed schema call) | **100% deterministic** (bundled OFAC SDN, TRM, & exploit DB) | **Hermetic Python**; zero shell/network escape; typed contract | `pip install "skillware[finance_wallet_screening]"` |
| **Unassisted Prompt + Code Gen** | 12 s – 45 s+ | High (800–2,500+ completion tokens) | Stochastic; hallucinated address checks; code syntax errors | High; unreviewed generated Python scripts executed in host | Complex prompt engineering; custom sandboxes |
| **Model Context Protocol (MCP)** | 2.5 s – 8 s | Moderate (schema prefill + RPC serialization) | Tool-dependent (relies on external server logic) | Requires securing and authenticating separate server processes | Deploy, configure, and supervise external daemon processes |
| **Orchestration Tool (LangChain/CrewAI)** | 4 s – 15 s | High (framework preambles & conversational wrappers) | Varies by wrapper; fragile error recovery loops | Dependent on host script boundaries; framework-coupled | Install large orchestration dependencies and custom wrappers |
| **Direct SaaS APIs (Chainalysis/TRM)** | < 1.0 s | Minimal (direct HTTP call) | High (SLA-backed) | Vendor-controlled; requires outbound internet & external keys | Enterprise vendor contracts, API key lifecycle management |

Skill detail: [`docs/skills/finance/wallet_screening.md`](docs/skills/finance/wallet_screening.md). Multi-layer offline and live screening executes deterministically via `finance/wallet_screening`.

---

## 1. Architectural Foundations: Versioned Software vs. Prompts

A core paradigm shift separates Skillware from prompt-first or script-directory approaches:

<div align="center">
  <img src="https://raw.githubusercontent.com/ARPAHLS/skillware-bench/main/docs/figures/fig02_bundle_anatomy.png" alt="Anatomy of a Skill Bundle" width="100%" />
</div>

> **Figure 1 (Skillware-Bench Fig. 2): Anatomy of a Skillware skill bundle.** Capabilities are decomposed into five first-class primitives rather than monolithic prompts: **Contract** (`manifest.yaml` declares typed actions, parameter schemas, and permissions), **Effect** (`skill.py` implements deterministic execution, pagination, and error boundaries), **Directive** (`instructions.md` provides SOP guidance and disambiguation rules), **Assurance** (`test_skill.py` provides hermetic pytest fixtures and contract invariants), and **Corpus** (`data/` stores domain reference datasets).

### The "Prompt vs. Software" Divide
Most agent tool ecosystems treat skills as **prompts**—loose markdown files containing natural-language instructions, regex heuristics, or snippets of Python code meant to be copy-pasted or evaluated on the fly. 

Skillware treats skills as **versioned software packages**:
1. **Immutable Contracts**: Input and output envelopes are strictly validated against JSON schemas in `manifest.yaml`. If an agent passes invalid parameters, the call fails immediately before any side-effect occurs.
2. **Deterministic Effect Handlers**: Real domain work runs in Python (`BaseSkill.execute()`). The model's reasoning is decoupled from the execution mechanism: the model decides *what* to do and *which* arguments to supply; pre-tested Python code executes the work.
3. **Rigorous Assurance**: A skill cannot enter the Skillware registry without hermetic offline tests (`test_skill.py`), stress tests, and schema verification.

<div align="center">
  <img src="https://raw.githubusercontent.com/ARPAHLS/skillware-bench/main/docs/figures/fig07_wallet_gate.png" alt="Deterministic Execution & Contract Gating" width="100%" />
</div>

> **Figure 2 (Skillware-Bench Fig. 7): Deterministic execution pipeline in Skillware.** Execution passes through a strict Contract gate (`manifest.yaml`), runs pre-compiled, offline-tested Python logic inside the Effect handler (`skill.py`), and returns a structured response envelope (`ready`, `needs_input`, `error`). Delegating domain logic to deterministic Python eliminates behavioral drift across model architectures and executes complex tasks with zero logic token expenditure.

---

## 2. Curation & Governance: Why Skillware Rejects Open-Market Scraping

Many agent repositories adopt an open-marketplace or directory-scraping model, accepting unreviewed user contributions, random GitHub repositories, or scraped prompt collections. While this inflates headline skill counts, it introduces fatal flaws for enterprise adoption:
- **Security Vulnerabilities**: Malicious skills can embed prompt injections, credential-harvesting hooks, or dangerous shell commands.
- **Fragile Quality**: Random prompt scripts frequently break when dependencies drift or model APIs change.
- **Inconsistent Interfaces**: Every developer invents their own parameters, return formats, and error semantics.

### The ARPA Curation Standard
Skillware enforces a **closed, curated governance model**:
*   **Vetted & Co-Designed**: Every skill in the registry is thoroughly audited, tested, and in the vast majority of cases co-designed, benchmarked, and steered directly by ARPA Hellenic Logical Systems.
*   **Manifest v2 Universal Taxonomy**: Every skill is classified across four standardized dimensions:
    - **Shape**: `atomic` (single-action utility), `workflow` (multi-step operational process), `middleware` (in-flight context/safety transformer), or `stream` (continuous event handler).
    - **Tier**: `core` (essential, air-gapped primitives), `cloud` (stateless API handlers), or `enterprise` (heavyweight business logic).
    - **Target**: `software` (safe virtual environments) or `hardware` (explicitly flagged physical actuators, sensors, and machines).
    - **Tags**: Governed semantic identifiers ensuring clean discovery and routing.
*   **Continuous Stress Testing**: Skills undergo regular simulation stress suites (`tests/test_host_simulation_stress.py`), async concurrency stress (`tests/test_async_concurrency_stress.py`), and multi-model benchmark evaluation across 23 frontier and open-weight models in [Skillware-Bench](https://github.com/ARPAHLS/skillware-bench).

---

## 3. Embedded Enterprise Security & Secret Isolation

In typical agent implementations, security is an afterthought. Operators are forced to build custom security sidecars, write post-processing guardrails, or manually audit runtime script generation to prevent agents from exfiltrating credentials or damaging infrastructure.

In Skillware, **security is baked directly into the skill contract and the core framework**:

<div align="center">
  <img src="https://raw.githubusercontent.com/ARPAHLS/skillware-bench/main/docs/figures/fig17_security_posture_radar.png" alt="Governance & Security Radar Profile" width="100%" />
</div>

> **Figure 3 (Skillware-Bench Fig. 17): Governance & Security Radar Profile.** Defense profile across six empirical attack vectors evaluated across 23 models (138 experimental conditions in Skillware-Bench). Unassisted models suffer critical vulnerabilities on obfuscated ciphers (82.6%), inbound phishing URLs (82.6%), and entity registry injections (60.9%). Skillware elevates overall defense from 84.1% to 92.0% while eliminating 100% of recursive debugging scripts via deterministic host micro-compute.

### Core Security Pillars:
1. **Isolated Secret Provider (`EnvSecretProvider`)**: Skills never perform unconstrained `os.environ` lookups. Skills declare required credentials in `manifest.yaml` under `env_vars`. The framework's secret provider injects only declared keys into the skill instance, preventing credential leakage across multi-tenant host sessions.
2. **Hardware Execution Safety Gates**: Skills that manipulate physical devices or actuators declare `target: [hardware]`. The `SkillContext` host rejects hardware-targeted skills by default (`allow_hardware_execution=False`), requiring explicit operator sign-off before hardware-effecting code can load.
3. **Hermetic Offline Testing**: Skills must pass test suites that mock network endpoints and external services. No network calls or side effects leak during packaging or verification.

---

## 4. Context Economics: Progressive Disclosure & JIT Context Excision

A primary cause of high latency, high inference bills, and reasoning failures in autonomous agents is **context bloat**. When an agent is loaded with 20+ tool definitions, dumping monolithic instruction playbooks, few-shot examples, and full schemas directly into the system prompt wastes tens of thousands of tokens per turn and causes the model to lose track of core user directives.

<div align="center">
  <img src="https://raw.githubusercontent.com/ARPAHLS/skillware-bench/main/docs/figures/fig06_context_excision.png" alt="Context Excision across simulation crucibles" width="100%" />
</div>

> **Figure 4 (Skillware-Bench Fig. 6): Prompt context excision across simulation crucibles.** Offloading executable skill logic (`skill.py`) and schema verification to deterministic host-side JIT handlers collapses resident prompt context by **84.0% on average** (from 15,400 to 2,460 tokens), slashing per-turn prefill latency and eliminating distraction-induced contract hallucination.

### Flexible Context Injection Strategies (`SkillContext`)
Skillware's `SkillContext` provides granular, progressive context management so operators can tailor context injection to their exact token budget and architecture:

| Injection Strategy | Configuration | How It Works | Ideal Use Case |
| :--- | :--- | :--- | :--- |
| **Catalog Brief** | `SkillContext(mode="brief")` | Injects concise single-line taxonomy summaries (`[tier:shape:target]`) into the system prompt alongside typed tool schemas. Saves ~85% prompt tokens. | Broad agent sessions exposing 10–30+ registry tools simultaneously. |
| **Category Scoping** | `SkillContext(categories=["finance", "compliance"])` | Dynamically filters and mounts only skills belonging to specific domain categories. | Specialized agents (e.g., a KYC compliance bot or DeFi trading agent). |
| **Cherry-Picked Bundles** | `SkillContext(skills=["office/gmail_handler", "finance/wallet_screening"])` | Mounts only an explicitly defined list of vetted capabilities. | Highly audited, deterministic production micro-agents. |
| **Full Directives** | `SkillContext(mode="directives")` | Injects full markdown Standard Operating Procedures (`instructions.md`) for all selected skills into the system prompt. | Narrow workflows with ≤ 3 tools where full SOP guidance is needed upfront. |
| **Lazy JIT Unlocking** | `SkillContext(mode="brief")` + `ctx.prepare(skill_id)` | Tools are exposed via schemas and brief summaries. When the model invokes a skill, the host calls `prepare()` to unlock the full `instructions.md` directive for subsequent turns. | Complex multi-turn workflows requiring deep SOP reasoning only after a tool is routed. |

---

## 5. Direct Technical Comparisons

### 5.1 Skillware vs. Model Context Protocol (MCP)

The [Model Context Protocol](https://github.com/modelcontextprotocol) (MCP) is an open standard connecting AI models to data sources and tools via client-server architecture (JSON-RPC over stdio or SSE).

```
┌─────────────────────────────────┐           ┌─────────────────────────────────┐
│     Model Context Protocol      │           │            Skillware            │
│  (Client-Server / Distributed)  │           │    (In-Process Python Native)   │
├─────────────────────────────────┤           ├─────────────────────────────────┤
│ Host Agent App                  │           │ Host Agent App                  │
│   │ (JSON-RPC over stdio/SSE)   │           │   │ (Direct Python Method Call) │
│   ▼                             │           │   ▼                             │
│ MCP Server Process (Local/Ext)  │           │ SkillLoader / SkillContext      │
│   │                             │           │   │                             │
│   ▼                             │           │   ▼                             │
│ Tool Script / API Endpoint      │           │ Deterministic Effect (skill.py) │
└─────────────────────────────────┘           └─────────────────────────────────┘
```

#### Key Distinctions:
*   **In-Process vs. Multi-Process**: MCP is fundamentally a transport protocol. Running MCP requires spawning and managing background server processes, serializing payloads over stdio or HTTP, and monitoring connection health. Skillware is **in-process Python**: skills load via `SkillLoader` as standard Python classes, executing with zero network overhead, zero serialization delay, and direct shared-memory data handling.
*   **Security Perimeter**: MCP servers are separate processes that must be individually authenticated and permissioned. Skillware bundles execute within the application's runtime boundary under Python's execution controls and Skillware's isolated secret provider.
*   **Complementary Positioning**: MCP and Skillware are not mutually exclusive. Skillware can be exposed *through* an MCP server (enabling external hosts to access Skillware capabilities over JSON-RPC), while MCP tools can be wrapped into Skillware bundles.

---

### 5.2 Skillware vs. Agent Skills (`SKILL.md`)

The [Agent Skills](https://agentskills.io) standard packages agent guidance as standalone markdown files (`SKILL.md`) with optional script folders, progressively read by IDE agents (such as Claude Code, Cursor, or Copilot).

#### Key Distinctions:
*   **Executable Software vs. Markdown Prompts**: Agent Skills rely primarily on natural-language instructions in `SKILL.md`, leaving execution to the host model's code synthesis or ad-hoc shell invocations. Skillware enforces typed parameter schemas in `manifest.yaml` and deterministic logic in `skill.py`.
*   **Automated Assurance**: An Agent Skill has no standardized test contract. A Skillware bundle requires hermetic pytest fixtures (`test_skill.py`) verifying that the implementation honors the manifest schema before it can be merged or deployed.
*   **Universal Runtime Adapters**: `SKILL.md` is tied to host environments that understand the markdown format. Skillware includes native adapters for Google Gemini, Anthropic Claude, OpenAI, Ollama, and AWS Bedrock, automatically translating contracts into native function declarations.

---

### 5.3 Skillware vs. Antigravity ("Agentic" IDE Skills)

Google DeepMind's Antigravity system uses `SKILL.md` files for autonomous coding workflows within an IDE.

#### Key Distinctions:
*   **Developer Memory vs. Runtime Capabilities**: Antigravity skills provide **procedural memory** for a coding agent ("how to run this repo's tests", "how to format migrations"). Skillware provides **runtime capabilities** for end-user agent applications ("how to screen this crypto wallet", "how to fill this PDF form", "how to query Companies House").
*   **Target Lifecycle**: Antigravity operates during development; Skillware operates in live production agent loops.

---

### 5.4 Skillware vs. LangChain Tools

[LangChain Tools](https://python.langchain.com/docs/concepts/tools/) provide Python/TypeScript classes wrapping APIs and functions for LangChain chains and agents.

#### Key Distinctions:
*   **Lightweight & Uncoupled**: LangChain tools are tightly coupled to the LangChain abstraction stack (`BaseTool`, `Runnable`, callbacks). Skillware has zero heavyweight orchestration dependencies. You can invoke a Skillware skill in a 10-line native Gemini script, an Ollama loop, a raw OpenAI API call, or inside LangChain itself.
*   **Complete Capability Bundles**: LangChain tools typically wrap API calls without standardized cognitive instructions or governance constitutions. A Skillware bundle ships the Effect code (`skill.py`), the reasoning directive (`instructions.md`), the typed schema (`manifest.yaml`), and catalog presentation (`card.json`).

---

### 5.5 Skillware vs. Multi-Agent Orchestrators (AutoGen & CrewAI)

[Microsoft AutoGen](https://microsoft.github.io/autogen/) and [CrewAI](https://www.crewai.com/) are frameworks for orchestrating multi-agent conversations, roles, and handoffs.

#### Key Distinctions:
*   **Orchestration vs. Capability Supply Chain**: Developers often conflate agent orchestration with agent capability. AutoGen and CrewAI excel at defining *who talks to whom* and managing agent memory. However, the tools given to those agents are often fragile, ad-hoc Python scripts. Skillware acts as the **vetted capability supply chain**: you use AutoGen or CrewAI to orchestrate your multi-agent architecture, and you equip those agents with Skillware bundles to execute real domain tasks safely.

---

### 5.6 Skillware vs. Microsoft Semantic Kernel

[Semantic Kernel](https://learn.microsoft.com/en-us/semantic-kernel/) is an enterprise SDK integrating models with code via plugins and native connectors.

#### Key Distinctions:
*   **Minimalist Python vs. Heavyweight Enterprise Stack**: Semantic Kernel requires adopting an enterprise-grade architectural paradigm (kernel builders, memory stores, pipeline filters, C#/Python duality). Skillware is Python-native, lightweight, and immediately embeddable into any existing application without re-architecting your backend.

---

## 6. Empirical Telemetry: Evidence from Skillware-Bench

All architectural distinctions above are grounded in empirical measurement from [Skillware-Bench](https://github.com/ARPAHLS/skillware-bench), an evaluation harness testing **23 frontier and sovereign models across 16 progressive difficulty layers (736 live experimental conditions)**:

### 6.1 Latency Anatomy: -55.6% End-to-End Speedup

<div align="center">
  <img src="https://raw.githubusercontent.com/ARPAHLS/skillware-bench/main/docs/figures/fig11_latency_anatomy.png" alt="Latency anatomy across execution stages" width="100%" />
</div>

> **Figure 5 (Skillware-Bench Fig. 11): Latency anatomy of a complex reference workflow (Office Mail Tier 2).** JIT context excision shrinks prefill latency from 4.1 s to 0.7 s, compact model routing shortens decode from 6.2 s to 3.4 s, and deterministic host validation eliminates speculative error loops: end-to-end median latency falls from 14.2 s to 6.3 s (−55.6%). Time to first token (TTFT) collapses from 1.9 s to 0.4 s.

### 6.2 Run-to-Run Determinism: 5.1× Variance Contraction

<div align="center">
  <img src="https://raw.githubusercontent.com/ARPAHLS/skillware-bench/main/docs/figures/fig14_run_to_run_determinism.png" alt="Run-to-run determinism and variance contraction" width="100%" />
</div>

> **Figure 6 (Skillware-Bench Fig. 14): Run-to-run determinism across 40 seeded replays under identical seeds (8B compact model).** Unassisted Vanilla execution scatters across an erratic score distribution (mean 61.0, σ = 4.1) driven by non-deterministic code synthesis paths. Skillware contracts run-to-run dispersion by 5.1× tighter (mean 88.2, σ = 0.8), establishing the execution predictability required for enterprise regression testing and CI/CD release gating.

### 6.3 The Cost Cascade: -97.3% Enterprise Spend Reduction

<div align="center">
  <img src="https://raw.githubusercontent.com/ARPAHLS/skillware-bench/main/docs/figures/fig04_cost_cascade.png" alt="The Benchmark Cost Cascade" width="100%" />
</div>

> **Figure 7 (Skillware-Bench Fig. 4): The benchmark cost cascade for a complex multi-turn task episode.** Illustrates compound spend reduction migrating from monolithic frontier models ($15.58 on unassisted multi-turn script debugging) to equipped compact workhorses ($0.42 on sovereign compact models): eliminating the recursive script debugging tax (−$6.47), JIT schema/directive excision (−$6.22), and compact workhorse substitution (−$2.47) achieve an aggregate 97.3% cost reduction.

### 6.4 The Parameter Paradox: Small Models + Skillware Outperform Frontier Models

<div align="center">
  <img src="https://raw.githubusercontent.com/ARPAHLS/skillware-bench/main/docs/figures/fig05_parameter_paradox.png" alt="The Parameter Paradox" width="100%" />
</div>

> **Figure 8 (Skillware-Bench Fig. 5): The empirical parameter paradox.** Across parameter scales from 8B to 550B+, Skillware-equipped models maintain a decisive performance wedge over unequipped baselines. A compact sovereign model like Qwen 3.8 Flash (16B) or Gemma 4 (31B) equipped with Skillware achieves a perfect 16/16 (100.0%) pass rate, outscoring unequipped frontier models Claude Sonnet 5 and GPT-6 Luna (both 14/16, 87.5%) at roughly 1/30th the operational cost.

### 6.5 Master Fleet Standings Across 12 Architectures

<div align="center">
  <img src="https://raw.githubusercontent.com/ARPAHLS/skillware-bench/main/docs/figures/tab07_four_axis_summary.png" alt="Four-Axis Master Summary Across 12 Models" width="100%" />
</div>

> **Figure 9 (Skillware-Bench Tab. 7): Four-axis master operational summary across 12 representative model architectures (736 live experimental conditions).** Across Frontier APIs, Enterprise deployments, Compact workhorses, and Edge models, Skillware delivers token compression from 29.6% to 77.1%, accelerates task execution by 1.36× to 2.35×, lifts composite pass rates from 81.5% to 91.6%, and completely eliminates workspace script debugging traps (464 scripts eliminated to 0).

---

## 7. Master Comparison Matrix

| Dimension | Skillware | Model Context Protocol (MCP) | Agent Skills (`SKILL.md`) | LangChain Tools | AutoGen & CrewAI | Semantic Kernel |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Primary Focus** | **Curated capability supply chain** | Standardized tool transport | IDE procedural guidance | Chain execution wrappers | Multi-agent conversation orchestration | Enterprise application SDK |
| **Architecture** | **In-process native Python library** | Client-Server (stdio / SSE JSON-RPC) | Standalone markdown / script files | Python / TypeScript classes | Multi-agent framework | Enterprise framework / SDK |
| **Logic Execution** | **Pre-compiled, offline-tested Python** | External server process | Host-interpreted or synthesized | Python method call | Agent-assigned Python functions | Plugin native/semantic functions |
| **Governance & Curation** | **Curated & co-designed by ARPA**; strictly vetted | Open protocol; uncurated servers | Open format; unvetted user repos | Community ecosystem | Custom internal functions | Enterprise-configured connectors |
| **Security Model** | **Embedded native security**; isolated secret provider; hardware execution gates | Transport security; external server authentication | Unrestricted shell / host script access | Host-managed Python environment | Host-managed Python environment | Enterprise IAM & Azure connectors |
| **Context Management** | **Progressive JIT excision** (brief, category, lazy unlock) | Monolithic tool schemas | Progressive file reading by IDE | Monolithic schema loading | In-context conversation history | Kernel plugin memory |
| **Test Assurance** | **Mandatory hermetic pytest fixtures & invariant tests** | Server-dependent (no standard) | None enforced | Optional unit tests | None enforced | Unit tests via SDK |
| **Model Compatibility** | **Universal native adapters** (Gemini, Claude, OpenAI, Ollama, Bedrock, DeepSeek) | Standardized protocol clients | Host-dependent (Cursor, Claude Code) | Broad via LangChain wrappers | Broad via model config | Broad via connectors |
| **Primary Failure Mode Addressed** | **Eliminates prompt drift, hallucination & script debugging traps** | Standardizes fragmented tool connections | Documents manual dev workflows | Connects APIs to chains | Coordinates multi-agent dialogue | Standardizes enterprise C#/Python |

---

## Summary: Don't Prompt Your Agents, Equip Them

The choice of tool framework shapes an autonomous agent's reliability, token economics, and security posture:
- If you need a **distributed transport protocol** to connect external tools over language boundaries, use **MCP**.
- If you need **procedural memory** for developer agents inside an IDE, use **Agent Skills**.
- If you need **multi-agent turn orchestration and conversation trees**, use **CrewAI** or **AutoGen**.
- If you need **deterministic, auditable, enterprise-grade capabilities** that execute real work safely, eliminate script debugging loops, compress token costs by up to 97%, and run identically across any LLM, **equip your agents with Skillware**.

For complete benchmark datasets, evaluation harnesses, and reproduction instructions, visit **[ARPAHLS/skillware-bench](https://github.com/ARPAHLS/skillware-bench)**.

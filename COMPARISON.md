# Comparison: Skillware vs. Alternatives

Skillware is a Python framework that decouples AI tool logic, cognition, and governance into self-contained, installable modules called **Skills**. For the project story and roadmap, see [docs/vision.md](docs/vision.md).

This document clarifies how Skillware compares to other common approaches for equipping AI agents with tools, including **Model Context Protocol (MCP)**, **Anthropic Skills**, **LangChain Tools**, **AutoGen**, and others.

---

## Wallet screening: same task, different approaches

**Screening an Ethereum wallet for sanctions and risk** — qualitative comparison across four methods:

| Method | Speed | Cost | Accuracy | Reliability | Security | Setup |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Skillware** (`wallet_screening`) | Seconds | Low (~$0 + optional Etherscan key) | High (deterministic OFAC/TRM-style data) | Repeatable, tested Python | Fixed code path | `pip install skillware` |
| **Prompt + web search** | Minutes | High tokens | Low (misses on-chain signals) | Varies per run | Generated code and scraping | Prompt engineering |
| **MCP / multi-agent** | Minutes+ | Tokens + infra | Medium (tool-dependent) | Server/agent-dependent | Many moving parts | Deploy servers |
| **Native APIs** (Chainalysis, TRM) | Sseconds | High (enterprise) | High | SLA-backed | Vendor-controlled | Contracts |

Skill detail: [wallet_screening.md](docs/skills/wallet_screening.md). Multi-layer screening runs locally in one call via [`finance/wallet_screening`](skills/finance/wallet_screening/).

---

## 1. Skillware vs. Model Context Protocol (MCP)

The [Model Context Protocol](https://github.com/modelcontextprotocol) (MCP) is an open standard that connects AI models to data sources and tools via a client-server architecture.

### Key Differences
*   **Architecture**: MCP operates on a **Client-Server** model (using JSON-RPC over stdio or SSE). This requires running and managing separate servers for your tools. Skillware is **Python-Native**. It operates entirely within the Python runtime via library imports (`SkillLoader`). There is no network overhead or need to deploy external servers.
*   **Deployment Complexity**: MCP is powerful for language-agnostic, distributed systems but introduces significant infrastructure overhead. Skillware is designed for direct embedding into GenAI application pipelines, making it trivial to deploy.

---

## 2. Skillware vs. Anthropic Skills

[Anthropic's Skills](https://github.com/anthropics/skills) repository provides reference tool implementations and prompts optimized specifically for Claude.

### Key Differences
*   **Model Agnosticism**: Anthropic skills are hardcoded for Claude's specific tool-calling schemas. Skillware features **Universal Adapters**. You write a single `manifest.yaml`, and Skillware's `SkillLoader` translates it dynamically at runtime to fit Gemini, Claude, or OpenAI formats natively.
*   **The "Managed" Runtime**: Anthropic provides standalone reference scripts. Skillware provides a comprehensive framework (`base_skill.py` and `loader.py`) that handles lifecycle, dynamic dependency checking, execution, and error handling automatically.

---

## 3. Skillware vs. Antigravity ("Agentic" Skills)

Frameworks like Google DeepMind's **Antigravity** use `SKILL.md` files to provide context to an autonomous coding agent working inside an IDE.

### Key Differences
*   **Target Audience**:
    *   **Antigravity Skills** provide **Procedural Memory** ("How to run this repository's build script") for a **Developer Agent** writing code.
    *   **Skillware** provides **Functional Capabilities** (executable Python logic like "Check this crypto wallet") for the **Runtime Agent** (the end-user application).

---

## 4. Skillware vs. LangChain Tools

[LangChain Tools](https://python.langchain.com/docs/modules/tools/) provide interfaces that chains and agents use to interact with external APIs and systems.

### Key Differences
*   **Beyond Execution Wrappers**: LangChain tools frequently act as simple execution wrappers around an API. Skillware focuses on **uncoupled runtime logic, cognition maps, and system governance**. A Skillware module doesn't just contain the code to execute a task; it includes standard instructions on *how* the agent should reason about the tool (`instructions.md`) and strict safety guardrails (`manifest.yaml`).
*   **Code-First, Framework-Agnostic**: LangChain tools are tightly coupled to the LangChain ecosystem. Skillware's code-first structure and universal adapters let you seamlessly inject skills into *any* minimal pipeline orchestrating Gemini, Claude, or OpenAI. You do not have to adopt an entire heavyweight orchestration ecosystem to use a Skillware module.

---

## 5. Skillware vs. AutoGen

[Microsoft AutoGen](https://microsoft.github.io/autogen/) is a framework for developing applications using multiple conversing agents.

### Key Differences
*   **Installable Capabilities vs. Internal Management**: In AutoGen, tool and skill management is typically handled internally by registering custom Python functions to specific agents. Skillware treats skills as **installable capabilities**—like `apt-get` for agents. Rather than coding functions from scratch, a developer can download a pre-vetted, domain-specific Skillware module and equip an AutoGen agent instantly.
*   **Separation of Concerns**: AutoGen focuses on multi-agent *orchestration* and conversation patterns. Skillware focuses purely on standardizing *domain expertise*. In fact, Skillware can be used *inside* AutoGen to provide its agents with standalone, secure, and pre-compiled capabilities.

---

## 6. Skillware vs. Microsoft Semantic Kernel (Plugins)

[Semantic Kernel](https://learn.microsoft.com/en-us/semantic-kernel/) is an enterprise SDK that integrates LLMs with code using a system of "Plugins," which is philosophically similar to Skillware.

### Key Differences
*   **Lightweight vs. Heavyweight**: Semantic Kernel is a complete, heavy enterprise orchestration layer that requires adopting its entire C#/Python architectural paradigm and pipeline management. Skillware is intentionally minimal. It simply provides the capability bundle, enabling you to use it in lightweight 10-line Python scripts or custom agent loops without needing an enterprise orchestrator.

---

## 7. Skillware vs. CrewAI

[CrewAI](https://www.crewai.com/) is a popular framework for orchestrating role-playing autonomous agents to accomplish tasks.

### Key Differences
*   **The Orchestrator vs. The Supply Chain**: Developers often confuse agent orchestration frameworks with capability frameworks. CrewAI excels at defining *roles* and managing *handoffs* between agents, but the tools those agents use are often simple script-bound Python functions. Skillware does not compete with CrewAI; rather, it acts as the supply chain. You use CrewAI to orchestrate your multi-agent workflow, and you use Skillware to supply those agents with robust, vetted, and cleanly separated capabilities.

---

## The Token Economy Advantage

A critical architectural distinction is how Skillware treats logic execution versus "code generation."

*   **The Code-Generation Approach**: Many platforms prompt the LLM to write code on the fly to solve a requested problem. This is expensive (you pay for output tokens every time), slow, and risky (the LLM executes unreviewed code).
*   **The Skillware Approach**: Skillware relies on **Pre-Compiled Logic**. The logical system decides *which* tool to call (e.g., wallet_screening) and passes arguments. The heavy lifting happens deterministically in the Python `BaseSkill` implementation. This results in **zero-cost logic execution**, instant processing, and static, auditable code boundaries.

---

## Executive Summary Matrix

| Feature | Skillware | Model Context Protocol (MCP) | Anthropic Skills | Antigravity Skills | LangChain Tools | AutoGen & CrewAI | Semantic Kernel |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Primary Goal** | **Installable App Capabilities** | **Standardized Tool Integration** | Claude Capabilities Showcase | **Developer Agent Guidance** | **Chain / Execution Wrappers** | **Multi-Agent Orchestration** | **Enterprise Orchestration** |
| **Architecture** | **Native Python Library** | **Client-Server (JSON-RPC)** | Standalone Scripts | Markdown Context Files | Python/JS Components | Python Framework | Enterprise SDK |
| **Model Compatibility** | **Universal** (Adapters built-in) | Standardized Protocol Clients | Claude Specific | Context injection | Broad via Ecosystem | Broad | Broad via Connectors |
| **Execution Context** | **Runtime Application** | Distributed / Networked | Runtime Application | IDE / Build Environment | LangChain Pipeline | Agent Workflows | Enterprise Service |

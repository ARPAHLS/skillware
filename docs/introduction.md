# Deep Dive: The Skillware Philosophy

**Skillware** is an Operating System for Agentic Capabilities. It was born from the realization that current agent frameworks (LangChain, AutoGPT) couple *intelligence* (the model) too tightly with *capability* (the tool).

If you want your agent to "know" how to analyze a balance sheet, you shouldn't have to prompt-engineer a specific model or write a custom tool definition for that specific model's API. You should be able to **install** that capability.

## 🧠 The Triad: Mind, Body, Language

In integration, a "Skill" is not just a function. It is a living unit of capability composed of three parts:

### 1. The Body (Logic)
*   **What it is**: The standardized Python code (inheriting from `BaseSkill`).
*   **Role**: Executes the actual work—fetching data, calculating numbers, hitting APIs.
*   **File**: `skill.py`
*   **Design**: Hardened, error-proof, and deterministic. It does not hallucinate.

### 2. The Mind (Cognition)
*   **What it is**: The System Instructions and "Cognitive Map".
*   **Role**: Teaches the LLM *how* to use the Body. It explains the nuances, edge cases, and reasoning steps required to use the tool effectively.
*   **File**: `instructions.md`
*   **Design**: Written in natural language optimized for LLM comprehension. It travels with the skill. When you load the skill, you load its mind into the agent.

### 3. The Conscience (Governance)
*   **What it is**: The Constitution and Manifest.
*   **Role**: Defines the boundaries. "Do not output PII", "Do not give financial advice".
*   **File**: `manifest.yaml`
*   **Design**: Enforced at the prompt level.

---

## 🏗️ The Architecture: How It Works

When you run `SkillLoader.load_skill("finance/wallet_screening")`, a complex orchestration happens behind the scenes:

### Step 1: Discovery & Loading
The loader scans the `skills/` directory structure. It mimics Python's import system but looking for Skillware bundles (directories with `manifest.yaml`).
*   It dynamically imports the `skill.py` module.
*   It parses the `manifest.yaml`.
*   It reads `instructions.md` and `card.json`.

### Step 2: Adaptation (The "Babel Fish")
This is Skillware's superpower. Every model (Gemini, Claude, GPT) speaks a different "Tool Language".
*   **Gemini** wants `FunctionDeclaration` with Protobuf types (UPPERCASE).
*   **Claude** wants `tool` definitions with JSON Schema input (lowercase).
*   **OpenAI** wants a `tools` list.

The `SkillLoader` acts as an adapter.
*   `SkillLoader.to_gemini_tool(skill)` -> Transmutes the manifest into Gemini's format.
*   `SkillLoader.to_claude_tool(skill)` -> Transmutes the manifest into Claude's format.

### Step 3: Injection
When you initialize your agent, you pass the skill's **Instructions** into the System Prompt.
*> "You are an agent equipped with the Wallet Screening capability. Here is how you use it: [Content of instructions.md]..."*

This "Context Injection" ensures the model isn't just *able* to call the tool, but is *intelligent* about it.

---

## 🔄 The Execution Loop

1.  **User Query**: "Is wallet 0x123 safe?"
2.  **Model Cognition**: The LLM reads the injected `instructions.md` and realizes it should use the `wallet_screening` tool.
3.  **Tool Call**: The LLM outputs a structured tool call (e.g., JSON or Protobuf).
4.  **Framework Execution**: Your script (or the model's auto-runner) executes `skill.execute({"address": "0x123"})`.
5.  **The Body Acts**: `skill.py` runs. It fetches Etherscan data, checks local JSON sanctions lists, mimics the logic of a complex forensic tool.
6.  **Structured Output**: The Body returns a rich JSON object.
7.  **Synthesis**: The LLM receives the JSON. Guided again by the `instructions.md` (which says "Summarize risk factors clearly"), it translates the data into a human-readable report.

## 🎯 Model Agnosticism

Skillware is designed to be the "Standard Library" for all agents.

| Platform | Integration Strategy |
| :--- | :--- |
| **Google Gemini** | Native `google.generativeai` support. Automatic type mapping. |
| **Anthropic Claude** | Native `anthropic` support. XML/JSON handling. |
| **OpenAI GPT** | (Planned) JSON Schema adapter. |
| **Local LLaMA** | (Planned) GBNF Grammar generation from manifests. |

---
**Next Steps:**
*   Explore the [Skill Library](skills/README.md)
*   Learn [How to Contribute](../CONTRIBUTING.md)


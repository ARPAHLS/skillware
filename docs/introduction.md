# Deep Dive: The Skillware Philosophy

**Skillware** is an Operating System for Agentic Capabilities. It was born from the realization that current agent frameworks (LangChain, AutoGPT) couple *intelligence* (the model) too tightly with *capability* (the tool).

If you want your agent to "know" how to analyze a balance sheet, you shouldn't have to prompt-engineer a specific model or write a custom tool definition for that specific model's API. You should be able to **install** that capability.

## The Triad: Mind, Body, Language

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
*   **Role**: Defines the boundaries. "Do not output PII", "Do not give financial advice". Records **issuer attribution** (who created or maintains the skill).
*   **File**: `manifest.yaml`
*   **Design**: Enforced at the prompt level. Issuer metadata (`name`, `email`, and optionally `github` / `org`) is for humans and catalog UIs—it is not passed to LLM tool schemas.

---

## The Architecture: How It Works

Skillware relies on a strict, modular layout. Instead of hardcoding tools into your primary application, you maintain a structured registry of capabilities:

```text
Skillware/
├── skills/
│   └── category/                   # Domain boundary (e.g., 'finance')
│       └── skill_name/             # A self-contained capability bundle
│           ├── manifest.yaml       # Inputs, outputs, constitution, and issuer attribution
│           ├── skill.py            # The deterministic Python execution logic
│           ├── instructions.md     # Natural language guidance for the LLM
│           ├── card.json           # Optional UI card (may mirror manifest issuer)
│           └── test_skill.py       # Unit tests for the skill bundle
└── skillware/
    └── core/
        ├── base_skill.py           # The interface every skill must implement
        ├── env.py                  # API key and secret loading
        └── loader.py               # The engine that bridges the skill to the LLM
```

When you run `SkillLoader.load_skill("category/skill_name")`, a complex orchestration happens behind the scenes:

### Step 1: Discovery & Loading
The loader resolves `category/skill_name` to a skill directory by checking, in order: an existing path on disk, roots in `SKILLWARE_SKILL_PATH`, a `skills/` folder in the current working directory (or its parents), then bundled skills installed with the package. Each bundle is a directory containing `manifest.yaml` and `skill.py`.
*   It dynamically imports the `skill.py` module.
*   It parses the `manifest.yaml` (including `issuer` for attribution, separate from tool-calling fields).
*   It reads `instructions.md` and `card.json`.

### Step 2: Adaptation (The "Babel Fish")
This is Skillware's superpower. Every model (Gemini, Claude, GPT) speaks a different "Tool Language".
*   **Gemini** wants `FunctionDeclaration` with Protobuf types (UPPERCASE).
*   **Claude** wants `tool` definitions with JSON Schema input (lowercase).
*   **OpenAI** wants a `tools` list.

The `SkillLoader` acts as an adapter.
*   `SkillLoader.to_gemini_tool(skill)` -> Transmutes the manifest into Gemini's format.
*   `SkillLoader.to_claude_tool(skill)` -> Transmutes the manifest into Claude's format.
*   `SkillLoader.to_openai_tool(skill)` -> Transmutes the manifest into OpenAI's tool format.
*   `SkillLoader.to_deepseek_tool(skill)` -> Transmutes the manifest into DeepSeek's tool format.
*   `SkillLoader.to_ollama_prompt(skill)` -> Textual tool description for Ollama prompt-based loops.

### Step 3: Injection
When you initialize your agent, you pass the skill's **Instructions** into the System Prompt.
*> "You are an agent equipped with the Wallet Screening capability. Here is how you use it: [Content of instructions.md]..."*

This "Context Injection" ensures the model isn't just *able* to call the tool, but is *intelligent* about it.

---

## The Execution Loop

1.  **User Query**: "Is wallet 0x123 safe?"
2.  **Model Cognition**: The LLM reads the injected `instructions.md` and realizes it should use the `wallet_screening` tool.
3.  **Tool Call**: The LLM outputs a structured tool call (e.g., JSON or Protobuf).
4.  **Framework Execution**: Your script (or the model's auto-runner) executes `skill.execute({"address": "0x123"})`.
5.  **The Body Acts**: `skill.py` runs. It fetches Etherscan data, checks local JSON sanctions lists, mimics the logic of a complex forensic tool.
6.  **Structured Output**: The Body returns a rich JSON object.
7.  **Synthesis**: The LLM receives the JSON. Guided again by the `instructions.md` (which says "Summarize risk factors clearly"), it translates the data into a human-readable report.

## Model Agnosticism

Skillware is designed to be the "Standard Library" for all agents.

| Platform | Integration Strategy |
| :--- | :--- |
| **Google Gemini** | Native `google-genai` support. Automatic type mapping. |
| **Anthropic Claude** | Native `anthropic` support. XML/JSON handling. |
| **Ollama** | Native `ollama` Python client support. Fully local JSON handling. |
| **OpenAI GPT** | `to_openai_tool()`; Chat Completions tool calling. |
| **DeepSeek** | `to_deepseek_tool()`; separate adapter, OpenAI-compatible client. |
| **Local LLaMA** | (Planned) GBNF Grammar generation from manifests. |

---
**Next Steps:**
*   Explore the [Skill Library](skills/README.md)
*   Browse the [Runnable Examples Index](../examples/README.md)
*   Read [How to Contribute](../CONTRIBUTING.md) (skills, docs, framework, and bugs)
*   If you are a contributing agent, follow the [Agent Contribution Workflow](contributing/ai_native_workflow.md)


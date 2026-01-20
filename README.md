# Skillware

<div align="center">
  <img src="https://img.shields.io/badge/Agentic-Native-blue?style=for-the-badge" alt="Agentic Native">
  <img src="https://img.shields.io/badge/Model-Agnostic-orange?style=for-the-badge" alt="Model Agnostic">
  <img src="https://img.shields.io/badge/Status-Beta-yellow?style=for-the-badge" alt="Status">
</div>

> "I know Kung Fu." - Neo

**Skillware** is an open-source framework and registry for modular, actionable Agent capabilities. It treats **Skills** as installable content, decoupling capability from intelligence.

Just as `apt-get` installs software and `pip` installs libraries, `skillware` installs *know-how* for AI agents.

---

## 🚀 Mission

The AI ecosystem is fragmented. Every developer re-invents tool definitions, system prompts, and safety rules for every project.

**Skillware** standardizes this by packaging capabilities into self-contained units that work across **Gemini**, **Claude**, **GPT**, and **Llama**.

A **Skill** in this framework provides everything an Agent needs to master a domain:
1.  **Logic**: Executable Python code (the muscle).
2.  **Cognition**: System instructions and "cognitive maps" (the mind).
3.  **Governance**: Constitution and safety boundaries (the conscience).
4.  **Interface**: Standardized schemas for LLM tool calling (the language).

## 📂 Repository Structure

This repository is organized "Corpo-Professional" style to serve as a robust foundation for enterprise-grade agents.

```bash
Skillware/
├── skillware/                  # The Core Framework Package
│   ├── core/
│   │   ├── base_skill.py       # Abstract Base Class for all skills
│   │   ├── loader.py           # Universal Skill Loader & Model Adapter
│   │   └── env.py              # Environment Management
│   └── skills/                 # The Skill Registry (Domain-driven)
│       └── finance/
│           └── wallet_screening/ # Example Complex Skill
│               ├── skill.py    # Logic
│               ├── manifest.yaml # Metadata & Constitution
│               ├── instructions.md # Cognitive Map
│               ├── card.json   # UI Presentation
│               ├── data/       # Integrated Knowledge Base
│               └── maintenance/ # Skill-Maintenance Tools
├── examples/                   # Reference Implementations
│   ├── gemini_wallet_check.py  # Google Gemini Integration
│   └── claude_wallet_check.py  # Anthropic Claude Integration
├── docs/                       # Comprehensive Documentation
│   ├── introduction.md         # Deep Dive into Philosophy
│   ├── usage/                  # Integration Guides
│   └── skills/                 # Skill Reference Cards
└── COMPARISON.md               # Vs. Anthropic Skills / MCP
```

## ⚡ Quick Start

### 1. Installation

Clone the repository and add it to your path (pip install coming soon).

```bash
git clone https://github.com/arpa/skillware.git
cd skillware
pip install -r requirements.txt
```

> **Note**: Individual skills may have their own dependencies. The `SkillLoader` will check `manifest.yaml` and warn you if you are missing a required package (e.g., `requests`, `pandas`) when you try to load a skill.

### 2. Configure Environment

Create a `.env` file with your keys:

```ini
ETHERSCAN_API_KEY="your_key" # Only if using crypto skills
GOOGLE_API_KEY="your_key"    # Your LLM Provider
```

### 3. "Hello World" (Gemini)

```python
import google.generativeai as genai
from skillware.core.loader import SkillLoader
from skillware.core.env import load_env_file

# Load Env
load_env_file()

# 1. Load the Skill
# The loader reads the code, manifest, and instructions automatically
skill_bundle = SkillLoader.load_skill("finance/wallet_screening")

# 3. Model & Chat Setup
model = genai.GenerativeModel(
    'gemini-2.5-flash',
    tools=[SkillLoader.to_gemini_tool(skill_bundle)], # The "Adapter"
    system_instruction=skill_bundle['instructions']   # The "Mind"
)
chat = model.start_chat(enable_automatic_function_calling=True)

# 4. Agent Loop
# The Google SDK handles the "Loop" internally with enable_automatic_function_calling=True.
# It calls the model -> sees tool call -> pauses -> YOU execute code -> sends result -> model replies.
# Note: In a production loop, you would manually handle the `function_call` parts to keep control.

response = chat.send_message("Screen wallet 0xd8dA... for risks.")
print(response.text)
```

## 📖 Documentation

*   **[Core Logic & Philosophy](docs/introduction.md)**: How Skillware decouples Logic, Cognition, and Governance.
*   **[Usage Guide: Gemini](docs/usage/gemini.md)**: Detailed integration with Google's GenAI SDK.
*   **[Usage Guide: Claude](docs/usage/claude.md)**: Detailed integration with Anthropic's SDK.
*   **[Skill Library](docs/skills/README.md)**: Browse available capabilities.

## 🤝 Contributing

We are building the "App Store" for Agents. We need professional, robust, and safe skills.

Please read **[CONTRIBUTING.md](CONTRIBUTING.md)** for our strict guidelines on folder structure, manifest schemas, and safety constitutions.

## 🆚 Comparison

How does this differ from the Model Context Protocol (MCP) or Anthropic's Skills repo?

*   **Model Agnostic**: Native adapters for Gemini, Claude, and OpenAI.
*   **Code-First**: Skills are executable Python packages, not just server specs.
*   **Runtime-Focused**: Unlike "Agentic Coding" skills (recipes for an IDE), Skillware provides **tools for the Application** (knives for the chef).

[Read the full comparison here](COMPARISON.md).

---
*Built by ARPA Hellenic Logical Systems*

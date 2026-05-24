<div align="center">
  <img src="assets/skillware_logo.png" alt="Skillware Logo" width="400px" />

  A Python framework for modular, self-contained skill management for machines.
</div>

<br/>

<div align="center">
  <img src="https://img.shields.io/badge/License-MIT-efcefa?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Python-3.11+-bae6fd?style=flat-square" alt="Python Version">
  <a href="https://pypi.org/project/skillware/"><img src="https://img.shields.io/pypi/v/skillware?style=flat-square&color=bbf7d0" alt="PyPI Version"></a>
</div>

<br/>

<div align="center">
  <a href="#mission">Mission</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#documentation">Documentation</a> •
  <a href="CHANGELOG.md">Changelog</a> •
  <a href="#contributing">Contributing</a> •
  <a href="#comparison">Comparison</a> •
  <a href="#contact">Contact</a>
</div>

---

**Skillware** is an open-source framework and registry for modular, actionable Agent capabilities. It treats **Skills** as installable content, decoupling capability from intelligence. Just as `apt-get` installs software and `pip` installs libraries, `skillware` installs *know-how* for AI agents.

> "I know Kung Fu." - Neo

## Mission

The AI ecosystem is fragmented. Developers often re-invent tool definitions, system prompts, and safety rules for every project. **Skillware** supplies a standard to package capabilities into self-contained units that work across **Gemini**, **Claude**, **Ollama**, **GPT**, and **Llama**.

A **Skill** in this framework provides everything an Agent needs to master a domain:

1.  **Logic**: Executable Python code.
2.  **Cognition**: System instructions and "cognitive maps".
3.  **Governance**: Constitution and safety boundaries.
4.  **Interface**: Standardized schemas for LLM tool calling.

### Skill library

Browse capabilities by category in the [Skill library](docs/skills/README.md).

## Architecture

This repository is organized into a core framework, a registry of skills, and
documentation. Runnable provider scripts are indexed in
[examples/README.md](examples/README.md).

```text
Skillware/
├── docs/                       # Introduction, testing, skill catalog, usage guides (docs/usage/)
├── examples/                   # Provider reference scripts (Gemini, Claude, OpenAI, Ollama, ...)
├── skills/                     # Skill Registry
│   └── category/               # Domain boundaries (e.g., finance)
│       └── skill_name/         # The Skill bundle
│           ├── manifest.yaml   # Definition, schema, and constitution
│           ├── skill.py        # Executable Python logic
│           ├── instructions.md # Cognitive map for the LLM
│           ├── card.json       # Optional UI presentation metadata
│           └── test_skill.py   # Unit tests and schema validation
├── skillware/                  # Core Framework Package
│   ├── cli.py                  # Command-line interface
│   └── core/
│       ├── base_skill.py       # Abstract Base Class for skills
│       ├── env.py              # Environment Management
│       └── loader.py           # Universal Skill Loader and Model Adapter
├── templates/                  # Boilerplate templates for new skills
│   └── python_skill/           # Standard template with required files
└── tests/                      # Automated test suite
```

## Quick Start

### 1. Installation

You can install Skillware directly from PyPI:

```bash
pip install skillware
```

Or for development, clone the repository and install in editable mode:

```bash
git clone https://github.com/arpahls/skillware.git
cd skillware
pip install -e .
```

> **Note**: Individual skills may have their own dependencies. The `SkillLoader` validates `manifest.yaml` and warns of missing packages (e.g., `requests`, `pandas`) upon loading a skill.

### 2. Verify your installation

```bash
pip install "skillware[cli]"
skillware list
```

This prints a table of all locally available skills and confirms the install and path resolution are working.

### 3. Configuration

Create a `.env` file with your API keys (e.g., Google Gemini API Key):

```ini
GOOGLE_API_KEY="your_key"
```

### 4. Usage Example (Gemini)

This example requires the Google SDK optional extra: `pip install "skillware[gemini]"` (local dev: `pip install -e ".[gemini]"`). See the [Gemini usage guide](docs/usage/gemini.md) for setup details.

```python
import os
import google.genai as genai
from google.genai import types
from skillware.core.loader import SkillLoader
from skillware.core.env import load_env_file

# Load Environment
load_env_file()

# 1. Load the Skill from the Registry
# The loader reads the code, manifest, and instructions automatically
skill_bundle = SkillLoader.load_skill("finance/wallet_screening")
skill = skill_bundle["module"].WalletScreeningSkill(
    config={"ETHERSCAN_API_KEY": os.environ.get("ETHERSCAN_API_KEY")}
)

# 2. Client & Tool Setup
client = genai.Client()
tool = SkillLoader.to_gemini_tool(skill_bundle)       # The "Adapter"
system_instruction = skill_bundle['instructions']     # The "Mind"

# 3. Agent Loop
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Screen wallet 0xd8dA... for risks.",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=system_instruction,
    ),
)

for part in response.candidates[0].content.parts:
    if part.function_call:
        result = skill.execute(dict(part.function_call.args))
        follow_up = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                "Use this tool result to answer the original request.",
                {
                    "function_response": {
                        "name": part.function_call.name,
                        "response": {"result": result},
                    }
                },
            ],
            config=types.GenerateContentConfig(
                tools=[tool],
                system_instruction=system_instruction,
            ),
        )
        print(follow_up.text)
    else:
        print(part.text)
```

For other providers and shared integration patterns, see the [usage guides index](docs/usage/README.md), [agent loops](docs/usage/agent_loops.md), [Gemini](docs/usage/gemini.md), [Claude](docs/usage/claude.md), [OpenAI](docs/usage/openai.md), [DeepSeek](docs/usage/deepseek.md), [Ollama](docs/usage/ollama.md), [API keys for skills](docs/usage/api_keys.md), and the [skill usage template](docs/usage/skill_usage_template.md) for contributors.

## Documentation

| Topic | Link |
| :--- | :--- |
| Introduction | [docs/introduction.md](docs/introduction.md) |
| Testing | [docs/TESTING.md](docs/TESTING.md) |
| Skill library | [docs/skills/README.md](docs/skills/README.md) |
| Usage guides | [index](docs/usage/README.md) — [Gemini](docs/usage/gemini.md) · [Claude](docs/usage/claude.md) · [OpenAI](docs/usage/openai.md) · [DeepSeek](docs/usage/deepseek.md) · [Ollama](docs/usage/ollama.md); [agent loops](docs/usage/agent_loops.md); [API keys](docs/usage/api_keys.md) |
| Examples index | [examples/README.md](examples/README.md) |
| CLI | [docs/usage/cli.md](docs/usage/cli.md) |
| Contributing | [CONTRIBUTING.md](CONTRIBUTING.md) · [agent workflow](docs/contributing/ai_native_workflow.md) |

## Contributing

We are building the "App Store" for Agents and require professional, robust, and safe skills. We welcome contributions to the skill registry, documentation, tests, and core framework.

* **[CONTRIBUTING.md](CONTRIBUTING.md)** — Contribution types, skill standard, pull request process, and navigation to all contributor docs.
* **[Agent Contribution Workflow](docs/contributing/ai_native_workflow.md)** — Workflow for AI agents contributing to the repository (operators supervise).
* **[Agent Code of Conduct](CODE_OF_CONDUCT.md)** — Deterministic outputs, safety boundaries, and acceptable use of skills.
* **[TESTING.md](docs/TESTING.md)** — Local linting and pytest before you open a PR.
* **[Pull request template](.github/PULL_REQUEST_TEMPLATE.md)** — Checklists for skills, docs, and framework changes (complete only the sections that apply).

## Comparison

Skillware differs from the Model Context Protocol (MCP) or Anthropic's Skills repository in the following ways:

*   **Model Agnostic**: Native adapters for Gemini, Claude, Ollama, and OpenAI.
*   **Code-First**: Skills are executable Python packages, not just server specs.
*   **Runtime-Focused**: Provides tools for the application, not just recipes for an IDE.

[Read the full comparison here](COMPARISON.md).

## Contact

For questions, suggestions, or contributions, please open an issue or reach out to us:

*   **Email**: [skillware-os@arpacorp.net](mailto:skillware-os@arpacorp.net)
*   **Issues**: [GitHub Issues](https://github.com/arpahls/skillware/issues)

---

<div align="center">
    <img src="assets/arpalogo.png" alt="ARPA Logo" width="50px" />
    <br/>
    Built & Maintained by ARPA Hellenic Logical Systems & the Community
</div>

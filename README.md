<div align="center">
  <img src="assets/skillware_logo.png" alt="Skillware Logo" width="400px" />

  A Python framework for modular, self-contained skill management for machines.
</div>

<br/>

<div align="center">
  <img src="https://img.shields.io/badge/License-MIT-efcefa?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/Python-3.10+-bae6fd?style=flat-square" alt="Python Version">
  <a href="https://pypi.org/project/skillware/"><img src="https://img.shields.io/pypi/v/skillware?style=flat-square&color=bbf7d0" alt="PyPI Version"></a>
  <a href="https://pepy.tech/projects/skillware"><img src="https://img.shields.io/pepy/dt/skillware?style=flat-square&label=DLs%20%E2%86%93&color=ffdac1" alt="Total PyPI downloads"></a>
</div>

<br/>

<div align="center">
  <a href="#mission">Mission</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#documentation">Documentation</a> •
  <a href="#contributing">Contributing</a> •
  <a href="#comparison">Comparison</a> •
  <a href="#stats">Stats</a> •
  <a href="CHANGELOG.md">Changelog</a> •
  <a href="#contact">Contact</a>
</div>

---

**Skillware** is an open-source framework and registry for modular, actionable Agent capabilities. It treats **Skills** as installable content, decoupling capability from intelligence. Just as `apt-get` installs software and `pip` installs libraries, `skillware` installs *know-how* for AI agents.

> "I know Kung Fu." - Neo

## Mission

The AI ecosystem is fragmented. Developers often re-invent tool definitions, system prompts, and safety rules for every project. **Skillware** supplies a standard to package capabilities into self-contained, installable units that work across **Gemini**, **Claude**, **Ollama**, **GPT**, and **Llama**. For the full story and roadmap, see our **[Vision](docs/vision.md)**.

A **Skill** in this framework provides everything an Agent needs to master a domain:

1. **Logic**: Executable Python so agents run real work, not guess it.
2. **Cognition**: System instructions and cognitive maps so any logical system uses the capability as intended.
3. **Governance**: Constitution, safety boundaries, and hard limits baked into the bundle.
4. **Interface**: Standardized tool schemas for any LLM or agent runtime.

### Skill library

Browse capabilities by category in the [Skill library](docs/skills/README.md) or on our <a href="https://skillware.site/skills" target="_blank" rel="noopener noreferrer">site&nbsp;↗</a>.

## Architecture

This repository is organized into a core framework, a registry of skills, and
documentation. Runnable provider scripts are indexed in
[examples/README.md](examples/README.md).

```text
Skillware/
├── docs/                       # Introduction, testing, skill catalog, usage guides (docs/usage/)
├── examples/                   # Provider reference scripts — usage demos, not pytest (see examples/README.md)
├── skills/                     # Skill Registry
│   └── category/               # Domain boundaries (e.g., finance)
│       └── skill_name/         # The Skill bundle
│           ├── manifest.yaml   # Definition, schema, and constitution
│           ├── skill.py        # Executable Python logic
│           ├── instructions.md # Cognitive map for the LLM
│           ├── card.json       # Optional UI presentation metadata
│           └── test_skill.py   # Bundle test (required for new skills; see docs/TESTING.md)
├── skillware/                  # Core Framework Package
│   ├── cli.py                  # Command-line interface
│   └── core/
│       ├── base_skill.py       # Abstract Base Class for skills
│       ├── env.py              # Environment Management
│       └── loader.py           # Universal Skill Loader and Model Adapter
├── templates/                  # Boilerplate templates for new skills
│   └── python_skill/           # Standard template with required files
└── tests/                      # Clone-repo tests (framework + optional maintainer skill tests)
    ├── test_*.py               # Framework tests (loader, CLI, issuer, …)
    └── skills/                 # Optional maintainer skill tests (edge cases)
```

## Quick Start

Requires **Python 3.10 or newer** (see `requires-python` in `pyproject.toml`).

### 1. Installation

You can install Skillware directly from PyPI:

```bash
pip install skillware
```

Or for development, clone the repository and install in editable mode:

```bash
git clone https://github.com/arpahls/skillware.git
cd skillware
pip install -e ".[dev,all]"
```

For documentation-only work, `pip install -e ".[dev]"` is enough. Skill and framework contributors should use `[dev,all]` to match CI (see [TESTING.md](docs/TESTING.md)).

> **Note**: Individual skills may have their own dependencies. The `SkillLoader` validates `manifest.yaml` and warns of missing packages (e.g., `requests`, `pandas`) upon loading a skill.

### 2. Verify your installation

```bash
skillware list
```

This prints a table of all locally available skills and confirms the install
and path resolution are working. Running `skillware` with no arguments opens
the interactive menu.

If `skillware` is not recognized, Python's `Scripts` directory may not be on
your PATH — use `python -m skillware list` as a fallback. See
[CLI Reference](docs/usage/cli.md#running-the-cli) for details.

### 3. Configuration

Copy the environment template and add your keys.

**Unix / macOS:**

```bash
cp .env.example .env
```

**Windows (PowerShell):**

```powershell
Copy-Item .env.example .env
```

Edit `.env` with agent keys (for example Gemini) and any keys your skills need. Agent keys power your LLM client; skill keys are declared per skill in the [Skill library](docs/skills/README.md). See [API keys for skills](docs/usage/api_keys.md) for setup, security, and framework variables.

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

| Topic | Links |
| :--- | :--- |
| **Introduction** | [Introduction](docs/introduction.md) · [Vision](docs/vision.md) · [Comparison](COMPARISON.md) |
| **Usage guides** | [Skill Library](docs/skills/README.md) · [Usage Guide](docs/usage/README.md) · [Examples](examples/README.md) · [Agent Loops](docs/usage/agent_loops.md) · [API Keys](docs/usage/api_keys.md) · [CLI](docs/usage/cli.md) |
| **Contributing** | [Contributing](CONTRIBUTING.md) · [Agent Native Workflow](docs/contributing/ai_native_workflow.md) · [Testing](docs/TESTING.md) · [Changelog](CHANGELOG.md) |

## Contributing

We are building the "App Store" for Agents. Skills are the main contribution, but documentation, tests, and framework fixes are welcome too. Human operators and supervised agents follow the same standards: scoped PRs, deterministic behavior, and verified tests.

See the **Contributing** row in [Documentation](#documentation) for the full path, [Contributing](CONTRIBUTING.md) (types, skill standard, PR process), [Agent Native Workflow](docs/contributing/ai_native_workflow.md) (for autonomous and semi-autonomous agents), [Testing](docs/TESTING.md) (Black, Flake8, framework and skill pytest, pre-PR checklist), and [Changelog](CHANGELOG.md) (user-facing entries under `[Unreleased]`).

Also read the [Agent Code of Conduct](CODE_OF_CONDUCT.md). Open PRs with the [pull request template](.github/PULL_REQUEST_TEMPLATE.md) and complete only the sections that apply.

## Comparison

Skillware differs from the Model Context Protocol (MCP), and Agent Skills (SKILL.md) in several ways:

*   **Model Agnostic**: Native adapters for Gemini, Claude, Ollama, and OpenAI.
*   **Code-First**: Skills are executable Python packages, not just server specs.
*   **Runtime-Focused**: Provides tools for the application, not just recipes for an IDE.

[Read the full comparison here](COMPARISON.md).

## Stats

<a href="https://pepy.tech/projects/skillware"><img src="https://img.shields.io/badge/Stats-PePyTech-ffdac1?style=flat-square" alt="PePy.tech dashboard"></a>
<a href="https://pypistats.org/packages/skillware"><img src="https://img.shields.io/badge/Stats-PyPiStats-ffdac1?style=flat-square" alt="PyPI Stats dashboard"></a>
<a href="https://pepy.tech/projects/skillware"><img src="https://img.shields.io/pepy/dt/skillware?style=flat-square&label=DLs%20%E2%86%93%20total&color=bbf7d0" alt="Total downloads (PePy)"></a>

PyPI download counts show how often `skillware` is installed from the package index. Numbers come from public third-party aggregators, and they include CI and mirror traffic, so they measure **install activity**, not unique users. Totals may differ slightly between services because each source uses its own window and methodology. Use the stats dashboards in the above badges for charts, version breakdowns, and longer history.

## Contact

For questions, suggestions, or contributions, please open an issue or reach out to us:

*   **Email**: [skillware-os@arpacorp.net](mailto:skillware-os@arpacorp.net)
*   **Enterprise**: [skills@arpacorp.net](mailto:skills@arpacorp.net) — enterprise skills, chaining, and forward deployed engineering
*   **Security**: [security@arpacorp.net](mailto:security@arpacorp.net) — report bugs, vulnerabilities, or other sensitive issues (see [SECURITY.md](SECURITY.md))
*   **Issues**: [GitHub Issues](https://github.com/arpahls/skillware/issues)

For skill-specific questions or reaching a skill's maintainer, check issuer and author details on the skill card, in the repo [Skill Library](docs/skills/README.md), or on our website's <a href="https://skillware.site/skills" target="_blank" rel="noopener noreferrer">skills catalog&nbsp;↗</a>.

---

<div align="center">
    <img src="assets/arpalogo.png" alt="ARPA Logo" width="50px" />
    <br/>
    Built & Maintained by ARPA Hellenic Logical Systems & the Community
</div>

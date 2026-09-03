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
  <a href="#how-it-works">How it works</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#documentation">Documentation</a> •
  <a href="#contributing">Contributing</a> •
  <a href="#comparison">Comparison</a> •
  <a href="#stats">Stats</a> •
  <a href="#citing">Citing</a> •
  <a href="CHANGELOG.md">Changelog</a> •
  <a href="#contact">Contact</a>
</div>

---

**Skillware** is an open-source framework and registry for modular, actionable Agent capabilities. It installs know-how for AI agents, or modular **Skills** (code, contract, and host guidance) decoupling capability from intelligence. In short, don't prompt your agents, equip them.

> "I know Kung Fu." - Neo

## Mission

Every new agent stack tends to reinvent tool schemas, system prompts, and safety rules. **Skillware** packages each capability as a self-contained bundle and adapts it to **Gemini**, **Claude**, **OpenAI**, **Ollama**, and other OpenAI-compatible hosts. For the full story and roadmap, see **[Vision](docs/vision.md)**.

A **Skill** in this framework provides everything an Agent needs to master a domain:

1. **Contract**: Constitution, safety boundaries, and typed I/O baked into the bundle.
2. **Effect**: Executable Python so agents run real work, not guess it.
3. **Directive**: System instructions and cognitive maps so any host uses the capability as intended.
4. **Assurance**: Offline tests that Effect honors Contract before a skill joins the registry.
5. **Interface**: Standardized tool schemas for any LLM or agent runtime.

Optional **Corpus** and **Reference** assets extend bundles when needed. Every bundled registry skill also ships **Presentation** (`card.json`) for catalog and UI metadata. Full reference: [Introduction — Skill anatomy](docs/introduction.md#skill-anatomy).

### Skill library

Browse capabilities by category in the [Skill library](docs/skills/README.md) or on our <a href="https://skillware.site/skills" target="_blank" rel="noopener noreferrer">site&nbsp;↗</a>.

## How it works

```mermaid
flowchart LR
    Registry[Registry] -->|Load| Loader[Loader]
    Loader -->|Adapt| AnyHost["Any Host"]
```

Install the registry once. Skillware loads a bundle, adapts it to your host's tool format, and your app runs the agent loop (Gemini, Claude, Ollama, custom scripts, …). See the [Introduction](docs/introduction.md) for loader details, [Agent loops](docs/usage/agent_loops.md) for the execution pattern, and [Skill chaining](docs/usage/skill_chaining.md) for multi-skill sessions (`SkillContext`, named `chains:`).

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
│           ├── manifest.yaml   # Contract: schema, constitution, issuer
│           ├── skill.py        # Effect: deterministic execution
│           ├── instructions.md # Directive: host guidance
│           ├── card.json       # Presentation: catalog / UI metadata
│           └── test_skill.py   # Assurance (required for registry skills)
├── skillware/                  # Core Framework Package
│   ├── cli.py                  # Command-line interface
│   ├── context.py              # SkillContext — multi-skill registry host context
│   ├── chains.py               # Named skill chain runner (run_chain, validate_chain)
│   └── core/
│       ├── base_skill.py       # Abstract Base Class for skills
│       ├── chains_config.py    # chains: YAML parsing
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

For documentation-only work, `pip install -e ".[dev]"` is enough. Skill and framework contributors should use `[dev,all]` to match CI (see [TESTING.md](docs/TESTING.md) and [Install extras](docs/usage/install_extras.md)).

> **Note**: Every skill has a dedicated pip extra (`pip install "skillware[category_skill]"`). The `SkillLoader` validates `manifest.yaml` on load and suggests the matching extra when packages are missing. See [Install extras](docs/usage/install_extras.md).

### 2. Verify your installation

```bash
skillware list
skillware paths
```

You should see a table of bundled registry skills and a paths summary confirming install and discovery. **Bundled skills from `pip install skillware` are always available** — an empty local `skills/` folder does not disable them.

For path tiers, shadowing, config files, and the interactive menu, see [CLI — paths & tiers](docs/usage/cli.md#skillware-paths), [CLI — config](docs/usage/cli.md#skillware-config), and [Finding skills on disk](docs/usage/README.md#finding-skills-on-disk). If `skillware` is not on your PATH, use `python -m skillware list` ([CLI Reference](docs/usage/cli.md#running-the-cli)).

### 3. Configuration

**Skill paths (optional):** copy [`.skillware.yaml.example`](.skillware.yaml.example) to `.skillware.yaml` in your project root, or use the interactive menu (**`4` / `paths`**) to persist project and external skill roots. Inspect merged settings with `skillware config show`. See [CLI — config](docs/usage/cli.md#skillware-config).

**API keys:** copy the environment template and add your keys.

**Unix / macOS:**

```bash
cp .env.example .env
```

**Windows (PowerShell):**

```powershell
Copy-Item .env.example .env
```

Edit `.env` with agent keys (for example Gemini) and any keys your skills need. Agent keys power your LLM client; skill keys are declared per skill in the [Skill library](docs/skills/README.md). See [API keys for skills](docs/usage/api_keys.md) for setup, security, and framework variables.

> Note: any loaded skill runs in your process and can read every variable in `os.environ`. Before wiring in real keys — especially with skills you did not write — see the [skill trust model](docs/security/skill-trust-model.md).

### 4. Usage Example (Gemini)

Requires `pip install "skillware[gemini]"` (dev: `pip install -e ".[gemini]"`) and `GOOGLE_API_KEY`. The skill itself is offline — no skill API keys. For setup details see [Gemini usage guide](docs/usage/gemini.md). Multi-turn loops: [Agent loops](docs/usage/agent_loops.md).

```python
import google.genai as genai
from google.genai import types
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("monitoring/token_limiter")
skill = bundle["class"]()
tool = SkillLoader.to_gemini_tool(bundle)

client = genai.Client()
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=(
        "Check token budget for task_id demo_run: "
        "current_token_count 95000, max_allowed_tokens 100000."
    ),
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)

for part in response.candidates[0].content.parts:
    if part.function_call:
        print(skill.execute(dict(part.function_call.args)))
    else:
        print(part.text)
```

For other providers and integration patterns, see the [usage guides](docs/usage/README.md).

## Documentation

| Topic | Links |
| :--- | :--- |
| **Introduction** | [Introduction](docs/introduction.md) · [Vision](docs/vision.md) · [Comparison](COMPARISON.md) |
| **Usage guides** | [Skill Library](docs/skills/README.md) · [Usage Guide](docs/usage/README.md) · [Skill chaining](docs/usage/skill_chaining.md) · [OpenAI-compatible hosts](docs/usage/openai_compatible.md) · [Install extras](docs/usage/install_extras.md) · [Examples](examples/README.md) · [Agent Loops](docs/usage/agent_loops.md) · [API Keys](docs/usage/api_keys.md) · [CLI](docs/usage/cli.md) |
| **Security** | [Skill trust model](docs/security/skill-trust-model.md) · [SECURITY.md](SECURITY.md) |
| **Contributing** | [Contributing](CONTRIBUTING.md) · [Agent Native Workflow](docs/contributing/ai_native_workflow.md) · [Testing](docs/TESTING.md) · [Changelog](CHANGELOG.md) |

## Contributing

Skills, docs, tests, and framework fixes are welcome. Start with [Contributing](CONTRIBUTING.md), [Agent Native Workflow](docs/contributing/ai_native_workflow.md), and [Testing](docs/TESTING.md). See the [Agent Code of Conduct](CODE_OF_CONDUCT.md). Open PRs with the [pull request template](.github/PULL_REQUEST_TEMPLATE.md).

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

PyPI download counts measure **install activity** from public aggregators (including CI and mirrors), not unique users. Use the badge links above for charts and version breakdowns.

## Citing

<a href="https://doi.org/10.5281/zenodo.21552745"><img src="https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21552745-c7d2fe?style=flat-square" alt="DOI 10.5281/zenodo.21552745"></a>

If you use Skillware in research or products, please cite it using [CITATION.cff](CITATION.cff) (GitHub **Cite this repository**) or the Zenodo **concept DOI** above. That DOI is stable across releases. For reproducibility, also record the **Skillware version** you used (PyPI or Git tag, for example `0.5.3`).

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

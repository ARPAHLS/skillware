# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **`finance/wallet_screening`**: Added FTM publicKey matching and an ETH sanctions index (#128).

### Changed
- **CLI**: Implemented a visual redesign for `skillware list`, including a new splash screen, menu loop, and table layout (#129).

## [0.3.1] - 2026-05-25

### Added
- **Novelty Extractor Skill**: Introduced the `data_engineering/novelty_extractor` skill (#116, fixes #24).
- **Examples Index**: Added `examples/README.md` to serve as the canonical index of runnable provider scripts (#107).

### Changed
- **SDK Migration**: Migrated framework and examples from `google-generativeai` to the new `google-genai` SDK (#97) and updated all usage documentation snippets (#92).
- **Documentation**: Improved README navigation and overall skill catalog discoverability (#98).
- **Documentation**: Cross-linked runnable examples directly on skill catalog pages (#121) and synced `agent_loops.md` with the central examples index (#122).

## [0.2.9] - 2026-05-22

### Added
- **CLI Tool:** Introduced the `skillware` command-line interface, starting with the `skillware list` command for skill discovery (implemented by contributor @rizzoMartin) (#84).
- **CLI Features:** The `list` command prints a rich table of locally installed skills and supports filtering via `--category`, `--issuer`, and `--skills-root` flags.
- **Optional Extras:** Added optional dependency groups in `pyproject.toml` (`[cli]`, `[gemini]`, `[claude]`, `[openai]`, `[office]`, `[all]`, `[dev]`) so users only install the SDKs their specific skills require (#87).

### Changed
- **Leaner Core Install:** Removed heavy SDKs (`anthropic`, `google-generativeai`, `pymupdf`, `openai`) from the default installation, reducing core requirements to just `requests`, `pyyaml`, `python-dotenv`, and `beautifulsoup4` (#87).
- **Dependency Management:** Consolidated dependency management entirely into `pyproject.toml`.
- **Requirements File:** Transformed `requirements.txt` into a dev-convenience pointer (running `pip install -e ".[dev,all]"`) rather than a duplicate flat dependency list.

## [0.2.8] - 2026-05-22

### Added
- **Issue Resolver Skill:** Introduced the `dev_tools/issue_resolver` skill for universal GitHub issue analysis and resolution (#56).
  - Validates and normalizes any public GitHub issue URL and returns a structured payload containing pre-computed GitHub API and raw content URLs.
  - Guides calling agents through a 5-stage workflow (fetch issue, read repo context, analyze files, produce a ranked plan, implement after approval).
  - Includes optional `github_token` and `extra_instructions` parameters.
  - Compatible with all five provider adapters (Gemini, Claude, OpenAI, DeepSeek, Ollama).
  - Requires no network calls itself and has no runtime dependencies beyond PyYAML.
- **Dev Tools Category:** Introduced the new `dev_tools` skill category.

### Changed
- **Skill Catalog Revamp:** Overhauled all pages under `docs/skills/` to include a breadcrumb trail, per-provider Usage Examples, environment variable tables linking to the API keys guide, data schema blocks, and a limitations section (#82).
- **Documentation Polish:** Removed emojis from all catalog pages and the main skills README index (#52).

### Fixed
- **Metadata:** Corrected the author name in `pyproject.toml` from `ARPA Hellenic Logic Systems` to `ARPA Hellenic Logical Systems`.

## [0.2.7] - 2026-05-18

### Added
- **Packaging:** Full skill bundles on PyPI. Wheels now include `manifest.yaml`, `instructions.md`, `card.json`, and skill data files, rather than only `.py` modules.
- **Packaging:** Configured `MANIFEST.in` to graft the `skills/` tree and updated `[tool.setuptools.package-data]` so new registry skills do not require per-skill `pyproject.toml` edits.
- **Registry:** Added empty `__init__.py` files under `skills/` category packages (and skill folders where needed) to ensure `setuptools` packages the complete tree. This requirement is now enforced in tests for new registry skills.
- **Documentation:** Added a "Finding skills on disk" usage guide.
- **Documentation:** Added contributor notes for PyPI packaging in `CONTRIBUTING.md` and the skill template README.

### Fixed
- **Skill Loader:** Fixed skill resolution paths after `pip install` (#13). `SkillLoader.load_skill()` no longer restricts searches to `site-packages/skills/`. It now falls back through the following order: 
  1. An existing path on disk (absolute or relative)
  2. Roots defined in the `SKILLWARE_SKILL_PATH` environment variable
  3. A local `skills/` folder in the current working directory (searching up to six parent directories)
  4. Bundled registry skills shipped with the package
  *(Note: If nothing matches, the error now explicitly lists the paths that were tried).*

## [0.2.6] - 2026-05-17

### Added
- **Framework:** Added OpenAI adapter (`SkillLoader.to_openai_tool()`) for Chat Completions tool calling (#68).
- **Framework:** Added DeepSeek adapter (`SkillLoader.to_deepseek_tool()`) as a separate public API (#70).
- **Framework:** Added shared function-name sanitization for OpenAI-compatible providers.
- **Documentation:** Added OpenAI and DeepSeek usage guides and corresponding integration examples (`examples/openai_tos_evaluator.py`, `examples/deepseek_tos_evaluator.py`) (#69, #70).
- **Documentation:** Added usage guides index, agent loops, and skill usage template (#71).
- **Documentation:** Added Usage Examples on all seven skill catalog pages (Gemini, Claude, OpenAI, DeepSeek, Ollama) (#71).
- **Documentation:** Added generic setup guide for API keys for skills (#67).
- **Documentation:** Added README links to usage index and agent loops (#71).
- **Contributing:** Added Agent Contribution Workflow, an agent-directed guide (#64, #65).
- **Registry:** Added Issuer attribution on all skills (`manifest.yaml`, `card.json`, `docs/skills/*.md`, catalog) (#63).
- **Registry:** Added Enterprise disclaimer on ARPA catalog skill pages (#59, #62).
- **Tests:** Added `tests/test_skill_issuer.py` for registry issuer validation (#63).

### Changed
- **Documentation:** Updated Ollama guide for current local models (#71).
- **Contributing:** Restructured `CONTRIBUTING.md` for contribution types and skill standards (#64).
- **Contributing:** Aligned the Usage Examples requirement in CONTRIBUTING and agent workflow (#71).

## [0.2.5] - 2026-04-28

### Added
- **TOS Evaluator Skill:** Introduced the `compliance/tos_evaluator` skill for local-first website policy evaluation prior to automated access.
  - Checks `robots.txt` permissions for target URLs and user-agents.
  - Discovers candidate legal pages (Terms, Legal, Acceptable Use, API links).
  - Extracts and evaluates policy clauses related to automated behaviors (scraping, crawling, indexing, monitoring, etc.).
  - Returns structured verdicts (`SAFE`, `UNSAFE`, `CAUTION`, `INSUFFICIENT_EVIDENCE`) alongside evidence payloads and next-step guidance.
  - Features an optional, provider-configurable low-cost LLM fallback for ambiguous clauses.
- **Skill Infrastructure:** Added the complete package contents for the TOS Evaluator under `skills/compliance/tos_evaluator/` (including manifest, logic, and instructions).
- **Testing:** Added central tests (`tests/skills/compliance/test_tos_evaluator.py`) and local skill tests.
- **Documentation:** Added dedicated skill documentation (`docs/skills/tos_evaluator.md`) and updated the central skill catalog.
- **Examples:** Added integration scripts (`examples/gemini_tos_evaluator.py`, `examples/claude_tos_evaluator.py`, `examples/ollama_tos_evaluator.py`).
- **Dependencies:** Added `beautifulsoup4` (`bs4` in the manifest) to the project for deterministic HTML parsing 

## [0.2.4] - 2026-04-11

### Added
- **MiCA Compliance Module:** Added the `compliance/mica_module` skill, featuring in-memory caching for ultra-low latency RAG (~1.7ms) and a weighted surgical router to prevent context window asphyxiation.

### Changed
- **Pure Cognitive Framework:** Realigned all MiCA examples (Gemini, Claude, Ollama) to follow a prompt-based cognitive pattern that avoids opaque native tool-calling obstacles.
- **Documentation:** Comprehensive documentation updates for the new Compliance category and a refined core README.

### Fixed
- **Quality Engineering:** Resolved all PEP 8 and Flake8 violations across the registry and verified execution with 100% unit test success.

## [0.2.3] - 2026-04-09

### Added
- **Zero-Latency PII Masker Skill:** Introduces the `compliance/pii_masker` component to act as a "Privacy Firewall", intercepting and scrubbing sensitive metadata (Names, Emails, Physical Addresses, Crypto Wallets) locally before external LLM dispatch.
- **Ollama Edge Interoperability:** Leverages the 270M parameter `arpacorp/micro-f1-mask` structure for optimized, offline processing.
- **Dynamic Modalities:** Added three processing modes for the masker: 
  - `mask`: Preserves contextual entity tags (e.g., `[PERSON_1]`).
  - `redact`: Completely overwrites tokens with localized constants (`xxxx`).
  - `remove`: Intelligently drops strings from the payload to decrease token size.
- **Testing:** Integrated rigorous Pytest mock structures intercepting the edge boundary.

### Changed
- **API Manifests:** Rewrote API compliance manifest parameters to match the internal JSON Schema architecture.

## [0.2.2] - 2026-04-03

### Added
- **New Skill:** Introduced the `data_engineering/synthetic_generator` skill for bulk-generating high-entropy synthetic training data to combat model collapse (Resolves #22).
- **Model Agnosticism:** Added internal routing support for the synthetic generator to use `Ollama`, `Gemini`, and `Anthropic`.
- **Zero-Dependency Entropy Scoring:** Added a new `zlib` compression ratio heuristic to natively validate lexical entropy and block boilerplate outputs without heavy NLP dependencies.
- **New Documentation:** Launched the `Data Engineering` category in the central skill registry along with comprehensive integration guides and integration scripts (`examples/build_dataset_demo.py`).

### Fixed
- **Bug Fixes:** Addressed all `flake8` PEP8 linting issues across the module.

## [0.2.1] - 2026-03-21
### Added
- **Prompt Token Rewriter Skill:** A new middleware skill (`optimization/prompt_rewriter`) that heuristically compresses bloated prompts into fewer tokens, supporting low, medium, and high aggression levels.
- **Optimization Category:** Established a new domain in the skill registry for architectural and operational efficiency tools.
- **Skill Reference Card:** Comprehensive documentation for the Rewriter at `docs/skills/prompt_rewriter.md`.
- **Interactive Demo:** Added `examples/prompt_compression_demo.py` for offline testing of compression logic.

### Changed
- **Middleware Patterns:** Updated the Gemini usage guide with "Skill Chaining" examples demonstrating the rewriter as an automated pre-processor.
- **Standardized Manifests:** Aligned all skill metadata with the new `parameters` and `constitution` standard.

### Fixed
- **CI/CD Alignment:** Fixed linting and formatting issues to ensure 100% `flake8` compliance in core registry files.

## [0.2.0] - 2026-03-21
- Consolidated and rolled forward into `v0.2.1`.

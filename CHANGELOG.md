# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Contributors add user-facing entries under `[Unreleased]` in the same PR. Maintainers rename that section to a version and date when cutting a PyPI release. See [CONTRIBUTING.md](CONTRIBUTING.md).

## [Unreleased]

### Added

- **Documentation:** OpenAI-compatible host guide and runnable Groq example covering shared `to_openai_tool()` usage, provider base URLs, credentials, and local servers (#261).
- **Framework:** `skillware/core/ui_schema.py` helpers to resolve dot paths and validate output-card field keys (#199).
- **CI:** Parametrized guard `tests/test_card_ui_schema.py` — every registry skill with output-card `ui_schema` must ship a fixture under `tests/fixtures/card_ui_schema/` whose samples cover all field keys (#199).

### Fixed

- **`compliance/mica_module`**, **`compliance/pii_masker`**: Align `card.json` output fields with actual `execute()` return shape (#199).

### Changed

- **Skills (finance/uk_companies_house_handler):** Completed Phase v2a upgrade (#220). Added `context` parameter to carry forward session state (`company_number`, `company_name`, `officer_filter`, etc.). Added `partial` envelope status and optional `pipeline` state to support paused multi-step pipelines (noted as v2b prep in instructions). Updated `_get_officers` to fallback to `company_name` from context and added tests for fallback logic. Updated `examples/gemini_uk_companies_house_handler.py` into a fully interactive chat loop.
- **Documentation:** CONTRIBUTING and contributor workflow checklists — update `card.json` and output fixtures together when changing `execute()` output (#199).

## [0.4.5] - 2026-07-16

### Added

- Added `creative/bg_remover`, an offline background removal skill powered by rembg (#196).
- **Packaging:** Category, per-skill, and `[all]` optional extras generated from skill manifests via `scripts/sync_extras.py`; hand-maintained `dev`, SDK extras, and meta `[agents]` (#236).
- **Documentation:** [Install extras](docs/usage/install_extras.md) — canonical guide for `pip install skillware[...]` targets (#236).
- **Framework:** `skillware/core/extras.py` and richer `ImportError` hints from `SkillLoader` when manifest requirements are missing (#236).
- **CI:** PyPI wheel packaging smoke test — builds a wheel, installs it in a fresh venv (base deps only), and verifies every bundled registry skill is present and loadable via `scripts/wheel_smoke_test.py` (#182).
- **Documentation:** Cross-linked wheel-smoke CI job in `CONTRIBUTING.md` and `docs/contributing/ai_native_workflow.md` (#182).
- **CLI:** `skillware paths` shows skill root resolution order (external → project → bundled), tier labels, shadowing summary, and operator tips; interactive menu option `4` wired (#81).
- **Framework:** `skillware/core/discovery.py` — shared skill root discovery for `SkillLoader` and the CLI (tier labels, shadowing, registry ID listing; foundation for config-driven paths in #246).
- **Framework:** `BaseSkill.validate_params()` — optional helper to validate tool arguments against manifest `parameters` JSON Schema; raises `SkillwareParamValidationError` on mismatch. Not called automatically by the loader or `execute()` (#125). Reference: `examples/claude_wallet_check.py`, `examples/gemini_tos_evaluator.py`.
- **Framework:** Registry manifests standardize on `outputs:` (legacy singular `output:` removed from `finance/wallet_screening`) (#125).

### Changed

- **Framework:** Map manifest requirement `pillow` to import name `PIL` in `SkillLoader` dependency checks (#196).
- **Packaging (breaking):** Removed legacy extras `cli`, `embeddings`; `[all]` is skill runtime deps only (not SDK packages). Use `[agents]` for Gemini + Claude + OpenAI SDK deps (#236).
- **CLI:** `skillware list` prints a pointer to the install extras guide (#236).
- **Documentation:** README, CONTRIBUTING, TESTING, skill catalog pages, and examples index updated for the new extra taxonomy; every skill doc recommends its per-skill extra (#236).
- **Framework:** `SkillLoader` delegates root resolution to `discovery.get_skill_roots()` so load, list, test, and `paths` use the same order (#81).
- **CLI:** Help and menu list `paths` as available (no longer “coming soon”) (#81).
- **Documentation:** README — trim redundant Contributing cross-links, add `skillware paths` to install verification, and link the skill trust model in the docs table; cross-link `skillware paths` in `docs/introduction.md` and `docs/usage/README.md`.
- **Documentation**: Add operator expectations (bundled vs external, out-of-band changes, where to report issues) and an instruction-only content note to `docs/security/skill-trust-model.md`; add trust-model cross-links from README configuration and CONTRIBUTING Skill Package Standard (#243).

## [0.4.3] - 2026-07-10

### Added

- **Framework:** Added `_sanitize_gemini_tool_name()` to `skillware/core/loader.py` to explicitly map provider tool naming constraints.
- **Tests:** Added `test_sanitize_gemini_tool_name()` to `tests/test_loader.py` to verify safe translation and `test_skill_docs_gemini_anti_patterns()` to `tests/test_registry_docs.py` to enforce documentation hygiene by preventing manual tool wrapping and mutation anti-patterns in skill catalog pages.
- **Documentation:** Added canonical dispatch guidelines to `docs/usage/gemini.md` and `docs/usage/skill_usage_template.md`.
- **Documentation:** Category selection guidance for contributors; issue-first policy for new top-level folders in `CONTRIBUTING.md` (#204).

### Changed

- **GitHub**: Overhauled issue templates (CLI, Skill Upgrade, Examples, Packaging), issue chooser `config.yml`, PR template, and label taxonomy with pastel colors; labels sync automatically from `.github/labels.json` via CI on merge to `main` (#227).
- **Framework:** `SkillLoader.to_gemini_tool()` now returns a `google.genai.types.Tool` object instead of a raw dictionary, ensuring compatibility with the `google-genai` SDK when passing tools to `GenerateContentConfig`.
- **Tests:** Updated `tests/test_loader.py` to assert against the properties of the `google.genai.types.Tool` object for `to_gemini_tool()`.
- **Documentation:** Updated Gemini integration snippets across all skill catalog pages and `introduction.md` to reflect the `to_gemini_tool()` API change and correct tool name sanitization.
- **Documentation:** Aligned `agent_loops.md` and `cli.md` with Gemini sanitized tool-name dispatch after #229 (#230 follow-up).
- **Examples:** Removed manual `types.Tool` wrapping, and consistently utilize `SkillLoader._sanitize_gemini_tool_name()` for derived tool names in gemini examples.

### Fixed

- **Framework:** `SkillLoader.to_gemini_tool()` returned a plain dictionary instead of `google.genai.types.Tool`, causing runtime failures when passed to `GenerateContentConfig(tools=...)` with the `google-genai` SDK. Fixes #223.

## [0.4.2] - 2026-07-08

### Changed

- **CLI**: Interactive splash — correct SKILLWARE ASCII logo, Rich 3-stop gradient on logo and tagline (`#D4E4F1` → `#79B6D8` → `#EBD8DC`), shared `_package_version_str()` for splash and `--version`, tagline `Skillware v{version} — Skill Management Framework` (#222).
- **Documentation**: Compact architecture Mermaid diagrams — shorter README labels, model-agnostic adapter nodes in introduction, horizontal agent-loop layout with role table (#210 follow-up, #221).
- **Documentation**: Docs sweep — README Mermaid Registry alignment; `vision.md` pinned to v0.4.x; skill catalog and usage guides prefer `bundle["class"]()` with explicit `bundle["module"].ClassName()` noted as still supported (#225).

## [0.4.1] - 2026-07-08

### Added

- **`finance/uk_companies_house_handler`**: New skill for UK Companies House REST API — deterministic company search, profile, officers, PSC, filing history, and intent-to-operation mapping with UK corporate terminology translation; bundled endpoint index and terminology map; status-based response envelope (ready/needs_input/error) with disambiguation support (#172, #218).
- **Documentation**: Add `docs/security/skill-trust-model.md` documenting the skill execution model, on-disk resolution order and shadowing, provenance tiers (Bundled / Project / External), and operator security guidance; wire links from SECURITY, usage, CONTRIBUTING, and CODE_OF_CONDUCT (#109).
- **Documentation**: Add minimal Mermaid architecture flow diagrams to README, introduction, and agent loops; cross-links, Step 1 mini-pipeline, adapter fan-out, and direct-path footnotes (#210, #217).

### Changed

- **Loader**: `SkillLoader.load_skill()` auto-discovers the single `BaseSkill` subclass in each `skill.py` and exposes it as `bundle["class"]`; `get_skill_class()` helper added. Existing `bundle["module"]` usage is unchanged (#89).
- **Loader**: `SkillLoader.load_skill()` validates that `manifest.yaml` `name` matches the path-derived registry ID for `category/skill_name` layouts; emits `SkillwareIdentityWarning` on mismatch (warn-only v1). Flat private skills under a skill root are unchanged. Bundles now include optional `registry_id` (#200).
- **Version policy**: Raise security support floor to `>= 0.3.5`, legacy band `0.3.0`–`0.3.4` (silent CLI), unsupported advisory for installs below `0.3.0` (#192).
- **Documentation**: Clarify skill ID vs manifest `name` vs provider tool names in `docs/usage/cli.md`, `docs/usage/agent_loops.md`, and `docs/introduction.md`; require full registry IDs in CONTRIBUTING manifest standard (#201).

### Fixed

- **`office/pdf_form_filler`** and **`defi/evm_tx_handler`**: Align `manifest.yaml` `name` with registry paths (`office/pdf_form_filler`, `defi/evm_tx_handler`); update examples and docs to use manifest-derived tool dispatch (#201).

## [0.4.0] - 2026-06-30

### Added

- **`monitoring/token_limiter`**: New monitoring skill that evaluates cumulative token usage and returns CONTINUE, WARN, or FORCE_TERMINATE for autonomous agent loops; bundled indicative model pricing, ROI scaffold fields for v2, local and provider loop examples (#23, #207).
- New **`monitoring`** skill category in CONTRIBUTING, `ai_native_workflow.md`, and `docs/skills/README.md`.
- **Tests**: `tests/test_registry_docs.py` — CI doc-drift guards that verify skill catalog, examples index, and agent-loops reference matrix stay in sync with the registry (#183, #189).
- **Documentation**: Cross-linked `tests/test_registry_docs.py` in `ai_native_workflow.md` and `CONTRIBUTING.md` so contributors know doc-drift guards run in CI; added explicit PR checklist reminder in `CONTRIBUTING.md` (#193, #197).

### Changed

- **Documentation**: `docs/skills/token_limiter.md` — budget disclaimer callout, limitations clarity, and enterprise disclaimer (#23).
- **Documentation**: README Stats section and live PyPI download badges (pepy / PyPI Stats dashboards, header `DLs ↓` total) (#198).
- **Documentation**: Aligned CLI and examples docs (`docs/usage/cli.md`, `examples/README.md`, `docs/vision.md`, `README.md`) with the `skillware test` / `skillware examples` behavior (#191, #194).

## [0.3.9] - 2026-06-26

### Fixed

- **CLI**: `skillware examples` and `list --examples` fetch `examples/README.md` from GitHub when no local copy is found (pip installs and directories outside a checkout).

## [0.3.8] - 2026-06-26

### Changed

- **Tests**: `tests/test_skill_issuer.py` now requires `test_skill.py` for every registry skill under `skills/` (#160).
- **Documentation**: Clarified that bundle tests must mock network calls and model downloads in CI (#170).
- **Documentation**: Added a **Status** section to [TESTING.md](docs/TESTING.md) summarizing the current testing model (#179).
- **Documentation**: Post-release alignment — category tables, Python 3.10+ badge, dev install (`[dev,all]` vs `[dev]`), README configuration via `.env.example`, DeFi env vars in `.env.example`, framework env vars in [api_keys.md](docs/usage/api_keys.md) (#154).

### Added

- **CLI**: `skillware test` runs bundle tests via pytest — all roots, by skill ID, or by `--category`; supports `-v` and `--no-header`. Documented in [cli.md](docs/usage/cli.md), [TESTING.md](docs/TESTING.md), and contributor guides (#83).
- **CLI**: `skillware list --examples` shows per-skill example script counts; `skillware examples [skill_id]` lists indexed runnable scripts from `examples/README.md` with GitHub source links; interactive menu option **examples** (#126).

## [0.3.7] - 2026-06-22

### Added
- **`wellness/mental_coach`**: Deterministic wellness coaching firewall with crisis triage, hard scope limits, embedded public KB, optional Gemini scope evaluator, and catalog documentation (#148).

### Changed
- **Tests**: Moved `tests/test_mica_module.py` to `tests/skills/compliance/test_mica_module.py` so maintainer skill tests follow the `tests/skills/<category>/` layout; `tests/` root is framework-only (#86).
- **`wellness/mental_coach`**: Set real issuer contact email and add health disclaimer on the catalog page (PR #174 follow-up).

### Fixed
- **`finance/wallet_screening`**: Align examples and docs with `finance/wallet_screening` manifest tool name; fix `gemini_wallet_check.py` and `claude_wallet_check.py` to match tool name dynamically from manifest; correct `card.json` UI fields to match actual skill output schema; update `instructions.md`, provider snippets, Data Schema, and usage docs (#173).

## [0.3.6] - 2026-06-15

### Added
- **Tests**: Backfilled `test_skill.py` for six registry skills (`mica_module`, `pii_masker`, `synthetic_generator`, `wallet_screening`, `pdf_form_filler`, `prompt_rewriter`); all registry skills now ship co-located bundle tests. Fixed `prompt_rewriter` package export so pytest can collect the bundle (#158).
- **CLI**: `skillware/__main__.py` enables `python -m skillware` as a fallback when the `skillware` command is not on PATH (#135). Added `cmd_help()` for rich-formatted help, wired to `skillware --help`/`-h` and interactive menu option `4`. Added `--version`/`-V` flag.

### Fixed
- **`novelty_extractor`**: Bundle tests mock fastembed embeddings so CI avoids HuggingFace downloads and rate limits (#159 follow-up).
- **`finance/wallet_screening`**: `WalletScreeningSkill.manifest` loads `manifest.yaml` from the bundle directory (#165).

### Changed
- **CI**: GitHub Actions runs `pytest skills/` then `pytest tests/` after lint (bundle + framework/maintainer tests; closes #90) (#159).
- **CI**: CodeQL GitHub Action upgraded from v3 to v4.
- **Dependencies**: Extended `[all]` with registry skill runtime deps (`web3`, `fastembed`, `numpy`); added `[defi]` and `[embeddings]` optional extras. Documented manifest ↔ `pyproject.toml` convention in CONTRIBUTING and TESTING.md.
- **Documentation**: [TESTING.md](docs/TESTING.md), [CONTRIBUTING.md](CONTRIBUTING.md), [ai_native_workflow.md](docs/contributing/ai_native_workflow.md), and README architecture tree document the bundle / framework / maintainer / example testing model. Pytest collects `tests/` and `skills/` only (`examples/` ignored).
- **Dependencies**: Moved `rich>=13.0` from `[cli]` extra to core dependencies; CLI is now available immediately after `pip install skillware`. The `[cli]` extra is kept as an empty deprecated alias for backward compatibility (#135).

## [0.3.5] - 2026-06-05

### Added
- **`defi/evm_tx_handler`** (#142): Structured EVM agent wallet skill on Ethereum and Base — `resolve`, Uni V2 `quote`/`preview`/`execute` (approve + swap), `transfer`, `balances`, `wallet_info`, YAML registries, optional CoinGecko USD preview, `max_trade_usd` fail-closed cap, balance pre-flight checks, and mocked Web3 tests. Examples: `examples/gemini_evm_tx_handler.py`, `examples/claude_evm_tx_handler.py`.

### Changed
- **CI**: GitHub Actions installs from `pyproject.toml` only (`pip install -e ".[dev,all]"`); runs `black --check`, `flake8`, then `pytest tests/` (#151, #153). Co-located `skills/**/test_skill.py` remains a local pre-PR step.
- **Documentation**: [COMPARISON.md](COMPARISON.md) and README updated for Agent Skills (SKILL.md) and fairer MCP framing (#123); [TESTING.md](docs/TESTING.md) and [CONTRIBUTING.md](CONTRIBUTING.md) aligned with CI and Black gate (#151, #153); `defi` skill category added to CONTRIBUTING.

### Fixed
- **`dev_tools/issue_resolver`**: Replaced wide emoji regex in commit-message validation with explicit Unicode ranges (CodeQL `py/overly-large-range`, #146).

## [0.3.3] - 2026-05-29

### Added
- **`dev_tools/issue_resolver`**: GitHub issue workflow with sequential stage checklists, conditional verify/commit gates, and commit-message validation (#143).
- **Examples**: `gemini_issue_resolver.py`, `claude_issue_resolver.py`, and `ollama_issue_resolver.py` for `dev_tools/issue_resolver` (#118).
- **Version policy**: `skillware/version_policy.py` with supported-version thresholds; CLI prints one dim stderr advisory only for installs below `0.2.6` (#132).
- **Tests**: `tests/test_version_policy.py` for advisory thresholds, opt-out, and CLI hook (#132).
- **Documentation**: Added [docs/vision.md](docs/vision.md) with project story, roadmap, and agent discoverability (#133).

### Changed
- **`finance/wallet_screening`**: Unified TRM/scam transaction risk index for analysis (#140).
- **SECURITY.md**: Supported-version table aligned with `>= 0.3.1` security support and unsupported `< 0.2.6` band (#132).
- **CLI**: Calls version advisory once at `main()` startup, not on menu re-loops (#132).
- **Dependencies**: Added `packaging` for semver comparisons (#132).
- **Documentation**: README Mission links to vision.md; wallet screening comparison table lives in COMPARISON.md; docs table and cross-links updated (#133).

## [0.3.2] - 2026-05-27

### Added
- **Changelog**: Added root `CHANGELOG.md` following Keep a Changelog, with retrospective release history from v0.2.0 and a README nav link (#108).
- **`finance/wallet_screening`**: FTM publicKey matching and an ETH sanctions index (#128).

### Changed
- **CLI**: Visual redesign for `skillware list`, including pastel table, `short_description` column, interactive splash, and menu (#129).
- **CLI**: Interactive polish - splash footer links, menu re-loop, stub labels for #81 / #83, width-aware table, shared terminal context (#130, #131).
- **Contributing**: Aligned Code of Conduct, CONTRIBUTING, agent workflow, and PR template for CHANGELOG maintenance and co-authoring rules (#124).
- **Documentation**: README documentation table and `docs/introduction.md` link to `CHANGELOG.md`; contributor template documents optional `short_description` (#130).

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
- **Dependencies:** Added `beautifulsoup4` (`bs4` in the manifest) to the project for deterministic HTML parsing.

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

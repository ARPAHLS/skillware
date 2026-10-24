# Skill Library

Welcome to the official catalog of Skillware capabilities. New here? Start with the [project README](../../README.md). Each skill page describes its bundle layout; shared role vocabulary is in [Skill anatomy](../introduction.md#skill-anatomy) and the [glossary](../glossary.md).

Browse by category below, or run `skillware list` (with optional `--shape`, `--tag`, `--target`, or `--category` filters) after `pip install skillware` to discover locally available skills. Learn more about runtime taxonomy filtering in [Agent loops](../usage/agent_loops.md#taxonomy-aware-skill-filtering-and-execution-safety) and discovery in the [CLI guide](../usage/cli.md#skillware-list). When contributing a new skill, see [Authoring manifests](../contributing/ai_native_workflow.md#authoring-manifests-and-schema) and [Choosing a category](../../CONTRIBUTING.md#choosing-a-category) in CONTRIBUTING.md.

Each category has a dedicated hub at `docs/skills/<category>/README.md`. Skill catalog pages live beside that hub (`docs/skills/<category>/<skill_name>.md`). Runtime IDs stay in registry form under `skills/` — the folder layout used by `SkillLoader` is unchanged. Full crawl map: [documentation sitemap](../sitemap.md).

## Office
Skills for document processing, email automation, and productivity.

**Category hub:** [Office agent skills](office/README.md).

| Skill | ID | Shape | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[PDF Form Filler](office/pdf_form_filler.md)** | `office/pdf_form_filler` | `workflow` | `0.1.2` (16 Oct 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Inspects, validates, and fills AcroForm PDFs deterministically with XFA and radio group safeguards. |
| **[Gmail Handler](office/gmail_handler.md)** | `office/gmail_handler` | `workflow` | `0.2.0` (19 Aug 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Gmail send, search, read, reply, and attachments via IMAP/SMTP with address book, signatures, and confirmation gates. |
| **[Web Form Mapper](office/web_form_mapper.md)** | `office/web_form_mapper` | `workflow` | `0.1.0` (04 Oct 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Deterministically maps identity profiles to HTML web forms and submits with CSRF preservation and confirmation gates. |

## Creative
Skills for image processing, media editing, and creative utilities.

**Category hub:** [Creative agent skills](creative/README.md).

| Skill | ID | Shape | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[Background Remover](creative/bg_remover.md)** | `creative/bg_remover` | `atomic` | `0.2.0` (2 Aug 2026) | [@AyushSrivastava1818](https://github.com/AyushSrivastava1818) ([@ARPAHLS](https://github.com/ARPAHLS)) | Removes image backgrounds locally using rembg and returns transparent PNGs. |
| **[Deck Builder](creative/deck_builder.md)** | `creative/deck_builder` | `workflow` | `0.2.0` (16 Sep 2026) | [@tusharjamunkar](https://github.com/tusharjamunkar) ([@ARPAHLS](https://github.com/ARPAHLS)) | Offline PPTX assembly from JSON deck specs — placeholders, lint_deck, suggest_outline, and 13 layouts. |

## Finance
Tools for financial analysis, blockchain interaction, and regulatory compliance.

**Category hub:** [Finance agent skills](finance/README.md).

| Skill | ID | Shape | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[Wallet Screening](finance/wallet_screening.md)** | `finance/wallet_screening` | `workflow` | `2.0.0` (20 Oct 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Comprehensive risk assessment for Ethereum wallets. Checks sanctions lists (OFAC, FBI) and identifies interactions with malicious contracts (Mixers, Scams). Schema v2 verdicts and hop-1 exposure. |
| **[UK Companies House Handler](finance/uk_companies_house_handler.md)** | `finance/uk_companies_house_handler` | `workflow` | `1.4.0` (15 Oct 2026) | [@Areen-09](https://github.com/Areen-09) ([@ARPAHLS](https://github.com/ARPAHLS)) | Deterministic UK Companies House API handler: company search, officers with deterministic role/name filtering, PSC, filing history with helpers, Document API discover/pick/download, and turn-by-turn pipeline orchestration. |

## DeFi
On-chain execution and trading for dedicated agent wallets (structured intent, previews, confirmations).

**Category hub:** [DeFi agent skills](defi/README.md).

**Operator setup (all defi skills):** Configure shared EVM chains and RPC once — [`skillware evm init`](../usage/cli.md#skillware-evm), RPC URLs in `.env`. Guide: [EVM operator config](../usage/evm_operator_config.md).

| Skill | ID | Shape | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[EVM Chain Reader](defi/evm_reader.md)** | `defi/evm_reader` | `atomic` | `0.1.0` (29 Sep 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Read-only EVM state plane — token balances, allowances, view calls, multicall batches, and addressbook resolution. |
| **[EVM Transaction Handler](defi/evm_tx_handler.md)** | `defi/evm_tx_handler` | `workflow` | `0.3.0` | [@Hendobox](https://github.com/Hendobox) ([@ARPAHLS](https://github.com/ARPAHLS)) | Uni V2 quote, preview, execute, and name-based transfer on Ethereum/Base via central address book. |
| **[Token Security Scanner](defi/token_security_scanner.md)** | `defi/token_security_scanner` | `atomic` | `0.2.0` | [@Hendobox](https://github.com/Hendobox) ([@ARPAHLS](https://github.com/ARPAHLS)) | Read-only GoPlus token honeypot/tax/ownership report before agent trades. |

## Optimization
Middleware skills that operate on text or state to increase performance, security, or efficiency.

**Category hub:** [Optimization agent skills](optimization/README.md).

| Skill | ID | Shape | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[Prompt Token Rewriter](optimization/prompt_rewriter.md)** | `optimization/prompt_rewriter` | `middleware` | `0.1.0` (16 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Aggressively compresses massive prompts or context histories while retaining semantic meaning to save tokens. |
| **[Context Window Optimizer](optimization/context_optimizer.md)** | `optimization/context_optimizer` | `middleware` | `0.1.0` (16 Sep 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Query-aware extractive selection — local embeddings score document chunks against agent_goal and return only relevant spans. |

## Data Engineering
Skills tailored for generating, parsing, and orchestrating large datasets for machine learning or analytics workflows.

**Category hub:** [Data Engineering agent skills](data_engineering/README.md).

| Skill | ID | Shape | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[Synthetic Data Generator](data_engineering/synthetic_generator.md)** | `data_engineering/synthetic_generator` | `atomic` | `0.1.1` (9 Sep 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Generates high-entropy structured synthetic data for model fine-tuning to avoid mode collapse. |
| **[Novelty Extractor](data_engineering/novelty_extractor.md)** | `data_engineering/novelty_extractor` | `atomic` | `0.1.0` (16 Jul 2026) | [@rizzoMartin](https://github.com/rizzoMartin) ([@ARPAHLS](https://github.com/ARPAHLS)) | Filters a text dataset by semantic novelty, retaining only chunks that carry new information above a configurable threshold. |
| **[Semantic Web Proxy](data_engineering/semantic_web_proxy.md)** | `data_engineering/semantic_web_proxy` | `atomic` | `0.1.0` (5 Sep 2026) | [@rizzoMartin](https://github.com/rizzoMartin) ([@ARPAHLS](https://github.com/ARPAHLS)) | Converts a live web page or raw HTML into token-efficient Markdown, text, or JSON, stripping boilerplate behind an SSRF guard and reporting estimated token savings. |
| **[Telemetry Normalizer](data_engineering/telemetry_normalizer.md)** | `data_engineering/telemetry_normalizer` | `stream` | `0.1.0` (12 Oct 2026) | [@rin-katsuragi](https://github.com/rin-katsuragi) ([@ARPAHLS](https://github.com/ARPAHLS)) | Normalizes raw sensor telemetry into canonical SI units and W3C SOSA/SSN observations. |

## Compliance
Enforces privacy, guardrails, and secure handling of sensitive data before it reaches external endpoints.

**Category hub:** [Compliance agent skills](compliance/README.md).

| Skill | ID | Shape | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[PII Masker](compliance/pii_masker.md)** | `compliance/pii_masker` | `middleware` | `0.1.0` (20 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | High-precision, local PII (Personally Identifiable Information) detection and redaction using the micro-f1-mask model. |
| **[MiCA Module](compliance/mica_module.md)** | `compliance/mica_module` | `atomic` | `0.1.2` (5 Oct 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Self-contained local Policy Enforcement and RAG engine strictly adhering to MiCA crypto-asset regulation. |
| **[Terms of Service Evaluator](compliance/tos_evaluator.md)** | `compliance/tos_evaluator` | `atomic` | `0.1.1` (9 Sep 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Local-first evaluation of robots.txt and website legal pages to decide whether an intended automated action appears permissible. |

## Security
Offline and local-first defenses for untrusted input before it reaches model context or host agents.

**Category hub:** [Security agent skills](security/README.md).

| Skill | ID | Shape | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[Prompt Injection Firewall](security/prompt_injection_firewall.md)** | `security/prompt_injection_firewall` | `middleware` | `0.2.0` (21 Sep 2026) | [@mrmasa88](https://github.com/mrmasa88) ([@ARPAHLS](https://github.com/ARPAHLS)) | Offline deterministic scan and sanitization for hostile instructions in untrusted text before LLM context. |
| **[Deceptive UI Guard](security/deceptive_ui_guard.md)** | `security/deceptive_ui_guard` | `middleware` | `0.2.0` (3 Sep 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Deterministic HTML surface scan with zone weighting, allowlists, optional render diff, trust scoring, and pre-click agent guidance (#314). |
| **[Deepfake Guard](security/deepfake_guard.md)** | `security/deepfake_guard` | `middleware` | `0.1.0` (6 Oct 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Offline media and KYC document authenticity guard: ICAO 9303 MRZ validation, C2PA provenance, ELA, noise residual variance, and moiré screen recapture detection (#48). |

## Dev Tools
Skills that assist developers in understanding codebases, planning changes, and resolving issues across any repository.

**Category hub:** [Dev Tools agent skills](dev_tools/README.md).

| Skill | ID | Shape | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[Issue Resolver](dev_tools/issue_resolver.md)** | `dev_tools/issue_resolver` | `workflow` | `0.3.0` (3 Aug 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | GitHub issue URL prep, optional caller-fetched repository profiles, nine-stage agent workflow, conditional verify/commit gates, and commit-message validation. |

## Monitoring
Observability and guardrails for long-running autonomous agent loops.

**Category hub:** [Monitoring agent skills](monitoring/README.md).

| Skill | ID | Shape | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[Token Limiter](monitoring/token_limiter.md)** | `monitoring/token_limiter` | `middleware` | `1.0.0` (16 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Deterministic token budget gate that returns CONTINUE, WARN, or FORCE_TERMINATE for host loops. |
| **[KPI Gate](monitoring/kpi_gate.md)** | `monitoring/kpi_gate` | `middleware` | `0.1.0` (29 Aug 2026) | [@mrmasa88](https://github.com/mrmasa88) ([AO](https://github.com/0x-AO-Protocol)) | Deterministic business-KPI gate evaluating a metrics snapshot against a policy charter with fail-closed findings (issue #317). |

## Wellness
Supportive coaching guardrails, crisis triage, and grounded psychoeducation for host agents.

**Category hub:** [Wellness agent skills](wellness/README.md).

| Skill | ID | Shape | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[Mental Coach](wellness/mental_coach.md)** | `wellness/mental_coach` | `atomic` | `0.1.1` (9 Sep 2026) | [@mrmasa88](https://github.com/mrmasa88) ([AO](https://github.com/0x-AO-Protocol)) | Deterministic wellness coaching firewall with crisis triage, scope limits, and cited KB retrieval. |

## Linguistics
Language adapters: curated lexicons so host agents can interpret and produce informal, internet-native language that foundation models routinely miss.

**Category hub:** [Linguistics agent skills](linguistics/README.md).

| Skill | ID | Shape | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[Korean Slang](linguistics/korean_slang.md)** | `linguistics/korean_slang` | `atomic` | `0.1.0` (19 Sep 2026) | [@bd-c3](https://github.com/bd-c3) ([@ARPAHLS](https://github.com/ARPAHLS)) | Offline Korean Gen-Z slang interpreter and peer-register generator (September 2026 pack). |

## Bio
Skills for life sciences, bioinformatics, genomics, and biotechnology.

**Category hub:** [Bio agent skills](bio/README.md).

| Skill | ID | Shape | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **[Sequence Operations](bio/sequence_ops.md)** | `bio/sequence_ops` | `atomic` | `0.1.0` (24 Oct 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Deterministic in-silico operations on DNA, RNA, and protein sequence strings. |

---

## Installing Skills

Registry skills live under `skills/<category>/<skill_name>/` in the repository and in the PyPI package. After `pip install skillware`, load by ID from your project (`./skills/...`), via `SKILLWARE_SKILL_PATH`, or from the bundled registry copy under `site-packages/skills/`. See [Usage guides](../usage/README.md#finding-skills-on-disk).

```python
from skillware.core.loader import SkillLoader

# Load by registry ID (category/skill_name)
bundle = SkillLoader.load_skill("finance/wallet_screening")
skill = bundle["class"]()
# Or: skill = bundle["module"].WalletScreeningSkill()
```

---

See [Usage guides](../usage/README.md) for provider adapters, [Agent loops](../usage/agent_loops.md) for the shared execute pattern and [taxonomy-aware filtering](../usage/agent_loops.md#taxonomy-aware-skill-filtering-and-execution-safety), [CLI documentation](../usage/cli.md#skillware-list) for filtering by taxonomy flags (`--shape`, `--tag`, `--target`, `--category`) and inspecting the taxonomy badge panel with `skillware info`, [Authoring manifests](../contributing/ai_native_workflow.md#authoring-manifests-and-schema) for Manifest v2 specifications, and [Testing](../TESTING.md) for running skill tests before opening a PR.

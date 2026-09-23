# Skill Library

Welcome to the official catalog of Skillware capabilities. New here? Start with the [project README](../../README.md). Each skill page describes its bundle layout; shared role vocabulary is in [Skill anatomy](../introduction.md#skill-anatomy) and the [glossary](../glossary.md).

Browse by category below, or run `skillware list` after `pip install skillware` to see locally available skills. When contributing a new skill, see [Choosing a category](../../CONTRIBUTING.md#choosing-a-category) in CONTRIBUTING.md.

## Office
Skills for document processing, email automation, and productivity.

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[PDF Form Filler](pdf_form_filler.md)** | `office/pdf_form_filler` | `0.1.0` (16 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Fills AcroForm-based PDFs by mapping user instructions to detected form fields using LLM-based semantic understanding. |
| **[Gmail Handler](gmail_handler.md)** | `office/gmail_handler` | `0.2.0` (19 Aug 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Gmail send, search, read, reply, and attachments via IMAP/SMTP with address book, signatures, and confirmation gates. |

## Creative
Skills for image processing, media editing, and creative utilities.

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Background Remover](bg_remover.md)** | `creative/bg_remover` | `0.2.0` (2 Aug 2026) | [@AyushSrivastava1818](https://github.com/AyushSrivastava1818) ([@ARPAHLS](https://github.com/ARPAHLS)) | Removes image backgrounds locally using rembg and returns transparent PNGs. |
| **[Deck Builder](deck_builder.md)** | `creative/deck_builder` | `0.2.0` (16 Sep 2026) | [@tusharjamunkar](https://github.com/tusharjamunkar) ([@ARPAHLS](https://github.com/ARPAHLS)) | Offline PPTX assembly from JSON deck specs — placeholders, lint_deck, suggest_outline, and 13 layouts. |

## Finance
Tools for financial analysis, blockchain interaction, and regulatory compliance.

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Wallet Screening](wallet_screening.md)** | `finance/wallet_screening` | `1.0.1` (23 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Comprehensive risk assessment for Ethereum wallets. Checks sanctions lists (OFAC, FBI) and identifies interactions with malicious contracts (Mixers, Scams). |
| **[UK Companies House Handler](uk_companies_house_handler.md)** | `finance/uk_companies_house_handler` | `1.3.0` (17 Sep 2026) | [@Areen-09](https://github.com/Areen-09) ([@ARPAHLS](https://github.com/ARPAHLS)) | Deterministic UK Companies House API handler: company search, officers with deterministic role/name filtering, PSC, filing history with helpers, and turn-by-turn pipeline orchestration. |

## DeFi
On-chain execution and trading for dedicated agent wallets (structured intent, previews, confirmations).

**Operator setup (all defi skills):** Configure shared EVM chains and RPC once — [`skillware evm init`](../usage/cli.md#skillware-evm), RPC URLs in `.env`. Guide: [EVM operator config](../usage/evm_operator_config.md).

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[EVM Transaction Handler](evm_tx_handler.md)** | `defi/evm_tx_handler` | `0.3.0` | [@Hendobox](https://github.com/Hendobox) ([@ARPAHLS](https://github.com/ARPAHLS)) | Uni V2 quote, preview, execute, and name-based transfer on Ethereum/Base via central address book. |

## Optimization
Middleware skills that operate on text or state to increase performance, security, or efficiency.

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Prompt Token Rewriter](prompt_rewriter.md)** | `optimization/prompt_rewriter` | `0.1.0` (16 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Aggressively compresses massive prompts or context histories while retaining semantic meaning to save tokens. |
| **[Context Window Optimizer](context_optimizer.md)** | `optimization/context_optimizer` | `0.1.0` (16 Sep 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Query-aware extractive selection — local embeddings score document chunks against agent_goal and return only relevant spans. |

## Data Engineering
Skills tailored for generating, parsing, and orchestrating large datasets for machine learning or analytics workflows.

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Synthetic Data Generator](synthetic_generator.md)** | `data_engineering/synthetic_generator` | `0.1.1` (9 Sep 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Generates high-entropy structured synthetic data for model fine-tuning to avoid mode collapse. |
| **[Novelty Extractor](novelty_extractor.md)** | `data_engineering/novelty_extractor` | `0.1.0` (16 Jul 2026) | [@rizzoMartin](https://github.com/rizzoMartin) ([@ARPAHLS](https://github.com/ARPAHLS)) | Filters a text dataset by semantic novelty, retaining only chunks that carry new information above a configurable threshold. |
| **[Semantic Web Proxy](semantic_web_proxy.md)** | `data_engineering/semantic_web_proxy` | `0.1.0` (5 Sep 2026) | [@rizzoMartin](https://github.com/rizzoMartin) ([@ARPAHLS](https://github.com/ARPAHLS)) | Converts a live web page or raw HTML into token-efficient Markdown, text, or JSON, stripping boilerplate behind an SSRF guard and reporting estimated token savings. |

## Compliance
Enforces privacy, guardrails, and secure handling of sensitive data before it reaches external endpoints.

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[PII Masker](pii_masker.md)** | `compliance/pii_masker` | `0.1.0` (20 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | High-precision, local PII (Personally Identifiable Information) detection and redaction using the micro-f1-mask model. |
| **[MiCA Module](mica_module.md)** | `compliance/mica_module` | `0.1.1` (9 Sep 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Self-contained local Policy Enforcement and RAG engine strictly adhering to MiCA crypto-asset regulation. |
| **[Terms of Service Evaluator](tos_evaluator.md)** | `compliance/tos_evaluator` | `0.1.1` (9 Sep 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Local-first evaluation of robots.txt and website legal pages to decide whether an intended automated action appears permissible. |

## Security
Offline and local-first defenses for untrusted input before it reaches model context or host agents.

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Prompt Injection Firewall](prompt_injection_firewall.md)** | `security/prompt_injection_firewall` | `0.2.0` (21 Sep 2026) | [@mrmasa88](https://github.com/mrmasa88) ([@ARPAHLS](https://github.com/ARPAHLS), [AO](https://github.com/0x-AO-Protocol)) | Offline deterministic scan and sanitization for hostile instructions in untrusted text before LLM context. |
| **[Deceptive UI Guard](deceptive_ui_guard.md)** | `security/deceptive_ui_guard` | `0.2.0` (3 Sep 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Deterministic HTML surface scan with zone weighting, allowlists, optional render diff, trust scoring, and pre-click agent guidance (#314). |

## Dev Tools
Skills that assist developers in understanding codebases, planning changes, and resolving issues across any repository.

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Issue Resolver](issue_resolver.md)** | `dev_tools/issue_resolver` | `0.3.0` (3 Aug 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | GitHub issue URL prep, optional caller-fetched repository profiles, nine-stage agent workflow, conditional verify/commit gates, and commit-message validation. |

## Monitoring
Observability and guardrails for long-running autonomous agent loops.

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Token Limiter](token_limiter.md)** | `monitoring/token_limiter` | `1.0.0` (16 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Deterministic token budget gate that returns CONTINUE, WARN, or FORCE_TERMINATE for host loops. |
| **[KPI Gate](kpi_gate.md)** | `monitoring/kpi_gate` | `0.1.0` (29 Aug 2026) | [@mrmasa88](https://github.com/mrmasa88) ([AO](https://github.com/0x-AO-Protocol)) | Deterministic business-KPI gate evaluating a metrics snapshot against a policy charter with fail-closed findings (issue #317). |

## Wellness
Supportive coaching guardrails, crisis triage, and grounded psychoeducation for host agents.

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Mental Coach](mental_coach.md)** | `wellness/mental_coach` | `0.1.1` (9 Sep 2026) | [@mrmasa88](https://github.com/mrmasa88) ([AO](https://github.com/0x-AO-Protocol)) | Deterministic wellness coaching firewall with crisis triage, scope limits, and cited KB retrieval. |

## Linguistics
Language adapters: curated lexicons so host agents can interpret and produce informal, internet-native language that foundation models routinely miss.

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Korean Slang](korean_slang.md)** | `linguistics/korean_slang` | `0.1.0` (19 Sep 2026) | [@bd-c3](https://github.com/bd-c3) ([@ARPAHLS](https://github.com/ARPAHLS)) | Offline Korean Gen-Z slang interpreter and peer-register generator (September 2026 pack). |

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

See [Usage guides](../usage/README.md) for provider adapters, [Agent loops](../usage/agent_loops.md) for the shared execute pattern, and [Testing](../TESTING.md) for running skill tests before opening a PR.

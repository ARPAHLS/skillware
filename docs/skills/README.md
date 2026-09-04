# Skill Library

Welcome to the official catalog of Skillware capabilities. New here? Start with the [project README](../../README.md). Each skill page describes its bundle layout; shared role vocabulary is in [Skill anatomy](../introduction.md#skill-anatomy).

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
| **[Deck Builder](deck_builder.md)** | `creative/deck_builder` | `0.1.0` (3 Sep 2026) | [@tusharjamunkar](https://github.com/tusharjamunkar) ([@ARPAHLS](https://github.com/ARPAHLS)) | Deterministic PowerPoint (.pptx) presentation assembly from structured JSON deck specs. |

## Finance
Tools for financial analysis, blockchain interaction, and regulatory compliance.

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Wallet Screening](wallet_screening.md)** | `finance/wallet_screening` | `1.0.1` (23 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Comprehensive risk assessment for Ethereum wallets. Checks sanctions lists (OFAC, FBI) and identifies interactions with malicious contracts (Mixers, Scams). |
| **[UK Companies House Handler](uk_companies_house_handler.md)** | `finance/uk_companies_house_handler` | `1.2.0` (24 Aug 2026) | [@Areen-09](https://github.com/Areen-09) ([@ARPAHLS](https://github.com/ARPAHLS)) | Deterministic UK Companies House API handler: company search, officers, PSC, filing history, pipeline orchestration, and UK corporate terminology translation via structured actions. |

## DeFi
On-chain execution and trading for dedicated agent wallets (structured intent, previews, confirmations).

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[EVM Transaction Handler](evm_tx_handler.md)** | `defi/evm_tx_handler` | `0.2.0` (16 Jul 2026) | [@Hendobox](https://github.com/Hendobox) | Uni V2 quote, preview, execute, and transfer on Ethereum/Base from structured intent. |

## Optimization
Middleware skills that operate on text or state to increase performance, security, or efficiency.

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Prompt Token Rewriter](prompt_rewriter.md)** | `optimization/prompt_rewriter` | `0.1.0` (16 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Aggressively compresses massive prompts or context histories while retaining semantic meaning to save tokens. |

## Data Engineering
Skills tailored for generating, parsing, and orchestrating large datasets for machine learning or analytics workflows.

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Synthetic Data Generator](synthetic_generator.md)** | `data_engineering/synthetic_generator` | `0.1.0` (16 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Generates high-entropy structured synthetic data for model fine-tuning to avoid mode collapse. |
| **[Novelty Extractor](novelty_extractor.md)** | `data_engineering/novelty_extractor` | `0.1.0` (16 Jul 2026) | [@rizzoMartin](https://github.com/rizzoMartin) ([@ARPAHLS](https://github.com/ARPAHLS)) | Filters a text dataset by semantic novelty, retaining only chunks that carry new information above a configurable threshold. |

## Compliance
Enforces privacy, guardrails, and secure handling of sensitive data before it reaches external endpoints.

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[PII Masker](pii_masker.md)** | `compliance/pii_masker` | `0.1.0` (20 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | High-precision, local PII (Personally Identifiable Information) detection and redaction using the micro-f1-mask model. |
| **[MiCA Module](mica_module.md)** | `compliance/mica_module` | `0.1.0` (20 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Self-contained local Policy Enforcement and RAG engine strictly adhering to MiCA crypto-asset regulation. |
| **[Terms of Service Evaluator](tos_evaluator.md)** | `compliance/tos_evaluator` | `0.1.0` (16 Jul 2026) | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Local-first evaluation of robots.txt and website legal pages to decide whether an intended automated action appears permissible. |

## Security
Offline and local-first defenses for untrusted input before it reaches model context or host agents.

| Skill | ID | Version | Issuer | Description |
| :--- | :--- | :--- | :--- | :--- |
| **[Prompt Injection Firewall](prompt_injection_firewall.md)** | `security/prompt_injection_firewall` | `0.1.0` (31 Jul 2026) | [@mrmasa88](https://github.com/mrmasa88) ([@ARPAHLS](https://github.com/ARPAHLS), [AO](https://github.com/0x-AO-Protocol)) | Offline deterministic scan and sanitization for hostile instructions in untrusted text before LLM context. |
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
| **[Mental Coach](mental_coach.md)** | `wellness/mental_coach` | `0.1.0` (16 Jul 2026) | [@mrmasa88](https://github.com/mrmasa88) ([AO](https://github.com/0x-AO-Protocol)) | Deterministic wellness coaching firewall with crisis triage, scope limits, and cited KB retrieval. |

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

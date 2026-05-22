# Skill Library

Welcome to the official catalog of Skillware capabilities.

## Office
Skills for document processing, email automation, and productivity.

| Skill | ID | Issuer | Description |
| :--- | :--- | :--- | :--- |
| **[PDF Form Filler](pdf_form_filler.md)** | `office/pdf_form_filler` | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Fills AcroForm-based PDFs by mapping user instructions to detected form fields using LLM-based semantic understanding. |

## Finance
Tools for financial analysis, blockchain interaction, and regulatory compliance.

| Skill | ID | Issuer | Description |
| :--- | :--- | :--- | :--- |
| **[Wallet Screening](wallet_screening.md)** | `finance/wallet_screening` | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Comprehensive risk assessment for Ethereum wallets. Checks sanctions lists (OFAC, FBI) and identifies interactions with malicious contracts (Mixers, Scams). |


## Optimization
Middleware skills that operate on text or state to increase performance, security, or efficiency.

| Skill | ID | Issuer | Description |
| :--- | :--- | :--- | :--- |
| **[Prompt Token Rewriter](prompt_rewriter.md)** | `optimization/prompt_rewriter` | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Aggressively compresses massive prompts or context histories while retaining semantic meaning to save tokens. |

## Data Engineering
Skills tailored for generating, parsing, and orchestrating large datasets for machine learning or analytics workflows.

| Skill | ID | Issuer | Description |
| :--- | :--- | :--- | :--- |
| **[Synthetic Data Generator](synthetic_generator.md)** | `data_engineering/synthetic_generator` | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Generates high-entropy structured synthetic data for model fine-tuning to avoid mode collapse. |

## Compliance
Enforces privacy, guardrails, and secure handling of sensitive data before it reaches external endpoints.

| Skill | ID | Issuer | Description |
| :--- | :--- | :--- | :--- |
| **[PII Masker](pii_masker.md)** | `compliance/pii_masker` | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | High-precision, local PII (Personally Identifiable Information) detection and redaction using the micro-f1-mask model. |
| **[MiCA Module](mica_module.md)** | `compliance/mica_module` | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Self-contained local Policy Enforcement and RAG engine strictly adhering to MiCA crypto-asset regulation. |
| **[Terms of Service Evaluator](tos_evaluator.md)** | `compliance/tos_evaluator` | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Local-first evaluation of robots.txt and website legal pages to decide whether an intended automated action appears permissible. |

## Dev Tools
Skills that assist developers in understanding codebases, planning changes, and resolving issues across any repository.

| Skill | ID | Issuer | Description |
| :--- | :--- | :--- | :--- |
| **[Issue Resolver](issue_resolver.md)** | `dev_tools/issue_resolver` | [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS)) | Analyzes any GitHub issue against its target repository and produces a structured resolution plan with ranked implementation options, affected files, and caveats. |

---

## Installing Skills

Registry skills live under `skills/<category>/<skill_name>/` in the repository and in the PyPI package. After `pip install skillware`, load by ID from your project (`./skills/...`), via `SKILLWARE_SKILL_PATH`, or from the bundled registry copy under `site-packages/skills/`. See [Usage guides](../usage/README.md#finding-skills-on-disk).

```python
from skillware.core.loader import SkillLoader

# Load by registry ID (category/skill_name)
skill = SkillLoader.load_skill("finance/wallet_screening")
```

---

See [Usage guides](../usage/README.md) for provider adapters, [Agent loops](../usage/agent_loops.md) for the shared execute pattern, and [Testing](../TESTING.md) for running skill tests before opening a PR.

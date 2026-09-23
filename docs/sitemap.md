# Documentation sitemap

Flat crawl map for Skillware documentation. Category hubs and skill catalog pages
are one hop from this file; runtime bundles stay under `skills/<category>/<skill_name>/`
with unchanged `SkillLoader.load_skill("<category>/<skill_name>")` IDs.

[Project README](../README.md) · [Skill library](skills/README.md) · [Glossary](glossary.md)

## Guides

- [Introduction](introduction.md)
- [Vision](vision.md)
- [Glossary](glossary.md)
- [Testing](TESTING.md)
- [Contributing](../CONTRIBUTING.md)
- [Agent-native workflow](contributing/ai_native_workflow.md)
- [Usage guides](usage/README.md)
- [Agent loops](usage/agent_loops.md)
- [Skill chaining](usage/skill_chaining.md)
- [Install extras](usage/install_extras.md)
- [API keys](usage/api_keys.md)
- [CLI](usage/cli.md)
- [Skill trust model](security/skill-trust-model.md)
- [Examples index](../examples/README.md)

## Skill category hubs

### Compliance

- [Compliance hub](skills/compliance/README.md)
- [`compliance/mica_module`](skills/compliance/mica_module.md)
- [`compliance/pii_masker`](skills/compliance/pii_masker.md)
- [`compliance/tos_evaluator`](skills/compliance/tos_evaluator.md)

### Creative

- [Creative hub](skills/creative/README.md)
- [`creative/bg_remover`](skills/creative/bg_remover.md)
- [`creative/deck_builder`](skills/creative/deck_builder.md)

### Data Engineering

- [Data Engineering hub](skills/data_engineering/README.md)
- [`data_engineering/novelty_extractor`](skills/data_engineering/novelty_extractor.md)
- [`data_engineering/semantic_web_proxy`](skills/data_engineering/semantic_web_proxy.md)
- [`data_engineering/synthetic_generator`](skills/data_engineering/synthetic_generator.md)

### DeFi

- [DeFi hub](skills/defi/README.md)
- [`defi/evm_tx_handler`](skills/defi/evm_tx_handler.md)
- [`defi/token_security_scanner`](skills/defi/token_security_scanner.md)

### Dev Tools

- [Dev Tools hub](skills/dev_tools/README.md)
- [`dev_tools/issue_resolver`](skills/dev_tools/issue_resolver.md)

### Finance

- [Finance hub](skills/finance/README.md)
- [`finance/uk_companies_house_handler`](skills/finance/uk_companies_house_handler.md)
- [`finance/wallet_screening`](skills/finance/wallet_screening.md)

### Linguistics

- [Linguistics hub](skills/linguistics/README.md)
- [`linguistics/korean_slang`](skills/linguistics/korean_slang.md)

### Monitoring

- [Monitoring hub](skills/monitoring/README.md)
- [`monitoring/kpi_gate`](skills/monitoring/kpi_gate.md)
- [`monitoring/token_limiter`](skills/monitoring/token_limiter.md)

### Office

- [Office hub](skills/office/README.md)
- [`office/gmail_handler`](skills/office/gmail_handler.md)
- [`office/pdf_form_filler`](skills/office/pdf_form_filler.md)

### Optimization

- [Optimization hub](skills/optimization/README.md)
- [`optimization/context_optimizer`](skills/optimization/context_optimizer.md)
- [`optimization/prompt_rewriter`](skills/optimization/prompt_rewriter.md)

### Security

- [Security hub](skills/security/README.md)
- [`security/deceptive_ui_guard`](skills/security/deceptive_ui_guard.md)
- [`security/prompt_injection_firewall`](skills/security/prompt_injection_firewall.md)

### Wellness

- [Wellness hub](skills/wellness/README.md)
- [`wellness/mental_coach`](skills/wellness/mental_coach.md)

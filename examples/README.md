# Skillware Examples Index

> **These are usage examples, not tests.** Runnable provider demos live here; automated tests live in `skills/**/test_skill.py` (bundle) and `tests/` (framework and optional maintainer depth). See [TESTING.md](../docs/TESTING.md).

Runnable examples in this directory show how to load Skillware skills, adapt
them for a provider, execute local skill logic, and return tool results to an
agent loop. After `pip install skillware`, run `skillware examples` or
`skillware list --examples` from any directory to browse the index in the
terminal; when no local `examples/README.md` is present, the index is fetched
from GitHub (network required); see
[CLI reference](../docs/usage/cli.md). Provider setup details live in the usage guides:

- [API keys for skills](../docs/usage/api_keys.md)
- [Gemini](../docs/usage/gemini.md)
- [Claude](../docs/usage/claude.md)
- [OpenAI](../docs/usage/openai.md)
- [DeepSeek](../docs/usage/deepseek.md)
- [Ollama](../docs/usage/ollama.md)
- [Install extras](../docs/usage/install_extras.md)
- [Agent loops](../docs/usage/agent_loops.md)

Install the **skill extra** for each script (see [Install extras](../docs/usage/install_extras.md)), plus an **SDK extra** when the provider column is not local execute:

```bash
pip install "skillware[office_pdf_form_filler]" "skillware[gemini]"
```

For local development with every skill and SDK:

```bash
pip install -e ".[dev,all,agents]"
```

## Runnable Scripts

| Script | Skill ID | Provider | Required extra | Required env vars | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `mental_coach_demo.py` | `wellness/mental_coach` | Local execute | `[wellness_mental_coach]` | None | Demonstrates coaching, crisis escalation, and blocked clinical paths locally. |
| `build_dataset_demo.py` | `data_engineering/synthetic_generator` | Local execute (Gemini backend) | `[data_engineering_synthetic_generator]`, `[gemini]` | `GOOGLE_API_KEY` | Generates a JSONL synthetic dataset with the synthetic generator skill. |
| `claude_pdf_form_filler.py` | `office/pdf_form_filler` | Claude | `[office_pdf_form_filler]`, `[claude]` | `ANTHROPIC_API_KEY` | Uses Claude with the PDF form filler skill to map instructions to fields. |
| `claude_tos_evaluator.py` | `compliance/tos_evaluator` | Claude | `[compliance_tos_evaluator]`, `[claude]` | `ANTHROPIC_API_KEY` | Runs a Claude tool loop for website automation policy review. |
| `claude_issue_resolver.py` | `dev_tools/issue_resolver` | Claude | `[dev_tools_issue_resolver]`, `[claude]` | `ANTHROPIC_API_KEY`; optional `GITHUB_TOKEN` | Claude loop for GitHub issue analysis; fetches issue data after `prepare` (sample: issue #123). |
| `claude_wallet_check.py` | `finance/wallet_screening` | Claude | `[finance_wallet_screening]`, `[claude]` | `ANTHROPIC_API_KEY`, `ETHERSCAN_API_KEY` | Screens an Ethereum wallet and returns the result through a Claude tool loop. |
| `deepseek_tos_evaluator.py` | `compliance/tos_evaluator` | DeepSeek | `[compliance_tos_evaluator]`, `[openai]` | `DEEPSEEK_API_KEY` | Uses the OpenAI-compatible DeepSeek API for terms-of-service evaluation. |
| `gemini_pdf_form_filler.py` | `office/pdf_form_filler` | Gemini | `[office_pdf_form_filler]`, `[gemini]` | `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY` | Uses Gemini as the agent while the PDF skill calls Anthropic for form filling. |
| `gemini_tos_evaluator.py` | `compliance/tos_evaluator` | Gemini | `[compliance_tos_evaluator]`, `[gemini]` | `GOOGLE_API_KEY` | Runs the terms-of-service evaluator with a Gemini function-calling loop. |
| `gemini_wallet_check.py` | `finance/wallet_screening` | Gemini | `[finance_wallet_screening]`, `[gemini]` | `GOOGLE_API_KEY`, `ETHERSCAN_API_KEY` | Screens an Ethereum wallet with Gemini orchestration and Etherscan data. |
| `gemini_evm_tx_handler.py` | `defi/evm_tx_handler` | Gemini | `[defi_evm_tx_handler]`, `[gemini]` | `GOOGLE_API_KEY`; for live swaps also `AGENT_WALLET_PRIVATE_KEY`, `BASE_RPC_URL` or `ETHEREUM_RPC_URL`. Set `EVM_TX_HANDLER_EXAMPLE_DEMO=1` for mocked flow without keys. | Resolve → quote → preview → execute buy flow via Gemini tool loop (or demo mode). |
| `claude_evm_tx_handler.py` | `defi/evm_tx_handler` | Claude | `[defi_evm_tx_handler]`, `[claude]` | `ANTHROPIC_API_KEY`; for live swaps also `AGENT_WALLET_PRIVATE_KEY`, RPC URLs. Demo: `EVM_TX_HANDLER_EXAMPLE_DEMO=1`. | Claude tool loop for structured DeFi intent and optional execute after confirmation. |
| `mica_claude_flow.py` | `compliance/mica_module` | Claude | `[compliance_mica_module]`, `[claude]` | `ANTHROPIC_API_KEY` | Runs a MiCA compliance agent loop through Claude. |
| `mica_ollama_flow.py` | `compliance/mica_module` | Ollama | `[compliance_mica_module]`; install `ollama` separately | None | Runs a local Ollama MiCA flow with prompt-mode tool calling. |
| `mica_rag_flow.py` | `compliance/mica_module` | Gemini | `[compliance_mica_module]`, `[gemini]` | `GOOGLE_API_KEY` | Runs the MiCA RAG flow with Gemini. |
| `ollama_skills_test.py` | `finance/wallet_screening`, `office/pdf_form_filler`, `optimization/prompt_rewriter` | Ollama | `[finance_wallet_screening]`, `[office_pdf_form_filler]`, `[optimization_prompt_rewriter]`; install `ollama` separately | `ETHERSCAN_API_KEY`, `ANTHROPIC_API_KEY` | Loads multiple skills and tests prompt-mode tool calling with Ollama. |
| `ollama_tos_evaluator.py` | `compliance/tos_evaluator` | Ollama | `[compliance_tos_evaluator]`; install `ollama` separately | None | Runs the terms-of-service evaluator with local Ollama prompt-mode calls. |
| `openai_tos_evaluator.py` | `compliance/tos_evaluator` | OpenAI | `[compliance_tos_evaluator]`, `[openai]` | `OPENAI_API_KEY` | Runs the terms-of-service evaluator with OpenAI function calling. |
| `pii_guardrail_flow.py` | `compliance/pii_masker` | Local execute | `[compliance_pii_masker]` | None | Demonstrates local PII masking before passing text to an external agent. |
| `prompt_compression_demo.py` | `optimization/prompt_rewriter` | Local execute | `[optimization_prompt_rewriter]` | None | Demonstrates prompt compression without a provider loop. |
| `novelty_extractor_demo.py` | `data_engineering/novelty_extractor` | Local execute | `[data_engineering_novelty_extractor]` | None | Demonstrates multi-turn corpus distillation using local embeddings with no API key. |
| `gemini_novelty_extractor.py` | `data_engineering/novelty_extractor` | Gemini | `[data_engineering_novelty_extractor]`, `[gemini]` | `GOOGLE_API_KEY` | Runs the novelty extractor with a Gemini function-calling loop. |
| `ollama_novelty_extractor.py` | `data_engineering/novelty_extractor` | Ollama | `[data_engineering_novelty_extractor]`; install `ollama` separately | None | Runs the novelty extractor with local Ollama prompt-mode calls. |
| `gemini_issue_resolver.py` | `dev_tools/issue_resolver` | Gemini | `[dev_tools_issue_resolver]`, `[gemini]` | `GOOGLE_API_KEY`; optional `GITHUB_TOKEN` | Gemini loop for GitHub issue analysis; fetches issue data after `prepare` (sample: issue #123). |
| `ollama_issue_resolver.py` | `dev_tools/issue_resolver` | Ollama | `[dev_tools_issue_resolver]`; install `ollama` separately | optional `GITHUB_TOKEN`; `OLLAMA_MODEL` (default `gemma4:e2b`) | Ollama prompt-mode loop for GitHub issue analysis (sample: issue #123). |
| `token_limiter_loop.py` | `monitoring/token_limiter` | Local execute | `[monitoring_token_limiter]` | None | Simulates a runaway task hitting a token ceiling with deterministic budget checks. |
| `gemini_token_limiter.py` | `monitoring/token_limiter` | Gemini | `[monitoring_token_limiter]`, `[gemini]` | Optional `GOOGLE_API_KEY` for Phase 2 live loop | Local budget simulation plus optional Gemini tool loop. |
| `claude_token_limiter.py` | `monitoring/token_limiter` | Claude | `[monitoring_token_limiter]`, `[claude]` | Optional `ANTHROPIC_API_KEY` for Phase 2 live loop | Local budget simulation plus optional Claude tool loop. |
| `gemini_uk_companies_house_handler.py` | `finance/uk_companies_house_handler` | Gemini | `[finance_uk_companies_house_handler]`, `[gemini]` | `GOOGLE_API_KEY`, `COMPANIES_HOUSE_API_KEY` | Resolve company, officers, filings via Gemini tool loop. |
| `uk_companies_house_handler_demo.py` | `finance/uk_companies_house_handler` | Local execute | `[finance_uk_companies_house_handler]` | None | Runs a scripted sequence (resolve, profile, officers, pscs, filings) with mocked HTTP responses (no API keys needed). |

## Notes

- **Skill extras** are listed per script above. Empty extras (`[]` in `pyproject.toml`) still install core + skillware; use them so docs stay stable when a skill gains new runtime deps.
- Agent-side model keys such as `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, and `DEEPSEEK_API_KEY` are documented in the provider
  guides.
- Skill runtime keys such as `ETHERSCAN_API_KEY` are documented in each skill
  manifest and on the skill catalog pages.
- Ollama examples require the Python `ollama` package, a local Ollama server,
  and the model named in the script, but no cloud API key.

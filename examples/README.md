# Skillware Examples Index

Runnable examples in this directory show how to load Skillware skills, adapt
them for a provider, execute local skill logic, and return tool results to an
agent loop. Provider setup details live in the usage guides:

- [API keys for skills](../docs/usage/api_keys.md)
- [Gemini](../docs/usage/gemini.md)
- [Claude](../docs/usage/claude.md)
- [OpenAI](../docs/usage/openai.md)
- [DeepSeek](../docs/usage/deepseek.md)
- [Ollama](../docs/usage/ollama.md)
- [Agent loops](../docs/usage/agent_loops.md)

Use the package extra shown below when installing from PyPI:
`pip install "skillware[gemini]"`. For local development, use the same extra
with editable install: `pip install -e ".[gemini]"`.

## Runnable Scripts

| Script | Skill ID | Provider | Required extra | Required env vars | Description |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `build_dataset_demo.py` | `data_engineering/synthetic_generator` | Local execute (Gemini backend) | `[gemini]` | `GOOGLE_API_KEY` | Generates a JSONL synthetic dataset with the synthetic generator skill. |
| `claude_pdf_form_filler.py` | `office/pdf_form_filler` | Claude | `[claude]`, `[office]` | `ANTHROPIC_API_KEY` | Uses Claude with the PDF form filler skill to map instructions to fields. |
| `claude_tos_evaluator.py` | `compliance/tos_evaluator` | Claude | `[claude]` | `ANTHROPIC_API_KEY` | Runs a Claude tool loop for website automation policy review. |
| `claude_wallet_check.py` | `finance/wallet_screening` | Claude | `[claude]` | `ANTHROPIC_API_KEY`, `ETHERSCAN_API_KEY` | Screens an Ethereum wallet and returns the result through a Claude tool loop. |
| `deepseek_tos_evaluator.py` | `compliance/tos_evaluator` | DeepSeek | `[openai]` | `DEEPSEEK_API_KEY` | Uses the OpenAI-compatible DeepSeek API for terms-of-service evaluation. |
| `gemini_pdf_form_filler.py` | `office/pdf_form_filler` | Gemini | `[gemini]`, `[office]` | `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY` | Uses Gemini as the agent while the PDF skill calls Anthropic for form filling. |
| `gemini_tos_evaluator.py` | `compliance/tos_evaluator` | Gemini | `[gemini]` | `GOOGLE_API_KEY` | Runs the terms-of-service evaluator with a Gemini function-calling loop. |
| `gemini_wallet_check.py` | `finance/wallet_screening` | Gemini | `[gemini]` | `GOOGLE_API_KEY`, `ETHERSCAN_API_KEY` | Screens an Ethereum wallet with Gemini orchestration and Etherscan data. |
| `mica_claude_flow.py` | `compliance/mica_module` | Claude | `[claude]` | `ANTHROPIC_API_KEY` | Runs a MiCA compliance agent loop through Claude. |
| `mica_ollama_flow.py` | `compliance/mica_module` | Ollama | No Skillware extra; install `ollama` separately | None | Runs a local Ollama MiCA flow with prompt-mode tool calling. |
| `mica_rag_flow.py` | `compliance/mica_module` | Gemini | `[gemini]` | `GOOGLE_API_KEY` | Runs the MiCA RAG flow with Gemini. |
| `ollama_skills_test.py` | `finance/wallet_screening`, `office/pdf_form_filler`, `optimization/prompt_rewriter` | Ollama | `[office]`; install `ollama` separately | `ETHERSCAN_API_KEY`, `ANTHROPIC_API_KEY` | Loads multiple skills and tests prompt-mode tool calling with Ollama. |
| `ollama_tos_evaluator.py` | `compliance/tos_evaluator` | Ollama | No Skillware extra; install `ollama` separately | None | Runs the terms-of-service evaluator with local Ollama prompt-mode calls. |
| `openai_tos_evaluator.py` | `compliance/tos_evaluator` | OpenAI | `[openai]` | `OPENAI_API_KEY` | Runs the terms-of-service evaluator with OpenAI function calling. |
| `pii_guardrail_flow.py` | `compliance/pii_masker` | Local execute | base install only | None | Demonstrates local PII masking before passing text to an external agent. |
| `prompt_compression_demo.py` | `optimization/prompt_rewriter` | Local execute | base install only | None | Demonstrates prompt compression without a provider loop. |
| `novelty_extractor_demo.py` | `data_engineering/novelty_extractor` | Local execute | `pip install fastembed numpy` | None | Demonstrates multi-turn corpus distillation using local embeddings with no API key. |
| `gemini_novelty_extractor.py` | `data_engineering/novelty_extractor` | Gemini | `[gemini]`, `pip install fastembed numpy` | `GOOGLE_API_KEY` | Runs the novelty extractor with a Gemini function-calling loop. |
| `ollama_novelty_extractor.py` | `data_engineering/novelty_extractor` | Ollama | `pip install fastembed numpy`; install `ollama` separately | None | Runs the novelty extractor with local Ollama prompt-mode calls. |

## Skills Without Runnable Examples

The catalog also includes skills that do not yet have a dedicated runnable
script under `examples/`:

| Skill ID | Status |
| :--- | :--- |
| `dev_tools/issue_resolver` | No runnable example yet. The skill has `skills/dev_tools/issue_resolver/test_skill.py`, but no provider or local workflow script in `examples/`. |

## Notes

- Agent-side model keys such as `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`, and `DEEPSEEK_API_KEY` are documented in the provider
  guides.
- Skill runtime keys such as `ETHERSCAN_API_KEY` are documented in each skill
  manifest and on the skill catalog pages.
- Ollama examples require the Python `ollama` package, a local Ollama server,
  and the model named in the script, but no cloud API key.

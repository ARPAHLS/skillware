# Enterprise cloud usage

Skillware is plain Python — it runs anywhere you can `pip install skillware` (laptop, EC2, GCE, AKS, Cloud Run, on-prem VM). **Where the framework runs** and **which LLM API your agent calls** are separate choices.

## Two layers

| Layer | Question | Skillware answer |
| :--- | :--- | :--- |
| **Host** | Where does my agent process run? | Any Python 3.10+ environment. Install once, load skills, call `execute()`. |
| **Model API** | Which endpoint does the loop call for inference? | Pick the adapter that matches the wire format (see below). |

Skill **runtime keys** (Etherscan, Companies House, Gmail, etc.) stay on the skill manifest's `env_vars`. Inject them via a [secret provider](api_keys.md#secret-managers) (`SkillLoader.resolve_env_vars`, `SkillContext(secret_provider=...)`) rather than relying on process-global `os.environ` in production. **Cloud IAM** covers the model client (Bedrock role, Azure credential, Vertex ADC) — not skill API keys.

## Choose the adapter

| Situation | Adapter | Guide |
| :--- | :--- | :--- |
| AWS Bedrock **Converse** API | `to_bedrock_tool()` | [bedrock.md](bedrock.md) |
| Azure OpenAI deployment | `to_openai_tool()` | [azure_openai.md](azure_openai.md) |
| Google Vertex AI (Gemini) | `to_gemini_tool()` | [vertex.md](vertex.md) |
| Direct Gemini / Claude / OpenAI / DeepSeek API | Provider-specific `to_*_tool()` | [Usage index](README.md) |
| OpenAI-compatible gateway (Groq, vLLM, LiteLLM, …) | `to_openai_tool()` | [openai_compatible.md](openai_compatible.md) |
| Local Ollama without native tools | `to_ollama_prompt()` | [ollama.md](ollama.md) |

Do **not** add a new adapter per cloud vendor when the schema is already covered — document the routing instead.

## Quick start on a cloud VM

Same steps on AWS EC2, Google Compute Engine, or Azure VM:

```bash
pip install skillware
pip install "skillware[<category>_<skill>]"   # skill runtime deps
pip install "skillware[bedrock]"              # or [gemini], [openai], …
skillware list
```

Configure:

1. **Model credentials** — IAM role (Bedrock), service principal (Azure), or ADC (Vertex).
2. **Skill credentials** — `.env` / secret manager for keys listed on each skill catalog page.

Run your agent loop (see provider guide). Skills and `execute()` behave the same as on a laptop.

## Provider guides

- [AWS Bedrock Converse](bedrock.md)
- [Azure OpenAI](azure_openai.md)
- [Vertex AI (Gemini)](vertex.md)
- [OpenAI-compatible hosts](openai_compatible.md)

## Related

- [Usage guide index](README.md)
- [API keys for skills](api_keys.md)
- [Agent loops](agent_loops.md)
- [Skill chaining](skill_chaining.md)
- [Install extras](install_extras.md)

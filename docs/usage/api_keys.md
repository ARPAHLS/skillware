# API Keys for Skills

Many Skillware skills call external services (block explorers, model APIs, and similar). Those skills read credentials from **environment variables** with fixed names declared in each skill's `manifest.yaml` under `env_vars`. This page explains how to configure keys safely. It does not list every skill in the registry; each [skill documentation page](../skills/README.md) states which variables that skill expects.

---

## Navigation

- [Skill keys vs agent keys](#skill-keys-vs-agent-keys)
- [Framework environment variables](#framework-environment-variables)
- [Local development](#local-development)
- [Cloud and CI](#cloud-and-ci)
- [Secret managers](#secret-managers)
- [Variable names and custom deployments](#variable-names-and-custom-deployments)
- [Security practices](#security-practices)
- [Illustrative examples](#illustrative-examples)

---

## Skill keys vs agent keys

| Kind | Who consumes it | Typical variables | Where documented |
| :--- | :--- | :--- | :--- |
| **Skill runtime keys** | `skill.py` when you call `execute()` | Names in `manifest.yaml` `env_vars` | Skill's catalog page + manifest |
| **Agent / LLM keys** | Your chat client (Gemini, Claude, OpenAI, and similar) | `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, and similar | Provider usage guides under `docs/usage/` |

A single workflow may need both: for example, a skill that screens wallets may require `ETHERSCAN_API_KEY`, while your Gemini agent loop separately needs `GOOGLE_API_KEY` to run the model. Configure each name the code actually reads.

---

## Framework environment variables

These are read by Skillware itself (loader and CLI), not by individual skills:

| Variable | Purpose |
| :--- | :--- |
| `SKILLWARE_SKILL_PATH` | Extra filesystem roots for skill discovery (OS path separator between multiple entries). See [CLI reference](cli.md#path-resolution). |
| `SKILLWARE_NO_VERSION_CHECK` | Set to `1` to disable the CLI version advisory (useful in CI and automation). See [CLI reference](cli.md#version-advisory). |

Skill-specific names remain on each skill's catalog page and in `manifest.yaml` `env_vars`.

---

## Local development

### `.env` file (recommended)

Copy the repository root template and fill in values:

```bash
cp .env.example .env
```

Skillware can load `.env` into the process environment before skills run:

```python
from skillware.core.env import load_env_file

load_env_file()  # reads `.env` in the current working directory by default
```

Run your script from the repository root (or pass an explicit path: `load_env_file("/path/to/.env")`).

Add `.env` to `.gitignore` (already ignored in this repository). Never commit real keys.

### Shell export

```bash
export ETHERSCAN_API_KEY="your_key"
python your_script.py
```

Exports apply only to the current shell session.

---

## Cloud and CI

Inject the same variable **names** the skill expects; do not rename them unless you also provide a mapping layer (see below).

**GitHub Actions (example):**

```yaml
env:
  ETHERSCAN_API_KEY: ${{ secrets.ETHERSCAN_API_KEY }}
```

**Docker (example):**

```bash
docker run --env-file .env your-image python examples/gemini_wallet_check.py
```

**Containers / Kubernetes:** mount secrets as environment variables with keys matching `manifest.yaml` (for example `ETHERSCAN_API_KEY`), not arbitrary secret aliases, unless your deployment template maps them.

---

## Secret managers

Pattern: fetch the secret at startup, then set `os.environ["EXPECTED_NAME"]` before loading or executing skills.

| Platform | Approach |
| :--- | :--- |
| **AWS Secrets Manager** | Retrieve secret in app init; `os.environ["ETHERSCAN_API_KEY"] = value` |
| **GCP Secret Manager** | Access version payload; assign to the env name the skill documents |
| **Azure Key Vault** | Resolve secret; export under the manifest variable name |

Keep secret-fetching code in your application layer, not inside contributed skills. Skills should continue to read standard environment variable names for portability.

---

## Variable names and custom deployments

Skills are written against **specific environment variable names** (for example `ETHERSCAN_API_KEY`). The manifest `env_vars` section documents meaning and whether each key is required.

If your organization uses different secret names:

1. **Preferred:** Map at deploy time so the process still exposes the name the skill expects:

   ```bash
   export ETHERSCAN_API_KEY="$(vault read -field=key secret/etherscan)"
   ```

2. **Alternative:** If the skill accepts a configuration dict (some skills read `self.config` as a fallback), pass the key there only when documented on the skill page. Do not assume all skills support custom config keys.

3. **Avoid:** Renaming the variable in `.env` to `MY_ETHERSCAN_KEY` without exporting `ETHERSCAN_API_KEY`—the skill will behave as if the key is missing.

When contributing a new skill, declare every external credential under `env_vars` in `manifest.yaml` and list the same names on the skill's documentation page with a link to this guide.

---

## Security practices

- Never hardcode API keys in `skill.py`, notebooks, or documentation.
- Never commit `.env`, key files, or CI logs containing secrets.
- Use least-privilege keys (read-only or scoped APIs where providers allow it).
- Rotate keys if they are exposed; revoke compromised keys at the provider.
- Prefer secret managers or platform secret stores for production, not plaintext files on servers.
- Do not print environment variable values in skill output or logs.

Report security concerns per [SECURITY.md](../../SECURITY.md).

---

## Illustrative examples

These patterns apply to many skills; see individual skill pages for exact variable names and requirements.

### External data API (required key)

A skill that fetches on-chain data may require a provider key before `execute()` returns useful results. Set the name from its manifest (illustrative):

```bash
export ETHERSCAN_API_KEY="your_etherscan_key"
```

If the key is missing, the skill should return a structured error rather than crash the host agent.

### Optional provider key

Some skills support a free tier when a key is absent and upgraded limits when present. The skill page and `env_vars.required` field state whether the key is optional.

### Optional LLM path inside a skill

Some skills optionally call a cloud model for one step (for example policy clause review). That path may require `GOOGLE_API_KEY` only when enabled via parameters such as `use_llm_evaluator: true`. The skill page lists when the key is needed.

### Local-only skills

Skills that talk only to `localhost` (for example a local Ollama instance) may not use API keys at all. No configuration is required beyond running the local service.

---

## Related documents

- [.env.example](../../.env.example) — starter template at repository root
- [CONTRIBUTING.md](../../CONTRIBUTING.md) — declaring `env_vars` for new skills
- [Usage: Gemini](gemini.md) — agent-side `GOOGLE_API_KEY`
- [Usage: Claude](claude.md) — agent-side `ANTHROPIC_API_KEY`
- [Usage: OpenAI](openai.md) — agent-side `OPENAI_API_KEY`
- [Usage: DeepSeek](deepseek.md) — agent-side `DEEPSEEK_API_KEY`
- [Skill library](../skills/README.md) — per-skill environment requirements

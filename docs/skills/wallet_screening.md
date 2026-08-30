# Wallet Screening Skill

**ID**: `finance/wallet_screening`
**Issuer**: [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
**Version**: `1.0.1` — 23 Jul 2026
<!-- skill-doc-meta:end -->

**Recommended install:** `pip install "skillware[finance_wallet_screening]"`. See [Install extras](../usage/install_extras.md).
[Skill Library](README.md) · [Testing](../TESTING.md)

A rigorous compliance and risk assessment tool for Ethereum wallets. This skill ports logic from professional forensic tools into the modular Skillware format.

## Capabilities

*   **Sanctions Check**: Screens against **880+** bundled lists (OFAC, FBI, Israel NBCTF, etc.) via dynamic dataset loading.
*   **Malicious Contract Detection**: Identifies interactions with known bad actors (Tornado Cash, Drainers).
*   **Financial Forensic Analysis**:
    *   Calculates total Inflows/Outflows/Gas.
    *   Computes PnL (Profit and Loss) in ETH, USD, and EUR.
    *   Identifies top counterparties and "most interacted" wallets.
*   **Risk Scoring**: Flags high-risk patterns based on transaction flow analysis.

## Internal Architecture

The skill is self-contained in `skills/finance/wallet_screening/`.

### 1. The Mind (`instructions.md`)
The system prompt teaches the AI specifically to:
*   ACT as a Senior Compliance Officer.
*   Analyze the JSON report for boolean flags (`sanctioned`, `malicious_interactions`).
*   Provide a verdict: "Low Risk", "Medium Risk", or "High Risk".

### 2. The Body (`skill.py`)
The Python implementation has been engineered for speed and depth:
*   **Dynamic Loading**: It scans the `data/` directory for *any* `.json` file, automatically indexing it as a sanctions source.
*   **API Integration**: Uses Etherscan for live transaction history and CoinGecko for real-time pricing.
*   **Forensic Engine**: Replays the wallet's entire history to build a counterparty graph.

### 3. The Knowledge (`data/`)
Contains localized JSON snapshots of global sanctions lists.
*   `entities.ftm.json`: Core sanctions list.
*   `malicious_scs_2025.json`: Known malicious smart contracts.
*   `data/*.json`: Hundreds of normalized lists (UniSwap TRM, FBI Lazarus, etc.).

### 4. Maintenance Subsystem (`maintenance/`)
Tools to keep the knowledge fresh.
*   `normalization_tool.py`: Ingests raw CSVs from authorities (FBI, Israel NBCTF) and converts them to the Skillware JSON schema.
*   `normalize_uniswap_trm.py`: Converts Uniswap's blocked address list into our risk format.

## Integration Guide

### Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `ETHERSCAN_API_KEY` | Yes | Etherscan API for transaction history |
| `COINGECKO_API_KEY` | No | CoinGecko pricing (free tier if unset) |

Configure values per [API keys for skills](../usage/api_keys.md). This skill reads the names declared in `skills/finance/wallet_screening/manifest.yaml`.

Agent loops also need a provider API key (for example `GOOGLE_API_KEY` with Gemini); see [Gemini usage](../usage/gemini.md).

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [API keys](../usage/api_keys.md).


Use `bundle["class"]()` in the snippets below; explicit `bundle["module"].ClassName()` also works.

Sample user message: *Screen wallet `0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045` for sanctions and malicious contract interactions.*

### Runnable examples

See [examples/README.md](../../examples/README.md) for the current runnable-script inventory. This page includes provider snippets, but the dedicated runnable flows today are `examples/gemini_wallet_check.py`, `examples/claude_wallet_check.py`, and the multi-skill Ollama harness `examples/ollama_skills_test.py`.

| Provider | Reference script |
| :--- | :--- |
| Gemini | `examples/gemini_wallet_check.py` |
| Claude | `examples/claude_wallet_check.py` |
| Ollama (multi-skill harness) | `examples/ollama_skills_test.py` |

### Gemini

```python
import os
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/wallet_screening")
skill = bundle["class"](
    config={"ETHERSCAN_API_KEY": os.environ.get("ETHERSCAN_API_KEY")}
)
client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
# Use the manifest name so the match stays correct if the name ever changes
tool_name = SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"])
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Screen wallet 0xd8dA... for sanctions and malicious contract interactions.",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call and part.function_call.name == tool_name:
        result = skill.execute(dict(part.function_call.args))
        follow_up = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                "Use this tool result to answer the original request.",
                {
                    "function_response": {
                        "name": part.function_call.name,
                        "response": {"result": result},
                    }
                },
            ],
            config=types.GenerateContentConfig(
                tools=[tool],
                system_instruction=bundle["instructions"],
            ),
        )
        print(follow_up.text)
```

### Claude

```python
import os
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/wallet_screening")
skill = bundle["class"](
    config={"ETHERSCAN_API_KEY": os.environ.get("ETHERSCAN_API_KEY")}
)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
# On tool_use, match name against bundle["manifest"]["name"] (finance/wallet_screening):
# skill.execute(tool_use.input), return tool_result
```

### OpenAI

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/wallet_screening")
skill = bundle["class"](
    config={"ETHERSCAN_API_KEY": os.environ.get("ETHERSCAN_API_KEY")}
)
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# Match tool_call.function.name to openai_tool["function"]["name"] (finance_wallet_screening)
```

### DeepSeek

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/wallet_screening")
skill = bundle["class"](
    config={"ETHERSCAN_API_KEY": os.environ.get("ETHERSCAN_API_KEY")}
)
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
# chat.completions.create(model="deepseek-chat", tools=[deepseek_tool], ...)
# Match tool_call.function.name to deepseek_tool["function"]["name"] (finance_wallet_screening)
```

### Ollama

Prompt mode via `SkillLoader.to_ollama_prompt(bundle)`; match `"tool": "finance/wallet_screening"` in the JSON block. See [Ollama usage](../usage/ollama.md) and [agent loops](../usage/agent_loops.md).

## Data Schema

The skill returns a rich forensic report. Agents act on this data. `metadata.warnings` is optional — present when Etherscan history is truncated or partially unavailable (see Limitations).

```json
{
  "metadata": {
    "screening_time": "2025-01-01T00:00:00",
    "wallet_address": "0xd8dA...",
    "data_sources_count": 3,
    "warnings": ["etherscan_txlist_truncated"]
  },
  "summary": {
    "risk_flag": true,
    "sanctioned_entity_match": false,
    "malicious_interaction_count": 3,
    "balance_eth": 1.5,
    "balance_usd": 3000.0,
    "total_transactions": 42
  },
  "financial_analysis": {
    "value_in_eth": 10.0,
    "value_in_usd": 20000.0,
    "value_out_eth": 8.5,
    "value_out_usd": 17000.0,
    "gas_paid_eth": 0.02,
    "pnl_eth": -1.52,
    "pnl_usd": -3040.0,
    "pnl_percent": -15.2
  },
  "risk_details": {
    "sanctions_hits": [],
    "malicious_interactions": [
      {
        "tx_hash": "0xabc...",
        "contract_name": "Tornado Cash Router",
        "severity": "critical"
      }
    ]
  },
  "network_analysis": {
    "most_interacted_wallet": ["0x123...", 45],
    "top_10_counterparties": [["0x123...", 45]]
  }
}
```

## Limitations

- **Ethereum only**: The skill screens Ethereum (EVM) addresses exclusively. Bitcoin, Solana, or other chain addresses are not supported and will fail address validation.
- **Etherscan transaction cap**: Normal ETH history is fetched via paginated `txlist` (1,000 txs per page, max 10 pages → **10,000 txs**). When that cap is hit, or Etherscan fails, the report includes `metadata.warnings` with codes such as `etherscan_txlist_truncated`, `etherscan_txlist_unavailable`, or `etherscan_txlist_partial`. Treat PnL and counterparty stats as incomplete when warnings are present.
- **Point-in-time sanctions data**: The bundled JSON lists (`entities.ftm.json`, `malicious_scs_2025.json`, and the normalized lists) reflect the state at the time of the last `maintenance/` run. They must be refreshed periodically to stay current.
- **No ERC-20 or internal transaction coverage**: Only standard ETH transfers from the Etherscan `txlist` action are analyzed. ERC-20 token transfers, internal transactions, and NFT transfers are not included in financial flow calculations.
- **Not legal advice**: Risk flags are derived from open-source sanctions data and pattern heuristics. A clean result does not constitute legal clearance.

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`finance/wallet_screening`](https://github.com/ARPAHLS/skillware/tree/main/skills/finance/wallet_screening)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`0b308d3`](https://github.com/ARPAHLS/skillware/commit/0b308d3) | feat(wallet_screening): paginate Etherscan txlist and surface warnings (#214) (#215) | 23 Jul 2026 | `1.0.1` | [@Hendobox](https://github.com/Hendobox) |
| [`bca8181`](https://github.com/ARPAHLS/skillware/commit/bca8181) | Add category and per-skill pip extras with manifest sync (#236). (#256) | 16 Jul 2026 | `1.0.0` | [@rosspeili](https://github.com/rosspeili) |
| [`f301088`](https://github.com/ARPAHLS/skillware/commit/f301088) | Implement manifest param validation and standardize outputs key. (#253) | 12 Jul 2026 | `1.0.0` | [@rosspeili](https://github.com/rosspeili) |
| [`4814478`](https://github.com/ARPAHLS/skillware/commit/4814478) | Fix: to_gemini_tool to return types.Tool object. Fixes #223 (#229) | 10 Jul 2026 | `1.0.0` | [@Areen-09](https://github.com/Areen-09) |
| [`0d550d0`](https://github.com/ARPAHLS/skillware/commit/0d550d0) | docs: sweep vision, bundle class usage, and README Mermaid | 8 Jul 2026 | `1.0.0` | [@rosspeili](https://github.com/rosspeili) |
| [`a941a92`](https://github.com/ARPAHLS/skillware/commit/a941a92) | docs(wallet_screening): align examples and docs with finance/wallet_s… (#175) | 20 Jun 2026 | `1.0.0` | [@Akanksha-H](https://github.com/Akanksha-H) |
| [`280ff40`](https://github.com/ARPAHLS/skillware/commit/280ff40) | fix(wallet_screening): address #165 review — bundle test, CHANGELOG, manifest name | 15 Jun 2026 | `1.0.0` | [@Hendobox](https://github.com/Hendobox) |
| [`904e18b`](https://github.com/ARPAHLS/skillware/commit/904e18b) | fix(wallet_screening): load manifest.yaml in skill.manifest property | 13 Jun 2026 | `1.0.0` | [@Hendobox](https://github.com/Hendobox) |
| [`0f81d1f`](https://github.com/ARPAHLS/skillware/commit/0f81d1f) | Backfill bundle tests for six registry skills missing test_skill.py. | 10 Jun 2026 | `1.0.0` | [@rosspeili](https://github.com/rosspeili) |
| [`2c7c2b9`](https://github.com/ARPAHLS/skillware/commit/2c7c2b9) | feat(wallet_screening): unify TRM/scam tx risk index for analysis (#140) | 29 May 2026 | `1.0.0` | [@Hendobox](https://github.com/Hendobox) |
| [`5b68b78`](https://github.com/ARPAHLS/skillware/commit/5b68b78) | Feat/issue 93 cli visual redesign (#129) | 26 May 2026 | `1.0.0` | [@rizzoMartin](https://github.com/rizzoMartin) |
| [`9f17292`](https://github.com/ARPAHLS/skillware/commit/9f17292) | feat(wallet_screening): FTM publicKey matching and ETH sanctions index (#128) | 26 May 2026 | `1.0.0` | [@Hendobox](https://github.com/Hendobox) |
| [`52cce29`](https://github.com/ARPAHLS/skillware/commit/52cce29) | docs: clarify runnable examples across skill pages (#121) | 24 May 2026 | `1.0.0` | [@narutamaaurum](https://github.com/narutamaaurum) |
| [`a3a7ac8`](https://github.com/ARPAHLS/skillware/commit/a3a7ac8) | docs: update Gemini snippets to google-genai (#92) | 23 May 2026 | `1.0.0` | [@kunal-9090](https://github.com/kunal-9090) |
| [`cca7334`](https://github.com/ARPAHLS/skillware/commit/cca7334) | docs: skill docs revamp — remove emojis, add breadcrumbs, fix index, add missing sections (closes #52) (#82) | 21 May 2026 | `1.0.0` | [@rosspeili](https://github.com/rosspeili) |
| [`e465dc4`](https://github.com/ARPAHLS/skillware/commit/e465dc4) | Fix skill path resolution and PyPI skill packaging. (#79) | 18 May 2026 | `1.0.0` | [@rosspeili](https://github.com/rosspeili) |
| [`5b18e21`](https://github.com/ARPAHLS/skillware/commit/5b18e21) | Document per-skill usage examples across providers. | 17 May 2026 | `1.0.0` | [@rosspeili](https://github.com/rosspeili) |
| [`39487f8`](https://github.com/ARPAHLS/skillware/commit/39487f8) | Add generic API keys guide for skills requiring external calls. | 17 May 2026 | `1.0.0` | [@rosspeili](https://github.com/rosspeili) |
| [`f800f41`](https://github.com/ARPAHLS/skillware/commit/f800f41) | Add skill issuer attribution across registry and docs. | 17 May 2026 | `1.0.0` | [@rosspeili](https://github.com/rosspeili) |
| [`e658e7e`](https://github.com/ARPAHLS/skillware/commit/e658e7e) | docs: update enterprise disclaimer heading and scope to ARPA catalog skills only | 16 May 2026 | `1.0.0` | [@shaansatsangi](https://github.com/shaansatsangi) |
| [`891f5cc`](https://github.com/ARPAHLS/skillware/commit/891f5cc) | docs: add standard enterprise disclaimer to all skill documentation pages (#59) | 16 May 2026 | `1.0.0` | [@shaansatsangi](https://github.com/shaansatsangi) |
| [`3838724`](https://github.com/ARPAHLS/skillware/commit/3838724) | feat: Add automated testing and strict linting (closes #8) | 15 Feb 2026 | `1.0.0` | [@rosspeili](https://github.com/rosspeili) |
| [`6b2e357`](https://github.com/ARPAHLS/skillware/commit/6b2e357) | Refactor: Move skills and templates to root to decouple content from framework | 23 Jan 2026 | `1.0.0` | [@rosspeili](https://github.com/rosspeili) |
| [`cc327c8`](https://github.com/ARPAHLS/skillware/commit/cc327c8) | Initial commit: Skillware Framework v1.0 | 20 Jan 2026 | `—` | [@rosspeili](https://github.com/rosspeili) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

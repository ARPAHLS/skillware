# Wallet Screening Skill

**ID**: `finance/wallet_screening`
**Issuer**: [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))

A rigorous compliance and risk assessment tool for Ethereum wallets. This skill ports logic from professional forensic tools into the modular Skillware format.

## 📋 Capabilities

*   **Sanctions Check**: Screens against **880+** bundled lists (OFAC, FBI, Israel NBCTF, etc.) via dynamic dataset loading.
*   **Malicious Contract Detection**: Identifies interactions with known bad actors (Tornado Cash, Drainers).
*   **Financial Forensic Analysis**:
    *   Calculates total Inflows/Outflows/Gas.
    *   Computes PnL (Profit and Loss) in ETH, USD, and EUR.
    *   Identifies top counterparties and "most interacted" wallets.
*   **Risk Scoring**: Flags high-risk patterns based on transaction flow analysis.

## 📂 Internal Architecture

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

## 💻 Integration Guide

### Environment

| Variable | Required | Purpose |
| :--- | :--- | :--- |
| `ETHERSCAN_API_KEY` | Yes | Etherscan API for transaction history |
| `COINGECKO_API_KEY` | No | CoinGecko pricing (free tier if unset) |

Configure values per [API keys for skills](../usage/api_keys.md). This skill reads the names declared in `skills/finance/wallet_screening/manifest.yaml`.

Agent loops also need a provider API key (for example `GOOGLE_API_KEY` with Gemini); see [Gemini usage](../usage/gemini.md).

## Usage Examples

Guides: [Usage index](../usage/README.md) · [Agent loops](../usage/agent_loops.md) · [API keys](../usage/api_keys.md).

Sample user message: *Screen wallet `0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045` for sanctions and malicious contract interactions.*

| Provider | Reference script |
| :--- | :--- |
| Gemini | `examples/gemini_wallet_check.py` |
| Claude | `examples/claude_wallet_check.py` |

### Gemini

```python
import os
import google.generativeai as genai
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/wallet_screening")
skill = bundle["module"].WalletScreeningSkill(
    config={"ETHERSCAN_API_KEY": os.environ.get("ETHERSCAN_API_KEY")}
)
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel(
    "gemini-2.5-flash",
    tools=[SkillLoader.to_gemini_tool(bundle)],
    system_instruction=bundle["instructions"],
)
# On function_call (name wallet_screening): skill.execute(dict(part.function_call.args))
```

### Claude

```python
import os
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/wallet_screening")
skill = bundle["module"].WalletScreeningSkill(
    config={"ETHERSCAN_API_KEY": os.environ.get("ETHERSCAN_API_KEY")}
)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
# On tool_use (name wallet_screening): skill.execute(tool_use.input), return tool_result
```

### OpenAI

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/wallet_screening")
skill = bundle["module"].WalletScreeningSkill(
    config={"ETHERSCAN_API_KEY": os.environ.get("ETHERSCAN_API_KEY")}
)
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
# Match tool_call.function.name to openai_tool["function"]["name"] (wallet_screening)
```

### DeepSeek

```python
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("finance/wallet_screening")
skill = bundle["module"].WalletScreeningSkill(
    config={"ETHERSCAN_API_KEY": os.environ.get("ETHERSCAN_API_KEY")}
)
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)
# chat.completions.create(model="deepseek-chat", tools=[deepseek_tool], ...)
```

### Ollama

Prompt mode via `SkillLoader.to_ollama_prompt(bundle)`; match `"tool": "wallet_screening"` in the JSON block. See [Ollama usage](../usage/ollama.md) and [agent loops](../usage/agent_loops.md).

## 📊 Data Schema

The skill returns a rich forensic report. Agents act on this data.

```json
{
  "summary": {
    "address": "0xd8dA...",
    "risk_flag": true,
    "sanctioned_entity_match": false,
    "malicious_interaction_count": 3,
    "pnl_usd": 4500.50
  },
  "risk_details": {
    "malicious_interactions": [
      {
        "tx_hash": "0xabc...",
        "contract_name": "Tornado Cash Router",
        "severity": "critical"
      }
    ]
  },
  "network_analysis": {
    "most_interacted_wallet": ["0x123...", 45]
  }
}
```

---

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

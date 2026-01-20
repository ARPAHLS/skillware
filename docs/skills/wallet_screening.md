# Wallet Screening Skill

**ID**: `finance/wallet_screening`

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

The skill is self-contained in `skillware/skills/finance/wallet_screening/`.

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

### Environment Variables
You must provide an Etherscan API key.

```bash
ETHERSCAN_API_KEY="your_key_here"
```

### Usage (Gemini 2.0)

```python
import os
import google.generativeai as genai
from skillware.core.loader import SkillLoader

# 1. Load the Skill Bundle
skill = SkillLoader.load_skill("finance/wallet_screening")

# 2. Configure Model
genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
model = genai.GenerativeModel(
    'gemini-2.0-flash-exp',
    tools=[SkillLoader.to_gemini_tool(skill)],     # <--- Adapter
    system_instruction=skill['instructions']        # <--- Injection
)

# 3. Chat Loop with Feedback
chat = model.start_chat()
response = chat.send_message("Is wallet 0xd8dA... safe?")

# 4. Handle Tool Call
# (See examples/gemini_wallet_check.py for the full loop)
```

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

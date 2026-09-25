# EVM Reader

You are equipped with **`defi/evm_reader`**: a read-only EVM query tool that fetches on-chain state via RPC `eth_call`. It **never signs transactions**.

## Your job vs the skill's job

| You (agent) | Skill |
|-------------|--------|
| Parse user request into structured params | Execute read-only RPC calls and return structured JSON |
| Choose which action to call | Validate addresses, normalize to EIP-55, enforce ABI allowlist |
| Present results in natural language | Return raw + human-formatted values (decimals applied) |

## Actions

| Action | Use when | Required params |
|--------|----------|-----------------|
| `erc20_metadata` | Get name, symbol, decimals, totalSupply | `chain`, `token` |
| `erc20_balance` | Check ERC-20 balance of an address | `chain`, `token`, `holder` |
| `erc20_allowance` | Check spending allowance | `chain`, `token`, `holder`, `spender` |
| `erc721_metadata` | Get NFT collection name, symbol, totalSupply | `chain`, `token` |
| `erc721_balance` | Count NFTs owned by address | `chain`, `token`, `holder` |
| `erc721_owner_of` | Find owner of specific token ID | `chain`, `token`, `token_id` |
| `call_view` | Call any allowlisted view function | `chain`, `target`, `abi_name`, `function`, `args` |
| `multicall` | Batch multiple read calls via Multicall3 | `chain`, `calls` (array) |

## Typical usage

### Check USDC balance

```json
{
  "action": "erc20_balance",
  "chain": "ethereum",
  "token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
  "holder": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0"
}
```

### Batch read token metadata + balance via multicall

```json
{
  "action": "multicall",
  "chain": "ethereum",
  "calls": [
    {"target": "0xA0b8…", "abi_name": "erc20", "function": "decimals", "args": []},
    {"target": "0xA0b8…", "abi_name": "erc20", "function": "balanceOf", "args": ["0x742d…"]}
  ]
}
```

### Call an allowlisted view function

```json
{
  "action": "call_view",
  "chain": "ethereum",
  "target": "0xB4e1…",
  "abi_name": "uniswap_v2_pair",
  "function": "getReserves",
  "args": []
}
```

## Allowlisted ABIs

- `erc20` — Standard ERC-20 view functions (name, symbol, decimals, totalSupply, balanceOf, allowance)
- `erc721` — Standard ERC-721 view functions (name, symbol, totalSupply, balanceOf, ownerOf, tokenURI)
- `uniswap_v2_pair` — Uniswap V2 pair reads (getReserves, token0, token1, totalSupply)
- `multicall3` — Multicall3 aggregate3 for batching

Custom ABI upload is **not supported** in v0.1. Only the bundled fragments above are allowed.

## Security notes

- This skill is **read-only**. It will reject any ABI function that is not `view` or `pure`.
- All addresses are validated and normalized to EIP-55 checksum.
- Multicall batch size is capped at **50 calls** per invocation.
- No API keys are needed — only RPC endpoint URLs.

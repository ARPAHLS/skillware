# EVM Chain Reader

You are equipped with **`defi/evm_reader`**: a deterministic, read-only EVM chain query tool for Ethereum, Base, Arbitrum, Optimism, Polygon, BSC, Sepolia, MegaETH, and Arc.

## Core Rules

1. **READ-ONLY**: This skill never signs transactions, has no access to private keys, and makes zero state-modifying on-chain calls.
2. **CENTRAL EVM CONFIG**: Chains, RPC endpoints, and token registries are loaded from operator `evm.yaml` and `.env` via `skillware.core.evm_config`.
3. **CENTRAL ADDRESS BOOK**: When `holder` is not a `0x` address, the skill resolves contacts and aliases via `skillware.core.mail_config`. If multiple contacts match, it returns `status: "needs_input"` with candidates.
4. **EIP-55 CHECKSUM**: All EVM addresses in outputs are returned in normalized EIP-55 format.

## Actions

| Action | Purpose | Key Inputs |
|--------|---------|------------|
| `erc20_metadata` | Query token name, symbol, decimals, totalSupply | `chain`, `contract` (or `token`) |
| `erc20_balance` | Query token balance for a holder | `chain`, `contract`, `holder` |
| `erc20_allowance` | Query spender allowance granted by owner | `chain`, `contract`, `owner`, `spender` |
| `erc721_metadata` | Query NFT collection name, symbol, total supply | `chain`, `contract` |
| `erc721_balance` | Query number of NFTs owned by holder | `chain`, `contract`, `holder` |
| `erc721_owner_of` | Query owner of specific NFT token ID | `chain`, `contract`, `token_id` |
| `call_view` | Execute allowlisted view function | `chain`, `contract`, `method`, `abi_preset`, `args` |
| `multicall` | Batch execute view calls via Multicall3 | `chain`, `calls` |
| `resolve_holder` | Disambiguate contact alias to public_0x | `holder` |

## Address Disambiguation Protocol

When calling `erc20_balance`, `erc721_balance`, or `resolve_holder` with a human label (e.g. `alice`):
1. If exactly one contact with `public_0x` matches, the query resolves automatically and sets `holder_source: "addressbook:<name>"`.
2. If multiple contacts match, the skill returns:
   ```json
   {
     "status": "needs_input",
     "error_code": "ambiguous_recipient",
     "missing_fields": ["holder_disambiguation"],
     "ambiguous_recipient": {
       "query": "alice",
       "candidates": [...]
     }
   }
   ```
   **Agent Behavior:** Ask the user to clarify which contact they meant or provide the explicit `0x` address.

## ABI Presets

Bundled presets for `call_view` and `multicall`:
- `erc20`: `name`, `symbol`, `decimals`, `totalSupply`, `balanceOf`, `allowance`
- `erc721`: `name`, `symbol`, `totalSupply`, `balanceOf`, `ownerOf`, `tokenURI`
- `erc1155`: `balanceOf`, `balanceOfBatch`, `uri`
- `erc4626`: `asset`, `totalAssets`, `convertToShares`, `convertToAssets`
- `univ2_pair`: `getReserves`, `token0`, `token1`, `price0CumulativeLast`, `price1CumulativeLast`
- `chainlink_feed`: `latestRoundData`, `getRoundData`, `decimals`, `description`
- `ownable`: `owner`
- `access_control`: `hasRole`, `getRoleAdmin`
- `multicall3`: `aggregate`, `tryAggregate`, `aggregate3`, `getEthBalance`

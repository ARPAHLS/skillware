# defi/permit2_helper Instructions

## Purpose and Scope
`defi/permit2_helper` constructs, validates, and hashes EIP-712 typed data payloads for the canonical Uniswap Permit2 contract (`0x000000000022D473030F116dDEE9F6B43aC78BA3`).

It does NOT hold private keys or sign transactions in v0.1. It generates the exact structured payload and 32-byte digest that the host agent or user wallet signs, eliminating domain mismatches, wrong spenders, and malformed nonces.

## When to Invoke
- Preparing an off-chain Permit2 allowance signature before calling a swap router (e.g. Uniswap Universal Router, SwapRouter02).
- Preparing a `PermitTransferFrom` signature for direct signature-based token transfers.
- Inspecting and validating an untrusted EIP-712 Permit2 payload to verify expected spender, chain, token, and expiration before presenting it to an agent or user wallet for signing.
- Hashing an existing EIP-712 typed data dictionary to generate its 32-byte signing digest.
- Querying current on-chain Permit2 allowance nonces for an owner/token/spender pair.

## When NOT to Invoke
- For legacy ERC-2612 token permits (which use the token contract's own domain separator rather than Permit2).
- For signing or broadcasting on-chain transactions directly (use `defi/evm_tx_handler`).
- For smart contract wallets (ERC-1271) requiring custom validation contracts.

## Safety and Guardrails
- **Unlimited Approvals**: Attempting to permit `type(uint160).max` or `type(uint256).max` fails closed by default. The host agent must explicitly pass `allow_unlimited: true` to permit maximum allowances.
- **Spender Verification**: In `validate_typed_data`, pass `expected_spender` and `expected_chain` to ensure the payload cannot redirect allowances to malicious contracts.
- **Expiration Enforcement**: Payloads with expired deadlines generate explicit warnings.

## Actions Reference

### `build_permit2`
Builds standard EIP-712 typed data and computes its signing digest.
```json
{
  "action": "build_permit2",
  "chain": "ethereum",
  "token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48",
  "spender": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD",
  "amount": "1000000",
  "nonce": 0,
  "deadline": 1735689600
}
```

### `validate_typed_data`
Validates an EIP-712 dictionary for domain accuracy, verifying contract, expiration, and expected parameters.
```json
{
  "action": "validate_typed_data",
  "typed_data": { ... },
  "expected_chain": "ethereum",
  "expected_spender": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD"
}
```

### `hash_typed_data`
Computes the 32-byte EIP-712 hash (digest) of any Permit2 typed data dictionary.
```json
{
  "action": "hash_typed_data",
  "typed_data": { ... }
}
```

### `read_nonce`
Reads on-chain Permit2 allowance, expiration, and nonce via RPC if configured.
```json
{
  "action": "read_nonce",
  "chain": "ethereum",
  "owner": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0",
  "token": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606EB48",
  "spender": "0x3fC91A3afd70395Cd496C647d5a6CC9D4B2b7FAD"
}
```

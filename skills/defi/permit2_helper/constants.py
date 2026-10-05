"""EIP-712 schemas, constants, and known spenders for Uniswap Permit2."""

from __future__ import annotations

from typing import Any, Dict, List

# Canonical Uniswap Permit2 contract address deployed identically across EVM networks
CANONICAL_PERMIT2_ADDRESS = "0x000000000022D473030F116dDEE9F6B43aC78BA3"

# Bit limits
MAX_UINT48 = (1 << 48) - 1
MAX_UINT160 = (1 << 160) - 1
MAX_UINT256 = (1 << 256) - 1

# Standard EIP-712 Types for Permit2
EIP712_DOMAIN_TYPE: List[Dict[str, str]] = [
    {"name": "name", "type": "string"},
    {"name": "chainId", "type": "uint256"},
    {"name": "verifyingContract", "type": "address"},
]

PERMIT_DETAILS_TYPE: List[Dict[str, str]] = [
    {"name": "token", "type": "address"},
    {"name": "amount", "type": "uint160"},
    {"name": "expiration", "type": "uint48"},
    {"name": "nonce", "type": "uint48"},
]

TOKEN_PERMISSIONS_TYPE: List[Dict[str, str]] = [
    {"name": "token", "type": "address"},
    {"name": "amount", "type": "uint256"},
]

PERMIT_SINGLE_TYPES: Dict[str, List[Dict[str, str]]] = {
    "EIP712Domain": EIP712_DOMAIN_TYPE,
    "PermitDetails": PERMIT_DETAILS_TYPE,
    "PermitSingle": [
        {"name": "details", "type": "PermitDetails"},
        {"name": "spender", "type": "address"},
        {"name": "sigDeadline", "type": "uint256"},
    ],
}

# Note: PERMIT_BATCH_TYPES is reserved for v0.2 batch operations
PERMIT_BATCH_TYPES: Dict[str, List[Dict[str, str]]] = {
    "EIP712Domain": EIP712_DOMAIN_TYPE,
    "PermitDetails": PERMIT_DETAILS_TYPE,
    "PermitBatch": [
        {"name": "details", "type": "PermitDetails[]"},
        {"name": "spender", "type": "address"},
        {"name": "sigDeadline", "type": "uint256"},
    ],
}

PERMIT_TRANSFER_FROM_TYPES: Dict[str, List[Dict[str, str]]] = {
    "EIP712Domain": EIP712_DOMAIN_TYPE,
    "TokenPermissions": TOKEN_PERMISSIONS_TYPE,
    "PermitTransferFrom": [
        {"name": "permitted", "type": "TokenPermissions"},
        {"name": "spender", "type": "address"},
        {"name": "nonce", "type": "uint256"},
        {"name": "deadline", "type": "uint256"},
    ],
}

# Note: PERMIT_BATCH_TRANSFER_FROM_TYPES is reserved for v0.2 batch operations
PERMIT_BATCH_TRANSFER_FROM_TYPES: Dict[str, List[Dict[str, str]]] = {
    "EIP712Domain": EIP712_DOMAIN_TYPE,
    "TokenPermissions": TOKEN_PERMISSIONS_TYPE,
    "PermitBatchTransferFrom": [
        {"name": "permitted", "type": "TokenPermissions[]"},
        {"name": "spender", "type": "address"},
        {"name": "nonce", "type": "uint256"},
        {"name": "deadline", "type": "uint256"},
    ],
}

# Known public spender labels (lowercase addresses mapped to human-readable names)
KNOWN_SPENDER_LABELS: Dict[str, str] = {
    "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad": "Uniswap Universal Router v1.2",
    "0xef1c6e67b5879d7fbfb75095cd9f5b3b86026574": "Uniswap Universal Router v1.0",
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap SwapRouter02",
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 SwapRouter",
    "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch Aggregation Router v5",
    "0x111111125421ca6dc452d289314280a0f8842a65": "1inch Aggregation Router v6",
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff": "0x Exchange Proxy",
    "0x9008d19f58aabd9ed0d60971565aa8510560ab41": "CoW Protocol Settlement",
    "0x198ef79f1f515f02dfe9e3115e9f878490552889": "Uniswap Universal Router (Base)",
}

# Minimal Permit2 ABI for view operations
PERMIT2_VIEW_ABI: List[Dict[str, Any]] = [
    {
        "inputs": [
            {"internalType": "address", "name": "user", "type": "address"},
            {"internalType": "address", "name": "token", "type": "address"},
            {"internalType": "address", "name": "spender", "type": "address"},
        ],
        "name": "allowance",
        "outputs": [
            {"internalType": "uint160", "name": "amount", "type": "uint160"},
            {"internalType": "uint48", "name": "expiration", "type": "uint48"},
            {"internalType": "uint48", "name": "nonce", "type": "uint48"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "DOMAIN_SEPARATOR",
        "outputs": [{"internalType": "bytes32", "name": "", "type": "bytes32"}],
        "stateMutability": "view",
        "type": "function",
    },
]

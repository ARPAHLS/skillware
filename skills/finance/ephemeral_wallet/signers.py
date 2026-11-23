# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ARPA Hellenic Logical Systems

"""Live EIP-3009 exact-scheme signer for x402 (eth_account + dedicated wallet secret)."""

from __future__ import annotations

import os
import secrets
import sys
import time
from typing import Any, Dict, Optional

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
if _PKG_DIR not in sys.path:
    sys.path.insert(0, _PKG_DIR)

from networks import normalize_network  # noqa: E402

_EIP712_TYPES = {
    "EIP712Domain": [
        {"name": "name", "type": "string"},
        {"name": "version", "type": "string"},
        {"name": "chainId", "type": "uint256"},
        {"name": "verifyingContract", "type": "address"},
    ],
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ],
}


def _caip2_chain_id(network: str) -> int:
    _, caip2 = normalize_network(network)
    namespace, _, reference = caip2.partition(":")
    if namespace != "eip155":
        raise ValueError(f"EIP-3009 signer only supports eip155 networks, got {caip2}.")
    return int(reference)


def _normalize_private_key(raw: str) -> str:
    key = str(raw or "").strip()
    if key.startswith("0x") or key.startswith("0X"):
        key = key[2:]
    if len(key) != 64:
        raise ValueError("CDP_WALLET_SECRET must be a 32-byte hex private key.")
    int(key, 16)  # validate hex
    return key


class Eip3009ExactSigner:
    """Sign x402 exact EVM authorizations via EIP-3009 TransferWithAuthorization."""

    def __init__(self, private_key: str):
        try:
            from eth_account import Account
        except ImportError as exc:  # pragma: no cover
            raise ImportError(
                "eth_account is required for live EIP-3009 signing. "
                'Install with: pip install "skillware[finance_ephemeral_wallet]"'
            ) from exc
        self._account = Account.from_key(_normalize_private_key(private_key))
        self.wallet_address = self._account.address
        self.signing_mode = "eip3009"

    def sign_exact(
        self,
        *,
        accepted: Dict[str, Any],
        resource: Dict[str, Any],
        extensions: Dict[str, Any],
    ) -> Dict[str, Any]:
        del resource, extensions  # echoed by settle_x402; not part of EIP-3009 message
        raw_extra = accepted.get("extra")
        extra: Dict[str, Any] = raw_extra if isinstance(raw_extra, dict) else {}
        name = str(extra.get("name") or "").strip()
        version = str(extra.get("version") or "").strip()
        if not name or not version:
            raise ValueError(
                "PAYMENT-REQUIRED accepted.extra must include EIP-712 name and version."
            )
        method = str(extra.get("assetTransferMethod") or "eip3009").lower()
        if method != "eip3009":
            raise ValueError(
                f"Unsupported assetTransferMethod {method!r}; only eip3009 is wired."
            )

        chain_id = _caip2_chain_id(str(accepted.get("network") or ""))
        asset = str(accepted.get("asset") or "").strip()
        pay_to = str(accepted.get("payTo") or "").strip()
        if not asset or not pay_to:
            raise ValueError("accepted.asset and accepted.payTo are required.")

        amount = int(str(accepted.get("amount")))
        timeout = int(accepted.get("maxTimeoutSeconds") or 60)
        now = int(time.time())
        nonce_hex = "0x" + secrets.token_hex(32)
        nonce_bytes = bytes.fromhex(nonce_hex[2:])

        authorization_wire = {
            "from": self.wallet_address,
            "to": pay_to,
            "value": str(amount),
            "validAfter": "0",
            "validBefore": str(now + timeout),
            "nonce": nonce_hex,
        }
        typed = {
            "types": _EIP712_TYPES,
            "primaryType": "TransferWithAuthorization",
            "domain": {
                "name": name,
                "version": version,
                "chainId": chain_id,
                "verifyingContract": asset,
            },
            "message": {
                "from": self.wallet_address,
                "to": pay_to,
                "value": amount,
                "validAfter": 0,
                "validBefore": now + timeout,
                "nonce": nonce_bytes,
            },
        }
        signed = self._account.sign_typed_data(full_message=typed)
        sig_hex = signed.signature.hex()
        if not sig_hex.startswith("0x"):
            sig_hex = "0x" + sig_hex
        return {
            "signature": sig_hex,
            "authorization": authorization_wire,
        }


def build_live_signer(private_key: Optional[str]) -> Eip3009ExactSigner:
    if not private_key:
        raise ValueError("CDP_WALLET_SECRET is required for live signing.")
    return Eip3009ExactSigner(private_key)

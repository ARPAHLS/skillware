# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ARPA Hellenic Logical Systems

"""Payment provider boundary for finance/ephemeral_wallet."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping, Optional, Protocol, Set
from uuid import uuid4

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
if _PKG_DIR not in sys.path:
    sys.path.insert(0, _PKG_DIR)

from x402_client import (  # noqa: E402
    HEADER_PAYMENT_SIGNATURE,
    MockExactSigner,
    PaymentSigner,
    ScriptedHttp,
    X402Error,
    build_mock_402_pair,
    inspect_payment_required,
    settle_x402,
)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class PaymentProvider(Protocol):
    """Settle a spend against a session-bound agent wallet."""

    name: str

    def pay(
        self,
        *,
        session_id: str,
        url: str,
        amount_usd: Optional[float],
        network_caip2: str,
        remaining_usd: float,
        used_nonces: Set[str],
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Return a payment receipt dict (no secrets). May raise X402Error."""

    def quote(
        self,
        *,
        url: str,
        network_caip2: str,
    ) -> Dict[str, Any]:
        """Dry-run 402 inspect (no spend). May raise X402Error."""


class MockX402Provider:
    """Offline stand-in that still exercises the x402 header handshake in-process."""

    name = "mock_x402"

    def __init__(self, signer: Optional[PaymentSigner] = None):
        self._signer: PaymentSigner = signer or MockExactSigner()

    def quote(self, *, url: str, network_caip2: str) -> Dict[str, Any]:
        challenge, _success = build_mock_402_pair(
            url=url,
            amount_atomic="500000",
            network_caip2=network_caip2,
        )
        http = ScriptedHttp([challenge])
        quote = inspect_payment_required(
            url=url,
            session_caip2=network_caip2,
            http_get=http.get,
        )
        quote["provider"] = self.name
        quote["settlement"] = "mock_x402"
        return quote

    def pay(
        self,
        *,
        session_id: str,
        url: str,
        amount_usd: Optional[float],
        network_caip2: str,
        remaining_usd: float,
        used_nonces: Set[str],
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        # Default mock charge: caller amount_usd, else $0.50 USDC atomic.
        if amount_usd is not None:
            atomic = str(int(round(float(amount_usd) * 1_000_000)))
        else:
            atomic = "500000"  # $0.50
        challenge, success = build_mock_402_pair(
            url=url,
            amount_atomic=atomic,
            network_caip2=network_caip2,
            tx="0x" + uuid4().hex + uuid4().hex,
        )
        http = ScriptedHttp([challenge, success])
        result = settle_x402(
            url=url,
            session_caip2=network_caip2,
            remaining_usd=remaining_usd,
            max_amount_usd=amount_usd,
            signer=self._signer,
            http_get=http.get,
            used_nonces=used_nonces,
            idempotency_key=idempotency_key,
        )
        used_nonces.add(result.nonce)
        return {
            "url": url,
            "amount_usd": result.amount_usd,
            "amount_atomic": result.amount_atomic,
            "network": result.network_caip2,
            "tx_ref": result.tx_ref,
            "receipt_ref": result.receipt_ref,
            "payer": result.payer,
            "nonce": result.nonce,
            "provider": self.name,
            "settlement": "mock_x402",
            "signing": "mock",
            "at": _utc_iso(),
            "session_id": session_id,
            "idempotency_key": idempotency_key,
        }


class HttpX402Provider:
    """Live HTTP transport for x402 v2 (injectable session for tests)."""

    name = "http_x402"

    def __init__(
        self,
        *,
        signer: Optional[PaymentSigner] = None,
        http_get: Optional[Callable[..., Any]] = None,
        timeout_s: float = 15.0,
    ):
        self._signer: PaymentSigner = signer or MockExactSigner()
        self._http_get = http_get
        self._timeout_s = timeout_s

    def quote(self, *, url: str, network_caip2: str) -> Dict[str, Any]:
        http_get = self._http_get or self._requests_get
        quote = inspect_payment_required(
            url=url,
            session_caip2=network_caip2,
            http_get=http_get,
            timeout_s=self._timeout_s,
        )
        quote["provider"] = self.name
        quote["settlement"] = "http_x402"
        return quote

    def pay(
        self,
        *,
        session_id: str,
        url: str,
        amount_usd: Optional[float],
        network_caip2: str,
        remaining_usd: float,
        used_nonces: Set[str],
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        http_get = self._http_get or self._requests_get
        result = settle_x402(
            url=url,
            session_caip2=network_caip2,
            remaining_usd=remaining_usd,
            max_amount_usd=amount_usd,
            signer=self._signer,
            http_get=http_get,
            used_nonces=used_nonces,
            timeout_s=self._timeout_s,
            idempotency_key=idempotency_key,
        )
        used_nonces.add(result.nonce)
        signing = getattr(self._signer, "signing_mode", type(self._signer).__name__)
        return {
            "url": url,
            "amount_usd": result.amount_usd,
            "amount_atomic": result.amount_atomic,
            "network": result.network_caip2,
            "tx_ref": result.tx_ref,
            "receipt_ref": result.receipt_ref,
            "payer": result.payer,
            "nonce": result.nonce,
            "provider": self.name,
            "settlement": "http_x402",
            "signing": signing,
            "at": _utc_iso(),
            "session_id": session_id,
            "idempotency_key": idempotency_key,
            "payment_signature_sent": True,
            "had_payment_response": True,
        }

    @staticmethod
    def _requests_get(
        url: str,
        headers: Optional[Mapping[str, str]] = None,
        timeout: float = 15.0,
    ) -> Any:
        import requests

        return requests.get(url, headers=dict(headers or {}), timeout=timeout)


__all__ = [
    "PaymentProvider",
    "MockX402Provider",
    "HttpX402Provider",
    "X402Error",
    "HEADER_PAYMENT_SIGNATURE",
]

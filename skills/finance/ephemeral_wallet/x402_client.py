# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ARPA Hellenic Logical Systems

"""x402 v2 HTTP transport client (402 → PAYMENT-SIGNATURE → PAYMENT-RESPONSE)."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Protocol
from uuid import uuid4

_PKG_DIR = os.path.dirname(os.path.abspath(__file__))
if _PKG_DIR not in sys.path:
    sys.path.insert(0, _PKG_DIR)

from networks import default_asset_decimals, networks_compatible  # noqa: E402

HEADER_PAYMENT_REQUIRED = "PAYMENT-REQUIRED"
HEADER_PAYMENT_SIGNATURE = "PAYMENT-SIGNATURE"
HEADER_PAYMENT_RESPONSE = "PAYMENT-RESPONSE"


class X402Error(Exception):
    """Structured protocol / transport failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class HttpResponse(Protocol):
    status_code: int
    headers: Mapping[str, str]
    text: str


HttpGet = Callable[..., HttpResponse]


@dataclass
class SettleResult:
    amount_usd: float
    amount_atomic: str
    network_caip2: str
    tx_ref: str
    receipt_ref: str
    payer: Optional[str]
    payment_required: Dict[str, Any]
    payment_payload: Dict[str, Any]
    payment_response: Dict[str, Any]
    nonce: str


class PaymentSigner(Protocol):
    """Build scheme-specific ``payload`` for a PaymentPayload."""

    wallet_address: str

    def sign_exact(
        self,
        *,
        accepted: Dict[str, Any],
        resource: Dict[str, Any],
        extensions: Dict[str, Any],
    ) -> Dict[str, Any]: ...


class MockExactSigner:
    """Offline signer that emits a structurally valid exact-scheme payload."""

    def __init__(
        self, wallet_address: str = "0x1111111111111111111111111111111111111111"
    ):
        self.wallet_address = wallet_address

    def sign_exact(
        self,
        *,
        accepted: Dict[str, Any],
        resource: Dict[str, Any],
        extensions: Dict[str, Any],
    ) -> Dict[str, Any]:
        now = int(time.time())
        timeout = int(accepted.get("maxTimeoutSeconds") or 60)
        # 32-byte nonce: two uuid4 hex strings = 64 hex chars
        nonce = "0x" + uuid4().hex + uuid4().hex
        body = {
            "from": self.wallet_address,
            "to": accepted.get("payTo"),
            "value": str(accepted.get("amount")),
            "validAfter": str(now - 30),
            "validBefore": str(now + timeout),
            "nonce": nonce,
            "resource": resource.get("url") if isinstance(resource, dict) else None,
            "extensions": extensions,
        }
        digest = hashlib.sha256(
            json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return {
            "signature": "0x" + digest,
            "authorization": {
                "from": body["from"],
                "to": body["to"],
                "value": body["value"],
                "validAfter": body["validAfter"],
                "validBefore": body["validBefore"],
                "nonce": nonce,
            },
        }


def b64json_encode(obj: Dict[str, Any]) -> str:
    raw = json.dumps(obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.b64encode(raw).decode("ascii")


def b64json_decode(header_value: str) -> Dict[str, Any]:
    if not header_value or not str(header_value).strip():
        raise X402Error("invalid_payment_required", "Empty payment header.")
    try:
        raw = base64.b64decode(str(header_value).strip(), validate=False)
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise X402Error(
            "invalid_payment_header", f"Failed to decode payment header: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise X402Error(
            "invalid_payment_header", "Payment header JSON must be an object."
        )
    return data


def _header_get(headers: Mapping[str, str], name: str) -> Optional[str]:
    # HTTP headers are case-insensitive
    target = name.lower()
    for key, value in headers.items():
        if str(key).lower() == target:
            return value
    return None


def atomic_to_usd(amount_atomic: str, decimals: int) -> float:
    try:
        raw = int(str(amount_atomic))
    except (TypeError, ValueError) as exc:
        raise X402Error(
            "invalid_amount", f"Invalid atomic amount: {amount_atomic!r}"
        ) from exc
    if raw < 0:
        raise X402Error("invalid_amount", "Atomic amount must be non-negative.")
    return raw / float(10**decimals)


def select_accepted(
    payment_required: Dict[str, Any],
    *,
    session_caip2: str,
) -> Dict[str, Any]:
    accepts = payment_required.get("accepts")
    if not isinstance(accepts, list) or not accepts:
        raise X402Error("no_accepts", "PAYMENT-REQUIRED has no accepts[].")
    for item in accepts:
        if not isinstance(item, dict):
            continue
        if str(item.get("scheme") or "").lower() != "exact":
            continue
        network = str(item.get("network") or "")
        if networks_compatible(session_caip2, network):
            return item
    raise X402Error(
        "network_mismatch",
        f"No exact accept for session network {session_caip2}.",
    )


def settle_x402(
    *,
    url: str,
    session_caip2: str,
    remaining_usd: float,
    max_amount_usd: Optional[float],
    signer: PaymentSigner,
    http_get: HttpGet,
    used_nonces: set[str],
    timeout_s: float = 15.0,
    idempotency_key: Optional[str] = None,
) -> SettleResult:
    """Run x402 v2 HTTP handshake; fail closed on amount / replay / settle errors."""
    challenge = http_get(url, headers={}, timeout=timeout_s)
    if challenge.status_code != 402:
        raise X402Error(
            "expected_402",
            f"Expected HTTP 402 Payment Required, got {challenge.status_code}.",
        )

    required_hdr = _header_get(challenge.headers, HEADER_PAYMENT_REQUIRED)
    if not required_hdr:
        raise X402Error(
            "missing_payment_required",
            "402 response missing PAYMENT-REQUIRED header.",
        )
    payment_required = b64json_decode(required_hdr)
    if int(payment_required.get("x402Version") or 0) != 2:
        raise X402Error(
            "unsupported_version",
            f"Unsupported x402Version {payment_required.get('x402Version')!r}; need 2.",
        )

    accepted = select_accepted(payment_required, session_caip2=session_caip2)
    decimals = default_asset_decimals(
        accepted.get("extra") if isinstance(accepted.get("extra"), dict) else None
    )
    amount_usd = atomic_to_usd(str(accepted.get("amount")), decimals)

    if amount_usd > float(remaining_usd) + 1e-9:
        raise X402Error(
            "over_cap",
            (
                f"Server amount {amount_usd} USD exceeds remaining_usd "
                f"{remaining_usd} (soft session policy)."
            ),
        )
    if max_amount_usd is not None and amount_usd > float(max_amount_usd) + 1e-9:
        raise X402Error(
            "over_cap",
            (
                f"Server amount {amount_usd} USD exceeds caller amount_usd "
                f"{max_amount_usd}."
            ),
        )

    resource = payment_required.get("resource")
    if not isinstance(resource, dict):
        resource = {"url": url}
    extensions = payment_required.get("extensions")
    if not isinstance(extensions, dict):
        extensions = {}

    scheme_payload = signer.sign_exact(
        accepted=accepted, resource=resource, extensions=extensions
    )
    auth = scheme_payload.get("authorization")
    if not isinstance(auth, dict) or not auth.get("nonce"):
        raise X402Error(
            "invalid_signature", "Signer did not return authorization.nonce."
        )
    nonce = str(auth["nonce"])
    if nonce in used_nonces:
        raise X402Error(
            "replay",
            "Payment nonce already used in this session (replay blocked).",
        )

    # Bind optional idempotency key into extensions echo (clients may append).
    echo_extensions = dict(extensions)
    if idempotency_key:
        echo_extensions["idempotencyKey"] = str(idempotency_key)

    payment_payload = {
        "x402Version": 2,
        "resource": resource,
        "accepted": accepted,
        "payload": scheme_payload,
        "extensions": echo_extensions,
    }

    paid = http_get(
        url,
        headers={HEADER_PAYMENT_SIGNATURE: b64json_encode(payment_payload)},
        timeout=timeout_s,
    )
    if paid.status_code not in {200, 201}:
        raise X402Error(
            "payment_failed",
            f"Paid retry returned HTTP {paid.status_code}.",
        )

    response_hdr = _header_get(paid.headers, HEADER_PAYMENT_RESPONSE)
    if not response_hdr:
        raise X402Error(
            "missing_payment_response",
            "Success response missing PAYMENT-RESPONSE header.",
        )
    payment_response = b64json_decode(response_hdr)
    if payment_response.get("success") is not True:
        reason = (
            payment_response.get("errorReason")
            or payment_response.get("errorMessage")
            or "settlement unsuccessful"
        )
        raise X402Error("settlement_failed", str(reason))

    tx_ref = str(payment_response.get("transaction") or f"x402_{nonce[-16:]}")
    receipt_ref = f"x402_rcpt_{hashlib.sha256(tx_ref.encode()).hexdigest()[:12]}"
    return SettleResult(
        amount_usd=amount_usd,
        amount_atomic=str(accepted.get("amount")),
        network_caip2=session_caip2,
        tx_ref=tx_ref,
        receipt_ref=receipt_ref,
        payer=(
            str(payment_response.get("payer"))
            if payment_response.get("payer")
            else None
        ),
        payment_required=payment_required,
        payment_payload=payment_payload,
        payment_response=payment_response,
        nonce=nonce,
    )


class ScriptedHttp:
    """Simple scripted HTTP for offline CI (402 then 200)."""

    def __init__(self, responses: list[Any]):
        self._responses = list(responses)
        self.calls: list[Dict[str, Any]] = []

    def get(
        self,
        url: str,
        headers: Optional[Mapping[str, str]] = None,
        timeout: float = 15.0,
    ) -> Any:
        self.calls.append(
            {"url": url, "headers": dict(headers or {}), "timeout": timeout}
        )
        if not self._responses:
            raise X402Error("http_exhausted", "No scripted HTTP responses left.")
        return self._responses.pop(0)


@dataclass
class SimpleResponse:
    status_code: int
    headers: Dict[str, str]
    text: str = ""


def build_mock_402_pair(
    *,
    url: str,
    amount_atomic: str,
    network_caip2: str,
    pay_to: str = "0x209693Bc6afc0C5328bA36FaF03C514EF312287C",
    asset: str = "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    tx: str = "0x" + "ab" * 32,
) -> tuple[SimpleResponse, SimpleResponse]:
    """Return (402 challenge, 200 settle) pair for tests / mock transport."""
    required = {
        "x402Version": 2,
        "resource": {"url": url, "description": "mock resource"},
        "accepts": [
            {
                "scheme": "exact",
                "network": network_caip2,
                "amount": amount_atomic,
                "asset": asset,
                "payTo": pay_to,
                "maxTimeoutSeconds": 60,
                "extra": {"name": "USDC", "version": "2"},
            }
        ],
        "extensions": {},
    }
    challenge = SimpleResponse(
        status_code=402,
        headers={HEADER_PAYMENT_REQUIRED: b64json_encode(required)},
        text="Payment Required",
    )
    settled = {
        "success": True,
        "transaction": tx,
        "network": network_caip2,
        "payer": "0x1111111111111111111111111111111111111111",
    }
    success = SimpleResponse(
        status_code=200,
        headers={HEADER_PAYMENT_RESPONSE: b64json_encode(settled)},
        text='{"ok":true}',
    )
    return challenge, success

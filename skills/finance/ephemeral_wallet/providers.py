# SPDX-License-Identifier: MIT
# Copyright (c) 2026 ARPA Hellenic Logical Systems

"""Payment provider boundary for finance/ephemeral_wallet.

v0.1 ships a mock x402-shaped provider for offline CI. A later slice wires a
live CDP + x402 adapter behind the same interface.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Protocol
from uuid import uuid4


class PaymentProvider(Protocol):
    """Settle a spend against a session-bound agent wallet."""

    name: str

    def pay(
        self,
        *,
        session_id: str,
        url: str,
        amount_usd: float,
        network: str,
    ) -> Dict[str, Any]:
        """Return a payment receipt dict (no secrets)."""


class MockX402Provider:
    """Offline stand-in for HTTP 402 → settle → 200."""

    name = "mock_x402"

    def pay(
        self,
        *,
        session_id: str,
        url: str,
        amount_usd: float,
        network: str,
    ) -> Dict[str, Any]:
        tx_ref = f"mock_tx_{uuid4().hex[:16]}"
        receipt_ref = f"mock_rcpt_{uuid4().hex[:12]}"
        return {
            "url": url,
            "amount_usd": float(amount_usd),
            "network": network,
            "tx_ref": tx_ref,
            "receipt_ref": receipt_ref,
            "provider": self.name,
            "at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "session_id": session_id,
        }

"""Offline demo for finance/ephemeral_wallet v0.2.

Exercises create_session → quote → pay → revoke with the in-process mock
x402 handshake. No network. Set EPHEMERAL_WALLET_LIVE=1 (plus CDP_* in .env)
to also open a live-signed session (HTTP pay still needs a real 402 endpoint).

    python examples/ephemeral_wallet_demo.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skillware.core.env import load_env_file  # noqa: E402
from skillware.core.loader import SkillLoader  # noqa: E402

URL = "https://api.example.com/v1/resource"


def run_offline() -> None:
    print("=== finance/ephemeral_wallet demo (offline mock x402) ===")
    skill = SkillLoader.load_skill("finance/ephemeral_wallet")["class"]()
    created = skill.execute(
        {
            "action": "create_session",
            "spend_cap_usd": 5.0,
            "ttl_seconds": 3600,
            "network": "base-sepolia",
            "allowed_domains": ["api.example.com"],
        }
    )
    assert created["status"] == "ready", created
    sid = created["session_id"]
    print(
        f"session={sid[:16]}… network_caip2={created['network_caip2']} "
        f"settlement={created['settlement']} remaining={created['remaining_usd']}"
    )

    quoted = skill.execute({"action": "quote", "session_id": sid, "url": URL})
    assert quoted["status"] == "quoted", quoted
    print(
        f"quote amount_usd={quoted['quote']['amount_usd']} "
        f"within_cap={quoted['within_cap']} asset={quoted['quote'].get('asset')}"
    )

    paid = skill.execute(
        {
            "action": "pay",
            "session_id": sid,
            "url": URL,
            "amount_usd": 0.5,
            "idempotency_key": "demo-order-1",
        }
    )
    assert paid["status"] == "confirmed", paid
    print(
        f"pay remaining={paid['remaining_usd']} tx_ref={paid['payment']['tx_ref'][:18]}…"
    )

    replay = skill.execute(
        {
            "action": "pay",
            "session_id": sid,
            "url": URL,
            "amount_usd": 0.5,
            "idempotency_key": "demo-order-1",
        }
    )
    assert replay.get("idempotent_replay") is True, replay
    print("idempotent_replay=True")

    revoked = skill.execute({"action": "revoke", "session_id": sid})
    assert revoked["status"] == "revoked", revoked
    print("revoked=True")
    print("Demo completed successfully.")


def run_live_session_only() -> None:
    print("=== live EIP-3009 session open (EPHEMERAL_WALLET_LIVE=1) ===")
    load_env_file()
    skill = SkillLoader.load_skill("finance/ephemeral_wallet")["class"]()
    created = skill.execute(
        {
            "action": "create_session",
            "spend_cap_usd": 1.0,
            "network": "base-sepolia",
            "live": True,
        }
    )
    print(
        json.dumps(
            {
                k: created.get(k)
                for k in (
                    "status",
                    "session_id",
                    "wallet_address",
                    "settlement",
                    "signing",
                    "error",
                    "agent_hint",
                )
                if k in created or created.get("status") != "ready"
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    run_offline()
    if os.environ.get("EPHEMERAL_WALLET_LIVE") == "1":
        run_live_session_only()

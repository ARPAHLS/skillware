"""
Pay a contact on Base, then email them the receipt — reproducible SkillContext chain.

Natural-language intent (for your agent or docs):
  "Pay Alice 0.01 ETH on Base for the work, and email her the transaction link."

Prerequisites (live run):
  pip install "skillware[office_gmail_handler,defi_evm_tx_handler]"

  1. .env (never commit):
       GMAIL_ADDRESS, GMAIL_APP_PASSWORD
       AGENT_WALLET_PRIVATE_KEY (or AGENT_PRIVATE_KEY)
       BASE_RPC_URL
     See docs/usage/api_keys.md

  2. Shared address book — contact must have emails + public_0x:
       skillware addressbook init
       skillware addressbook add --name "Alice" --email alice@example.com --wallet 0x…
     See docs/usage/addressbook_operator_config.md

  3. EVM operator config:
       skillware evm init
     See docs/usage/evm_operator_config.md

Edit the RECIPE block below (contact name, amount, chain), then:

  python examples/pay_and_notify_demo.py

CI / offline smoke only (mocked Web3 + SMTP):
  PAY_NOTIFY_DEMO=1 python examples/pay_and_notify_demo.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict

from skillware import SkillContext
from skillware.core.env import load_env_file

from pay_and_notify_common import (
    AMOUNT_ETH,
    ASSET,
    CHAIN,
    CONTACT_QUERY,
    EMAIL_SUBJECT,
    EVM_SKILL,
    GMAIL_SKILL,
    TRANSFER_RECIPIENT,
    check_prerequisites,
    contact_emails,
    demo_mode_enabled,
    demo_mocks,
    write_demo_addressbook,
)

# --- RECIPE: change these for your operator setup ---
# CONTACT_QUERY / TRANSFER_RECIPIENT must match a row in ~/.config/skillware/addressbook.yaml


def build_notify_body(*, amount_eth: float, tx_hash: str, explorer_url: str) -> str:
    return (
        f"Hi,\n\n"
        f"Payment sent: {amount_eth} {ASSET.upper()} on {CHAIN.title()}.\n\n"
        f"Transaction: {tx_hash}\n"
        f"Explorer: {explorer_url}\n"
    )


def run_pay_and_notify_chain(ctx: SkillContext) -> Dict[str, Any]:
    """Manual host chain — same pattern as examples/deck_builder_chain_demo.py."""

    print("=== Step 1: resolve recipient (office/gmail_handler) ===")
    resolved = ctx.execute(
        GMAIL_SKILL,
        {"action": "resolve_recipients", "query": [CONTACT_QUERY]},
    )
    print(json.dumps(resolved, indent=2))
    if resolved.get("status") != "ready" or not resolved.get("resolved"):
        return {"status": "aborted", "step": "resolve_recipients", "detail": resolved}

    print(
        f"\n=== Step 2: transfer {AMOUNT_ETH} {ASSET} on {CHAIN} (defi/evm_tx_handler) ==="
    )
    transfer = ctx.execute(
        EVM_SKILL,
        {
            "action": "transfer",
            "confirmed": True,
            "intent": {
                "chain": CHAIN,
                "target_asset": ASSET,
                "amount": AMOUNT_ETH,
                "recipient": TRANSFER_RECIPIENT,
            },
        },
    )
    print(json.dumps(transfer, indent=2))
    if transfer.get("status") != "confirmed":
        return {"status": "aborted", "step": "transfer", "detail": transfer}

    tx_hash = transfer["tx_hash"]
    explorer = transfer.get("explorer_url", "")
    to_addrs = contact_emails(TRANSFER_RECIPIENT)
    if not to_addrs:
        first = resolved["resolved"][0]
        email = first.get("email") if isinstance(first, dict) else None
        if email:
            to_addrs = [email]

    print("\n=== Step 3: email receipt (office/gmail_handler) ===")
    notify = ctx.execute(
        GMAIL_SKILL,
        {
            "action": "send",
            "confirmed": True,
            "to": to_addrs,
            "subject": EMAIL_SUBJECT,
            "body_plain": build_notify_body(
                amount_eth=AMOUNT_ETH,
                tx_hash=tx_hash,
                explorer_url=explorer,
            ),
        },
    )
    print(json.dumps(notify, indent=2))
    return {"status": "ok", "transfer": transfer, "notify": notify}


def main() -> None:
    load_env_file()

    if demo_mode_enabled():
        print("PAY_NOTIFY_DEMO=1 — mocked Web3/SMTP for smoke tests only.\n")
        print(
            "For a real run: configure .env + addressbook + evm.yaml, unset PAY_NOTIFY_DEMO.\n"
        )
        os.environ.setdefault("GMAIL_ADDRESS", "agent@example.com")
        os.environ.setdefault("GMAIL_APP_PASSWORD", "demo")
        os.environ.setdefault("AGENT_WALLET_PRIVATE_KEY", "0x" + "11" * 32)
        os.environ.setdefault("BASE_RPC_URL", "http://127.0.0.1:8545")
        with tempfile.TemporaryDirectory() as tmp:
            book = Path(tmp) / "addressbook.yaml"
            write_demo_addressbook(book)
            os.environ["GMAIL_ADDRESSBOOK_PATH"] = str(book)
            ctx = SkillContext(skills=[EVM_SKILL, GMAIL_SKILL], mode="brief")
            with demo_mocks(ctx):
                run_pay_and_notify_chain(ctx)
        print("\nDemo complete.")
        return

    missing = check_prerequisites()
    if missing:
        print("Setup incomplete — fix the following, then re-run:\n")
        for item in missing:
            print(f"  - {item}")
        print("\nDocs:")
        print("  - docs/usage/api_keys.md")
        print("  - docs/usage/addressbook_operator_config.md")
        print("  - docs/usage/evm_operator_config.md")
        print("  - docs/usage/skill_chaining.md")
        sys.exit(1)

    ctx = SkillContext(skills=[EVM_SKILL, GMAIL_SKILL], mode="brief")
    print("SkillContext:", ", ".join(ctx.skill_ids))
    print(
        f"Recipe: pay {AMOUNT_ETH} {ASSET} on {CHAIN} to {TRANSFER_RECIPIENT!r}, "
        f"then email {CONTACT_QUERY!r}\n"
    )
    result = run_pay_and_notify_chain(ctx)
    if result.get("status") != "ok":
        sys.exit(1)
    print("\nChain complete.")


if __name__ == "__main__":
    main()

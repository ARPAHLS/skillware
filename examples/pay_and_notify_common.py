"""Shared config and optional demo mocks for pay_and_notify_demo.py."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Iterator, List
from unittest.mock import MagicMock, patch

from skillware.core.evm_config import is_rpc_configured, resolve_evm_config_path

if TYPE_CHECKING:
    from skillware.context import SkillContext
from skillware.core.loader import SkillLoader
from skillware.core.env import load_env_file
from skillware.core.mail_config import (
    init_addressbook_file,
    load_addressbook_yaml,
    resolve_addressbook_path,
    resolve_recipient_query,
)

GMAIL_SKILL = "office/gmail_handler"
EVM_SKILL = "defi/evm_tx_handler"

# --- Recipe defaults (edit in pay_and_notify_demo.py or here) ---
CONTACT_QUERY = "Alice"
TRANSFER_RECIPIENT = "alice"  # contact id or alias passed to evm transfer
CHAIN = "base"
ASSET = "eth"
AMOUNT_ETH = 0.01
EMAIL_SUBJECT = "Payment sent on Base"


def demo_mode_enabled() -> bool:
    return os.environ.get("PAY_NOTIFY_DEMO", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


def write_demo_addressbook(path: Path) -> None:
    init_addressbook_file(path)
    data = load_addressbook_yaml(path)
    data["contacts"] = {
        TRANSFER_RECIPIENT: {
            "display_name": CONTACT_QUERY,
            "emails": ["alice@example.com"],
            "aliases": ["Ali"],
            "public_0x": "0x3333333333333333333333333333333333333333",
        }
    }
    import yaml

    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def check_prerequisites() -> List[str]:
    """Return human-readable missing setup items (empty list = ready for live run)."""
    load_env_file()

    missing: List[str] = []
    if not os.environ.get("GMAIL_ADDRESS"):
        missing.append(".env: GMAIL_ADDRESS")
    if not os.environ.get("GMAIL_APP_PASSWORD"):
        missing.append(".env: GMAIL_APP_PASSWORD")
    if not os.environ.get("AGENT_WALLET_PRIVATE_KEY") and not os.environ.get(
        "AGENT_PRIVATE_KEY"
    ):
        missing.append(".env: AGENT_WALLET_PRIVATE_KEY")
    if CHAIN == "base" and not os.environ.get("BASE_RPC_URL"):
        missing.append(".env: BASE_RPC_URL")

    ab_path = resolve_addressbook_path()
    if not ab_path.is_file():
        missing.append(
            f"address book file missing ({ab_path}) — run: skillware addressbook init"
        )
    else:
        data = load_addressbook_yaml(ab_path)
        wallet = resolve_recipient_query(data, TRANSFER_RECIPIENT)
        if wallet.get("status") != "resolved":
            missing.append(
                f"contact {TRANSFER_RECIPIENT!r} needs public_0x — "
                "skillware addressbook set-wallet <id> <0x…>"
            )
        contact = data.get("contacts", {}).get(TRANSFER_RECIPIENT, {})
        if not contact.get("emails"):
            missing.append(
                f"contact {TRANSFER_RECIPIENT!r} needs emails — skillware addressbook add/edit"
            )

    evm_path = resolve_evm_config_path()
    if not evm_path.is_file():
        missing.append("evm.yaml missing — run: skillware evm init")

    if not demo_mode_enabled() and not is_rpc_configured(CHAIN):
        missing.append(
            f"RPC not configured for chain {CHAIN!r} (check BASE_RPC_URL in .env)"
        )

    return missing


def contact_emails(contact_id: str) -> List[str]:
    path = resolve_addressbook_path()
    data = load_addressbook_yaml(path)
    contact = data.get("contacts", {}).get(contact_id, {})
    emails = contact.get("emails") or []
    return [str(e).strip() for e in emails if str(e).strip()]


@contextmanager
def demo_mocks(ctx: "SkillContext") -> Iterator[None]:
    """Patch the same skill classes SkillContext.execute uses."""
    evm_cls = SkillLoader.get_skill_class(dict(ctx.prepare(EVM_SKILL).bundle))
    mail_cls = SkillLoader.get_skill_class(dict(ctx.prepare(GMAIL_SKILL).bundle))

    w3 = MagicMock()
    w3.eth.gas_price = 10**9
    w3.eth.get_transaction_count.return_value = 0
    w3.eth.get_balance = MagicMock(return_value=10**22)
    w3.to_wei.side_effect = lambda val, unit: (
        int(val * 10**9) if unit == "gwei" else int(val)
    )
    transport = MagicMock()
    transport.send_message.return_value = ("<demo@skillware.local>", "250 OK")

    patches = [
        patch.object(evm_cls, "_get_web3", return_value=w3),
        patch.object(evm_cls, "_token_balance_wei", return_value=10**22),
        patch.object(evm_cls, "_sign_and_send", return_value="0x" + "ab" * 32),
        patch.object(
            evm_cls,
            "_wait_receipt",
            return_value={"block_number": 42, "gas_used": 21000, "success": True},
        ),
        patch.object(mail_cls, "_get_transport", return_value=transport),
    ]
    for item in patches:
        item.start()
    try:
        yield None
    finally:
        for item in reversed(patches):
            item.stop()

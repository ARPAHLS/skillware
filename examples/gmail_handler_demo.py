"""
Mocked demo for office/gmail_handler.

Runs resolve -> preview_send -> blocked send -> search -> read with mocked IMAP/SMTP.
No live Gmail credentials required.

Usage:
  python examples/gmail_handler_demo.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gmail_handler_common import (  # noqa: E402
    MOCK_INBOX_SUMMARIES,
    MOCK_MESSAGE,
    SKILL_ID,
    print_step,
)
from skillware.core.loader import SkillLoader  # noqa: E402


def main() -> None:
    print("DEMO MODE: mocked IMAP/SMTP — no live Gmail credentials required.\n")

    with tempfile.TemporaryDirectory() as tmp:
        book_path = Path(tmp) / "addressbook.yaml"
        book_path.write_text(
            yaml.safe_dump(
                {
                    "contacts": {
                        "john_taller": {
                            "display_name": "John Taller",
                            "emails": ["john@skillware.site"],
                            "aliases": ["John", "Jon"],
                        }
                    }
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        os.environ["GMAIL_ADDRESSBOOK_PATH"] = str(book_path)
        os.environ.setdefault("GMAIL_ADDRESS", "agent@example.com")
        os.environ.setdefault("GMAIL_APP_PASSWORD", "demo-password")

        bundle = SkillLoader.load_skill(SKILL_ID)
        skill = bundle["class"]()

        transport = MagicMock()
        transport.search_uids.return_value = [8421, 8422]
        transport.fetch_summaries.return_value = MOCK_INBOX_SUMMARIES
        transport.fetch_message.return_value = MOCK_MESSAGE
        transport.mailbox_status.return_value = {
            "mailbox": "INBOX",
            "unread_count": 1,
            "highest_uid": 8422,
        }

        with patch.object(skill, "_get_transport", return_value=transport):
            resolve = skill.execute(
                {"action": "resolve_recipients", "query": ["John"]},
            )
            print_step("resolve_recipients", resolve)

            preview = skill.execute(
                {
                    "action": "preview_send",
                    "context": resolve.get("context", {}),
                    "to": ["john@skillware.site"],
                    "subject": "Re: Friday",
                    "body_plain": "We cannot make it this Friday.",
                }
            )
            print_step("preview_send", preview)

            blocked = skill.execute(
                {
                    "action": "send",
                    "context": preview.get("context", {}),
                    "to": ["john@skillware.site"],
                    "subject": "Re: Friday",
                    "body_plain": "We cannot make it this Friday.",
                }
            )
            print_step("send (expect needs_confirmation)", blocked)

            search = skill.execute(
                {
                    "action": "search_messages",
                    "from_names": ["John"],
                    "limit": 5,
                    "update_cursor": False,
                }
            )
            print_step("search_messages", search)

            read = skill.execute({"action": "read_message", "uid": 8422})
            print_step("read_message", read)

    print("\nDemo complete.")


if __name__ == "__main__":
    main()

"""
Interactive Gemini agent loop for office/gmail_handler.

Demonstrates resolve, search, read, preview/send, and reply flows via Gemini
tool calling. Uses a dedicated agent Gmail account for live IMAP/SMTP.

Environment (live mode):
  GOOGLE_API_KEY
  GMAIL_ADDRESS          — dedicated agent mailbox (NOT your personal inbox)
  GMAIL_APP_PASSWORD     — App Password for that mailbox

Optional:
  GMAIL_ADDRESSBOOK_PATH
  GMAIL_SCAN_STATE_PATH
  GMAIL_SEND_LEDGER_PATH

Demo mode (mocked IMAP/SMTP, no Gmail credentials):
  GMAIL_HANDLER_EXAMPLE_DEMO=1 python examples/gemini_gmail_handler.py

Usage:
  python examples/gemini_gmail_handler.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator
from unittest.mock import MagicMock, patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gmail_handler_common import (  # noqa: E402
    MOCK_INBOX_SUMMARIES,
    MOCK_MESSAGE,
    SKILL_ID,
    handle_tool_call,
)
from skillware.core.env import load_env_file  # noqa: E402
from skillware.core.loader import SkillLoader  # noqa: E402


def demo_mode_enabled() -> bool:
    return os.environ.get("GMAIL_HANDLER_EXAMPLE_DEMO", "").strip() in {
        "1",
        "true",
        "yes",
    }


@contextmanager
def demo_skill() -> Iterator[Any]:
    """Yield a skill instance with mocked transport for demo mode."""
    with tempfile.TemporaryDirectory() as tmp:
        book_path = Path(tmp) / "addressbook.yaml"
        book_path.write_text(
            yaml.safe_dump(
                {
                    "contacts": {
                        "john_taller": {
                            "display_name": "John Taller",
                            "emails": ["john@example.com"],
                            "aliases": ["John"],
                            "org": "Example Corp",
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
            yield skill


def main() -> None:
    load_env_file()

    if demo_mode_enabled():
        print("DEMO MODE: mocked IMAP/SMTP — no live Gmail credentials required.\n")
        with demo_skill() as skill:
            for action, args in [
                (
                    "resolve_recipients",
                    {"action": "resolve_recipients", "query": ["Ross"]},
                ),
                (
                    "mailbox_status",
                    {"action": "mailbox_status"},
                ),
                (
                    "search_messages",
                    {"action": "search_messages", "from_names": ["Ross"], "limit": 3},
                ),
            ]:
                result = skill.execute(args)
                print(f"\n--- {action} ---")
                print(json.dumps(result, indent=2)[:2500])
        return

    import google.genai as genai
    from google.genai import types

    bundle = SkillLoader.load_skill(SKILL_ID)
    skill = bundle["class"]()
    client = genai.Client()
    tool = SkillLoader.to_gemini_tool(bundle)
    system_instruction = bundle["instructions"]
    tool_name = SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"])

    print("\n" + "=" * 60)
    print("Gmail Handler — Gemini Agent")
    print("=" * 60)
    print("Uses a DEDICATED agent Gmail account (GMAIL_ADDRESS), not personal mail.")
    print("Try asking:")
    print("  - 'What is my mailbox status?'")
    print("  - 'Any unread mail from Ross?'")
    print("  - 'Resolve recipient Ross and preview an email about a schedule change'")
    print("\nType 'exit' or 'quit' to stop.")
    print("=" * 60)

    chat = client.chats.create(
        model="gemini-2.5-flash",
        config=types.GenerateContentConfig(
            tools=[tool],
            system_instruction=system_instruction,
        ),
    )

    while True:
        try:
            user_query = input("\nUser: ").strip()
        except EOFError:
            break

        if not user_query:
            continue
        if user_query.lower() in ("exit", "quit"):
            break

        response = chat.send_message(user_query)

        while response.function_calls:
            tool_call = response.function_calls[0]
            fn_name = tool_call.name
            fn_args = dict(tool_call.args)

            print("\n--- Tool Call ---")
            print(f"Function: {fn_name}")
            print(f"Arguments: {json.dumps(fn_args, indent=2)}")

            if fn_name != tool_name:
                api_result = {"status": "error", "message": f"Unknown tool: {fn_name}"}
            else:
                api_result = handle_tool_call(skill, fn_args)

            print("\n--- Skill Result ---")
            print(json.dumps(api_result, indent=2)[:4000])

            response = chat.send_message(
                types.Part.from_function_response(
                    name=fn_name,
                    response={"result": api_result},
                )
            )

        if response.text:
            print(f"\nAgent: {response.text}")


if __name__ == "__main__":
    main()

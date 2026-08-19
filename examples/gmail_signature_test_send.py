#!/usr/bin/env python3
"""
Send (or preview) one outbound mail to verify skillware mail signature setup.

Requires a dedicated agent mailbox in .env:
  GMAIL_ADDRESS, GMAIL_APP_PASSWORD

Run signature init first:
  skillware mail signature init

Usage (from repo root):
  python examples/gmail_signature_test_send.py --to you@example.com
  python examples/gmail_signature_test_send.py --to you@example.com --preview-only
"""

from __future__ import annotations

import argparse
import json
import sys

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

from gmail_handler_common import SKILL_ID


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Preview or send a single test message with configured signature.",
    )
    parser.add_argument(
        "--to",
        required=True,
        help="Recipient email address.",
    )
    parser.add_argument(
        "--subject",
        default="Skillware signature test",
        help="Email subject line.",
    )
    parser.add_argument(
        "--body",
        default="Live signature test — please confirm logo + links render.",
        help="Plain body before signature append.",
    )
    parser.add_argument(
        "--preview-only",
        action="store_true",
        help="Call preview_send only (no SMTP).",
    )
    args = parser.parse_args()

    load_env_file()
    skill = SkillLoader.load_skill(SKILL_ID)["class"]()

    action = "preview_send" if args.preview_only else "send"
    payload = {
        "action": action,
        "to": [args.to],
        "subject": args.subject,
        "body_plain": args.body,
    }
    if action == "send":
        payload["confirmed"] = True

    result = skill.execute(payload)
    print(json.dumps(result, indent=2, default=str))

    status = (result or {}).get("status", "")
    if status in {"ready", "sent", "ok"}:
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())

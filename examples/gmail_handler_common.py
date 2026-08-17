"""Shared constants and helpers for gmail_handler examples."""

from __future__ import annotations

from typing import Any, Dict, List

SKILL_ID = "office/gmail_handler"

MOCK_INBOX_SUMMARIES: List[Dict[str, Any]] = [
    {
        "uid": 8422,
        "from": "John Taller <john@skillware.site>",
        "from_email": "john@skillware.site",
        "to": "agent@example.com",
        "subject": "Friday meetup",
        "date": "Sun, 24 May 2026 14:32:00 +0300",
        "snippet": "Can we still meet this Friday?",
        "unread": True,
        "folder": "INBOX",
    }
]

MOCK_MESSAGE: Dict[str, Any] = {
    "uid": 8422,
    "folder": "INBOX",
    "from": "John Taller <john@skillware.site>",
    "from_email": "john@skillware.site",
    "to": ["agent@example.com"],
    "subject": "Friday meetup",
    "date": "Sun, 24 May 2026 14:32:00 +0300",
    "body_plain": "Hi,\n\nCan we still meet this Friday?\n\nThanks,\nJohn",
    "body_html_stripped": None,
    "message_id": "<john-friday@skillware.site>",
    "in_reply_to": "",
    "references": [],
    "untrusted_content": True,
    "snippet": "Can we still meet this Friday?",
}


def handle_tool_call(skill: Any, fn_args: Dict[str, Any]) -> Dict[str, Any]:
    """Execute one gmail_handler tool call and return the JSON envelope."""
    return skill.execute(fn_args)


def print_step(title: str, payload: Dict[str, Any]) -> None:
    print(f"\n=== {title} ===")
    for key in ("status", "code", "agent_hint", "missing_fields"):
        if key in payload:
            print(f"{key}: {payload[key]}")
    if "resolved" in payload:
        print("resolved:", payload["resolved"])
    if "ambiguous" in payload and payload["ambiguous"]:
        print("ambiguous:", payload["ambiguous"])
    if "preview" in payload:
        preview = payload["preview"]
        print(
            "preview:",
            {
                "to": preview.get("to"),
                "subject": preview.get("subject"),
                "body_plain": (preview.get("body_plain") or "")[:120],
            },
        )
    if "matches" in payload:
        print("matches:", payload["matches"])
    if "message" in payload:
        msg = payload["message"]
        print(
            "message:",
            {
                "from": msg.get("from"),
                "subject": msg.get("subject"),
                "body_plain": (msg.get("body_plain") or "")[:120],
            },
        )

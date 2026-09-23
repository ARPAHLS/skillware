"""
Minimal interactive Gemini loop for office/gmail_handler.

Prerequisites (.env — see docs/usage/api_keys.md):
  GOOGLE_API_KEY
  GMAIL_ADDRESS          dedicated agent mailbox (not your personal inbox)
  GMAIL_APP_PASSWORD     App Password for that mailbox

Optional: skillware addressbook init + add contacts (docs/usage/addressbook_operator_config.md)

Install:
  pip install "skillware[office_gmail_handler,gemini]"

Run:
  python examples/gemini_gmail_minimal.py
"""

from __future__ import annotations

import os
import sys

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

SKILL_ID = "office/gmail_handler"


def _missing_env() -> list[str]:
    load_env_file()
    missing = []
    if not os.environ.get("GOOGLE_API_KEY"):
        missing.append("GOOGLE_API_KEY")
    if not os.environ.get("GMAIL_ADDRESS"):
        missing.append("GMAIL_ADDRESS")
    if not os.environ.get("GMAIL_APP_PASSWORD"):
        missing.append("GMAIL_APP_PASSWORD")
    return missing


def main() -> None:
    missing = _missing_env()
    if missing:
        print("Missing environment variables:", ", ".join(missing))
        print("Copy .env.example to .env and set Gmail + Gemini keys.")
        print("Guide: docs/usage/api_keys.md")
        sys.exit(1)

    import google.genai as genai
    from google.genai import types

    bundle = SkillLoader.load_skill(SKILL_ID)
    skill = bundle["class"]()
    tool_name = SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"])
    client = genai.Client()
    chat = client.chats.create(
        model=os.environ.get("GEMINI_MODEL", "gemini-3.5-flash"),
        config=types.GenerateContentConfig(
            tools=[SkillLoader.to_gemini_tool(bundle)],
            system_instruction=bundle["instructions"],
        ),
    )

    print("Gemini + Gmail Handler — type a request (exit to quit)\n")
    while True:
        try:
            user = input("You: ").strip()
        except EOFError:
            break
        if not user or user.lower() in {"exit", "quit"}:
            break

        response = chat.send_message(user)
        while response.function_calls:
            call = response.function_calls[0]
            result = skill.execute(dict(call.args))
            response = chat.send_message(
                types.Part.from_function_response(
                    name=call.name,
                    response={"result": result},
                )
            )
        if response.text:
            print(f"Agent: {response.text}\n")


if __name__ == "__main__":
    main()

"""
Interactive Gemini agent loop for finance/uk_companies_house_handler (v1.2.1).

Demonstrates an interactive flow with turn-by-turn pipeline orchestration and composites:
  - map_intent / run_pipeline for multi-intent queries
  - resolve_and_get_officers / resolve_and_get_filings for single-intent shortcuts
  - needs_input disambiguation resume via lean context or follow-up user message
  - record truncation limits (10-item default) with full record rendering

The agent must pass clean query strings and optional role_hint — the skill does
not parse conversational prefixes. When the skill returns needs_input, show
candidates to the user and continue the chat with a company number or name.

Environment (live mode):
  GOOGLE_API_KEY
  COMPANIES_HOUSE_API_KEY

Usage:
  python examples/gemini_uk_companies_house_handler.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from uk_companies_house_handler_common import (  # noqa: E402
    SKILL_ID,
    handle_tool_call,
)
from skillware.core.env import load_env_file  # noqa: E402
from skillware.core.loader import SkillLoader  # noqa: E402


def _print_needs_input_hint(result: dict) -> None:
    if result.get("status") != "needs_input":
        return
    candidates = result.get("candidates") or []
    if not candidates:
        return
    print("\n--- Disambiguation needed ---")
    for idx, candidate in enumerate(candidates[:5], 1):
        print(
            f"  {idx}. {candidate.get('title')} "
            f"({candidate.get('company_number')}) — {candidate.get('company_status')}"
        )
    print("Reply with the company number or full name to continue.\n")


def main() -> None:
    load_env_file()

    import google.genai as genai
    from google.genai import types

    bundle = SkillLoader.load_skill(SKILL_ID)
    skill = bundle["class"]()
    client = genai.Client()

    tool = SkillLoader.to_gemini_tool(bundle)
    expected_tool_name = SkillLoader._sanitize_gemini_tool_name(
        bundle["manifest"]["name"]
    )
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

    system_instruction = bundle["instructions"]

    print("\n" + "=" * 60)
    print("UK Companies House Gemini Agent")
    print("=" * 60)
    print("This agent can look up UK companies, officers, PSCs, and filings.")
    print("Try asking:")
    print("  - 'Who is the CEO of BP?' (agent should pass query='BP', role_hint='ceo')")
    print("  - 'Show me officers and filings for Tesco' (map_intent + run_pipeline)")
    print(
        "  - 'Get me the CEO of Tesco and its 10-K' (intent translation + run_pipeline)"
    )
    print("  - 'Who owns Monzo?'")
    print("\nType 'exit' or 'quit' to stop.")
    print("=" * 60)

    chat = client.chats.create(
        model=model,
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

            print("--- Tool Call ---")
            print(f"Function: {fn_name}")
            print(f"Arguments: {json.dumps(fn_args, indent=2)}")

            if fn_name != expected_tool_name:
                print(f"Unknown tool: {fn_name}")
                api_result = {"error": f"Unknown tool: {fn_name}"}
            else:
                api_result = handle_tool_call(skill, fn_args)

            print("\n--- Skill Result ---")
            print(json.dumps(api_result, indent=2))
            _print_needs_input_hint(api_result)

            response = chat.send_message(
                types.Part.from_function_response(
                    name=fn_name, response={"result": api_result}
                )
            )

        if response.text:
            print(f"\nAgent: {response.text}")


if __name__ == "__main__":
    main()

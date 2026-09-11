"""
Interactive Claude agent loop for finance/uk_companies_house_handler (v2b).

Demonstrates an interactive flow with pipeline orchestration and composites:
  - map_intent / run_pipeline for multi-intent queries
  - resolve_and_get_officers / resolve_and_get_filings for single-intent shortcuts
  - needs_input disambiguation resume via context or follow-up user message
  - partial previews (10-item limits) with full record rendering

The agent must pass clean query strings and optional role_hint — the skill does
not parse conversational prefixes. When the skill returns needs_input, show
candidates to the user and continue the loop with a company number or name.

Environment (live mode):
  ANTHROPIC_API_KEY
  COMPANIES_HOUSE_API_KEY

Usage:
  python examples/claude_uk_companies_house_handler.py
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

    import anthropic

    bundle = SkillLoader.load_skill(SKILL_ID)
    skill = bundle["class"]()
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    tools = [SkillLoader.to_claude_tool(bundle)]
    tool_name = tools[0]["name"]
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

    system_instruction = bundle["instructions"]

    print("\n" + "=" * 60)
    print("UK Companies House Claude Agent")
    print("=" * 60)
    print("This agent can look up UK companies, officers, PSCs, and filings.")
    print("Try asking:")
    print("  - 'Who is the CEO of BP?' (agent should pass query='BP', role_hint='ceo')")
    print("  - 'Show me officers and filings for Tesco' (map_intent + run_pipeline)")
    print("  - 'Who owns Monzo?'")
    print("\nType 'exit' or 'quit' to stop.")
    print("=" * 60)

    messages: list[dict] = []

    while True:
        try:
            user_query = input("\nUser: ").strip()
        except EOFError:
            break

        if not user_query:
            continue

        if user_query.lower() in ("exit", "quit"):
            break

        messages.append({"role": "user", "content": user_query})

        while True:
            response = client.messages.create(
                model=model,
                max_tokens=2048,
                system=system_instruction,
                tools=tools,
                messages=messages,
            )

            if response.stop_reason != "tool_use":
                for block in response.content:
                    if getattr(block, "text", None):
                        print(f"\nAgent: {block.text}")
                messages.append({"role": "assistant", "content": response.content})
                break

            tool_uses = [b for b in response.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []

            for tool_use in tool_uses:
                print("--- Tool Call ---")
                print(f"Function: {tool_use.name}")
                print(f"Arguments: {json.dumps(tool_use.input, indent=2)}")

                if tool_use.name != tool_name:
                    print(f"Unknown tool: {tool_use.name}")
                    payload = {"error": f"Unknown tool: {tool_use.name}"}
                else:
                    payload = handle_tool_call(skill, dict(tool_use.input))

                print("\n--- Skill Result ---")
                print(json.dumps(payload, indent=2))
                _print_needs_input_hint(payload)

                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(payload),
                    }
                )

            messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    main()

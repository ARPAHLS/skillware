# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""
Multi-turn Claude agent loop for office/pdf_form_filler v0.2.2.

Demonstrates curated IRS Form W-9 discovery, tax classification radio group
selection, PII-masked preview, and explicit confirmation gating.
"""

import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import anthropic  # noqa: E402
from skillware.core.env import load_env_file  # noqa: E402
from skillware.core.loader import SkillLoader  # noqa: E402


def main() -> None:
    load_env_file()

    skill_bundle = SkillLoader.load_skill("office/pdf_form_filler")
    print(f"Loaded Skill: {skill_bundle['manifest']['name']}")

    pdf_skill = skill_bundle["class"]()
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    claude_tool = SkillLoader.to_claude_tool(skill_bundle)
    tool_name = claude_tool["name"]
    model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-0")

    user_query = (
        "Inspect the curated 'us_irs_w9' template schema, validate a draft for "
        "John Smith (Individual/sole proprietor) at 123 Main St, Austin, TX 78701, "
        "and return a PII-redacted fill preview without writing the final file yet."
    )
    print(f"User: {user_query}")

    messages = [{"role": "user", "content": user_query}]

    for _turn in range(6):
        message = client.messages.create(
            model=model,
            max_tokens=1024,
            system=skill_bundle["instructions"],
            messages=messages,
            tools=[claude_tool],
        )

        if message.stop_reason != "tool_use":
            text_blocks = [b.text for b in message.content if hasattr(b, "text")]
            print("\nClaude:", "\n".join(text_blocks))
            break

        messages.append({"role": "assistant", "content": message.content})
        tool_results = []

        for block in message.content:
            if block.type != "tool_use":
                continue
            print(f"\nClaude calls: {block.name}({json.dumps(block.input)})")
            if block.name == tool_name:
                try:
                    result = pdf_skill.execute(block.input)
                except Exception as exc:
                    result = {"status": "error", "message": str(exc)}
            else:
                result = {"status": "error", "message": f"Unknown tool: {block.name}"}

            print(f"Tool result: {json.dumps(result, indent=2)}")
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                }
            )

        messages.append({"role": "user", "content": tool_results})


if __name__ == "__main__":
    main()

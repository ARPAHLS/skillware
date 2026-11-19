# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""
Multi-turn OpenAI agent loop for office/pdf_form_filler v0.2.2.

Demonstrates template discovery (bundled + custom PDF_TEMPLATES_DIR),
section-chunked schema retrieval, and configurable PDF_OUTPUT_DIR routing.
"""

import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from openai import OpenAI  # noqa: E402
from skillware.core.env import load_env_file  # noqa: E402
from skillware.core.loader import SkillLoader  # noqa: E402


def main() -> None:
    load_env_file()

    skill_bundle = SkillLoader.load_skill("office/pdf_form_filler")
    print(f"Loaded Skill: {skill_bundle['manifest']['name']}")

    pdf_skill = skill_bundle["class"]()
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    openai_tool = SkillLoader.to_openai_tool(skill_bundle)
    tool_name = openai_tool["function"]["name"]
    model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    user_query = (
        "List available PDF form templates, then fetch Part I of 'us_irs_w8ben' "
        "and summarize which fields are required."
    )
    print(f"User: {user_query}")

    messages = [
        {"role": "system", "content": skill_bundle["instructions"]},
        {"role": "user", "content": user_query},
    ]

    for _turn in range(6):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=[openai_tool],
            tool_choice="auto",
        )
        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            print(f"\nOpenAI: {msg.content}")
            break

        for tc in msg.tool_calls:
            fn_args = json.loads(tc.function.arguments or "{}")
            print(f"\nOpenAI calls: {tc.function.name}({json.dumps(fn_args)})")
            if tc.function.name == tool_name:
                try:
                    result = pdf_skill.execute(fn_args)
                except Exception as exc:
                    result = {"status": "error", "message": str(exc)}
            else:
                result = {
                    "status": "error",
                    "message": f"Unknown tool: {tc.function.name}",
                }

            print(f"Tool result: {json.dumps(result, indent=2)}")
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result),
                }
            )


if __name__ == "__main__":
    main()

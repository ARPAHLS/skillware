# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""
Multi-turn Gemini agent loop for office/pdf_form_filler v0.2.2.

Demonstrates a Smart Interview workflow on the curated IRS Form W-8BEN template
(`session_init` -> `session_update` -> `session_preview` -> `session_finalize`)
using Skillware's host-agnostic PDF engine (no Anthropic key required).
"""

import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import google.genai as genai  # noqa: E402
from google.genai import types  # noqa: E402
from skillware.core.env import load_env_file  # noqa: E402
from skillware.core.loader import SkillLoader  # noqa: E402


def main() -> None:
    load_env_file()

    skill_bundle = SkillLoader.load_skill("office/pdf_form_filler")
    print(f"Loaded Skill: {skill_bundle['manifest']['name']}")

    pdf_skill = skill_bundle["class"]()
    client = genai.Client()
    tool = SkillLoader.to_gemini_tool(skill_bundle)
    system_instruction = skill_bundle["instructions"]
    tool_name = SkillLoader._sanitize_gemini_tool_name(skill_bundle["manifest"]["name"])
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    user_query = (
        "Help me start a W-8BEN tax form session (template_id='us_irs_w8ben') "
        "for Jane Doe, citizen of Greece, living at 10 Ermou St, Athens 10563, Greece. "
        "Initialize the session, store these fields, and show me the PII-masked preview."
    )
    print(f"User: {user_query}")

    history = [
        types.Content(role="user", parts=[types.Part.from_text(text=user_query)])
    ]

    for _turn in range(6):
        response = client.models.generate_content(
            model=model,
            contents=history,
            config=types.GenerateContentConfig(
                tools=[tool],
                system_instruction=system_instruction,
            ),
        )
        if not response.candidates:
            break

        candidate_content = response.candidates[0].content
        history.append(candidate_content)

        function_calls = [
            p.function_call for p in (candidate_content.parts or []) if p.function_call
        ]
        if not function_calls:
            print(f"\nAgent: {response.text}")
            break

        response_parts = []
        for fc in function_calls:
            fn_name = fc.name
            fn_args = dict(fc.args or {})
            print(f"\nAgent calls: {fn_name}({json.dumps(fn_args)})")

            if fn_name == tool_name:
                try:
                    result = pdf_skill.execute(fn_args)
                except Exception as exc:
                    result = {"status": "error", "message": str(exc)}
            else:
                result = {"status": "error", "message": f"Unknown tool: {fn_name}"}

            print(f"Tool result: {json.dumps(result, indent=2)}")
            response_parts.append(
                types.Part.from_function_response(
                    name=fn_name,
                    response={"result": result},
                )
            )

        history.append(types.Content(role="user", parts=response_parts))


if __name__ == "__main__":
    main()

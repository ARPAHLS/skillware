"""
Non-interactive Gemini agent loop for finance/uk_companies_house_handler.

Demonstrates the full "Who is the CEO of BP?" flow:
  1. map_intent -- translate intent keywords to an action pipeline
  2. resolve_company -- search by name, receive ranked candidates
  3. Agent disambiguates (scripted: picks BP P.L.C.)
  4. get_officers -- list directors for the resolved company number

Environment (live mode):
  GOOGLE_API_KEY
  COMPANIES_HOUSE_API_KEY

Usage:
  python examples/gemini_uk_companies_house_handler.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from uk_companies_house_handler_common import (  # noqa: E402
    SKILL_ID,
    handle_tool_call,
)
from skillware.core.env import load_env_file  # noqa: E402
from skillware.core.loader import SkillLoader  # noqa: E402


def main() -> None:
    load_env_file()

    import google.genai as genai
    from google.genai import types

    bundle = SkillLoader.load_skill(SKILL_ID)
    skill = bundle["module"].UkCompaniesHouseHandlerSkill()
    client = genai.Client()

    # Convert the manifest to a Gemini function declaration and sanitize the name
    gemini_decl = SkillLoader.to_gemini_tool(bundle)
    gemini_decl["name"] = SkillLoader._sanitize_function_tool_name(gemini_decl["name"])
    tool = types.Tool(function_declarations=[gemini_decl])

    system_instruction = bundle["instructions"]

    user_query = "Who is the CEO of BP?"
    print(f"User: {user_query}\n")

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_query,
        config=types.GenerateContentConfig(
            tools=[tool],
            system_instruction=system_instruction,
        ),
    )

    while response.candidates and response.candidates[0].content.parts:
        part = response.candidates[0].content.parts[0]
        if not part.function_call:
            break

        fn_name = part.function_call.name
        fn_args = dict(part.function_call.args)
        print("--- Tool Call ---")
        print(f"Function: {fn_name}")
        print(f"Arguments: {json.dumps(fn_args, indent=2)}")

        expected_tool_name = SkillLoader._sanitize_function_tool_name(
            bundle["manifest"]["name"]
        )
        if fn_name != expected_tool_name:
            print(f"Unknown tool: {fn_name}")
            break

        api_result = handle_tool_call(skill, fn_args)
        print("\n--- Skill Result ---")
        print(json.dumps(api_result, indent=2))

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                "Use this tool result to answer the original request.",
                {
                    "function_response": {
                        "name": fn_name,
                        "response": {"result": api_result},
                    }
                },
            ],
            config=types.GenerateContentConfig(
                tools=[tool],
                system_instruction=system_instruction,
            ),
        )

    print("\nAgent Final Response:")
    print(response.text)


if __name__ == "__main__":
    main()

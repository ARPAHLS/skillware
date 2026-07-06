"""
Interactive Gemini chat for finance/uk_companies_house_handler.

Multi-turn conversation with full history retention. The agent can call
the Companies House skill as many times as needed across turns.

Environment:
  GOOGLE_API_KEY
  COMPANIES_HOUSE_API_KEY

Usage:
  python examples/gemini_uk_companies_house_handler.py

Type 'exit' or 'quit' to end the session.
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


def _build_gemini_tool(bundle):
    """Build a Gemini-compatible Tool from a skill bundle."""
    from google.genai import types

    raw = SkillLoader.to_gemini_tool(bundle)

    def _sanitize(schema):
        out = {}
        for key, val in schema.items():
            if key == "type" and isinstance(val, str):
                out[key] = val.upper()
            elif key == "properties" and isinstance(val, dict):
                out[key] = {k: _sanitize(v) for k, v in val.items()}
            elif key == "items" and isinstance(val, dict):
                out[key] = _sanitize(val)
            else:
                out[key] = val
        return out

    safe_name = raw["name"].replace("/", "_")
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name=safe_name,
                description=raw["description"],
                parameters=_sanitize(raw["parameters"]),
            )
        ]
    )


def _process_tool_calls(
    client, skill, tool, tool_name, system_instruction, response, history
):
    """Handle tool calls in a loop until the model produces a text response.

    Appends all model and tool-result turns to *history* so subsequent
    user turns see the full conversation.
    """
    from google.genai import types

    while response.candidates and response.candidates[0].content.parts:
        part = response.candidates[0].content.parts[0]
        if not part.function_call:
            break

        fn_name = part.function_call.name
        fn_args = dict(part.function_call.args)
        print("\n--- Tool Call ---")
        print(f"Function: {fn_name}")
        print(f"Arguments: {json.dumps(fn_args, indent=2)}")

        if fn_name != tool_name:
            print(f"ERROR: Unknown tool: {fn_name}")
            break

        # Record the model's function-call turn
        history.append(response.candidates[0].content)

        # Execute locally
        api_result = handle_tool_call(skill, fn_args)
        print("\n--- Skill Result ---")
        print(json.dumps(api_result, indent=2))

        # Build the function-response content and record it
        fn_response_part = types.Part.from_function_response(
            name=fn_name,
            response={"result": api_result},
        )
        fn_response_content = types.Content(
            role="user",
            parts=[fn_response_part],
        )
        history.append(fn_response_content)

        # Send full history back so the model has context
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=history,
            config=types.GenerateContentConfig(
                tools=[tool],
                system_instruction=system_instruction,
            ),
        )

    return response


def main() -> None:
    load_env_file()

    import google.genai as genai
    from google.genai import types

    bundle = SkillLoader.load_skill(SKILL_ID)
    skill = bundle["module"].UkCompaniesHouseHandlerSkill()
    client = genai.Client()
    tool = _build_gemini_tool(bundle)
    system_instruction = bundle["instructions"]
    tool_name = bundle["manifest"]["name"].replace("/", "_")

    # Conversation history — persists across turns
    history = []

    print("=" * 60)
    print("  UK Companies House - Interactive Chat")
    print("  Powered by Gemini + Skillware")
    print("=" * 60)
    print()
    print("Ask anything about UK companies — directors, owners,")
    print("filings, company details. Type 'exit' or 'quit' to stop.")
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "q"):
            print("Goodbye!")
            break

        # Append user turn
        history.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_input)],
            )
        )

        # Send full history
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=history,
            config=types.GenerateContentConfig(
                tools=[tool],
                system_instruction=system_instruction,
            ),
        )

        # Handle any tool calls
        response = _process_tool_calls(
            client,
            skill,
            tool,
            tool_name,
            system_instruction,
            response,
            history,
        )

        # Extract and display the final text
        if response.candidates and response.candidates[0].content.parts:
            # Record the model's text response in history
            history.append(response.candidates[0].content)
            agent_text = response.text
        else:
            agent_text = "(No response from agent)"

        print(f"\nAgent: {agent_text}\n")


if __name__ == "__main__":
    main()

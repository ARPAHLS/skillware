"""
Gemini agent loop for defi/evm_tx_handler.

Environment (live mode):
  GOOGLE_API_KEY
  AGENT_WALLET_PRIVATE_KEY
  BASE_RPC_URL and/or ETHEREUM_RPC_URL
  optional COINGECKO_API_KEY

Demo mode (mocked Web3, no live keys):
  EVM_TX_HANDLER_EXAMPLE_DEMO=1 python examples/gemini_evm_tx_handler.py
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from evm_tx_handler_common import (  # noqa: E402
    SKILL_ID,
    demo_mode_enabled,
    handle_tool_call,
    load_skill,
    run_scripted_flow,
)
from skillware.core.env import load_env_file  # noqa: E402
from skillware.core.loader import SkillLoader  # noqa: E402


def main() -> None:
    load_env_file()

    if demo_mode_enabled():
        print("DEMO MODE: mocked Web3 — no live RPC or signing.\n")
        with load_skill() as skill:
            run_scripted_flow(skill, execute=True)
        return

    import google.genai as genai
    from google.genai import types

    bundle = SkillLoader.load_skill(SKILL_ID)
    skill = bundle["module"].EvmTxHandlerSkill()
    client = genai.Client()
    tool = SkillLoader.to_gemini_tool(bundle)
    system_instruction = bundle["instructions"]
    # Derive the tool name from the manifest so this stays correct if the name changes
    TOOL_NAME = SkillLoader._sanitize_gemini_tool_name(bundle["manifest"]["name"])

    user_query = (
        "Plan a buy of 10 DEGEN on Base paying with USDC. "
        "Resolve missing fields, quote, show preview, then execute after I confirm."
    )
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
        print(f"Agent tool call: {fn_name} -> {json.dumps(fn_args)}")

        if fn_name != TOOL_NAME:
            print(f"Unknown tool: {fn_name}")
            break

        api_result = handle_tool_call(skill, fn_args)
        print(f"Skill result: {json.dumps(api_result, indent=2)[:2000]}...\n")

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                "Use this tool result and continue the trade workflow.",
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

    print("\nAgent final response:")
    print(response.text)


if __name__ == "__main__":
    main()

"""
Claude agent loop for defi/evm_tx_handler.

Environment (live mode):
  ANTHROPIC_API_KEY
  AGENT_WALLET_PRIVATE_KEY
  BASE_RPC_URL and/or ETHEREUM_RPC_URL
  optional COINGECKO_API_KEY

Demo mode (mocked Web3, no live keys):
  EVM_TX_HANDLER_EXAMPLE_DEMO=1 python examples/claude_evm_tx_handler.py
"""

import json
import os
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

    import anthropic

    bundle = SkillLoader.load_skill(SKILL_ID)
    skill = bundle["module"].EvmTxHandlerSkill()
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    tools = [SkillLoader.to_claude_tool(bundle)]
    tool_name = tools[0]["name"]

    user_query = (
        "Plan a buy of 10 DEGEN on Base with USDC: resolve, quote, preview, "
        "then execute only after explicit user confirmation."
    )
    print(f"User: {user_query}\n")

    message = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2048,
        system=bundle["instructions"],
        messages=[{"role": "user", "content": user_query}],
        tools=tools,
    )

    messages = [{"role": "user", "content": user_query}]

    while message.stop_reason == "tool_use":
        tool_use = next(block for block in message.content if block.type == "tool_use")
        print(f"Claude tool call: {tool_use.name} -> {json.dumps(tool_use.input)}")

        if tool_use.name != tool_name:
            print(f"Unknown tool: {tool_use.name}")
            break

        result = handle_tool_call(skill, tool_use.input)
        print(f"Skill result: {json.dumps(result, indent=2)[:2000]}...\n")

        messages = [
            *messages,
            {"role": "assistant", "content": message.content},
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": json.dumps(result),
                    }
                ],
            },
        ]

        message = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=2048,
            system=bundle["instructions"],
            tools=tools,
            messages=messages,
        )

    print("\nAgent final response:")
    for block in message.content:
        if hasattr(block, "text"):
            print(block.text)


if __name__ == "__main__":
    main()

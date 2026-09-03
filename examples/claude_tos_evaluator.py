import json
import os

import anthropic

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()

bundle = SkillLoader.load_skill("compliance/tos_evaluator")
TOOL_NAME = bundle["manifest"]["name"]
print(f"Loaded Skill: {TOOL_NAME}")

TOSEvaluatorSkill = bundle["module"].TOSEvaluatorSkill
tos_skill = TOSEvaluatorSkill()

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]

user_query = (
    "Can I use an automated crawler against https://hackernoon.com/tagged/devops "
    "for research indexing? Check first."
)
print(f"User: {user_query}")

message = client.messages.create(
    model="claude-3-5-sonnet-latest",
    max_tokens=1024,
    system=bundle["instructions"],
    messages=[{"role": "user", "content": user_query}],
    tools=tools,
)

if message.stop_reason == "tool_use":
    tool_use = next(block for block in message.content if block.type == "tool_use")
    tool_name = tool_use.name
    tool_input = tool_use.input

    print(f"Claude requested tool: {tool_name}")
    print(f"Input: {tool_input}")

    if tool_name == TOOL_NAME:
        result = tos_skill.execute(tool_input)
        print(json.dumps(result, indent=2))

        response = client.messages.create(
            model="claude-3-5-sonnet-latest",
            max_tokens=1024,
            system=bundle["instructions"],
            tools=tools,
            messages=[
                {"role": "user", "content": user_query},
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
            ],
        )

        print("\nFinal Response:")
        print(response.content[0].text)

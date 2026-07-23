"""Run a Skillware tool loop through the OpenAI-compatible Groq API."""

import json
import os

from openai import OpenAI

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()

bundle = SkillLoader.load_skill("compliance/tos_evaluator")
print(f"Loaded Skill: {bundle['manifest']['name']}")

tos_skill = bundle["class"]()
openai_tool = SkillLoader.to_openai_tool(bundle)
tool_name = openai_tool["function"]["name"]
print(f"OpenAI tool name: {tool_name}")

client = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)
model = os.environ["GROQ_MODEL"]

user_query = (
    "Before an agent crawls https://hackernoon.com/tagged/ai for research, "
    "check whether that appears allowed."
)
print(f"User: {user_query}")

messages = [
    {"role": "system", "content": bundle["instructions"]},
    {"role": "user", "content": user_query},
]

response = client.chat.completions.create(
    model=model,
    messages=messages,
    tools=[openai_tool],
)

while response.choices[0].message.tool_calls:
    assistant_message = response.choices[0].message
    messages.append(assistant_message)

    for tool_call in assistant_message.tool_calls:
        if tool_call.function.name != tool_name:
            raise RuntimeError(f"Unexpected tool: {tool_call.function.name}")

        fn_args = json.loads(tool_call.function.arguments)
        print(f"OpenAI-compatible host requested tool: {tool_call.function.name}")
        print(f"Input: {fn_args}")

        result = tos_skill.execute(fn_args)
        print(json.dumps(result, indent=2))

        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            }
        )

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=[openai_tool],
    )

print("\nFinal Response:")
print(response.choices[0].message.content or "")

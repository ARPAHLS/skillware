"""Run a Skillware tool loop through AWS Bedrock Converse."""

import os

import boto3

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()

bundle = SkillLoader.load_skill("compliance/tos_evaluator")
print(f"Loaded Skill: {bundle['manifest']['name']}")

tos_skill = bundle["class"]()
bedrock_tool = SkillLoader.to_bedrock_tool(bundle)
tool_name = bedrock_tool["toolSpec"]["name"]
print(f"Bedrock tool name: {tool_name}")

client = boto3.client("bedrock-runtime", region_name=os.environ["AWS_REGION"])
model_id = os.environ["BEDROCK_MODEL_ID"]

user_query = (
    "Before an agent crawls https://hackernoon.com/tagged/ai for research, "
    "check whether that appears allowed."
)
print(f"User: {user_query}")

messages = [{"role": "user", "content": [{"text": user_query}]}]

response = client.converse(
    modelId=model_id,
    system=[{"text": bundle["instructions"]}],
    messages=messages,
    toolConfig={"tools": [bedrock_tool], "toolChoice": {"auto": {}}},
)

while True:
    output = response["output"]["message"]
    messages.append(output)
    tool_uses = [block for block in output["content"] if "toolUse" in block]
    if not tool_uses:
        break

    tool_results = []
    for block in tool_uses:
        use = block["toolUse"]
        if use["name"] != tool_name:
            raise RuntimeError(f"Unexpected tool: {use['name']}")
        result = tos_skill.execute(dict(use["input"]))
        print(f"Tool result status: {result.get('status', result)}")
        tool_results.append(
            {
                "toolResult": {
                    "toolUseId": use["toolUseId"],
                    "content": [{"json": result}],
                }
            }
        )

    messages.append({"role": "user", "content": tool_results})
    response = client.converse(
        modelId=model_id,
        system=[{"text": bundle["instructions"]}],
        messages=messages,
        toolConfig={"tools": [bedrock_tool], "toolChoice": {"auto": {}}},
    )

for block in response["output"]["message"]["content"]:
    if "text" in block:
        print(block["text"])

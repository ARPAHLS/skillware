import json
import re

import ollama

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()

bundle = SkillLoader.load_skill("compliance/tos_evaluator")
TOOL_NAME = bundle["manifest"]["name"]
TOSEvaluatorSkill = bundle["module"].TOSEvaluatorSkill
tos_skill = TOSEvaluatorSkill()

tool_description = SkillLoader.to_ollama_prompt(bundle)
tool_description += f"\n**Cognitive Instructions:**\n{bundle['instructions']}\n"

system_prompt = f"""You are an intelligent agent equipped with a local website policy evaluation skill.
To use a skill, output exactly one JSON code block:
```json
{{
  "tool": "{TOOL_NAME}",
  "arguments": {{
    "param_name": "value"
  }}
}}
```
Wait for the system response containing the tool result before continuing.

Available skill:
{tool_description}
"""

messages = [
    {"role": "system", "content": system_prompt},
    {
        "role": "user",
        "content": (
            "Before I crawl https://hackernoon.com/tagged/startups with a bot for research, "
            "check whether that seems allowed."
        ),
    },
]

model_name = "llama3"
response = ollama.chat(model=model_name, messages=messages)
message_content = response.get("message", {}).get("content", "")
print(message_content)

tool_match = re.search(r"```json\s*({.*?})\s*```", message_content, re.DOTALL)
if tool_match:
    tool_call = json.loads(tool_match.group(1))
    fn_name = tool_call.get("tool")
    fn_args = tool_call.get("arguments", {})

    if fn_name == TOOL_NAME:
        result = tos_skill.execute(fn_args)
        print(json.dumps(result, indent=2))
        messages.append({"role": "assistant", "content": message_content})
        messages.append(
            {
                "role": "user",
                "content": (
                    "SYSTEM RESPONSE:\n"
                    f"```json\n{json.dumps(result)}\n```\n"
                    "Please provide the final answer."
                ),
            }
        )
        final_response = ollama.chat(model=model_name, messages=messages)
        print(final_response.get("message", {}).get("content", ""))

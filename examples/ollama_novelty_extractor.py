import json
import re
import ollama
from skillware.core.loader import SkillLoader
from skillware.core.env import load_env_file

load_env_file()

bundle = SkillLoader.load_skill("data_engineering/novelty_extractor")
NoveltyExtractor = bundle["module"].NoveltyExtractor
skill = NoveltyExtractor()

tool_description = SkillLoader.to_ollama_prompt(bundle)
tool_description += f"\n**Cognitive Instructions:**\n{bundle['instructions']}\n"

system_prompt = f"""You are an intelligent agent equipped with a local dataset novelty filtering skill.
To use a skill, output exactly one JSON code block:
```json
{{
  "tool": "the_tool_name",
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
            "Filter this dataset and keep only novel chunks with threshold 0.85:\n\n"
            "Bitcoin is a decentralized digital currency.\n\n"
            "Bitcoin operates without a central bank.\n\n"
            "The sky is blue and the weather is nice today.\n\n"
            "Python is a high-level programming language.\n\n"
            "Bitcoin was created by Satoshi Nakamoto."
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

    if fn_name == "data_engineering/novelty_extractor":
        result = skill.execute(fn_args)
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

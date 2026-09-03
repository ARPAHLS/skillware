import json
import re

import ollama
from skillware import SkillContext
from skillware.core.env import load_env_file

load_env_file()

SKILL_IDS = [
    "finance/wallet_screening",
    "office/pdf_form_filler",
    "optimization/prompt_rewriter",
]

ctx = SkillContext(skills=SKILL_IDS, mode="brief")

# Manifest name -> registry id for ctx.execute()
tool_name_to_skill_id = {}
for skill_id in ctx.skill_ids:
    prep = ctx.prepare(skill_id)
    manifest_name = prep.manifest.get("name", skill_id)
    tool_name_to_skill_id[manifest_name] = skill_id
    print(f"Loaded Skill: {manifest_name}")

combined_system_prompt = (
    """You are an intelligent agent equipped with specialized capabilities (skills).
To use a skill, you MUST output a JSON code block in the EXACT following format and then STOP GENERATING.
Do not add conversational text after the JSON block.

```json
{
  "tool": "the_tool_name",
  "arguments": {
    "param_name": "value"
  }
}
```

Wait until you receive the SYSTEM RESPONSE containing the tool execution results before proceeding.
Once you have the results, provide your final answer to the user.

Here are the available skills and their instructions:
""" + ctx.ollama_prompt
)

model_name = "llama3"
user_query = (
    "Please screen this ethereum wallet: 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045. "
    "Also, please rewrite this prompt for me: 'make me a cool image of a cat'."
)

print(f"\nUser: {user_query}")

messages = [
    {"role": "system", "content": combined_system_prompt},
    {"role": "user", "content": user_query},
]

print(f"\nCalling Ollama model: {model_name}...")

for _ in range(5):
    response = ollama.chat(model=model_name, messages=messages)

    message_content = response.get("message", {}).get("content", "")
    print(f"\n[Model Output]:\n{message_content}")
    messages.append({"role": "assistant", "content": message_content})

    tool_match = re.search(r"```json\s*({.*?})\s*```", message_content, re.DOTALL)

    if tool_match:
        try:
            tool_call = json.loads(tool_match.group(1))
            fn_name = tool_call.get("tool")
            fn_args = tool_call.get("arguments", {})

            print(f"\nAgent invoked tool: {fn_name}")
            print(f"   Arguments: {fn_args}")

            skill_id = tool_name_to_skill_id.get(fn_name)
            if skill_id:
                print(f"Executing skill '{fn_name}' via SkillContext...")
                try:
                    api_result = ctx.execute(skill_id, fn_args)
                    result_str = json.dumps(api_result)
                except Exception as exc:
                    result_str = f"Error executing tool: {exc}"

                print(f"Result generated ({len(result_str)} bytes)")

                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"SYSTEM RESPONSE (Result from {fn_name}):\n"
                            f"```json\n{result_str}\n```\n"
                            "Please continue based on this result."
                        ),
                    }
                )
            else:
                print(f"Unknown function requested: {fn_name}")
                messages.append(
                    {
                        "role": "user",
                        "content": f"SYSTEM ERROR: Tool '{fn_name}' not found.",
                    }
                )
        except json.JSONDecodeError:
            print("Failed to decode JSON from tool call block.")
            messages.append(
                {
                    "role": "user",
                    "content": "SYSTEM ERROR: Invalid JSON format. Please output valid JSON.",
                }
            )
    else:
        print("\nFinal Answer reached. End of execution.")
        break

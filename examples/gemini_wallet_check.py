import os

import google.genai as genai
from google.genai import types

from skillware.core.loader import SkillLoader
from skillware.core.env import load_env_file

load_env_file()

SKILL_PATH = "finance/wallet_screening"
skill_bundle = SkillLoader.load_skill(SKILL_PATH)

print(f"Loaded Skill: {skill_bundle['manifest']['name']}")

WalletScreeningSkill = skill_bundle["module"].WalletScreeningSkill
wallet_skill = WalletScreeningSkill(
    config={"ETHERSCAN_API_KEY": os.environ.get("ETHERSCAN_API_KEY")}
)

client = genai.Client()
tool = SkillLoader.to_gemini_tool(skill_bundle)
system_instruction = skill_bundle["instructions"]

user_query = (
    "Can you screen this wallet for me? 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
)
print(f"User: {user_query}")

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

    if part.function_call:
        fn_name = part.function_call.name
        fn_args = dict(part.function_call.args)

        print(f"Agent wants to call: {fn_name}")

        if fn_name == "wallet_screening":
            print("Executing skill locally...")
            api_result = wallet_skill.execute(fn_args)

            print("Sending result back to Agent...")
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
        else:
            print(f"Unknown function: {fn_name}")
            break
    else:
        break

print("\nAgent Final Response:")
print(response.text)

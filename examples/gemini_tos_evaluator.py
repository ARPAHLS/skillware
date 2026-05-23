import json

import google.genai as genai
from google.genai import types

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()

bundle = SkillLoader.load_skill("compliance/tos_evaluator")
print(f"Loaded Skill: {bundle['manifest']['name']}")

TOSEvaluatorSkill = bundle["module"].TOSEvaluatorSkill
tos_skill = TOSEvaluatorSkill()

client = genai.Client()
tool = SkillLoader.to_gemini_tool(bundle)
system_instruction = bundle["instructions"]

user_query = (
    "Before scraping Hackernoon tagged AI pages, check whether automated crawling "
    "appears allowed for https://hackernoon.com/tagged/ai."
)
print(f"User: {user_query}")

response = client.models.generate_content(
    model="gemini-2.5-flash-lite",
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
    print(f"Gemini requested tool: {fn_name}")
    print(f"Input: {fn_args}")

    if fn_name == "compliance/tos_evaluator":
        result = tos_skill.execute(fn_args)
        print(json.dumps(result, indent=2))
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[
                "Use this tool result to answer the original request.",
                {
                    "function_response": {
                        "name": fn_name,
                        "response": {"result": result},
                    }
                },
            ],
            config=types.GenerateContentConfig(
                tools=[tool],
                system_instruction=system_instruction,
            ),
        )
    else:
        break

print("\nFinal Response:")
print(response.text)

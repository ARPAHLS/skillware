import google.genai as genai
from google.genai import types
from skillware.core.loader import SkillLoader
from skillware.core.env import load_env_file

load_env_file()

SKILL_PATH = "data_engineering/novelty_extractor"
skill_bundle = SkillLoader.load_skill(SKILL_PATH)
print(f"Loaded Skill: {skill_bundle['manifest']['name']}")

NoveltyExtractor = skill_bundle["module"].NoveltyExtractor
skill = NoveltyExtractor()

client = genai.Client()
tool = SkillLoader.to_gemini_tool(skill_bundle)
system_instruction = skill_bundle["instructions"]

user_query = (
    "Filter this dataset and keep only the chunks that contain genuinely new "
    "information. Use a novelty threshold of 0.85.\n\n"
    "Bitcoin is a decentralized digital currency.\n\n"
    "Bitcoin operates without a central bank.\n\n"
    "The sky is blue and the weather is nice today.\n\n"
    "Python is a high-level programming language.\n\n"
    "Bitcoin was created by Satoshi Nakamoto."
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
        print("Executing skill locally...")
        result = skill.execute(fn_args)
        print("Sending result back to Agent...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
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

print("\nAgent Final Response:")
print(response.text)

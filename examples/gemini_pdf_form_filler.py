import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import google.genai as genai  # noqa: E402
from google.genai import types  # noqa: E402
from skillware.core.loader import SkillLoader  # noqa: E402
from skillware.core.env import load_env_file  # noqa: E402

load_env_file()

skill_bundle = SkillLoader.load_skill("office/pdf_form_filler")
print(f"Loaded Skill: {skill_bundle['manifest']['name']}")

PDFFormFillerSkill = skill_bundle["module"].PDFFormFillerSkill
pdf_skill = PDFFormFillerSkill()

client = genai.Client()
tool = SkillLoader.to_gemini_tool(skill_bundle)
system_instruction = skill_bundle["instructions"]

pdf_path = os.path.abspath("test_form.pdf")
user_query = (
    f"Fill out the form at {pdf_path}. Set the name to 'Jane Doe' and check the "
    "'Subscribe' box."
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
        print(f"   Args: {fn_args}")

        if fn_name == "pdf_form_filler":
            try:
                if not os.path.exists(fn_args.get("pdf_path", "")):
                    print(f"Error: PDF file not found at {fn_args.get('pdf_path')}")
                    result = {"error": "PDF file not found."}
                else:
                    print("Executing skill...")
                    result = pdf_skill.execute(fn_args)
                    print(f"Result: {result}")
            except Exception as exc:
                result = {"error": str(exc)}

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
    else:
        break

print("\nAgent Final Response:")
print(response.text)

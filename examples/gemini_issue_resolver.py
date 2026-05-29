import json
import os
import sys
from pathlib import Path

import google.genai as genai
from google.genai import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
from issue_resolver_github_context import execute_skill  # noqa: E402

from skillware.core.env import load_env_file  # noqa: E402
from skillware.core.loader import SkillLoader  # noqa: E402

load_env_file()

SKILL_ID = "dev_tools/issue_resolver"
ISSUE_URL = "https://github.com/ARPAHLS/skillware/issues/123"

bundle = SkillLoader.load_skill(SKILL_ID)
print(f"Loaded Skill: {bundle['manifest']['name']}")

IssueResolverSkill = bundle["module"].IssueResolverSkill
skill = IssueResolverSkill()
github_token = os.environ.get("GITHUB_TOKEN") or None

client = genai.Client()
tool_decl = SkillLoader.to_gemini_tool(bundle)
tool_decl["name"] = SkillLoader._sanitize_function_tool_name(SKILL_ID)
gemini_tool = types.Tool(function_declarations=[tool_decl])
gemini_fn_name = tool_decl["name"]
system_instruction = bundle["instructions"]
model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")

user_query = (
    f"Analyze {ISSUE_URL} and produce a structured resolution plan. "
    "Use the issue_resolver skill: start with action prepare, call stage_checklist "
    "for discover_issue and discover_repository, then present the plan. "
    "Do not implement code or commit."
)
print(f"User: {user_query}")

contents: list = [user_query]

response = client.models.generate_content(
    model=model,
    contents=contents,
    config=types.GenerateContentConfig(
        tools=[gemini_tool],
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

    if fn_name != gemini_fn_name:
        break

    result = execute_skill(skill, fn_args, github_token)
    print(json.dumps(result, indent=2))

    contents.append(response.candidates[0].content)
    contents.append(
        types.Content(
            role="user",
            parts=[
                types.Part(
                    function_response=types.FunctionResponse(
                        name=fn_name,
                        response={"result": result},
                    )
                )
            ],
        )
    )
    response = client.models.generate_content(
        model=model,
        contents=contents,
        config=types.GenerateContentConfig(
            tools=[gemini_tool],
            system_instruction=system_instruction,
        ),
    )

print("\nFinal Response:")
print(response.text)

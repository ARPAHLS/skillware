import json
import os
import re
import sys
from pathlib import Path

import ollama

sys.path.insert(0, str(Path(__file__).resolve().parent))
from issue_resolver_github_context import execute_skill  # noqa: E402

from skillware.core.env import load_env_file  # noqa: E402
from skillware.core.loader import SkillLoader  # noqa: E402

load_env_file()

if not os.environ.get("OLLAMA_HOST"):
    os.environ["OLLAMA_HOST"] = "127.0.0.1:11434"

SKILL_ID = "dev_tools/issue_resolver"
ISSUE_URL = "https://github.com/ARPAHLS/skillware/issues/123"
MODEL_NAME = os.environ.get("OLLAMA_MODEL", "gemma4:e2b")

bundle = SkillLoader.load_skill(SKILL_ID)
print(f"Loaded Skill: {bundle['manifest']['name']}")

IssueResolverSkill = bundle["module"].IssueResolverSkill
skill = IssueResolverSkill()
github_token = os.environ.get("GITHUB_TOKEN") or None

tool_description = SkillLoader.to_ollama_prompt(bundle)
tool_description += f"\n**Cognitive Instructions:**\n{bundle['instructions']}\n"

system_prompt = f"""You are an intelligent agent equipped with a GitHub issue resolver skill.
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

user_query = (
    f"Analyze {ISSUE_URL} and produce a structured resolution plan. "
    "Start with action prepare on the issue URL, then call stage_checklist for "
    "discover_issue. Stop after presenting the plan — do not implement code."
)
print(f"User: {user_query}")
print(f"Ollama model: {MODEL_NAME}")

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": user_query},
]

tool_pattern = re.compile(r"```json\s*({.*?})\s*```", re.DOTALL)

while True:
    response = ollama.chat(model=MODEL_NAME, messages=messages)
    message_content = response.get("message", {}).get("content", "")
    print(message_content)

    tool_match = tool_pattern.search(message_content)
    if not tool_match:
        break

    tool_call = json.loads(tool_match.group(1))
    fn_name = tool_call.get("tool")
    fn_args = tool_call.get("arguments", {})

    if fn_name != SKILL_ID:
        break

    result = execute_skill(skill, fn_args, github_token, slim=True)
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

import json
import os
import sys
from pathlib import Path

import anthropic

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

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
tools = [SkillLoader.to_claude_tool(bundle)]
system = bundle["instructions"]

user_query = (
    f"Analyze {ISSUE_URL} and produce a structured resolution plan. "
    "Use the issue_resolver skill: start with action prepare, call stage_checklist "
    "for discover_issue and discover_repository, then present the plan. "
    "Do not implement code or commit."
)
print(f"User: {user_query}")

messages = [{"role": "user", "content": user_query}]
response = None

while True:
    response = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
        max_tokens=4096,
        system=system,
        tools=tools,
        messages=messages,
    )

    if response.stop_reason != "tool_use":
        break

    tool_uses = [block for block in response.content if block.type == "tool_use"]
    if not tool_uses:
        break

    messages.append({"role": "assistant", "content": response.content})
    tool_results = []

    for tool_use in tool_uses:
        print(f"Claude requested tool: {tool_use.name}")
        print(f"Input: {tool_use.input}")

        if tool_use.name != SKILL_ID:
            break

        result = execute_skill(skill, tool_use.input, github_token)
        print(json.dumps(result, indent=2))
        tool_results.append(
            {
                "type": "tool_result",
                "tool_use_id": tool_use.id,
                "content": json.dumps(result),
            }
        )
    else:
        messages.append({"role": "user", "content": tool_results})
        continue
    break

print("\nFinal Response:")
if response is not None:
    for block in response.content:
        if hasattr(block, "text"):
            print(block.text)

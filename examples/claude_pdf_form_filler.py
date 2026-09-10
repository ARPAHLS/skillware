import os
import json
import anthropic
from skillware.core.loader import SkillLoader
from skillware.core.env import load_env_file

# Load Env (Requires ANTHROPIC_API_KEY for both Agent and Skill)
load_env_file()

# 1. Load the Skill
skill_bundle = SkillLoader.load_skill("office/pdf_form_filler")
print(f"Loaded Skill: {skill_bundle['manifest']['name']}")

# 2. Instantiate Skill
PDFFormFillerSkill = skill_bundle["module"].PDFFormFillerSkill
pdf_skill = PDFFormFillerSkill()

# 3. Setup Claude Client
client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
)

claude_tool = SkillLoader.to_claude_tool(skill_bundle)
tools = [claude_tool]
TOOL_NAME = claude_tool["name"]

# 4. Run Agent Loop
pdf_path = os.path.abspath("test_form.pdf")
user_query = f"Please fill out the form at {pdf_path}. My name is John Smith and I want to enable notifications."

print(f"User: {user_query}")

message = client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=1024,
    system=skill_bundle["instructions"],
    messages=[{"role": "user", "content": user_query}],
    tools=tools,
)

if message.stop_reason == "tool_use":
    tool_use = next(block for block in message.content if block.type == "tool_use")
    tool_name = tool_use.name
    tool_input = tool_use.input

    print(f"\nClaude requested tool: {tool_name}")
    print(f"Input: {tool_input}")

    if tool_name == TOOL_NAME:
        # Check file
        if not os.path.exists(tool_input.get("pdf_path", "")):
            print(
                f"⚠️ Warning: File {tool_input.get('pdf_path')} does not exist. Execution might fail."
            )

        # Execute
        print("⚙️ Executing skill...")
        try:
            result = pdf_skill.execute(tool_input)
            print("✅ Skill Execution Result:")
            print(json.dumps(result, indent=2))
        except Exception as e:
            result = {"error": str(e)}
            print(f"❌ Error: {e}")

        # Feed back to Claude
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1024,
            system=skill_bundle["instructions"],
            tools=tools,
            messages=[
                {"role": "user", "content": user_query},
                {"role": "assistant", "content": message.content},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": tool_use.id,
                            "content": json.dumps(result),
                        }
                    ],
                },
            ],
        )

        print("\nAgent Final Response:")
        print(response.content[0].text)

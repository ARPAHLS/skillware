import os
import json
import anthropic
from skillware.core.loader import SkillLoader
from skillware.core.env import load_env_file

# Load Global Env (User should have ETHERSCAN_API_KEY and ANTHROPIC_API_KEY)
load_env_file()

# 1. Load the Skill
skill = SkillLoader.load_skill("finance/wallet_screening")
print(f"Loaded Skill: {skill['manifest']['name']}")

# 2. Instantiate the Skill Logic
WalletScreeningSkill = skill['module'].WalletScreeningSkill
wallet_skill = WalletScreeningSkill(config={
    "ETHERSCAN_API_KEY": os.environ.get("ETHERSCAN_API_KEY")
})

# 3. Setup Claude Client
client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY"),
)

# Define the tool set
tools = [SkillLoader.to_claude_tool(skill)]

# 4. Run the Agent Loop
user_query = "Please assess the risk of this wallet: 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
print(f"User: {user_query}")

message = client.messages.create(
    model="claude-3-opus-20240229",
    max_tokens=1024,
    system=skill['instructions'], # Inject the cognitive map
    messages=[
        {"role": "user", "content": user_query}
    ],
    tools=tools,
)

# 5. Handle Tool Use
if message.stop_reason == "tool_use":
    tool_use = next(block for block in message.content if block.type == "tool_use")
    tool_name = tool_use.name
    tool_input = tool_use.input
    
    print(f"\nClaude requested tool: {tool_name}")
    print(f"Input: {tool_input}")

    if tool_name == "wallet_screening":
        # Execute the skill
        result = wallet_skill.execute(tool_input)
        
        print("\nSkill Execution Result (Summary):")
        print(json.dumps(result.get('summary', {}), indent=2))

        # Feed back to Claude
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=1024,
            system=skill['instructions'],
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
                            "content": json.dumps(result)
                        }
                    ],
                },
            ],
        )
        
        print("\nAgent Final Response:")
        print(response.content[0].text)

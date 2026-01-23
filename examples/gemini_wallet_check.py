import os
import sys
# Add repo root to path to allow import of 'skillware'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import google.generativeai as genai
from skillware.core.loader import SkillLoader
from skillware.core.env import load_env_file

# Load Global Env (User should create a .env file with ETHERSCAN_API_KEY and GOOGLE_API_KEY)
load_env_file()

# 1. Load the Skill dynamically
# Adjust path to where the skill is located relative to this script
SKILL_PATH = "finance/wallet_screening"
skill_bundle = SkillLoader.load_skill(SKILL_PATH)

print(f"Loaded Skill: {skill_bundle['manifest']['name']}")

# 2. Instantiate the Skill
WalletScreeningSkill = skill_bundle['module'].WalletScreeningSkill
wallet_skill = WalletScreeningSkill(config={
    "ETHERSCAN_API_KEY": os.environ.get("ETHERSCAN_API_KEY")
})

# 3. Setup Gemini
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Define the tool for Gemini using the manifest
tools_listing = [SkillLoader.to_gemini_tool(skill_bundle)]

# Create the model with the tool
model = genai.GenerativeModel(
    'gemini-2.5-flash',
    tools=tools_listing,
    system_instruction=skill_bundle['instructions'] # Inject the skill's cognitive map
)

chat = model.start_chat(enable_automatic_function_calling=True)

# 4. Run the Agent Loop
user_query = "Can you screen this wallet for me? 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045" # Vitalik's address as example
print(f"User: {user_query}")

# Create a function map for manual execution if automatic calling wasn't enabled 
# (though the library handles it, describing it here for clarity)
function_map = {
    'wallet_screening': wallet_skill.execute
}

# In a real loop, you would handle the tool call response. 
# Here we simulate the key steps or let the library's auto-function calling work if supported by the client lib version.
# Note: Python client support for auto-execution might vary, so we define a simple runner.

# Send initial message
response = chat.send_message(user_query)

# Simple loop to handle tool calls (depth 1 for demo, but loop is better)
while response.candidates and response.candidates[0].content.parts:
    part = response.candidates[0].content.parts[0]
    
    # Check if the model wants to call a function
    if part.function_call:
        fn_name = part.function_call.name
        fn_args = dict(part.function_call.args)
        
        print(f"🤖 Agent wants to call: {fn_name}")
        
        if fn_name == 'wallet_screening':
            # Execute the skill logic
            print("⚙️ Executing skill locally...")
            api_result = wallet_skill.execute(fn_args)
            
            # Send the result back to the model
            print("📤 Sending result back to Agent...")
            response = chat.send_message(
                [
                    {
                        "function_response": {
                            "name": fn_name,
                            "response": {'result': api_result}
                        }
                    }
                ]
            )
        else:
            print(f"Unknown function: {fn_name}")
            break
    else:
        # No function call, just text
        break

print("\n💬 Agent Final Response:")
print(response.text)


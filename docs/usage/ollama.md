# Using Ollama with Skillware

Skillware natively supports [Ollama](https://ollama.com/), enabling you to run open-source models completely locally while seamlessly utilizing skills. Ollama's tool-calling format is directly compatible with Skillware's manifest structure.

## Prerequisites

1.  **Install Ollama:** Follow the instructions at [ollama.com](https://ollama.com/) to install Ollama on your machine.
2.  **Pull a Model:** Use a model that follows instructions reliably in prompt mode (JSON tool blocks). Examples: `gemma3`, `qwen3.5`, or `llama3.1`.
    ```bash
    ollama pull gemma3
    ollama run gemma3
    ```
3.  **Install Python Client:** Install the official Ollama Python package.
    ```bash
    pip install ollama
    ```

## Example Usage

Here is a simple example demonstrating how to load a skill and execute it using a local model running via Ollama.

````python
import json
import re
import ollama
from skillware.core.loader import SkillLoader
from skillware.core.env import load_env_file

# Load Env for API Keys if any needed by skills
load_env_file()

# 1. Load the Skill dynamically
SKILL_PATH = "finance/wallet_screening"
skill_bundle = SkillLoader.load_skill(SKILL_PATH)
WalletScreeningSkill = getattr(skill_bundle["module"], "WalletScreeningSkill")
wallet_skill = WalletScreeningSkill()

print(f"Loaded Skill: {skill_bundle['manifest']['name']}")

# 2. Build the System Prompt with Tool Rules
tool_description = SkillLoader.to_ollama_prompt(skill_bundle)

system_prompt = f"""You are an intelligent agent equipped with specialized capabilities.
To use a skill, you MUST output a JSON code block in the EXACT following format:
```json
{{
  "tool": "the_tool_name",
  "arguments": {{
    "param_name": "value"
  }}
}}
```
Wait for the system to return the result of the tool before proceeding.

Available skills:
{tool_description}
Instructions: {skill_bundle.get('instructions', '')}
"""

messages = [
    {"role": "system", "content": system_prompt},
    {"role": "user", "content": "Please screen this ethereum wallet: 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"}
]

# 3. Call the Ollama Model
model_name = "gemma3"
print(f"🤖 Calling Ollama model: {model_name}...")
response = ollama.chat(
    model=model_name,
    messages=messages
)

message_content = response.get("message", {}).get("content", "")
print(f"\n[Model Output]:\n{message_content}")

# 4. Handle Text-based Tool Calls
tool_match = re.search(r"```json\s*({.*?})\s*```", message_content, re.DOTALL)
if tool_match:
    tool_call = json.loads(tool_match.group(1))
    fn_name = tool_call.get("tool")
    fn_args = tool_call.get("arguments", {})

    if fn_name == skill_bundle["manifest"]["name"]:
        print(f"⚙️ Executing skill '{fn_name}' locally...")
        api_result = wallet_skill.execute(fn_args)

        # Give result back to model
        messages.append({"role": "assistant", "content": message_content})
        messages.append({
            "role": "user",
            "content": f"SYSTEM RESPONSE (Result from {fn_name}):\n```json\n{json.dumps(api_result)}\n```\nPlease continue."
        })

        print("\n🤖 Sending tool results back to Agent...")
        final_resp = ollama.chat(model=model_name, messages=messages)
        print("\n💬 Final Answer:")
        print(final_resp.get("message", {}).get("content", ""))
````

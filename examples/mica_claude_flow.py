import os
import json
import re
import anthropic
from skillware.core.loader import SkillLoader
from skillware.core.env import load_env_file


def main():
    # 1. Setup
    load_env_file()
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Please set ANTHROPIC_API_KEY in your .env file.")
        return

    client = anthropic.Anthropic()

    print("[System] Loading MiCA Module (Cognitive/Surgical Mode)...")
    skill_bundle = SkillLoader.load_skill("compliance/mica_module")
    # Instantiate the logic
    MiCA_Module = skill_bundle["module"].MiCAModuleSkill
    mica_skill = MiCA_Module()

    # 2. Build Cognitive Map
    tool_text = SkillLoader.to_ollama_prompt(skill_bundle)

    system_instruction = f"""{skill_bundle.get('instructions', '')}

**Available tools:**
{tool_text}

**Protocol:**
To get MiCA context, output exactly a JSON block like this:
```json
{{
  "tool": "{skill_bundle['manifest']['name']}",
  "arguments": {{ "user_prompt": "query" }}
}}
```
Wait for the system response before providing your final answer.
"""

    user_query = (
        "What are the authorization requirements for a company wanting to be a CASP under MiCA? "
        "Please cite Articles 59-63."
    )
    model_name = "claude-3-haiku-20240307"

    print(f"\n[User]: {user_query}")
    print("-" * 50)

    messages = [{"role": "user", "content": user_query}]

    print("Agent (Claude) is thinking...", flush=True)

    for turn in range(3):
        try:
            # Use streaming for visual feedback
            with client.messages.stream(
                model=model_name,
                max_tokens=1024,
                system=system_instruction,
                messages=messages,
            ) as stream:
                print("\n[Agent]: ", end="", flush=True)
                full_content = ""
                for text in stream.text_stream:
                    print(text, end="", flush=True)
                    full_content += text

            # Extract Tool Call
            match = re.search(r"```json\s*({.*?})\s*```", full_content, re.DOTALL)
            if match:
                messages.append({"role": "assistant", "content": full_content})

                call_data = json.loads(match.group(1))
                fn_args = call_data.get("arguments", {})

                print(
                    "\n\n[Skillware] Match Detected. Executing Surgical RAG...",
                    end="",
                    flush=True,
                )
                # Execute locally
                result = mica_skill.execute(fn_args)
                print(" [DONE]")

                sections = result.get("retrieved_sections", [])
                print(f" > Articles found: {', '.join(sections)}")

                # Feedback loop
                result_msg = (
                    f"SYSTEM RESPONSE (Source Articles):\n{result.get('final_context_for_agent', '')}\n\n"
                    "Please generate your final authorized response."
                )
                messages.append({"role": "user", "content": result_msg})
            else:
                # No more tool calls, done
                print("\n\n(Scenario Complete)")
                break

        except Exception as e:
            print(f"\n[Error]: {e}")
            break


if __name__ == "__main__":
    main()

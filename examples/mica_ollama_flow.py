import os
import sys
import json
import re
import ollama

# Add the parent directory to the path so we can import skillware locally
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from skillware.core.loader import SkillLoader  # noqa: E402
from skillware.core.base_skill import BaseSkill  # noqa: E402


def load_skill_instance(path):
    bundle = SkillLoader.load_skill(path)
    for attr_name in dir(bundle["module"]):
        attr = getattr(bundle["module"], attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, BaseSkill)
            and attr is not BaseSkill
        ):
            return bundle, attr()
    raise ValueError("No Skill class found")


def main():
    # 1. Load the MiCA Skill
    print("[System] Loading specialized MiCA Compliance Skill (Cached/Surgical)...")
    bundle, mica_skill = load_skill_instance("compliance/mica_module")

    # 2. Build Cognitive Map
    tool_text = SkillLoader.to_ollama_prompt(bundle)
    system_instruction = f"""{bundle.get('instructions', '')}

**Available tools:**
{tool_text}

**Protocol:**
If you need regulatory context, output exactly one JSON block like this:
```json
{{
  "tool": "{bundle['manifest']['name']}",
  "arguments": {{ "user_prompt": "query" }}
}}
```
Wait for the response before making your final compliant determination.
"""

    model_name = "llama3"
    user_query = (
        "What are the rules for a company wanting to be authorized as a crypto-asset service provider "
        "(CASP) in the EU?"
    )

    print(f"\n[User]: {user_query}")
    print("-" * 50)

    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": user_query},
    ]

    print(f"Agent (Ollama/{model_name}) is thinking...", flush=True)

    try:
        # turn limit for safety
        for turn in range(3):
            # Use streaming for visual feedback
            response_stream = ollama.chat(
                model=model_name, messages=messages, stream=True
            )

            full_content = ""
            print("\n[Agent]: ", end="", flush=True)
            for chunk in response_stream:
                part = chunk["message"]["content"]
                print(part, end="", flush=True)
                full_content += part
            print("\n")

            # Extract Tool Call
            match = re.search(r"```json\s*({.*?})\s*```", full_content, re.DOTALL)
            if match:
                messages.append({"role": "assistant", "content": full_content})

                call_data = json.loads(match.group(1))
                fn_args = call_data.get("arguments", {})

                print(
                    "[Skillware] Match Detected. Executing Local RAG lookup...",
                    end="",
                    flush=True,
                )
                result = mica_skill.execute(fn_args)
                print(" [DONE]")

                sections = result.get("retrieved_sections", [])
                print(f" > Articles found: {', '.join(sections[:3])}...")

                # Feedback loop
                result_msg = (
                    f"SYSTEM RESPONSE (Source Articles):\n{result.get('final_context_for_agent', '')}\n\n"
                    "Please generate your final authorized response."
                )
                messages.append({"role": "user", "content": result_msg})
            else:
                # No more tool calls, done
                print("\n(Scenario Complete)")
                break

    except Exception as e:
        print(f"\n[Error] Optimization failed: {e}")


if __name__ == "__main__":
    main()

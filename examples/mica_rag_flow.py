import json
import re

import google.genai as genai
from skillware.core.loader import SkillLoader
from skillware.core.env import load_env_file


def main():
    load_env_file()
    client = genai.Client()

    print("[System] Loading MiCA Module (Cognitive/Surgical Mode)...")
    skill_bundle = SkillLoader.load_skill("compliance/mica_module")
    MiCA_Module = skill_bundle["module"].MiCAModuleSkill
    mica_skill = MiCA_Module()

    tool_text = SkillLoader.to_ollama_prompt(skill_bundle)

    system_instruction = f"""{skill_bundle.get('instructions', '')}

**Available Tools in your Mind:**
{tool_text}

**Protocol:**
If you need regulatory context, output a JSON block like this:
```json
{{
  "tool": "{skill_bundle['manifest']['name']}",
  "arguments": {{ "user_prompt": "query" }}
}}
```
Wait for the response before making your final compliant determination.
"""

    user_query = (
        "How do I get an authorization to be a crypto-asset service provider (CASP) in the EU?"
    )

    print(f"\n[User]: {user_query}")
    print("-" * 50)

    result_msg = ""

    print("Agent (Gemini) is thinking...", flush=True)

    for turn in range(3):
        try:
            prompt = (
                system_instruction + "\n\nUSER QUERY: " + user_query
                if turn == 0
                else result_msg
            )

            full_content = ""
            print("\n[Agent]: ", end="", flush=True)
            for chunk in client.models.generate_content_stream(
                model="gemini-2.5-flash-lite",
                contents=prompt,
            ):
                if chunk.text:
                    print(chunk.text, end="", flush=True)
                    full_content += chunk.text

            match = re.search(r"```json\s*({.*?})\s*```", full_content, re.DOTALL)
            if match:
                call_data = json.loads(match.group(1))
                fn_args = call_data.get("arguments", {})

                print(
                    "\n\n[Skillware] Match Detected. Executing Surgical RAG...",
                    end="",
                    flush=True,
                )
                result = mica_skill.execute(fn_args)
                print(" [DONE]")

                sections = result.get("retrieved_sections", [])
                print(f" > Articles found: {', '.join(sections)}")

                result_msg = (
                    f"SYSTEM RESPONSE (Source Articles):\n"
                    f"{result.get('final_context_for_agent', '')}\n\n"
                    "Please generate your final authorized response."
                )
            else:
                print("\n\n(Scenario Complete)")
                break

        except Exception as exc:
            print(f"\n[Error]: {exc}")
            break


if __name__ == "__main__":
    main()

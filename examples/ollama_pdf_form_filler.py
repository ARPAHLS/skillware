# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""
100% offline/private Ollama agent loop for office/pdf_form_filler v0.2.2.

Ideal for privacy-sensitive tax, legal, or HR forms where no document data
or PII should leave the local machine.
"""

import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import ollama  # noqa: E402
from skillware.core.loader import SkillLoader  # noqa: E402


def main() -> None:
    skill_bundle = SkillLoader.load_skill("office/pdf_form_filler")
    print(f"Loaded Skill: {skill_bundle['manifest']['name']}")

    pdf_skill = skill_bundle["class"]()
    system_prompt = SkillLoader.to_prompt_mode(skill_bundle)
    model = os.environ.get("OLLAMA_MODEL", "llama3.1")

    user_query = (
        "List the available PDF templates and tell me which template to use "
        "for a non-US individual claiming US tax treaty benefits."
    )
    print(f"User: {user_query}")

    # 1. Execute deterministic discovery locally and feed structured output to Ollama
    templates = pdf_skill.execute({"action": "list_templates"})
    print(f"Local skill result: {json.dumps(templates, indent=2)}")

    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query},
            {
                "role": "assistant",
                "content": f"Tool output (list_templates): {json.dumps(templates)}",
            },
            {
                "role": "user",
                "content": "Summarize the best matching template ID and next steps.",
            },
        ],
    )
    print(f"\nOllama ({model}):\n{response['message']['content']}")


if __name__ == "__main__":
    main()


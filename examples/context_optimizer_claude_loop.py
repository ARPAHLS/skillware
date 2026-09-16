"""Optional live Claude loop: context_optimizer -> answer from optimized_context.

Requires ANTHROPIC_API_KEY and pip install "skillware[claude]".
Set CONTEXT_OPTIMIZER_CLAUDE_LIVE=1 to run the model call.
"""

from __future__ import annotations

import os
from pathlib import Path

from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

SAMPLE = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "optimization"
    / "context_optimizer"
    / "data"
    / "sample_policy.txt"
)


def main() -> None:
    load_env_file()
    if os.environ.get("CONTEXT_OPTIMIZER_CLAUDE_LIVE", "").strip().lower() not in {
        "1",
        "true",
        "yes",
    }:
        print(
            "Set CONTEXT_OPTIMIZER_CLAUDE_LIVE=1 and ANTHROPIC_API_KEY to run live phase."
        )
        return

    import anthropic

    bundle = SkillLoader.load_skill("optimization/context_optimizer")
    skill = bundle["class"]()
    document = SAMPLE.read_text(encoding="utf-8")
    agent_goal = "Summarize jurisdiction and data handling obligations only."
    max_tokens = int(os.environ.get("CONTEXT_OPTIMIZER_MAX_TOKENS", "250"))
    min_score = float(os.environ.get("CONTEXT_OPTIMIZER_MIN_SCORE", "0.45"))

    selected = skill.execute(
        {
            "document_text": document,
            "agent_goal": agent_goal,
            "max_tokens_return": max_tokens,
            "min_score": min_score,
        }
    )
    print(
        "Optimizer:",
        selected.get("status"),
        selected.get("reduction_percentage"),
        f"chunks={selected.get('chunks_selected_count')}/{selected.get('chunks_total')}",
        f"out~{selected.get('estimated_output_tokens')}tok",
    )
    excerpt = selected.get("optimized_context", "")
    if not excerpt.strip():
        print("No excerpt selected — cannot run Claude phase.")
        print("agent_hint:", selected.get("agent_hint"))
        return
    print("Excerpt preview:", excerpt[:240].replace("\n", " "), "...")

    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
    prompt = (
        f"Task: {agent_goal}\n\n"
        "Answer using ONLY the excerpt below. If the excerpt lacks enough detail, say so.\n\n"
        f"--- EXCERPT ---\n{excerpt}\n--- END EXCERPT ---"
    )
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system="You are a compliance assistant. Cite only the provided excerpt.",
        messages=[{"role": "user", "content": prompt}],
    )
    for block in response.content:
        if block.type == "text":
            print("\nClaude answer:\n", block.text)


if __name__ == "__main__":
    main()

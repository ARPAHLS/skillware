"""Offline demo for optimization/context_optimizer.

Loads bundled sample policy text and selects jurisdiction-relevant spans.
No API keys required (fastembed mocked in CI via bundle tests; first local run may download model).
"""

from __future__ import annotations

import json
from pathlib import Path

from skillware.core.loader import SkillLoader

SKILL_ID = "optimization/context_optimizer"
SAMPLE = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "optimization"
    / "context_optimizer"
    / "data"
    / "sample_policy.txt"
)


def main() -> None:
    print(f"Loading {SKILL_ID}...")
    bundle = SkillLoader.load_skill(SKILL_ID)
    skill = bundle["class"]()
    document = SAMPLE.read_text(encoding="utf-8")

    result = skill.execute(
        {
            "document_text": document,
            "agent_goal": "Find jurisdiction and data handling clauses.",
            "max_tokens_return": 250,
            "min_score": 0.45,
        }
    )
    print(json.dumps(result, indent=2))
    print("\nDemo complete.")


if __name__ == "__main__":
    main()

"""Chain demo: prompt_injection_firewall → context_optimizer (offline).

Demonstrates trust-boundary selection before a hypothetical main LLM call.
"""

from __future__ import annotations

import json
from pathlib import Path

from skillware import SkillContext

FIREWALL = "security/prompt_injection_firewall"
OPTIMIZER = "optimization/context_optimizer"
SAMPLE = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "optimization"
    / "context_optimizer"
    / "data"
    / "sample_policy.txt"
)


def main() -> None:
    print("context_optimizer chain demo (offline)...")
    ctx = SkillContext(skills=[FIREWALL, OPTIMIZER])
    raw = SAMPLE.read_text(encoding="utf-8")
    # Benign document — firewall passes through
    fw = ctx.execute(
        FIREWALL,
        {"source_text": raw, "input_mode": "plain", "sensitivity": "balanced"},
    )
    print(f"  firewall is_safe={fw.get('is_safe')}")
    source = fw.get("sanitized_text") or raw

    opt = ctx.execute(
        OPTIMIZER,
        {
            "document_text": source,
            "agent_goal": "jurisdiction and cross-border data handling",
            "max_tokens_return": 250,
            "min_score": 0.45,
        },
    )
    print(
        f"  optimizer status={opt.get('status')} reduction={opt.get('reduction_percentage')}"
    )
    print(json.dumps(opt, indent=2)[:1200])
    print("\nChain demo complete.")


if __name__ == "__main__":
    main()

"""Shared helpers for token hard limit examples."""

from __future__ import annotations

import json
from typing import Any, Dict, List


def simulate_budget_loop(
    skill: Any,
    *,
    task_id: str,
    max_allowed_tokens: int,
    turn_deltas: List[int],
    model_id: str = "gpt-4o",
) -> List[Dict[str, Any]]:
    """Simulate an agent loop that checks the budget after each turn."""
    cumulative = 0
    results: List[Dict[str, Any]] = []

    for index, delta in enumerate(turn_deltas, start=1):
        cumulative += delta
        result = skill.execute(
            {
                "task_id": task_id,
                "turn_id": f"turn-{index}",
                "current_token_count": cumulative,
                "max_allowed_tokens": max_allowed_tokens,
                "model_id": model_id,
                "input_tokens": delta // 2,
                "output_tokens": delta - (delta // 2),
            }
        )
        results.append(result)
        print(f"Turn {index}: action={result['action']} tokens={cumulative}")
        print(json.dumps(result, indent=2))
        if result.get("action") == "FORCE_TERMINATE":
            break

    return results

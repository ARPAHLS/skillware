"""Deterministic token budget evaluation for agent loops."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

SCHEMA_VERSION = "1.0"
DEFAULT_SOFT_THRESHOLD_PCT = 80.0
VALID_ACTIONS = frozenset({"check", "reset"})
VALID_DECISIONS = frozenset({"CONTINUE", "WARN", "FORCE_TERMINATE"})


def utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def load_pricing(data_dir: str) -> Dict[str, Any]:
    pricing_path = os.path.join(data_dir, "model_pricing.json")
    with open(pricing_path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _positive_int(value: Any, field: str) -> Tuple[Optional[int], Optional[str]]:
    if value is None:
        return None, f"{field} is required."
    if isinstance(value, bool):
        return None, f"{field} must be an integer."
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None, f"{field} must be an integer."
    if parsed < 0:
        return None, f"{field} must be zero or greater."
    return parsed, None


def _optional_non_negative_int(
    value: Any, field: str
) -> Tuple[Optional[int], Optional[str]]:
    if value is None:
        return None, None
    return _positive_int(value, field)


def _soft_threshold_pct(value: Any) -> Tuple[float, Optional[str]]:
    if value is None:
        return DEFAULT_SOFT_THRESHOLD_PCT, None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return DEFAULT_SOFT_THRESHOLD_PCT, "soft_threshold_pct must be a number."
    if parsed <= 0 or parsed > 100:
        return (
            DEFAULT_SOFT_THRESHOLD_PCT,
            "soft_threshold_pct must be between 0 and 100.",
        )
    return parsed, None


def estimate_cost_usd(
    pricing: Dict[str, Any],
    model_id: Optional[str],
    current_token_count: int,
    input_tokens: Optional[int],
    output_tokens: Optional[int],
) -> Tuple[Optional[float], List[str]]:
    warnings: List[str] = []
    if not model_id:
        return None, warnings

    models = pricing.get("models", {})
    model_key = str(model_id).strip()
    rates = models.get(model_key)

    if rates is None:
        fallback = pricing.get("fallback", {})
        blended = float(fallback.get("blended_usd_per_1m", 5.0))
        warnings.append(
            f"Unknown model_id {model_key!r}; using fallback blended rate "
            f"{blended} USD per 1M tokens."
        )
        cost = (current_token_count / 1_000_000.0) * blended
        return round(cost, 6), warnings

    input_rate = float(rates.get("input_usd_per_1m", 0.0))
    output_rate = float(rates.get("output_usd_per_1m", 0.0))

    if input_tokens is None and output_tokens is None:
        input_tokens = current_token_count // 2
        output_tokens = current_token_count - input_tokens
        warnings.append(
            "input_tokens and output_tokens were not provided; "
            "assuming a 50/50 split for cost estimation."
        )
    elif input_tokens is None:
        input_tokens = max(0, current_token_count - int(output_tokens))
    elif output_tokens is None:
        output_tokens = max(0, current_token_count - int(input_tokens))

    cost = (input_tokens / 1_000_000.0) * input_rate + (
        output_tokens / 1_000_000.0
    ) * output_rate
    return round(cost, 6), warnings


def build_roi_scaffold(
    params: Dict[str, Any], cost_usd: Optional[float]
) -> Dict[str, Any]:
    roi_value = params.get("roi_value_usd")
    expected_outcome = params.get("expected_outcome")
    outcome_delivered = params.get("outcome_delivered")

    scaffold: Dict[str, Any] = {
        "enabled": False,
        "status": "not_evaluated",
        "notes": (
            "ROI enforcement is not active in v1. Token limits are the sole "
            "termination trigger. Future versions may compare expected_outcome "
            "and outcome_delivered against token spend."
        ),
    }

    if roi_value is not None or expected_outcome or outcome_delivered is not None:
        scaffold["enabled"] = True
        scaffold["roi_value_usd"] = roi_value
        scaffold["expected_outcome"] = expected_outcome
        scaffold["outcome_delivered"] = outcome_delivered
        scaffold["cost_incurred_usd"] = cost_usd
        scaffold["status"] = "scaffold_only"

    return scaffold


def evaluate_budget(
    params: Dict[str, Any],
    pricing: Dict[str, Any],
    turn_cache: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    action = (params.get("action") or "check").strip().lower()
    if action not in VALID_ACTIONS:
        return {
            "status": "error",
            "message": f"Invalid action {action!r}. Expected one of: check, reset.",
        }

    task_id = (params.get("task_id") or "").strip()
    if not task_id:
        return {"status": "error", "message": "task_id is required."}

    if action == "reset":
        prefix = f"{task_id}|"
        keys_to_delete = [key for key in turn_cache if key.startswith(prefix)]
        for key in keys_to_delete:
            del turn_cache[key]
        return {
            "status": "ready",
            "schema_version": SCHEMA_VERSION,
            "action": "RESET",
            "task_id": task_id,
            "message": f"Cleared {len(keys_to_delete)} cached turn result(s) for task.",
            "timestamp": utc_now_iso(),
        }

    current_token_count, err = _positive_int(
        params.get("current_token_count"), "current_token_count"
    )
    if err:
        return {"status": "error", "message": err}

    max_allowed_tokens, err = _positive_int(
        params.get("max_allowed_tokens"), "max_allowed_tokens"
    )
    if err:
        return {"status": "error", "message": err}

    if max_allowed_tokens == 0:
        return {
            "status": "error",
            "message": "max_allowed_tokens must be greater than zero.",
        }

    soft_threshold_pct, soft_err = _soft_threshold_pct(params.get("soft_threshold_pct"))
    turn_id = (params.get("turn_id") or "").strip()
    cache_key = f"{task_id}|{turn_id}|{current_token_count}|{max_allowed_tokens}"

    if turn_id and cache_key in turn_cache:
        cached = dict(turn_cache[cache_key])
        cached["metadata"] = dict(cached.get("metadata", {}))
        cached["metadata"]["cache_hit"] = True
        return cached

    input_tokens, input_err = _optional_non_negative_int(
        params.get("input_tokens"), "input_tokens"
    )
    if input_err:
        return {"status": "error", "message": input_err}

    output_tokens, output_err = _optional_non_negative_int(
        params.get("output_tokens"), "output_tokens"
    )
    if output_err:
        return {"status": "error", "message": output_err}

    model_id = (params.get("model_id") or "").strip() or None
    cost_usd, cost_warnings = estimate_cost_usd(
        pricing,
        model_id,
        current_token_count,
        input_tokens,
        output_tokens,
    )

    utilization_pct = round((current_token_count / max_allowed_tokens) * 100.0, 2)
    tokens_over_budget = max(0, current_token_count - max_allowed_tokens)
    soft_limit = int(max_allowed_tokens * (soft_threshold_pct / 100.0))

    warnings: List[str] = []
    if soft_err:
        warnings.append(soft_err)
    warnings.extend(cost_warnings)

    if current_token_count >= max_allowed_tokens:
        decision = "FORCE_TERMINATE"
        reason = (
            f"Token budget exceeded by {tokens_over_budget} "
            f"({utilization_pct}% of limit)."
        )
    elif current_token_count >= soft_limit:
        decision = "WARN"
        reason = (
            f"Token utilization at {utilization_pct}% "
            f"(soft threshold {soft_threshold_pct}%)."
        )
    else:
        decision = "CONTINUE"
        reason = (
            f"Token utilization at {utilization_pct}% "
            f"({current_token_count}/{max_allowed_tokens})."
        )

    roi = build_roi_scaffold(params, cost_usd)

    result: Dict[str, Any] = {
        "status": "ready",
        "schema_version": SCHEMA_VERSION,
        "action": decision,
        "task_id": task_id,
        "reason": reason,
        "budget": {
            "current_token_count": current_token_count,
            "max_allowed_tokens": max_allowed_tokens,
            "utilization_pct": utilization_pct,
            "tokens_over_budget": tokens_over_budget,
            "soft_threshold_pct": soft_threshold_pct,
            "soft_limit_tokens": soft_limit,
        },
        "cost": {
            "incurred_usd": cost_usd,
            "model_id": model_id,
            "pricing_source": "data/model_pricing.json",
            "pricing_last_updated": pricing.get("last_updated"),
        },
        "roi": roi,
        "metadata": {
            "warnings": warnings,
            "turn_id": turn_id or None,
            "cache_hit": False,
            "host_responsibility": (
                "The host loop must stop when action is FORCE_TERMINATE."
            ),
        },
        "timestamp": utc_now_iso(),
    }

    if turn_id:
        turn_cache[cache_key] = dict(result)

    return result

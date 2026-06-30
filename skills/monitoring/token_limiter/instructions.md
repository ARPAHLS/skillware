# Cognition Instructions: Token Limiter

You have access to the `monitoring/token_limiter` tool.

This skill is a **budget gate** for long-running autonomous loops. It does **not** stop the loop itself. After each model turn (or before the next one), call it with the **cumulative** token count for the task. If the result is `FORCE_TERMINATE`, you must **stop the loop immediately** and report the reason to the operator.

## When to use this skill

- Before starting a high-risk autonomous task (scraping, multi-step research, codegen loops).
- After **every** model turn in a loop where token spend must stay bounded.
- When the operator sets a maximum token budget for a task.

## Required host behavior

1. Track `task_id` for the session and pass **cumulative** `current_token_count` (not just the last turn delta unless you maintain the running total yourself).
2. Set `max_allowed_tokens` from operator policy or task metadata.
3. On `action: WARN`, consider narrowing scope, compressing context, or asking the operator before continuing.
4. On `action: FORCE_TERMINATE`, **do not** call the main model again for this task. Return the skill payload to the dashboard or user.

## Parameters

| Field | Required | Notes |
| :--- | :--- | :--- |
| `task_id` | Yes | Stable task identifier |
| `current_token_count` | Yes (check) | Cumulative tokens used so far |
| `max_allowed_tokens` | Yes (check) | Hard ceiling |
| `turn_id` | No | Use for idempotent retries of the same turn |
| `model_id` | No | Enables indicative USD cost in the response |
| `soft_threshold_pct` | No | Default 80; triggers WARN before hard limit |

## ROI scaffold (v2, not enforced)

Optional fields `roi_value_usd`, `expected_outcome`, and `outcome_delivered` are accepted for future ROI logic. **v1 never terminates on ROI alone.** Token limits are the only termination trigger today.

## Interpreting the response

- `CONTINUE`: Under the soft threshold. Proceed with the next turn.
- `WARN`: Approaching the limit. Tighten scope or warn the operator.
- `FORCE_TERMINATE`: Hard limit reached. Stop the loop and surface `reason`.
- `RESET`: Administrative action clearing cached turn results for a `task_id`.

Cost figures in `cost.incurred_usd` are **indicative** estimates from bundled list prices, not invoice amounts.

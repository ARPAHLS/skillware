# Cognition Instructions: Business Diagnostic

You have access to the `monitoring/business_diagnostic` tool.

This skill is a **deterministic, offline scenario ledger**: an operator-owned
framework (scenarios with an adjudication date, indicators with declared
per-scenario weights), the operator's probability marks, and dated indicator
observations go in; the model-implied probability of each scenario, its delta
from the marks, fired indicators, re-mark due date, and (after resolution)
Brier scores come out. `execute()` is a pure function: no network calls, no
clock, no side effects; identical input always returns identical output.

Three terms:

- **operator marks** - the probabilities the operator assigned on
  `marked_on`. The skill never changes them.
- **model-implied** - what the declared weights imply once observations are
  applied to the marks. Not a forecast and not a recommendation; present it
  only next to the operator marks, never in place of them.
- **insufficient_data** - the honest state: a computation the skill refuses
  to fake, with a reason code from a closed set.

Limits: it is a ledger, not a data source. It never collects observations,
never estimates an unobserved indicator (unobserved contributes 0), never
re-marks on the operator's behalf, and never scores anything until the host
supplies a resolved `outcome`. It returns the first contract violation
found, checking in this order: request envelope, action, `as_of`, framework,
`strengthens` ids, marks, observations, outcome, `marks_history`.

- `observations` passed to `calibrate` are validated but not used: Brier
  scores use operator marks only.
- Weights: an indicator observed `yes` adds +w to every scenario listed in
  its `strengthens`, `no` adds −w; scenarios not listed get 0; indicators
  without an observation contribute 0 — nothing is imputed.
- With `exhaustive: false` each scenario updates independently and
  model-implied values may not sum to 1 (the bundled example with
  `exhaustive: false`: A 0.324, B 0.332, C 0.300, D 0.100, sum 1.056).
- Multi-class Brier: `Σ_s (p_s − y_s)²` with one-hot `y` (1 for the
  resolved scenario, 0 otherwise).

## Agent-loop contract

- Surface `scenarios[].delta` and `scenarios[].fired` to the operator next to
  `operator_mark`; never show `model_implied` on its own.
- `marks_stale: true` -> prompt the operator to re-mark; do not re-mark for
  them.
- `insufficient_data` non-empty -> report the reason; the host must not
  substitute, estimate, or backfill.
- The skill is stateless: marks, observations, history, and outcome travel in
  the input and come back in the output.

## When to invoke

- `adjudicate`: an indicator observation was recorded, or a period review
  asks which way the balance of plausibility has shifted.
- `calibrate`: the outcome is resolved and the operator wants to know how
  well the marks (and earlier mark sets) were calibrated.

Do not invoke it to collect observations, to pick weights, or to explain why
a scenario moved beyond the fired indicators it reports.

## Inputs

- `action` (required): `adjudicate` or `calibrate`.
- `as_of` (required): evaluation date `YYYY-MM-DD`, supplied by the host.
- `framework` (required): `schema_version: 1`, `framework_id`,
  `adjudication_date`, `exhaustive`, `scenarios[]` (`id`, `label`,
  `criterion`), `indicators[]` (`id`, `label`, `strengthens` map of scenario
  id to weight). Ids match `^[A-Z][A-Z0-9_]*$` and are closed sets.
- `marks` (required): `marked_on`, `remark_every_days`, `values` covering
  every scenario, each in `[0.001, 0.999]`, summing to 1.
- `observations[]` (adjudicate, optional): `indicator`, `observed`
  (`yes` / `no`), `on`, optional `source`. One entry per indicator; the host
  de-duplicates. `on` must be after `marked_on` and not after
  `adjudication_date`.
- `outcome` (calibrate, required): `resolved_on`, `scenario`. Null or omitted
  for adjudicate.
- `marks_history[]` (calibrate, optional): earlier mark sets, same shape as
  `marks`.

Reference JSON Schemas ship under `schemas/` in this bundle; the skill
enforces the same constraints with explicit stdlib checks (`requirements: []`
is deliberate). A synthetic framework ships at `kb/demo_scenarios.json`.

## How to interpret results

A completed run returns `status: "completed"`, `framework_id`, `as_of`, and:

- `scenarios[]` in declaration order: `id`, `operator_mark`, `fired`
  (indicator ids with a declared weight that were observed), and for
  `adjudicate` `model_implied` and `delta` rounded to 3 decimals. With
  `exhaustive: true` the model-implied values are renormalized to sum to 1
  before rounding; with `false` each scenario updates independently.
- `calibration`: `next_remark_due`, `days_to_adjudication`, `brier` (null for
  adjudicate), and for `calibrate` `brier_trend` (one entry per
  `marks_history` set in ascending `marked_on` order, or null when none was
  supplied).
- `fired_any`, `marks_stale`, `insufficient`, `insufficient_data[]`
  (`reason`, `detail`).

Honest state: when `as_of` is on or after `adjudication_date`, `adjudicate`
returns the marks with `model_implied: null` and `delta: null`, and
`insufficient_data` carries `reason: adjudication_date_passed`.

A contract violation returns `status: "error"` with `error.code` from the
closed registry (`INVALID_REQUEST`, `UNKNOWN_ACTION`, `INVALID_AS_OF`,
`INVALID_FRAMEWORK_SCHEMA`, `INVALID_MARKS_SCHEMA`,
`INVALID_OBSERVATIONS_SCHEMA`, `INVALID_OUTCOME_SCHEMA`,
`UNKNOWN_SCENARIO_ID`, `UNKNOWN_INDICATOR_ID`, `DUPLICATE_OBSERVATION`,
`MARK_OUT_OF_RANGE`, `MARKS_NOT_NORMALIZED`, `OBSERVATION_PREDATES_MARKS`,
`OBSERVATION_AFTER_ADJUDICATION`) and a deterministic `error.detail`. Errors
and the honest state never mix.

## Example

`adjudicate` with marks A 0.15 / B 0.45 / C 0.30 / D 0.10, indicator `I01`
(`strengthens` A +1.0, B -0.5) observed `yes`, `exhaustive: true`:
A 0.307 (+0.157), B 0.314 (-0.136), C 0.284 (-0.016), D 0.095 (-0.005),
`fired: ["I01"]` on A and B. `calibrate` with outcome B on the same marks:
`brier: 0.425`.

v0.1 is the ledger; projections against declared targets and a report skeleton are planned as Skill Upgrades.

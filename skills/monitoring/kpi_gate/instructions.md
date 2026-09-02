# Cognition Instructions: KPI Gate

You have access to the `monitoring/kpi_gate` tool.

This skill is a **deterministic, offline KPI gate**: a metrics snapshot plus a
policy charter (and optional versioned benchmark data) go in, structured
findings come out. `execute()` is a pure function with no network calls and no
side effects; identical input always returns identical output.

Limits: it is an auditor, not a data pipeline. It never fetches CRM, email, or
analytics data, never estimates missing values, and never optimizes thresholds.

## Agent-loop contract

- `error` finding → the host blocks the dependent action until an operator
  override is recorded.
- `warning` finding → surface to the operator; never block on a warning.
- `insufficient_data` → treat the metric as absent. The host must not
  substitute, estimate, or backfill a value.

## When to invoke

- Gating a scheduled action (send, publish, spend) on business-KPI health
- Auditing a periodic metrics snapshot against operator-declared thresholds
- Comparing observed metrics against versioned benchmark doctrine

Do not invoke it to collect metrics, to explain why a metric moved (no causal
inference), or to pick thresholds (no optimization).

## Inputs

- `metrics` (required): snapshot object — `schema_version: 1`, a `period`
  (`start`, `end`, `granularity`), and a map of `lower_snake_case` keys to
  non-negative numbers. Every key must be declared by the policy.
- `policy` (required): charter object — `schema_version: 2`, `policy_id`, the
  closed `metrics` declaration, and ordered `rules`. Finding ids (for example
  `NO_BOOKING`) are declared here, not in the skill. Typically maintained as
  versioned YAML and parsed by the host before the call.
- `benchmarks` (optional): versioned benchmark data — required only when a
  rule uses `benchmark_ref`. A demo file ships at `kb/benchmarks_demo.json`.

Reference JSON Schemas for all three inputs ship under `schemas/` in this
bundle. The skill enforces the same constraints with explicit stdlib checks
(`requirements: []` is deliberate); the schema files are documentation, not a
runtime dependency. Hosts that call `validate_params()` also get top-level
argument validation from the manifest.

## How to interpret results

A completed run returns `status: "completed"` with `policy_id`,
`benchmark_version` (`null` when no benchmarks input was supplied), and
`findings` in rule-declaration order:

- Rule finding: `finding` (charter-declared id), `severity`, `detail`
  (`metric`, `threshold`, `observed`), `action`
  (`blocked — requires operator override` or
  `none — surfaced for the operator`).
- Refusal: `state: "insufficient_data"`, `detail.metric`, and `reason` — the
  rule's declared `reason_code`, or `honesty_floor_unmet` when the rule
  declared none, or `metric_missing_from_snapshot` when the rule's metric is
  absent from the snapshot. When a granularity floor or a missing denominator
  caused the refusal, `detail.unmet_floor` names it (`granularity` or
  `denominator`); the canonical below-minimum-denominator refusal keeps the
  exact shape pinned by issue #317.

A contract violation returns `status: "error"` with
`error.code` from the closed registry (`INVALID_METRICS_SCHEMA`,
`INVALID_POLICY_SCHEMA`, `INVALID_BENCHMARKS_SCHEMA`, `NO_METRICS_PROVIDED`,
`UNKNOWN_METRIC_KEY`, `UNKNOWN_RULE_METRIC`, `UNKNOWN_DENOMINATOR_METRIC`,
`BENCHMARK_VERSION_MISSING`, `BENCHMARK_REF_UNRESOLVED`) and a deterministic
`error.detail`. Errors and honest non-computability never mix: a refusal is a
finding inside a completed run, never an error envelope.

## Reserved fields (v1)

`check.applies_to` is shape-validated and echoed into `detail.applies_to` on a
finding, but carries no evaluation semantics in v1. Do not assume it filters
or scopes rule evaluation.

## Validation order (fail-closed)

1. Strict schema checks on `metrics`, then `policy`, then `benchmarks` — the
   first violation returns a contract error.
2. Cross-checks: rule metrics and denominator metrics must be declared by the
   policy; snapshot keys must be declared by the policy; every
   `benchmark_ref` must resolve.
3. Honesty floors: declared preconditions only — the evaluator never infers
   which metric backs a rate. An unmet floor refuses with the declared reason
   code.
4. Rules evaluate in declared order; a passing rule emits nothing.

## What this skill cannot do

- Data acquisition: it never fetches, scrapes, or polls anything.
- Causal inference: it reports threshold breaches, not why they happened.
- Threshold optimization: thresholds come from the charter and benchmarks;
  the skill never tunes them.

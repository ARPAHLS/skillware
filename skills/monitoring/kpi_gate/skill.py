"""Deterministic business-KPI gate: {metrics, policy, benchmarks?} -> findings[].

Implements the interface frozen in ARPAHLS/skillware issue #317. Validation is
fail-closed and runs in four stages: (1) strict stdlib schema checks on all
three inputs, (2) cross-checks between inputs, (3) honesty floors, and
(4) rule evaluation in declared order. Contract violations return an error
envelope with a code from the closed registry below; honest non-computability
is returned as insufficient_data findings and the two never mix.

Finding codes (for example NO_BOOKING) are charter content declared by the
policy file, never part of this module's registry.
"""

import os
import re
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import yaml

from skillware.core.base_skill import BaseSkill

REGISTRY_ID = "monitoring/kpi_gate"

# Closed error registry: contract violations only. These codes are the skill's
# identity and never change per operator.
INVALID_METRICS_SCHEMA = "INVALID_METRICS_SCHEMA"
INVALID_POLICY_SCHEMA = "INVALID_POLICY_SCHEMA"
INVALID_BENCHMARKS_SCHEMA = "INVALID_BENCHMARKS_SCHEMA"
NO_METRICS_PROVIDED = "NO_METRICS_PROVIDED"
UNKNOWN_METRIC_KEY = "UNKNOWN_METRIC_KEY"
UNKNOWN_RULE_METRIC = "UNKNOWN_RULE_METRIC"
UNKNOWN_DENOMINATOR_METRIC = "UNKNOWN_DENOMINATOR_METRIC"
BENCHMARK_VERSION_MISSING = "BENCHMARK_VERSION_MISSING"
BENCHMARK_REF_UNRESOLVED = "BENCHMARK_REF_UNRESOLVED"

ERROR_REGISTRY = frozenset(
    {
        INVALID_METRICS_SCHEMA,
        INVALID_POLICY_SCHEMA,
        INVALID_BENCHMARKS_SCHEMA,
        NO_METRICS_PROVIDED,
        UNKNOWN_METRIC_KEY,
        UNKNOWN_RULE_METRIC,
        UNKNOWN_DENOMINATOR_METRIC,
        BENCHMARK_VERSION_MISSING,
        BENCHMARK_REF_UNRESOLVED,
    }
)

# Fixed reason codes the skill itself may emit on refusal. Charters declare
# their own reason codes for honesty floors; these two cover the cases where
# no charter-declared code applies.
REASON_HONESTY_FLOOR_UNMET = "honesty_floor_unmet"
REASON_METRIC_MISSING = "metric_missing_from_snapshot"

ACTION_BY_SEVERITY = {
    "error": "blocked — requires operator override",
    "warning": "none — surfaced for the operator",
}

_METRIC_KEY_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_RULE_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_URI_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")

_GRANULARITIES = ("daily", "weekly", "monthly")
_THRESHOLD_OPS = ("gte", "lte", "gt", "lt", "eq")
_UNLIMITED_OPS = ("lte", "lt")
_BENCHMARK_OPS = ("gte", "lte")
_SEVERITIES = ("error", "warning")
_OP_SYMBOLS = {"gte": ">=", "lte": "<=", "gt": ">", "lt": "<", "eq": "=="}


class _ContractError(Exception):
    """Internal signal carrying a closed-registry code and a detail string."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def _fail(code: str, detail: str) -> None:
    raise _ContractError(code, detail)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_object(value: Any, code: str, path: str) -> None:
    if not isinstance(value, dict):
        _fail(code, f"{path}: expected an object")


def _check_exact_keys(
    obj: Dict[str, Any],
    required: Tuple[str, ...],
    optional: Tuple[str, ...],
    code: str,
    path: str,
) -> None:
    for key in required:
        if key not in obj:
            _fail(code, f"{path}: missing required property '{key}'")
    allowed = set(required) | set(optional)
    for key in sorted(obj):
        if key not in allowed:
            _fail(code, f"{path}: unexpected property '{key}'")


def _check_string(value: Any, code: str, path: str) -> None:
    if not isinstance(value, str):
        _fail(code, f"{path}: expected a string")


def _check_date(value: Any, code: str, path: str) -> None:
    _check_string(value, code, path)
    if not _DATE_RE.match(value):
        _fail(code, f"{path}: expected an ISO date (YYYY-MM-DD)")
    try:
        date.fromisoformat(value)
    except ValueError:
        _fail(code, f"{path}: expected a valid calendar date")


def _check_const(value: Any, expected: int, code: str, path: str) -> None:
    if not _is_number(value) or value != expected:
        _fail(code, f"{path}: expected the constant {expected}")


def _validate_metrics(snapshot: Any) -> None:
    code = INVALID_METRICS_SCHEMA
    _require_object(snapshot, code, "metrics")
    _check_exact_keys(
        snapshot, ("schema_version", "period", "metrics"), (), code, "metrics"
    )
    _check_const(snapshot["schema_version"], 1, code, "metrics.schema_version")

    period = snapshot["period"]
    _require_object(period, code, "metrics.period")
    _check_exact_keys(
        period, ("start", "end", "granularity"), (), code, "metrics.period"
    )
    _check_date(period["start"], code, "metrics.period.start")
    _check_date(period["end"], code, "metrics.period.end")
    if period["granularity"] not in _GRANULARITIES:
        _fail(
            code,
            "metrics.period.granularity: expected one of " + ", ".join(_GRANULARITIES),
        )

    values = snapshot["metrics"]
    _require_object(values, code, "metrics.metrics")
    if not values:
        _fail(NO_METRICS_PROVIDED, "metrics.metrics: at least one metric is required")
    for key in sorted(values):
        if not isinstance(key, str) or not _METRIC_KEY_RE.match(key):
            _fail(
                code,
                f"metrics.metrics: key '{key}' does not match ^[a-z][a-z0-9_]*$",
            )
        value = values[key]
        if not _is_number(value):
            _fail(code, f"metrics.metrics.{key}: expected a number")
        if value < 0:
            _fail(code, f"metrics.metrics.{key}: expected a number >= 0")


def _validate_threshold_check(check: Dict[str, Any], code: str, path: str) -> None:
    _check_exact_keys(check, ("op", "threshold"), ("applies_to",), code, path)
    if check["op"] not in _THRESHOLD_OPS:
        _fail(code, f"{path}.op: expected one of " + ", ".join(_THRESHOLD_OPS))
    threshold = check["threshold"]
    if isinstance(threshold, str):
        if threshold != "unlimited":
            _fail(
                code,
                f"{path}.threshold: string threshold must be the literal 'unlimited'",
            )
        if check["op"] not in _UNLIMITED_OPS:
            _fail(
                code,
                f"{path}.threshold: 'unlimited' is valid only with op lte or lt",
            )
    elif not _is_number(threshold):
        _fail(code, f"{path}.threshold: expected a number or the literal 'unlimited'")
    if "applies_to" in check:
        applies_to = check["applies_to"]
        if not isinstance(applies_to, list):
            _fail(code, f"{path}.applies_to: expected an array of strings")
        for index, item in enumerate(applies_to):
            if not isinstance(item, str):
                _fail(code, f"{path}.applies_to[{index}]: expected a string")


def _validate_benchmark_check(check: Dict[str, Any], code: str, path: str) -> None:
    _check_exact_keys(check, ("op", "benchmark_ref"), ("tolerance_pct",), code, path)
    if check["op"] not in _BENCHMARK_OPS:
        _fail(code, f"{path}.op: expected one of " + ", ".join(_BENCHMARK_OPS))
    _check_string(check["benchmark_ref"], code, f"{path}.benchmark_ref")
    if "tolerance_pct" in check:
        tolerance = check["tolerance_pct"]
        if not _is_number(tolerance) or tolerance < 0:
            _fail(code, f"{path}.tolerance_pct: expected a number >= 0")


def _validate_requires(requires: Any, code: str, path: str) -> None:
    _require_object(requires, code, path)
    _check_exact_keys(
        requires,
        (),
        ("denominator_metric", "min_denominator", "granularity", "reason_code"),
        code,
        path,
    )
    if "denominator_metric" in requires:
        value = requires["denominator_metric"]
        _check_string(value, code, f"{path}.denominator_metric")
        if not _METRIC_KEY_RE.match(value):
            _fail(
                code,
                f"{path}.denominator_metric: does not match ^[a-z][a-z0-9_]*$",
            )
    if "min_denominator" in requires:
        value = requires["min_denominator"]
        if not _is_number(value) or value < 1:
            _fail(code, f"{path}.min_denominator: expected a number >= 1")
        if "denominator_metric" not in requires:
            _fail(
                code,
                f"{path}: 'min_denominator' requires 'denominator_metric' "
                "(dependentRequired)",
            )
    if "granularity" in requires and requires["granularity"] not in _GRANULARITIES:
        _fail(
            code,
            f"{path}.granularity: expected one of " + ", ".join(_GRANULARITIES),
        )
    if "reason_code" in requires:
        value = requires["reason_code"]
        _check_string(value, code, f"{path}.reason_code")
        if not _METRIC_KEY_RE.match(value):
            _fail(code, f"{path}.reason_code: does not match ^[a-z][a-z0-9_]*$")


def _validate_policy(policy: Any) -> None:
    code = INVALID_POLICY_SCHEMA
    _require_object(policy, code, "policy")
    _check_exact_keys(
        policy,
        ("schema_version", "policy_id", "metrics", "rules"),
        (),
        code,
        "policy",
    )
    _check_const(policy["schema_version"], 2, code, "policy.schema_version")
    _check_string(policy["policy_id"], code, "policy.policy_id")

    declared = policy["metrics"]
    if not isinstance(declared, list) or not declared:
        _fail(code, "policy.metrics: expected a non-empty array of metric keys")
    for index, key in enumerate(declared):
        if not isinstance(key, str) or not _METRIC_KEY_RE.match(key):
            _fail(
                code,
                f"policy.metrics[{index}]: does not match ^[a-z][a-z0-9_]*$",
            )

    rules = policy["rules"]
    if not isinstance(rules, list) or not rules:
        _fail(code, "policy.rules: expected a non-empty array of rules")
    for index, rule in enumerate(rules):
        path = f"policy.rules[{index}]"
        _require_object(rule, code, path)
        _check_exact_keys(
            rule, ("id", "metric", "check", "severity"), ("requires",), code, path
        )
        _check_string(rule["id"], code, f"{path}.id")
        if not _RULE_ID_RE.match(rule["id"]):
            _fail(code, f"{path}.id: does not match ^[A-Z][A-Z0-9_]*$")
        _check_string(rule["metric"], code, f"{path}.metric")
        if rule["severity"] not in _SEVERITIES:
            _fail(
                code,
                f"{path}.severity: expected one of " + ", ".join(_SEVERITIES),
            )
        check = rule["check"]
        _require_object(check, code, f"{path}.check")
        has_threshold = "threshold" in check
        has_benchmark = "benchmark_ref" in check
        if has_threshold == has_benchmark:
            _fail(
                code,
                f"{path}.check: exactly one of 'threshold' or 'benchmark_ref' "
                "must be declared",
            )
        if has_threshold:
            _validate_threshold_check(check, code, f"{path}.check")
        else:
            _validate_benchmark_check(check, code, f"{path}.check")
        if "requires" in rule:
            _validate_requires(rule["requires"], code, f"{path}.requires")


def _validate_benchmarks(benchmarks: Any) -> None:
    code = INVALID_BENCHMARKS_SCHEMA
    _require_object(benchmarks, code, "benchmarks")
    _check_exact_keys(
        benchmarks,
        ("schema_version", "benchmark_version", "as_of", "sources", "values"),
        (),
        code,
        "benchmarks",
    )
    _check_const(benchmarks["schema_version"], 1, code, "benchmarks.schema_version")
    _check_string(benchmarks["benchmark_version"], code, "benchmarks.benchmark_version")
    _check_date(benchmarks["as_of"], code, "benchmarks.as_of")

    sources = benchmarks["sources"]
    if not isinstance(sources, list) or not sources:
        _fail(code, "benchmarks.sources: expected a non-empty array of URIs")
    for index, source in enumerate(sources):
        if not isinstance(source, str) or not _URI_SCHEME_RE.match(source):
            _fail(code, f"benchmarks.sources[{index}]: expected a URI")

    values = benchmarks["values"]
    _require_object(values, code, "benchmarks.values")
    if not values:
        _fail(code, "benchmarks.values: at least one benchmark value is required")
    for key in sorted(values):
        if not isinstance(key, str) or not _METRIC_KEY_RE.match(key):
            _fail(
                code,
                f"benchmarks.values: key '{key}' does not match ^[a-z][a-z0-9_]*$",
            )
        entry = values[key]
        path = f"benchmarks.values.{key}"
        _require_object(entry, code, path)
        _check_exact_keys(entry, ("value",), ("unit", "denominator_scope"), code, path)
        if not _is_number(entry["value"]):
            _fail(code, f"{path}.value: expected a number")
        if "unit" in entry:
            _check_string(entry["unit"], code, f"{path}.unit")
        if "denominator_scope" in entry:
            _check_string(entry["denominator_scope"], code, f"{path}.denominator_scope")


def _cross_checks(
    snapshot: Dict[str, Any],
    policy: Dict[str, Any],
    benchmarks: Optional[Dict[str, Any]],
) -> None:
    declared = set(policy["metrics"])
    rules = policy["rules"]

    for index, rule in enumerate(rules):
        if rule["metric"] not in declared:
            _fail(
                UNKNOWN_RULE_METRIC,
                f"policy.rules[{index}]: metric '{rule['metric']}' is not "
                "declared in policy.metrics",
            )

    for index, rule in enumerate(rules):
        requires = rule.get("requires") or {}
        denominator = requires.get("denominator_metric")
        if denominator is not None and denominator not in declared:
            _fail(
                UNKNOWN_DENOMINATOR_METRIC,
                f"policy.rules[{index}]: denominator_metric '{denominator}' is "
                "not declared in policy.metrics",
            )

    for key in sorted(snapshot["metrics"]):
        if key not in declared:
            _fail(
                UNKNOWN_METRIC_KEY,
                f"metrics.metrics: key '{key}' is not declared in policy.metrics",
            )

    for index, rule in enumerate(rules):
        check = rule["check"]
        if "benchmark_ref" not in check:
            continue
        ref = check["benchmark_ref"]
        if benchmarks is None:
            _fail(
                BENCHMARK_VERSION_MISSING,
                f"policy.rules[{index}]: benchmark_ref '{ref}' requires "
                "benchmarks input, but none was supplied",
            )
        if ref not in benchmarks["values"]:
            _fail(
                BENCHMARK_REF_UNRESOLVED,
                f"policy.rules[{index}]: benchmark_ref '{ref}' does not resolve "
                "in benchmarks.values",
            )


def _compare(op: str, observed: float, threshold: float) -> bool:
    if op == "gte":
        return observed >= threshold
    if op == "lte":
        return observed <= threshold
    if op == "gt":
        return observed > threshold
    if op == "lt":
        return observed < threshold
    return observed == threshold


def _evaluate_check(
    check: Dict[str, Any],
    observed: float,
    benchmarks: Optional[Dict[str, Any]],
) -> Tuple[str, bool]:
    """Return (threshold display string, whether the rule passes)."""
    op = check["op"]
    symbol = _OP_SYMBOLS[op]
    if "benchmark_ref" in check:
        base = benchmarks["values"][check["benchmark_ref"]]["value"]
        tolerance = check.get("tolerance_pct", 0)
        if tolerance:
            factor = 1 - tolerance / 100.0 if op == "gte" else 1 + tolerance / 100.0
            effective = base * factor
        else:
            effective = base
        return f"{symbol} {effective} (benchmark)", _compare(op, observed, effective)
    threshold = check["threshold"]
    if threshold == "unlimited":
        # Explicit no-bound literal: an upper-bound rule with no cap always
        # passes. Stage 1 rejects 'unlimited' with any op other than lte/lt.
        return f"{symbol} unlimited", True
    return f"{symbol} {threshold}", _compare(op, observed, threshold)


def _insufficient(
    metric: str, reason: str, unmet_floor: Optional[str] = None
) -> Dict[str, Any]:
    detail: Dict[str, Any] = {"metric": metric}
    if unmet_floor is not None:
        detail["unmet_floor"] = unmet_floor
    return {"state": "insufficient_data", "detail": detail, "reason": reason}


def _evaluate_rules(
    snapshot: Dict[str, Any],
    policy: Dict[str, Any],
    benchmarks: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    metric_values = snapshot["metrics"]
    snapshot_granularity = snapshot["period"]["granularity"]

    for rule in policy["rules"]:
        metric = rule["metric"]
        requires = rule.get("requires") or {}
        floor_reason = requires.get("reason_code", REASON_HONESTY_FLOOR_UNMET)

        # Honesty floors, checked against declared preconditions only — the
        # evaluator never infers which metric backs a rate. Granularity is
        # checked before the denominator floor; the first unmet floor refuses.
        if (
            "granularity" in requires
            and snapshot_granularity != requires["granularity"]
        ):
            findings.append(
                _insufficient(metric, floor_reason, unmet_floor="granularity")
            )
            continue
        if "min_denominator" in requires:
            denominator = requires["denominator_metric"]
            if denominator not in metric_values:
                findings.append(
                    _insufficient(metric, floor_reason, unmet_floor="denominator")
                )
                continue
            if metric_values[denominator] < requires["min_denominator"]:
                # Canonical refusal shape pinned by the #317 output contract.
                findings.append(_insufficient(metric, floor_reason))
                continue

        if metric not in metric_values:
            findings.append(_insufficient(metric, REASON_METRIC_MISSING))
            continue

        observed = metric_values[metric]
        threshold_str, passed = _evaluate_check(rule["check"], observed, benchmarks)
        if passed:
            continue
        detail: Dict[str, Any] = {
            "metric": metric,
            "threshold": threshold_str,
            "observed": observed,
        }
        if "applies_to" in rule["check"]:
            # Reserved in v1: shape-validated and echoed, no evaluation
            # semantics (issue #317 scope).
            detail["applies_to"] = list(rule["check"]["applies_to"])
        severity = rule["severity"]
        findings.append(
            {
                "finding": rule["id"],
                "severity": severity,
                "detail": detail,
                "action": ACTION_BY_SEVERITY[severity],
            }
        )
    return findings


def evaluate_kpi_gate(params: Dict[str, Any]) -> Dict[str, Any]:
    """Pure evaluation entry point: validates, cross-checks, and evaluates."""
    if not isinstance(params, dict):
        _fail(
            INVALID_METRICS_SCHEMA,
            "parameters: expected a JSON object with 'metrics' and 'policy'",
        )
    if "metrics" not in params:
        _fail(INVALID_METRICS_SCHEMA, "metrics: required input is missing")
    if "policy" not in params:
        _fail(INVALID_POLICY_SCHEMA, "policy: required input is missing")

    snapshot = params["metrics"]
    policy = params["policy"]
    benchmarks = params.get("benchmarks")

    _validate_metrics(snapshot)
    _validate_policy(policy)
    if benchmarks is not None:
        _validate_benchmarks(benchmarks)
    _cross_checks(snapshot, policy, benchmarks)
    findings = _evaluate_rules(snapshot, policy, benchmarks)

    return {
        "status": "completed",
        "policy_id": policy["policy_id"],
        "benchmark_version": (
            benchmarks["benchmark_version"] if benchmarks is not None else None
        ),
        "findings": findings,
    }


class KpiGateSkill(BaseSkill):
    """Deterministic KPI gate over {metrics, policy, benchmarks?} inputs."""

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as handle:
                return yaml.safe_load(handle)
        return {"name": REGISTRY_ID, "version": "0.1.0"}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return evaluate_kpi_gate(params)
        except _ContractError as error:
            return {
                "status": "error",
                "error": {"code": error.code, "detail": error.detail},
            }

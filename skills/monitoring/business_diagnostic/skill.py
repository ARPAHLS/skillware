"""Deterministic scenario ledger and calibration.

Implements the v0.1 interface agreed in ARPAHLS/skillware issue #338 with the
same design split as monitoring/kpi_gate: the framework (scenarios,
adjudication date, weighted indicators) and the operator's probability marks
are operator-owned inputs; the skill ships no scenarios or indicators of its
own. Validation is fail-closed: contract violations return an error envelope
with a code from the closed registry below, honest non-computability is
returned as insufficient_data with a reason code, and the two never mix.

Actions:
  adjudicate - model-implied probability per scenario under the declared
               weights, delta from the operator marks, fired indicators,
               next re-mark due date, days to adjudication.
  calibrate  - Brier score of the marks against a resolved outcome, plus the
               Brier trend over marks_history when supplied.

Validation is fail-closed and returns the first contract violation found, in
this order: request envelope, action, as_of, framework shape, strengthens ids,
marks, observations, outcome, marks_history.

The evaluation date is the as_of input; execute() never reads the clock.
"""

import math
import os
import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import yaml

from skillware.core.base_skill import BaseSkill

REGISTRY_ID = "monitoring/business_diagnostic"

# Closed error registry: contract violations only. These codes are the skill's
# identity and never change per operator.
INVALID_REQUEST = "INVALID_REQUEST"
UNKNOWN_ACTION = "UNKNOWN_ACTION"
INVALID_AS_OF = "INVALID_AS_OF"
INVALID_FRAMEWORK_SCHEMA = "INVALID_FRAMEWORK_SCHEMA"
INVALID_MARKS_SCHEMA = "INVALID_MARKS_SCHEMA"
INVALID_OBSERVATIONS_SCHEMA = "INVALID_OBSERVATIONS_SCHEMA"
INVALID_OUTCOME_SCHEMA = "INVALID_OUTCOME_SCHEMA"
UNKNOWN_SCENARIO_ID = "UNKNOWN_SCENARIO_ID"
UNKNOWN_INDICATOR_ID = "UNKNOWN_INDICATOR_ID"
DUPLICATE_OBSERVATION = "DUPLICATE_OBSERVATION"
MARK_OUT_OF_RANGE = "MARK_OUT_OF_RANGE"
MARKS_NOT_NORMALIZED = "MARKS_NOT_NORMALIZED"
OBSERVATION_PREDATES_MARKS = "OBSERVATION_PREDATES_MARKS"
OBSERVATION_AFTER_ADJUDICATION = "OBSERVATION_AFTER_ADJUDICATION"

ERROR_REGISTRY = frozenset(
    {
        INVALID_REQUEST,
        UNKNOWN_ACTION,
        INVALID_AS_OF,
        INVALID_FRAMEWORK_SCHEMA,
        INVALID_MARKS_SCHEMA,
        INVALID_OBSERVATIONS_SCHEMA,
        INVALID_OUTCOME_SCHEMA,
        UNKNOWN_SCENARIO_ID,
        UNKNOWN_INDICATOR_ID,
        DUPLICATE_OBSERVATION,
        MARK_OUT_OF_RANGE,
        MARKS_NOT_NORMALIZED,
        OBSERVATION_PREDATES_MARKS,
        OBSERVATION_AFTER_ADJUDICATION,
    }
)

# Closed set of reason codes for the honest state (insufficient_data).
REASON_ADJUDICATION_DATE_PASSED = "adjudication_date_passed"

ACTION_ADJUDICATE = "adjudicate"
ACTION_CALIBRATE = "calibrate"
_ACTIONS = (ACTION_ADJUDICATE, ACTION_CALIBRATE)
_PARAM_KEYS = (
    "action",
    "as_of",
    "framework",
    "marks",
    "observations",
    "outcome",
    "marks_history",
)

_ID_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_MARK_MIN = 0.001
_MARK_MAX = 0.999
_SUM_TOLERANCE = 1e-6
_OBSERVED_VALUES = {"yes": 1, "no": -1}
_ROUNDING = 3


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


def _check_id(value: Any, code: str, path: str) -> None:
    _check_string(value, code, path)
    if not _ID_RE.match(value):
        _fail(code, f"{path}: does not match ^[A-Z][A-Z0-9_]*$")


def _check_date(value: Any, code: str, path: str) -> date:
    _check_string(value, code, path)
    if not _DATE_RE.match(value):
        _fail(code, f"{path}: expected an ISO date (YYYY-MM-DD)")
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail(code, f"{path}: expected a valid calendar date")
    return date.min  # unreachable; keeps the return type explicit


def _validate_framework(framework: Any) -> None:
    code = INVALID_FRAMEWORK_SCHEMA
    _require_object(framework, code, "framework")
    _check_exact_keys(
        framework,
        (
            "schema_version",
            "framework_id",
            "adjudication_date",
            "exhaustive",
            "scenarios",
            "indicators",
        ),
        (),
        code,
        "framework",
    )
    version = framework["schema_version"]
    if not _is_number(version) or version != 1:
        _fail(code, "framework.schema_version: expected the constant 1")
    _check_string(framework["framework_id"], code, "framework.framework_id")
    _check_date(framework["adjudication_date"], code, "framework.adjudication_date")
    if not isinstance(framework["exhaustive"], bool):
        _fail(code, "framework.exhaustive: expected a boolean")

    scenarios = framework["scenarios"]
    if not isinstance(scenarios, list) or not scenarios:
        _fail(code, "framework.scenarios: expected a non-empty array")
    seen_scenarios = set()
    for index, scenario in enumerate(scenarios):
        path = f"framework.scenarios[{index}]"
        _require_object(scenario, code, path)
        _check_exact_keys(scenario, ("id", "label", "criterion"), (), code, path)
        _check_id(scenario["id"], code, f"{path}.id")
        _check_string(scenario["label"], code, f"{path}.label")
        _check_string(scenario["criterion"], code, f"{path}.criterion")
        if scenario["id"] in seen_scenarios:
            _fail(code, f"{path}.id: duplicate scenario id '{scenario['id']}'")
        seen_scenarios.add(scenario["id"])

    indicators = framework["indicators"]
    if not isinstance(indicators, list):
        _fail(code, "framework.indicators: expected an array")
    seen_indicators = set()
    for index, indicator in enumerate(indicators):
        path = f"framework.indicators[{index}]"
        _require_object(indicator, code, path)
        _check_exact_keys(indicator, ("id", "label", "strengthens"), (), code, path)
        _check_id(indicator["id"], code, f"{path}.id")
        _check_string(indicator["label"], code, f"{path}.label")
        if indicator["id"] in seen_indicators:
            _fail(code, f"{path}.id: duplicate indicator id '{indicator['id']}'")
        seen_indicators.add(indicator["id"])
        strengthens = indicator["strengthens"]
        _require_object(strengthens, code, f"{path}.strengthens")
        for key in sorted(strengthens):
            _check_id(key, code, f"{path}.strengthens: key '{key}'")
            if not _is_number(strengthens[key]):
                _fail(code, f"{path}.strengthens.{key}: expected a number")


def _validate_marks(marks: Any, declared: List[str], path: str) -> None:
    code = INVALID_MARKS_SCHEMA
    _require_object(marks, code, path)
    _check_exact_keys(
        marks, ("marked_on", "remark_every_days", "values"), (), code, path
    )
    _check_date(marks["marked_on"], code, f"{path}.marked_on")
    every = marks["remark_every_days"]
    if not isinstance(every, int) or isinstance(every, bool) or every < 1:
        _fail(code, f"{path}.remark_every_days: expected an integer >= 1")
    values = marks["values"]
    _require_object(values, code, f"{path}.values")
    for key in sorted(values):
        _check_id(key, code, f"{path}.values: key '{key}'")
        if not _is_number(values[key]):
            _fail(code, f"{path}.values.{key}: expected a number")
    declared_set = set(declared)
    for key in sorted(values):
        if key not in declared_set:
            _fail(
                UNKNOWN_SCENARIO_ID,
                f"{path}.values: scenario '{key}' is not declared in "
                "framework.scenarios",
            )
    missing = [sid for sid in declared if sid not in values]
    if missing:
        _fail(
            code,
            f"{path}.values: missing marks for declared scenario(s) "
            + ", ".join(missing),
        )
    for sid in declared:
        value = values[sid]
        if value < _MARK_MIN or value > _MARK_MAX:
            _fail(
                MARK_OUT_OF_RANGE,
                f"{path}.values.{sid}: {value} is outside "
                f"[{_MARK_MIN}, {_MARK_MAX}]",
            )
    total = sum(values[sid] for sid in declared)
    if abs(total - 1.0) > _SUM_TOLERANCE:
        _fail(
            MARKS_NOT_NORMALIZED,
            f"{path}.values: marks sum to {total!r}, expected 1 within "
            f"{_SUM_TOLERANCE}",
        )


def _validate_observations(
    observations: Any,
    declared_indicators: List[str],
    marked_on: date,
    adjudication_date: date,
) -> None:
    code = INVALID_OBSERVATIONS_SCHEMA
    if not isinstance(observations, list):
        _fail(code, "observations: expected an array")
    for index, observation in enumerate(observations):
        path = f"observations[{index}]"
        _require_object(observation, code, path)
        _check_exact_keys(
            observation, ("indicator", "observed", "on"), ("source",), code, path
        )
        _check_id(observation["indicator"], code, f"{path}.indicator")
        if observation["observed"] not in _OBSERVED_VALUES:
            _fail(code, f"{path}.observed: expected one of yes, no")
        _check_date(observation["on"], code, f"{path}.on")
        if "source" in observation:
            _check_string(observation["source"], code, f"{path}.source")

    declared_set = set(declared_indicators)
    for index, observation in enumerate(observations):
        indicator = observation["indicator"]
        if indicator not in declared_set:
            _fail(
                UNKNOWN_INDICATOR_ID,
                f"observations[{index}]: indicator '{indicator}' is not declared "
                "in framework.indicators",
            )

    seen = set()
    for index, observation in enumerate(observations):
        indicator = observation["indicator"]
        if indicator in seen:
            _fail(
                DUPLICATE_OBSERVATION,
                f"observations[{index}]: indicator '{indicator}' is observed more "
                "than once; the host must de-duplicate",
            )
        seen.add(indicator)

    for index, observation in enumerate(observations):
        observed_on = date.fromisoformat(observation["on"])
        if observed_on <= marked_on:
            _fail(
                OBSERVATION_PREDATES_MARKS,
                f"observations[{index}].on: {observation['on']} is not after "
                f"marks.marked_on {marked_on.isoformat()}",
            )
        if observed_on > adjudication_date:
            _fail(
                OBSERVATION_AFTER_ADJUDICATION,
                f"observations[{index}].on: {observation['on']} is after "
                f"framework.adjudication_date {adjudication_date.isoformat()}",
            )


def _validate_outcome(outcome: Any, declared: List[str], required: bool) -> None:
    code = INVALID_OUTCOME_SCHEMA
    if outcome is None:
        if required:
            _fail(code, "outcome: required for action calibrate")
        return
    _require_object(outcome, code, "outcome")
    _check_exact_keys(outcome, ("resolved_on", "scenario"), (), code, "outcome")
    _check_date(outcome["resolved_on"], code, "outcome.resolved_on")
    _check_id(outcome["scenario"], code, "outcome.scenario")
    if outcome["scenario"] not in declared:
        _fail(
            UNKNOWN_SCENARIO_ID,
            f"outcome.scenario: '{outcome['scenario']}' is not declared in "
            "framework.scenarios",
        )


def _validate_marks_history(history: Any, declared: List[str]) -> None:
    if not isinstance(history, list):
        _fail(INVALID_MARKS_SCHEMA, "marks_history: expected an array")
    for index, marks in enumerate(history):
        _validate_marks(marks, declared, f"marks_history[{index}]")


def _logit(probability: float) -> float:
    return math.log(probability / (1.0 - probability))


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-value))


def _round(value: float) -> float:
    # Adding 0.0 folds a negative zero into 0.0 so output is canonical.
    return round(value, _ROUNDING) + 0.0


def _brier(values: Dict[str, float], declared: List[str], winner: str) -> float:
    total = 0.0
    for sid in declared:
        target = 1.0 if sid == winner else 0.0
        total += (values[sid] - target) ** 2
    return _round(total)


def _model_implied(
    framework: Dict[str, Any],
    marks: Dict[str, Any],
    observations: List[Dict[str, Any]],
) -> Tuple[Dict[str, float], Dict[str, List[str]]]:
    """Return (model-implied probability per scenario, fired ids per scenario)."""
    signal = {
        observation["indicator"]: _OBSERVED_VALUES[observation["observed"]]
        for observation in observations
    }
    values = marks["values"]
    raw: Dict[str, float] = {}
    fired: Dict[str, List[str]] = {}
    for scenario in framework["scenarios"]:
        sid = scenario["id"]
        shift = 0.0
        fired_here: List[str] = []
        for indicator in framework["indicators"]:
            weight = indicator["strengthens"].get(sid)
            if weight is None:
                continue
            observed = signal.get(indicator["id"], 0)
            if observed == 0:
                continue
            shift += weight * observed
            fired_here.append(indicator["id"])
        raw[sid] = _sigmoid(_logit(values[sid]) + shift)
        fired[sid] = fired_here
    if framework["exhaustive"]:
        total = sum(raw.values())
        raw = {sid: value / total for sid, value in raw.items()}
    return raw, fired


def _adjudicate(
    params: Dict[str, Any], as_of: date, adjudication_date: date
) -> Dict[str, Any]:
    framework = params["framework"]
    marks = params["marks"]
    observations = params.get("observations") or []
    declared = [scenario["id"] for scenario in framework["scenarios"]]
    marked_on = date.fromisoformat(marks["marked_on"])
    _validate_observations(
        observations,
        [indicator["id"] for indicator in framework["indicators"]],
        marked_on,
        adjudication_date,
    )
    _validate_outcome(params.get("outcome"), declared, required=False)

    next_due = marked_on + timedelta(days=marks["remark_every_days"])
    calibration = {
        "next_remark_due": next_due.isoformat(),
        "days_to_adjudication": (adjudication_date - as_of).days,
        "brier": None,
    }
    insufficient_data: List[Dict[str, Any]] = []
    scenarios: List[Dict[str, Any]] = []
    fired_any = False

    if as_of >= adjudication_date:
        insufficient_data.append(
            {
                "reason": REASON_ADJUDICATION_DATE_PASSED,
                "detail": {
                    "as_of": as_of.isoformat(),
                    "adjudication_date": adjudication_date.isoformat(),
                },
            }
        )
        for sid in declared:
            scenarios.append(
                {
                    "id": sid,
                    "operator_mark": marks["values"][sid],
                    "model_implied": None,
                    "delta": None,
                    "fired": [],
                }
            )
    else:
        implied, fired = _model_implied(framework, marks, observations)
        for sid in declared:
            mark = marks["values"][sid]
            scenarios.append(
                {
                    "id": sid,
                    "operator_mark": mark,
                    "model_implied": _round(implied[sid]),
                    "delta": _round(implied[sid] - mark),
                    "fired": fired[sid],
                }
            )
            if fired[sid]:
                fired_any = True

    return {
        "status": "completed",
        "framework_id": framework["framework_id"],
        "as_of": as_of.isoformat(),
        "scenarios": scenarios,
        "calibration": calibration,
        "fired_any": fired_any,
        "marks_stale": as_of > next_due,
        "insufficient": bool(insufficient_data),
        "insufficient_data": insufficient_data,
    }


def _calibrate(
    params: Dict[str, Any], as_of: date, adjudication_date: date
) -> Dict[str, Any]:
    framework = params["framework"]
    marks = params["marks"]
    declared = [scenario["id"] for scenario in framework["scenarios"]]
    marked_on = date.fromisoformat(marks["marked_on"])
    if "observations" in params and params["observations"] is not None:
        _validate_observations(
            params["observations"],
            [indicator["id"] for indicator in framework["indicators"]],
            marked_on,
            adjudication_date,
        )
    outcome = params.get("outcome")
    _validate_outcome(outcome, declared, required=True)
    history = params.get("marks_history")
    if history is not None:
        _validate_marks_history(history, declared)

    winner = outcome["scenario"]
    brier_trend: Optional[List[Dict[str, Any]]] = None
    if history is not None:
        ordered = sorted(
            history, key=lambda item: date.fromisoformat(item["marked_on"])
        )
        brier_trend = [
            {
                "marked_on": item["marked_on"],
                "brier": _brier(item["values"], declared, winner),
            }
            for item in ordered
        ]

    next_due = marked_on + timedelta(days=marks["remark_every_days"])
    scenarios = [
        {"id": sid, "operator_mark": marks["values"][sid], "fired": []}
        for sid in declared
    ]
    return {
        "status": "completed",
        "framework_id": framework["framework_id"],
        "as_of": as_of.isoformat(),
        "scenarios": scenarios,
        "calibration": {
            "next_remark_due": next_due.isoformat(),
            "days_to_adjudication": (adjudication_date - as_of).days,
            "brier": _brier(marks["values"], declared, winner),
            "brier_trend": brier_trend,
        },
        "fired_any": False,
        "marks_stale": as_of > next_due,
        "insufficient": False,
        "insufficient_data": [],
    }


def evaluate_business_diagnostic(params: Dict[str, Any]) -> Dict[str, Any]:
    """Pure evaluation entry point: validates, cross-checks, and evaluates."""
    if not isinstance(params, dict):
        _fail(INVALID_REQUEST, "parameters: expected a JSON object with 'action'")
    for key in sorted(params):
        if key not in _PARAM_KEYS:
            _fail(INVALID_REQUEST, f"parameters: unexpected property '{key}'")
    if "action" not in params:
        _fail(UNKNOWN_ACTION, "action: required input is missing")
    action = params["action"]
    if action not in _ACTIONS:
        _fail(UNKNOWN_ACTION, f"action: expected one of {', '.join(_ACTIONS)}")
    if "as_of" not in params:
        _fail(INVALID_AS_OF, "as_of: required input is missing")
    as_of = _check_date(params["as_of"], INVALID_AS_OF, "as_of")
    if "framework" not in params:
        _fail(INVALID_FRAMEWORK_SCHEMA, "framework: required input is missing")
    if "marks" not in params:
        _fail(INVALID_MARKS_SCHEMA, "marks: required input is missing")

    framework = params["framework"]
    _validate_framework(framework)
    declared = [scenario["id"] for scenario in framework["scenarios"]]
    declared_set = set(declared)
    for index, indicator in enumerate(framework["indicators"]):
        for key in sorted(indicator["strengthens"]):
            if key not in declared_set:
                _fail(
                    UNKNOWN_SCENARIO_ID,
                    f"framework.indicators[{index}].strengthens: scenario '{key}' "
                    "is not declared in framework.scenarios",
                )
    _validate_marks(params["marks"], declared, "marks")
    adjudication_date = date.fromisoformat(framework["adjudication_date"])

    if action == ACTION_ADJUDICATE:
        return _adjudicate(params, as_of, adjudication_date)
    return _calibrate(params, as_of, adjudication_date)


class BusinessDiagnosticSkill(BaseSkill):
    """Deterministic scenario ledger and calibration over operator inputs."""

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as handle:
                return yaml.safe_load(handle)
        return {"name": REGISTRY_ID, "version": "0.1.0"}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return evaluate_business_diagnostic(params)
        except _ContractError as error:
            return {
                "status": "error",
                "error": {"code": error.code, "detail": error.detail},
            }

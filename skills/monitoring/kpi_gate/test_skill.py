"""Bundle tests for monitoring/kpi_gate.

All tests are offline and deterministic: fixtures under fixtures/ and kb/
exercise the exact interface frozen in issue #317, including the end-to-end
example, every closed-registry error code, the honesty-floor boundary, and
bit-identical repeat execution. No network access is required or permitted.
"""

import copy
import json
import os
import re

import pytest
import yaml

from skillware.core.loader import SkillLoader

from . import skill as skill_module
from .skill import (
    BENCHMARK_REF_UNRESOLVED,
    BENCHMARK_VERSION_MISSING,
    ERROR_REGISTRY,
    INVALID_BENCHMARKS_SCHEMA,
    INVALID_METRICS_SCHEMA,
    INVALID_POLICY_SCHEMA,
    NO_METRICS_PROVIDED,
    REASON_HONESTY_FLOOR_UNMET,
    REASON_METRIC_MISSING,
    UNKNOWN_DENOMINATOR_METRIC,
    UNKNOWN_METRIC_KEY,
    UNKNOWN_RULE_METRIC,
    KpiGateSkill,
)

BUNDLE_DIR = os.path.dirname(__file__)
FIXTURES_DIR = os.path.join(BUNDLE_DIR, "fixtures")
KB_DIR = os.path.join(BUNDLE_DIR, "kb")


def _load_json(directory, name):
    with open(os.path.join(directory, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_yaml(directory, name):
    with open(os.path.join(directory, name), "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture
def skill():
    return KpiGateSkill()


@pytest.fixture
def manifest():
    return _load_yaml(BUNDLE_DIR, "manifest.yaml")


@pytest.fixture
def e2e_params():
    return {
        "metrics": _load_json(FIXTURES_DIR, "example_snapshot.json"),
        "policy": _load_yaml(FIXTURES_DIR, "example_charter.yaml"),
        "benchmarks": _load_json(KB_DIR, "benchmarks_demo.json"),
    }


@pytest.fixture
def boundary_charter():
    return _load_yaml(FIXTURES_DIR, "charter_floor_boundary.yaml")


def _assert_error(result, code):
    assert result["status"] == "error"
    assert result["error"]["code"] == code
    assert result["error"]["detail"]
    assert "findings" not in result


def test_skill_manifest_consistency(skill, manifest, e2e_params):
    assert skill.manifest["name"] == manifest["name"] == "monitoring/kpi_gate"
    assert skill.manifest["version"] == manifest["version"]
    assert manifest["requirements"] == []
    assert "env_vars" not in manifest
    assert "output" not in manifest
    result = skill.execute(e2e_params)
    for key in manifest["outputs"]:
        assert key in result


def test_skill_loader_can_import():
    bundle = SkillLoader.load_skill("monitoring/kpi_gate")
    assert bundle["manifest"]["name"] == "monitoring/kpi_gate"
    assert hasattr(bundle["module"], "KpiGateSkill")


def test_error_registry_is_closed_and_final():
    assert ERROR_REGISTRY == frozenset(
        {
            "INVALID_METRICS_SCHEMA",
            "INVALID_POLICY_SCHEMA",
            "INVALID_BENCHMARKS_SCHEMA",
            "NO_METRICS_PROVIDED",
            "UNKNOWN_METRIC_KEY",
            "UNKNOWN_RULE_METRIC",
            "UNKNOWN_DENOMINATOR_METRIC",
            "BENCHMARK_VERSION_MISSING",
            "BENCHMARK_REF_UNRESOLVED",
        }
    )
    assert "FUNNEL_MODE_REQUIRED" not in ERROR_REGISTRY


def test_e2e_matches_expected_findings_exactly(skill, e2e_params):
    expected = _load_json(FIXTURES_DIR, "expected_findings.json")
    result = skill.execute(e2e_params)
    assert result == expected
    assert json.dumps(result, sort_keys=True) == json.dumps(expected, sort_keys=True)


def test_repeat_execution_is_bit_identical(skill, e2e_params):
    first = skill.execute(copy.deepcopy(e2e_params))
    second = skill.execute(copy.deepcopy(e2e_params))
    assert json.dumps(first) == json.dumps(second)


def test_invalid_metrics_schema(skill, e2e_params):
    params = dict(e2e_params)
    params["metrics"] = _load_json(FIXTURES_DIR, "invalid_snapshot_schema.json")
    _assert_error(skill.execute(params), INVALID_METRICS_SCHEMA)


def test_no_metrics_provided(skill, e2e_params):
    params = dict(e2e_params)
    params["metrics"] = _load_json(FIXTURES_DIR, "snapshot_empty_metrics.json")
    _assert_error(skill.execute(params), NO_METRICS_PROVIDED)


def test_unknown_metric_key(skill, e2e_params):
    params = dict(e2e_params)
    params["metrics"] = _load_json(FIXTURES_DIR, "snapshot_unknown_key.json")
    result = skill.execute(params)
    _assert_error(result, UNKNOWN_METRIC_KEY)
    assert "undeclared_extra_metric" in result["error"]["detail"]


def test_invalid_policy_schema(skill, e2e_params):
    params = dict(e2e_params)
    params["policy"] = _load_yaml(FIXTURES_DIR, "invalid_charter_schema.yaml")
    _assert_error(skill.execute(params), INVALID_POLICY_SCHEMA)


def test_dependent_required_rejected(skill, e2e_params):
    params = dict(e2e_params)
    params["policy"] = _load_yaml(
        FIXTURES_DIR, "invalid_charter_dependent_required.yaml"
    )
    result = skill.execute(params)
    _assert_error(result, INVALID_POLICY_SCHEMA)
    assert "dependentRequired" in result["error"]["detail"]


def test_unknown_rule_metric(skill):
    params = {
        "metrics": {
            "schema_version": 1,
            "period": {
                "start": "2026-08-17",
                "end": "2026-08-23",
                "granularity": "weekly",
            },
            "metrics": {"bookings": 2},
        },
        "policy": _load_yaml(FIXTURES_DIR, "invalid_charter_unknown_rule_metric.yaml"),
    }
    _assert_error(skill.execute(params), UNKNOWN_RULE_METRIC)


def test_unknown_denominator_metric(skill):
    params = {
        "metrics": {
            "schema_version": 1,
            "period": {
                "start": "2026-08-17",
                "end": "2026-08-23",
                "granularity": "weekly",
            },
            "metrics": {"reply_to_booking_rate_pct": 4.0},
        },
        "policy": _load_yaml(FIXTURES_DIR, "invalid_charter_unknown_denominator.yaml"),
    }
    _assert_error(skill.execute(params), UNKNOWN_DENOMINATOR_METRIC)


def test_invalid_benchmarks_schema(skill, e2e_params):
    params = dict(e2e_params)
    params["benchmarks"] = _load_json(FIXTURES_DIR, "invalid_benchmarks_schema.json")
    _assert_error(skill.execute(params), INVALID_BENCHMARKS_SCHEMA)


def test_benchmark_version_missing(skill, e2e_params):
    params = {"metrics": e2e_params["metrics"], "policy": e2e_params["policy"]}
    _assert_error(skill.execute(params), BENCHMARK_VERSION_MISSING)


def test_benchmark_ref_unresolved(skill, e2e_params):
    params = dict(e2e_params)
    params["benchmarks"] = _load_json(FIXTURES_DIR, "benchmarks_missing_ref.json")
    _assert_error(skill.execute(params), BENCHMARK_REF_UNRESOLVED)


def test_floor_at_minimum_denominator_computes(skill, boundary_charter):
    params = {
        "metrics": _load_json(FIXTURES_DIR, "snapshot_floor_at_min.json"),
        "policy": boundary_charter,
    }
    result = skill.execute(params)
    assert result["status"] == "completed"
    assert result["benchmark_version"] is None
    assert result["findings"] == [
        {
            "finding": "BOOKING_CONVERSION_TRACKED",
            "severity": "warning",
            "detail": {
                "metric": "reply_to_booking_rate_pct",
                "threshold": ">= 10",
                "observed": 4.0,
            },
            "action": "none — surfaced for the operator",
        }
    ]


def test_floor_below_minimum_denominator_refuses(skill, boundary_charter):
    params = {
        "metrics": _load_json(FIXTURES_DIR, "snapshot_floor_below_min.json"),
        "policy": boundary_charter,
    }
    result = skill.execute(params)
    assert result["status"] == "completed"
    assert result["findings"] == [
        {
            "state": "insufficient_data",
            "detail": {"metric": "reply_to_booking_rate_pct"},
            "reason": "cohort_attribution_unavailable",
        }
    ]


def test_granularity_floor_refusal_names_unmet_floor(skill, boundary_charter):
    snapshot = _load_json(FIXTURES_DIR, "snapshot_floor_at_min.json")
    snapshot["period"]["granularity"] = "daily"
    result = skill.execute({"metrics": snapshot, "policy": boundary_charter})
    assert result["status"] == "completed"
    assert result["findings"] == [
        {
            "state": "insufficient_data",
            "detail": {
                "metric": "reply_to_booking_rate_pct",
                "unmet_floor": "granularity",
            },
            "reason": "cohort_attribution_unavailable",
        }
    ]


def test_missing_denominator_refusal_names_unmet_floor(skill, boundary_charter):
    snapshot = _load_json(FIXTURES_DIR, "snapshot_floor_at_min.json")
    del snapshot["metrics"]["replies"]
    result = skill.execute({"metrics": snapshot, "policy": boundary_charter})
    assert result["status"] == "completed"
    assert result["findings"] == [
        {
            "state": "insufficient_data",
            "detail": {
                "metric": "reply_to_booking_rate_pct",
                "unmet_floor": "denominator",
            },
            "reason": "cohort_attribution_unavailable",
        }
    ]


def test_floor_without_reason_code_uses_fixed_default(skill, boundary_charter):
    policy = copy.deepcopy(boundary_charter)
    del policy["rules"][0]["requires"]["reason_code"]
    snapshot = _load_json(FIXTURES_DIR, "snapshot_floor_below_min.json")
    result = skill.execute({"metrics": snapshot, "policy": policy})
    assert result["findings"][0]["reason"] == REASON_HONESTY_FLOOR_UNMET


def test_metric_missing_from_snapshot_refuses(skill):
    params = {
        "metrics": {
            "schema_version": 1,
            "period": {
                "start": "2026-08-17",
                "end": "2026-08-23",
                "granularity": "weekly",
            },
            "metrics": {"replies": 5},
        },
        "policy": {
            "schema_version": 2,
            "policy_id": "missing_metric_demo",
            "metrics": ["bookings", "replies"],
            "rules": [
                {
                    "id": "NO_BOOKING",
                    "metric": "bookings",
                    "check": {"op": "gte", "threshold": 1},
                    "severity": "error",
                }
            ],
        },
    }
    result = skill.execute(params)
    assert result["status"] == "completed"
    assert result["findings"] == [
        {
            "state": "insufficient_data",
            "detail": {"metric": "bookings"},
            "reason": REASON_METRIC_MISSING,
        }
    ]


def test_passing_rules_emit_no_findings(skill, boundary_charter):
    snapshot = _load_json(FIXTURES_DIR, "snapshot_floor_at_min.json")
    snapshot["metrics"]["reply_to_booking_rate_pct"] = 50.0
    result = skill.execute({"metrics": snapshot, "policy": boundary_charter})
    assert result["status"] == "completed"
    assert result["findings"] == []


def test_unlimited_literal_upper_bound_always_passes(skill):
    params = {
        "metrics": {
            "schema_version": 1,
            "period": {
                "start": "2026-08-17",
                "end": "2026-08-23",
                "granularity": "weekly",
            },
            "metrics": {"active_clients": 999},
        },
        "policy": {
            "schema_version": 2,
            "policy_id": "unlimited_demo",
            "metrics": ["active_clients"],
            "rules": [
                {
                    "id": "CAPACITY_CAP",
                    "metric": "active_clients",
                    "check": {"op": "lte", "threshold": "unlimited"},
                    "severity": "error",
                }
            ],
        },
    }
    result = skill.execute(params)
    assert result["status"] == "completed"
    assert result["findings"] == []


def test_unlimited_literal_rejected_outside_upper_bound_ops(skill):
    params = {
        "metrics": {
            "schema_version": 1,
            "period": {
                "start": "2026-08-17",
                "end": "2026-08-23",
                "granularity": "weekly",
            },
            "metrics": {"active_clients": 1},
        },
        "policy": {
            "schema_version": 2,
            "policy_id": "unlimited_misuse_demo",
            "metrics": ["active_clients"],
            "rules": [
                {
                    "id": "CAPACITY_FLOOR",
                    "metric": "active_clients",
                    "check": {"op": "gte", "threshold": "unlimited"},
                    "severity": "error",
                }
            ],
        },
    }
    _assert_error(skill.execute(params), INVALID_POLICY_SCHEMA)


def test_benchmark_tolerance_loosens_toward_passing(skill, e2e_params):
    policy = {
        "schema_version": 2,
        "policy_id": "tolerance_demo",
        "metrics": ["download_rate_pct"],
        "rules": [
            {
                "id": "DOWNLOAD_RATE_BELOW_DOCTRINE",
                "metric": "download_rate_pct",
                "check": {
                    "op": "gte",
                    "benchmark_ref": "lead_magnet_download_rate_pct",
                    "tolerance_pct": 10,
                },
                "severity": "warning",
            }
        ],
    }
    snapshot = {
        "schema_version": 1,
        "period": {
            "start": "2026-08-17",
            "end": "2026-08-23",
            "granularity": "weekly",
        },
        "metrics": {"download_rate_pct": 23.0},
    }
    benchmarks = e2e_params["benchmarks"]
    passing = skill.execute(
        {"metrics": snapshot, "policy": policy, "benchmarks": benchmarks}
    )
    assert passing["findings"] == []

    snapshot["metrics"]["download_rate_pct"] = 22.0
    failing = skill.execute(
        {"metrics": snapshot, "policy": policy, "benchmarks": benchmarks}
    )
    assert failing["findings"][0]["detail"]["threshold"] == ">= 22.5 (benchmark)"
    assert failing["findings"][0]["detail"]["observed"] == 22.0


def test_applies_to_is_echoed_without_semantics(skill):
    params = {
        "metrics": {
            "schema_version": 1,
            "period": {
                "start": "2026-08-17",
                "end": "2026-08-23",
                "granularity": "weekly",
            },
            "metrics": {"one_to_one_price_usd": 4000},
        },
        "policy": {
            "schema_version": 2,
            "policy_id": "applies_to_demo",
            "metrics": ["one_to_one_price_usd"],
            "rules": [
                {
                    "id": "FLOOR_PRICE_BREACH",
                    "metric": "one_to_one_price_usd",
                    "check": {
                        "op": "gte",
                        "threshold": 6000,
                        "applies_to": ["one_to_one"],
                    },
                    "severity": "error",
                }
            ],
        },
    }
    result = skill.execute(params)
    assert result["findings"][0]["detail"]["applies_to"] == ["one_to_one"]


def test_error_envelope_and_findings_never_mix(skill, e2e_params):
    completed = skill.execute(e2e_params)
    assert completed["status"] == "completed"
    assert "error" not in completed

    broken = dict(e2e_params)
    broken["metrics"] = _load_json(FIXTURES_DIR, "snapshot_empty_metrics.json")
    errored = skill.execute(broken)
    assert errored["status"] == "error"
    assert "findings" not in errored
    assert errored["error"]["code"] in ERROR_REGISTRY


def test_skill_module_imports_no_network_modules():
    source_path = os.path.join(BUNDLE_DIR, "skill.py")
    with open(source_path, "r", encoding="utf-8") as handle:
        source = handle.read()
    imports = re.findall(r"^(?:import|from)\s+([\w.]+)", source, re.MULTILINE)
    forbidden = {"socket", "http", "urllib", "requests", "ssl", "ftplib"}
    imported_roots = {name.split(".")[0] for name in imports}
    assert not (imported_roots & forbidden)
    assert not hasattr(skill_module, "socket")

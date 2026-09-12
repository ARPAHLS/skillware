"""Bundle tests for monitoring/business_diagnostic.

All tests are offline and deterministic: fixtures under fixtures/ and kb/
exercise the v0.1 interface agreed in issue #338, including the end-to-end
example, every closed-registry error code, the honest state, boundary dates,
and bit-identical repeat execution. No network access is required or
permitted.
"""

import copy
import json
import os
import re

import pytest

from skillware.core.loader import SkillLoader

from . import skill as skill_module
from .skill import (
    ERROR_REGISTRY,
    INVALID_MARKS_SCHEMA,
    INVALID_REQUEST,
    REASON_ADJUDICATION_DATE_PASSED,
    BusinessDiagnosticSkill,
)

BUNDLE_DIR = os.path.dirname(__file__)
FIXTURES_DIR = os.path.join(BUNDLE_DIR, "fixtures")
KB_DIR = os.path.join(BUNDLE_DIR, "kb")

# One minimal fixture per closed-registry code. test_error_fixtures_cover_registry
# pins this mapping to ERROR_REGISTRY so no code can be added without a test.
ERROR_FIXTURES = {
    "INVALID_REQUEST": "error_invalid_request.json",
    "UNKNOWN_ACTION": "error_unknown_action.json",
    "INVALID_AS_OF": "error_invalid_as_of.json",
    "INVALID_FRAMEWORK_SCHEMA": "error_invalid_framework_schema.json",
    "INVALID_MARKS_SCHEMA": "error_invalid_marks_schema.json",
    "INVALID_OBSERVATIONS_SCHEMA": "error_invalid_observations_schema.json",
    "INVALID_OUTCOME_SCHEMA": "error_invalid_outcome_schema.json",
    "UNKNOWN_SCENARIO_ID": "error_unknown_scenario_id.json",
    "UNKNOWN_INDICATOR_ID": "error_unknown_indicator_id.json",
    "DUPLICATE_OBSERVATION": "error_duplicate_observation.json",
    "MARK_OUT_OF_RANGE": "error_mark_out_of_range.json",
    "MARKS_NOT_NORMALIZED": "error_marks_not_normalized.json",
    "OBSERVATION_PREDATES_MARKS": "error_observation_predates_marks.json",
    "OBSERVATION_AFTER_ADJUDICATION": "error_observation_after_adjudication.json",
}


def _load_json(folder, name):
    with open(os.path.join(folder, name), "r", encoding="utf-8") as handle:
        return json.load(handle)


@pytest.fixture
def skill():
    return BusinessDiagnosticSkill()


@pytest.fixture
def manifest():
    import yaml

    with open(os.path.join(BUNDLE_DIR, "manifest.yaml"), "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


@pytest.fixture
def adjudicate_params():
    return _load_json(FIXTURES_DIR, "example_adjudicate_params.json")


@pytest.fixture
def calibrate_params():
    return _load_json(FIXTURES_DIR, "example_calibrate_params.json")


def _assert_error(result, code):
    assert result["status"] == "error"
    assert result["error"]["code"] == code
    assert result["error"]["detail"]
    assert "scenarios" not in result


def test_skill_manifest_consistency(
    skill, manifest, adjudicate_params, calibrate_params
):
    assert skill.manifest["name"] == manifest["name"]
    assert manifest["name"] == "monitoring/business_diagnostic"
    assert skill.manifest["version"] == manifest["version"]
    assert manifest["requirements"] == []
    assert "env_vars" not in manifest
    assert "output" not in manifest
    for params in (adjudicate_params, calibrate_params):
        result = skill.execute(params)
        for key in manifest["outputs"]:
            assert key in result


def test_manifest_identity_matches_folder(manifest):
    category = os.path.basename(os.path.dirname(BUNDLE_DIR))
    folder = os.path.basename(BUNDLE_DIR)
    assert manifest["name"] == f"{category}/{folder}"


def test_manifest_parameters_validate_fixtures(
    skill, adjudicate_params, calibrate_params
):
    assert skill.validate_params(adjudicate_params) is True
    assert skill.validate_params(calibrate_params) is True


def test_skill_loader_can_import():
    bundle = SkillLoader.load_skill("monitoring/business_diagnostic")
    assert bundle["manifest"]["name"] == "monitoring/business_diagnostic"
    assert hasattr(bundle["module"], "BusinessDiagnosticSkill")


def test_error_registry_is_closed_and_final():
    assert ERROR_REGISTRY == frozenset(
        {
            "INVALID_REQUEST",
            "UNKNOWN_ACTION",
            "INVALID_AS_OF",
            "INVALID_FRAMEWORK_SCHEMA",
            "INVALID_MARKS_SCHEMA",
            "INVALID_OBSERVATIONS_SCHEMA",
            "INVALID_OUTCOME_SCHEMA",
            "UNKNOWN_SCENARIO_ID",
            "UNKNOWN_INDICATOR_ID",
            "DUPLICATE_OBSERVATION",
            "MARK_OUT_OF_RANGE",
            "MARKS_NOT_NORMALIZED",
            "OBSERVATION_PREDATES_MARKS",
            "OBSERVATION_AFTER_ADJUDICATION",
        }
    )


def test_error_fixtures_cover_registry():
    assert set(ERROR_FIXTURES) == set(ERROR_REGISTRY)


@pytest.mark.parametrize("code", sorted(ERROR_FIXTURES))
def test_each_error_code_from_its_fixture(skill, code):
    params = _load_json(FIXTURES_DIR, ERROR_FIXTURES[code])
    _assert_error(skill.execute(params), code)


def test_marks_missing_scenario_is_marks_schema_error(skill):
    params = _load_json(FIXTURES_DIR, "error_marks_missing_scenario.json")
    result = skill.execute(params)
    _assert_error(result, INVALID_MARKS_SCHEMA)
    assert "D" in result["error"]["detail"]


def test_e2e_adjudicate_matches_expected_exactly(skill, adjudicate_params):
    expected = _load_json(FIXTURES_DIR, "expected_adjudicate.json")
    result = skill.execute(adjudicate_params)
    assert result == expected
    assert json.dumps(result, sort_keys=True) == json.dumps(expected, sort_keys=True)


def test_e2e_calibrate_matches_expected_exactly(skill, calibrate_params):
    expected = _load_json(FIXTURES_DIR, "expected_calibrate.json")
    result = skill.execute(calibrate_params)
    assert result == expected
    assert result["calibration"]["brier"] == 0.425
    assert result["calibration"]["brier_trend"] is None


def test_kb_demo_framework_equals_e2e_framework(adjudicate_params):
    demo = _load_json(KB_DIR, "demo_scenarios.json")
    assert demo["framework"] == adjudicate_params["framework"]
    assert demo["generated_at"]
    assert demo["sources"]


def test_repeat_execution_is_bit_identical(skill, adjudicate_params, calibrate_params):
    for params in (adjudicate_params, calibrate_params):
        first = skill.execute(copy.deepcopy(params))
        second = skill.execute(copy.deepcopy(params))
        assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_brier_trend_sorted_ascending_by_marked_on(skill, calibrate_params):
    params = dict(calibrate_params)
    params["marks_history"] = _load_json(FIXTURES_DIR, "example_marks_history.json")
    assert (
        params["marks_history"][0]["marked_on"]
        > params["marks_history"][1]["marked_on"]
    )
    result = skill.execute(params)
    assert result["status"] == "completed"
    assert result["calibration"]["brier_trend"] == _load_json(
        FIXTURES_DIR, "expected_brier_trend.json"
    )


def test_non_exhaustive_updates_independently(skill, adjudicate_params):
    params = copy.deepcopy(adjudicate_params)
    params["framework"]["exhaustive"] = False
    result = skill.execute(params)
    by_id = {row["id"]: row for row in result["scenarios"]}
    assert by_id["A"]["model_implied"] == 0.324
    assert by_id["B"]["model_implied"] == 0.332
    assert by_id["C"]["model_implied"] == 0.3
    assert by_id["D"]["model_implied"] == 0.1
    assert by_id["C"]["delta"] == 0.0
    assert by_id["A"]["fired"] == ["I01"]
    assert by_id["C"]["fired"] == []


def test_observed_no_moves_in_negative_direction(skill, adjudicate_params):
    params = copy.deepcopy(adjudicate_params)
    params["framework"]["exhaustive"] = False
    params["observations"][0]["observed"] = "no"
    result = skill.execute(params)
    by_id = {row["id"]: row for row in result["scenarios"]}
    assert by_id["A"]["model_implied"] == 0.061
    assert by_id["A"]["delta"] == -0.089
    assert by_id["B"]["model_implied"] == 0.574
    assert by_id["B"]["delta"] == 0.124
    assert by_id["A"]["fired"] == ["I01"]
    assert by_id["B"]["fired"] == ["I01"]
    assert result["fired_any"] is True


def test_identity_without_indicators_or_observations(skill, adjudicate_params):
    params = copy.deepcopy(adjudicate_params)
    params["framework"]["indicators"] = []
    params["observations"] = []
    result = skill.execute(params)
    assert result["status"] == "completed"
    assert result["fired_any"] is False
    for row in result["scenarios"]:
        assert row["model_implied"] == row["operator_mark"]
        assert row["delta"] == 0.0
        assert row["fired"] == []


def test_marks_stale_boundary(skill, adjudicate_params):
    on_due = copy.deepcopy(adjudicate_params)
    on_due["as_of"] = "2026-10-16"
    assert skill.execute(on_due)["marks_stale"] is False
    after_due = copy.deepcopy(adjudicate_params)
    after_due["as_of"] = "2026-10-17"
    assert skill.execute(after_due)["marks_stale"] is True


def test_adjudication_date_passed_is_honest_state(skill):
    params = _load_json(FIXTURES_DIR, "adjudication_date_passed_params.json")
    expected = _load_json(FIXTURES_DIR, "expected_adjudication_date_passed.json")
    result = skill.execute(params)
    assert result == expected
    assert result["insufficient"] is True
    assert result["insufficient_data"][0]["reason"] == REASON_ADJUDICATION_DATE_PASSED
    assert "error" not in result


def test_day_before_adjudication_still_computes(skill, adjudicate_params):
    params = copy.deepcopy(adjudicate_params)
    params["as_of"] = "2027-12-30"
    result = skill.execute(params)
    assert result["insufficient"] is False
    assert result["calibration"]["days_to_adjudication"] == 1
    assert result["scenarios"][0]["model_implied"] == 0.307


def test_error_envelope_and_completed_run_never_mix(skill, adjudicate_params):
    completed = skill.execute(adjudicate_params)
    assert completed["status"] == "completed"
    assert "error" not in completed
    broken = dict(adjudicate_params)
    broken["action"] = "forecast"
    errored = skill.execute(broken)
    assert errored["status"] == "error"
    assert "scenarios" not in errored
    assert errored["error"]["code"] in ERROR_REGISTRY


def test_unexpected_top_level_property_is_rejected(skill, adjudicate_params):
    params = dict(adjudicate_params)
    params["extra"] = 1
    _assert_error(skill.execute(params), INVALID_REQUEST)


def test_non_object_parameters_is_invalid_request(skill):
    _assert_error(skill.execute(["adjudicate"]), INVALID_REQUEST)


def test_skill_module_uses_no_clock_and_no_network():
    source_path = os.path.join(BUNDLE_DIR, "skill.py")
    with open(source_path, "r", encoding="utf-8") as handle:
        source = handle.read()
    assert "date.today(" not in source
    assert "datetime.now(" not in source
    assert "time.time(" not in source
    imports = re.findall(r"^(?:import|from)\s+([\w.]+)", source, re.MULTILINE)
    forbidden = {"socket", "http", "urllib", "requests", "ssl", "ftplib"}
    imported_roots = {name.split(".")[0] for name in imports}
    assert not (imported_roots & forbidden)
    assert not hasattr(skill_module, "socket")

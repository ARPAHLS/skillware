"""
Local execute demo for monitoring/business_diagnostic.

Runs the deterministic scenario ledger entirely offline against the in-bundle
fixtures, covering the full v0.1 lifecycle: adjudicate the demo framework
against one recorded observation, calibrate the same marks against a resolved
outcome, calibrate again with a marks history to get the Brier trend, the
honest state when the adjudication date has passed, and two fail-closed
contract errors from the closed registry. No API keys, no network, no clock:
as_of comes from the fixtures.
"""

import json
from pathlib import Path

from skillware.core.loader import SkillLoader


def _bundle_dir(module) -> Path:
    return Path(module.__file__).resolve().parent


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _print_scenarios(result: dict) -> None:
    for row in result["scenarios"]:
        line = f"  {row['id']}: operator_mark={row['operator_mark']}"
        if "model_implied" in row:
            line += f" model_implied={row['model_implied']} delta={row['delta']}"
        if row["fired"]:
            line += f" fired={row['fired']}"
        print(line)


def _print_result(result: dict) -> None:
    print(f"  status: {result['status']}")
    if result["status"] != "completed":
        error = result["error"]
        print(f"  contract error: {error['code']} (fail-closed)")
        print(f"  detail: {error['detail']}")
        return
    _print_scenarios(result)
    calibration = result["calibration"]
    print(
        f"  fired_any: {result['fired_any']}"
        f" marks_stale: {result['marks_stale']}"
        f" next_remark_due: {calibration['next_remark_due']}"
        f" days_to_adjudication: {calibration['days_to_adjudication']}"
    )
    if calibration["brier"] is not None:
        print(f"  brier: {calibration['brier']}")
    if calibration.get("brier_trend"):
        print("  brier_trend:")
        for point in calibration["brier_trend"]:
            print(f"    {point['marked_on']} {point['brier']}")
    if result["insufficient_data"]:
        print(f"  insufficient: {result['insufficient']}")
        for item in result["insufficient_data"]:
            print(f"  insufficient_data: {item['reason']} (detail: {item['detail']})")


def run_demo() -> None:
    print("Loading monitoring/business_diagnostic...")
    bundle = SkillLoader.load_skill("monitoring/business_diagnostic")
    skill = bundle["class"]()
    fixtures = _bundle_dir(bundle["module"]) / "fixtures"

    print("\nScenario 1: adjudicate the demo framework against one observation")
    _print_result(
        skill.execute(_load_json(fixtures / "example_adjudicate_params.json"))
    )

    print("\nScenario 2: calibrate the same marks against the resolved outcome")
    calibrate_params = _load_json(fixtures / "example_calibrate_params.json")
    _print_result(skill.execute(calibrate_params))

    print("\nScenario 3: calibrate with a marks history (Brier trend, ascending)")
    with_history = dict(calibrate_params)
    with_history["marks_history"] = _load_json(fixtures / "example_marks_history.json")
    _print_result(skill.execute(with_history))

    print("\nScenario 4: adjudicate on the adjudication date (honest state)")
    _print_result(
        skill.execute(_load_json(fixtures / "adjudication_date_passed_params.json"))
    )

    print("\nScenario 5a: marks that do not sum to 1 (fail-closed contract error)")
    _print_result(
        skill.execute(_load_json(fixtures / "error_marks_not_normalized.json"))
    )

    print("\nScenario 5b: duplicate observation (fail-closed contract error)")
    _print_result(
        skill.execute(_load_json(fixtures / "error_duplicate_observation.json"))
    )

    print("\nDemo complete.")


if __name__ == "__main__":
    run_demo()

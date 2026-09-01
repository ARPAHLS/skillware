"""
Local execute demo for monitoring/kpi_gate.

Runs the deterministic KPI gate entirely offline against the in-bundle
fixtures: a weekly metrics snapshot evaluated under the demo policy charter
and versioned benchmark data, an insufficient-data snapshot, and a
fail-closed contract error from the closed registry. No API keys, no network.
"""

import json
from pathlib import Path

import yaml

from skillware.core.loader import SkillLoader


def _bundle_dir(module) -> Path:
    return Path(module.__file__).resolve().parent


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _print_result(result: dict) -> None:
    print(f"  status: {result['status']}")
    if result["status"] == "completed":
        for finding in result["findings"]:
            if finding.get("state") == "insufficient_data":
                print(
                    "  insufficient_data:"
                    f" {finding['detail']['metric']}"
                    f" (reason: {finding['reason']})"
                )
            else:
                print(
                    f"  {finding['severity']}: {finding['finding']}"
                    f" (observed: {finding['detail'].get('observed')})"
                )
    else:
        error = result["error"]
        print(f"  contract error: {error['code']} (fail-closed)")
        print(f"  detail: {error['detail']}")


def run_demo() -> None:
    print("Loading monitoring/kpi_gate...")
    bundle = SkillLoader.load_skill("monitoring/kpi_gate")
    skill = bundle["class"]()
    fixtures = _bundle_dir(bundle["module"]) / "fixtures"
    kb = _bundle_dir(bundle["module"]) / "kb"

    policy = _load_yaml(fixtures / "example_charter.yaml")
    benchmarks = _load_json(kb / "benchmarks_demo.json")

    print("\nScenario 1: weekly snapshot vs policy charter + benchmark doctrine")
    _print_result(
        skill.execute(
            {
                "metrics": _load_json(fixtures / "example_snapshot.json"),
                "policy": policy,
                "benchmarks": benchmarks,
            }
        )
    )

    print("\nScenario 2: empty metrics map (fail-closed contract error)")
    _print_result(
        skill.execute(
            {
                "metrics": _load_json(fixtures / "snapshot_empty_metrics.json"),
                "policy": policy,
                "benchmarks": benchmarks,
            }
        )
    )

    print("\nScenario 3: malformed charter (fail-closed contract error)")
    _print_result(
        skill.execute(
            {
                "metrics": _load_json(fixtures / "example_snapshot.json"),
                "policy": _load_yaml(fixtures / "invalid_charter_schema.yaml"),
                "benchmarks": benchmarks,
            }
        )
    )

    print("\nDemo complete.")


if __name__ == "__main__":
    run_demo()

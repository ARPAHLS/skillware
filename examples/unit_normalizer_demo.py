"""Offline demo for data_engineering/unit_normalizer.

Runs entirely locally: no network access, no API keys, no dependencies. Shows the
behaviours a host agent cares about - one-call batch conversion with declared
assumptions and non-blocking errors, compound string parsing, and table mapping.
"""

from skillware.core.loader import SkillLoader


def report(label, result):
    print(f"\n[{label}] status: {result['status']}")
    print(f"  hint: {result['agent_hint']}")
    for row in result["results"]:
        line = f"  {row['id']}: {row['display_value']} {row['to_unit']}"
        if row.get("assumed"):
            line += (
                f"  (assumed: {row['assumption']};"
                f" alternatives {', '.join(row['alternatives'])}"
            )
            if row["risk_variance"] is not None:
                line += f"; risk {row['risk_variance']}"
            line += ")"
        print(line)
    for error in result["errors"]:
        print(f"  {error['id']}: {error['code']} - {error['detail']}")


def run_demo():
    print("Loading data_engineering/unit_normalizer...")
    bundle = SkillLoader.load_skill("data_engineering/unit_normalizer")
    skill = bundle["class"]()

    batch = skill.execute(
        {
            "action": "normalize_batch",
            "records": [
                {"id": "pump_a", "value": 120, "from_unit": "psi", "to_unit": "kPa"},
                {"id": "oven", "value": 350, "from_unit": "degF", "to_unit": "degC"},
                {"id": "motor", "value": 1800, "from_unit": "rpm", "to_unit": "rad/s"},
                {"id": "cargo", "value": 20, "from_unit": "ton", "to_unit": "kg"},
                {"id": "bad_row", "value": 5, "from_unit": "km", "to_unit": "kg"},
            ],
            "precision": 3,
        }
    )
    report("Batch conversion", batch)

    locked = skill.execute(
        {
            "action": "normalize",
            "value": 20,
            "from_unit": "ton",
            "to_unit": "kg",
            "assume": {"ton": "us_short_ton"},
            "precision": 3,
        }
    )
    report("Same ton, reading locked with assume", locked)

    for text, target in (("5 ft 11 in", "cm"), ("3 1/2 gal", "L"), ("5'11\"", "m")):
        parsed = skill.execute(
            {"action": "parse_quantity", "text": text, "target_unit": target}
        )
        report(f"Parse '{text}'", parsed)

    table = skill.execute(
        {
            "action": "normalize_table",
            "table": [
                {"sensor": "s1", "speed": 60, "temp": 72},
                {"sensor": "s2", "speed": "45.5", "temp": None},
            ],
            "columns": {
                "speed": {"from_unit": "mph", "to_unit": "km/h"},
                "temp": {"from_unit": "degF", "to_unit": "degC"},
            },
            "precision": 2,
        }
    )
    print(f"\n[Table normalization] status: {table['status']}")
    print(f"  hint: {table['agent_hint']}")
    # table cells keep full float precision; round only for display here.
    for row in table["table"]:
        cells = {k: round(v, 2) if isinstance(v, float) else v for k, v in row.items()}
        print(f"  {cells}")

    print("\nDemo complete.")


if __name__ == "__main__":
    run_demo()

# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT
"""Local execute demo for data_engineering/telemetry_normalizer.

Demonstrates deterministic offline telemetry normalization:
- Robotics kinematics IMU stream (deg/s to rad/s, degF to degC)
- Environmental air quality mesh with out-of-bounds particulate spikes
- EV fleet battery telemetry with stuck sensor fault detection
- Smart building HVAC conversion from imperial to SI units
- W3C SOSA/SSN JSON-LD semantic export

Completely offline: no live hardware, no API keys, no network calls.
"""

from __future__ import annotations

import json
from skillware.core.loader import SkillLoader


def run_demo() -> None:
    print("Loading data_engineering/telemetry_normalizer...")
    bundle = SkillLoader.load_skill("data_engineering/telemetry_normalizer")
    skill = bundle["class"]()

    # Scenario 1: Robotics IMU
    print("\n--- Scenario 1: Robotics Kinematics IMU Normalization ---")
    imu_raw = {
        "node": "robot_chassis_front",
        "t": 1728648000120,
        "gyro_z_dps": 180.0,
        "temp_f": 113.0,
        "v_batt": 24.2,
        "accel_x": 0.0,
        "accel_z": 9.80665,
    }
    imu_res = skill.execute(
        {
            "action": "normalize",
            "schema_profile": "robotics_kinematics_imu",
            "raw_telemetry": imu_raw,
        }
    )
    print(f"Status: {imu_res['status']}")
    print(f"Agent hint: {imu_res['agent_hint']}")
    for obs in imu_res["observations"]:
        print(
            f"  {obs['phenomenon']}: {obs['raw_value']} {obs['raw_unit']} -> "
            f"{obs['canonical_value']} {obs['canonical_unit']} ({obs['quality']})"
        )

    # Scenario 2: Smart City Air Quality Mesh
    print(
        "\n--- Scenario 2: Smart City Environmental Air Quality (Spike Detection) ---"
    )
    air_raw = {
        "station_id": "station_alpha_07",
        "timestamp": "2026-10-12T08:35:00Z",
        "pm25": 850.0,
        "pm10": 1800.0,  # Exceeds max_valid 1500 ug/m3
        "co2_ppm": 490.0,
        "temp_c": 19.5,
        "rh": 60.0,
    }
    air_res = skill.execute(
        {
            "action": "normalize",
            "schema_profile": "environmental_air_quality",
            "raw_telemetry": air_raw,
        }
    )
    print(f"Status: {air_res['status']}")
    print(
        f"Out-of-bounds readings: {air_res['quality_metrics']['out_of_bounds_count']}"
    )
    print(f"Agent hint: {air_res['agent_hint']}")

    # Scenario 3: EV Battery Fleet Hardware Fault Guard
    print("\n--- Scenario 3: EV Battery Fleet (Sensor Fault Tagging) ---")
    battery_raw = {
        "pack_id": "bus_ev_102",
        "time": "2026-10-12T10:00:00Z",
        "soc": 60.0,
        "voltage": 648.0,
        "current": -115.0,
        "temperature": 99999.0,  # Stuck ADC hardware fault
    }
    batt_res = skill.execute(
        {
            "action": "normalize",
            "schema_profile": "energy_battery_fleet",
            "raw_telemetry": battery_raw,
        }
    )
    print(f"Status: {batt_res['status']}")
    print(
        f"Sensor faults detected: {batt_res['quality_metrics']['sensor_fault_count']}"
    )
    print(f"Agent hint: {batt_res['agent_hint']}")

    # Scenario 4: Smart Building HVAC
    print("\n--- Scenario 4: Smart Building HVAC (Imperial to SI) ---")
    hvac_raw = {
        "zone_id": "vav_zone_03",
        "timestamp": "2026-10-12T11:30:00Z",
        "airflow_cfm": 500.0,
        "static_pressure_in_wc": 1.5,
        "temp_f": 72.0,
        "damper_pos": 65.0,
    }
    hvac_res = skill.execute(
        {
            "action": "normalize",
            "schema_profile": "smart_building_hvac",
            "raw_telemetry": hvac_raw,
        }
    )
    print(f"Status: {hvac_res['status']}")
    for obs in hvac_res["observations"]:
        print(
            f"  {obs['phenomenon']}: {obs['raw_value']} {obs['raw_unit']} -> "
            f"{obs['canonical_value']} {obs['canonical_unit']}"
        )

    # Scenario 5: W3C SOSA / SSN JSON-LD Export
    print("\n--- Scenario 5: W3C SOSA / SSN Linked Data Semantic Export ---")
    export_res = skill.execute(
        {
            "action": "normalize",
            "schema_profile": "environmental_air_quality",
            "raw_telemetry": {
                "station_id": "station_01",
                "timestamp": "2026-10-12T12:00:00Z",
                "pm25": 14.2,
                "co2_ppm": 415.0,
            },
            "output_format": "jsonld",
        }
    )
    print("Export graph size:", len(export_res["jsonld_payload"]["@graph"]))
    print("Sample SOSA observation triple:")
    print(json.dumps(export_res["jsonld_payload"]["@graph"][0], indent=2))

    print("\nTelemetry normalizer demo completed successfully.")


if __name__ == "__main__":
    run_demo()

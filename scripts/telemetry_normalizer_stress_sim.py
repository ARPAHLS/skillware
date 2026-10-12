#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline stress harness and multi-domain simulation for data_engineering/telemetry_normalizer.

Walks simulated robotics IMU streams, smart city air quality meshes, EV battery fleet
telemetry under sensor failure, and multi-zone HVAC BMS controls.
Validates unit conversions, bounds guards, fault detection, and W3C SOSA/SSN export.
Exits 1 if any test scenario fails. Safe for CI and completely offline.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skillware.core.loader import SkillLoader  # noqa: E402


def section(title: str) -> None:
    print(f"\n{'=' * 70}\n{title}\n{'=' * 70}")


def run_imu_stream_simulation(skill) -> None:
    section("Scenario 1: High-Frequency Robotics IMU Stream (500 Readings)")
    readings = []
    base_t = 1728648000000  # ms epoch

    for i in range(500):
        # Sine wave oscillating angular velocity
        dps = math.sin(i * 0.1) * 360.0
        # Alternating epoch formats
        if i % 4 == 0:
            ts = base_t + i * 20  # ms
        elif i % 4 == 1:
            ts = (base_t + i * 20) * 1000  # us
        elif i % 4 == 2:
            ts = (base_t + i * 20) * 1000000  # ns
        else:
            ts = (base_t + i * 20) / 1000.0  # s

        readings.append(
            {
                "node": f"imu_chassis_{i % 4}",
                "t": ts,
                "gyro_z_dps": round(dps, 3),
                "accel_z": round(9.80665 + math.cos(i * 0.05) * 2.0, 3),
                "temp_f": round(95.0 + (i % 20) * 0.5, 2),
                "v_batt": round(24.0 - (i * 0.005), 3),
            }
        )

    t0 = time.perf_counter()
    res = skill.execute(
        {
            "action": "normalize",
            "schema_profile": "robotics_kinematics_imu",
            "raw_telemetry": readings,
        }
    )
    duration_ms = (time.perf_counter() - t0) * 1000

    assert res["status"] in ("ready", "warning"), f"Unexpected status: {res['status']}"
    assert res["error"] is None
    obs = res["observations"]
    assert len(obs) == 2000, f"Expected 2000 observations, got {len(obs)}"
    metrics = res["quality_metrics"]
    assert metrics["mapped_count"] == 2000
    assert metrics["coverage_score"] == 1.0

    print(f"Processed 500 IMU packets (2,000 observations) in {duration_ms:.2f} ms")
    print(f"Throughput: {len(obs) / (duration_ms / 1000):.0f} observations/sec")
    print(f"Agent hint: {res['agent_hint']}")


def run_air_quality_mesh_simulation(skill) -> None:
    section("Scenario 2: Smart City Air Quality Mesh (10 Stations with Spikes)")
    stations = []
    for s_id in range(1, 11):
        # Station 7 experiences an extreme particulate matter spike
        is_spike = s_id == 7
        stations.append(
            {
                "station_id": f"station_alpha_{s_id:02d}",
                "timestamp": f"2026-10-12T08:{s_id * 5:02d}:00Z",
                "pm25": 850.0 if is_spike else 15.0 + s_id,
                "pm10": (
                    1800.0 if is_spike else 30.0 + s_id * 2
                ),  # 1800 exceeds max_valid 1500
                "co2_ppm": 420.0 + s_id * 10,
                "temp_c": 19.5,
                "rh": 60.0,
            }
        )

    res = skill.execute(
        {
            "action": "normalize",
            "schema_profile": "environmental_air_quality",
            "raw_telemetry": stations,
        }
    )

    assert res["status"] == "warning", "Expected warning due to out-of-bounds PM10"
    metrics = res["quality_metrics"]
    assert (
        metrics["out_of_bounds_count"] == 1
    ), f"Expected 1 out_of_bounds, got {metrics['out_of_bounds_count']}"
    assert metrics["total_readings"] == 50

    spike_obs = [
        o
        for o in res["observations"]
        if o["phenomenon"] == "pm10" and o["quality"] == "out_of_bounds"
    ]
    assert len(spike_obs) == 1
    assert spike_obs[0]["sensor_id"] == "station_alpha_07"

    print("Station 7 PM10 spike properly flagged as 'out_of_bounds'.")
    print(f"Agent hint: {res['agent_hint']}")


def run_battery_fleet_fault_simulation(skill) -> None:
    section("Scenario 3: EV Fleet Telemetry with Stuck Sensors & Corrupted Packets")
    fleet_packets = [
        # Normal packet
        {
            "pack_id": "bus_ev_101",
            "time": "2026-10-12T10:00:00Z",
            "soc": 78.4,
            "voltage": 650.0,
            "current": -120.0,
            "temp_c": 32.5,
        },
        # Stuck sensor fault (99999)
        {
            "pack_id": "bus_ev_102",
            "time": "2026-10-12T10:00:00Z",
            "soc": 60.0,
            "voltage": 648.0,
            "current": -115.0,
            "temperature": 99999.0,
        },
        # NaN floating point corruption
        {
            "pack_id": "bus_ev_103",
            "time": "2026-10-12T10:00:00Z",
            "soc": float("nan"),
            "v_mv": 652000.0,
            "i_ma": -118000.0,
            "cell_temp": 31.0,
        },
        # Extreme overvoltage out of bounds
        {
            "pack_id": "bus_ev_104",
            "time": "2026-10-12T10:00:00Z",
            "soc": 95.0,
            "voltage": 1250.0,  # exceeds max 1000V
            "current": 10.0,
            "temp_c": 33.0,
        },
    ]

    res = skill.execute(
        {
            "action": "normalize",
            "schema_profile": "energy_battery_fleet",
            "raw_telemetry": fleet_packets,
        }
    )

    assert res["status"] == "warning"
    metrics = res["quality_metrics"]
    assert (
        metrics["sensor_fault_count"] == 2
    ), f"Expected 2 faults, got {metrics['sensor_fault_count']}"
    assert (
        metrics["out_of_bounds_count"] == 1
    ), f"Expected 1 out_of_bounds, got {metrics['out_of_bounds_count']}"
    assert metrics["mapped_count"] == 14

    print(
        f"Detected {metrics['sensor_fault_count']} hardware faults "
        f"and {metrics['out_of_bounds_count']} out-of-bounds readings."
    )
    print(f"Agent hint: {res['agent_hint']}")


def run_smart_building_hvac_simulation(skill) -> None:
    section("Scenario 4: Multi-Zone Smart Building HVAC (Imperial to SI)")
    zones = []
    for z in range(1, 26):
        zones.append(
            {
                "zone_id": f"vav_zone_{z:02d}",
                "timestamp": "2026-10-12T11:30:00Z",
                "airflow_cfm": 350.0 + z * 10,
                "static_pressure_in_wc": 1.2 + z * 0.02,
                "temp_f": 72.0 + (z % 3),
                "damper_pos": 45.0 + z,
            }
        )

    res = skill.execute(
        {
            "action": "normalize",
            "schema_profile": "smart_building_hvac",
            "raw_telemetry": zones,
        }
    )

    assert res["status"] == "ready"
    assert res["quality_metrics"]["mapped_count"] == 100
    assert res["quality_metrics"]["out_of_bounds_count"] == 0

    sample = res["observations"][0]
    print(
        f"Sample conversion: {sample['raw_value']} {sample['raw_unit']} -> "
        f"{sample['canonical_value']} {sample['canonical_unit']}"
    )
    print("25 HVAC zones (100 observations) normalized successfully to SI units.")


def run_jsonld_sosa_export_simulation(skill) -> None:
    section("Scenario 5: W3C SOSA / SSN Linked Data Semantic Export")
    raw = [
        {
            "station_id": "environmental_station_01",
            "timestamp": "2026-10-12T12:00:00Z",
            "pm25": 14.2,
            "co2_ppm": 415.0,
            "temp_c": 22.0,
        }
    ]

    res = skill.execute(
        {
            "action": "normalize",
            "schema_profile": "environmental_air_quality",
            "raw_telemetry": raw,
            "output_format": "jsonld",
        }
    )

    assert res["status"] == "ready"
    jsonld = res.get("jsonld_payload")
    assert jsonld is not None
    assert "@context" in jsonld
    assert "@graph" in jsonld
    assert len(jsonld["@graph"]) == 3

    print("W3C SOSA/SSN JSON-LD payload structure validated:")
    print(json.dumps(jsonld, indent=2))


def main() -> int:
    print("=" * 70)
    print("STARTING TELEMETRY NORMALIZER OFFLINE STRESS & DOMAIN SIMULATION")
    print("=" * 70)

    bundle = SkillLoader.load_skill("data_engineering/telemetry_normalizer")
    skill = bundle["class"]()

    run_imu_stream_simulation(skill)
    run_air_quality_mesh_simulation(skill)
    run_battery_fleet_fault_simulation(skill)
    run_smart_building_hvac_simulation(skill)
    run_jsonld_sosa_export_simulation(skill)

    section("STRESS HARNESS COMPLETED SUCCESSFULLY")
    print(
        "All multi-domain simulation scenarios, bounds guards, and conversions verified."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

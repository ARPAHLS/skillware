# SPDX-License-Identifier: MIT
"""Offline bundle test suite for data_engineering/telemetry_normalizer."""

from __future__ import annotations

from pathlib import Path
import pytest
import yaml

from .skill import TelemetryNormalizerSkill
from . import normalizer


@pytest.fixture
def skill() -> TelemetryNormalizerSkill:
    return TelemetryNormalizerSkill()


@pytest.fixture
def manifest() -> dict:
    manifest_path = Path(__file__).resolve().parent / "manifest.yaml"
    with open(manifest_path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


class TestManifestAndProfiles:
    def test_manifest_metadata(self, manifest: dict):
        assert manifest["name"] == "data_engineering/telemetry_normalizer"
        assert manifest["version"] == "0.1.0"
        assert manifest["category"] == "data_engineering"
        assert "issuer" in manifest
        assert manifest["issuer"]["name"] == "Rin Katsuragi"
        assert manifest["issuer"]["email"] == "r.katsuragi@proton.me"
        assert "outputs" in manifest
        assert manifest["requirements"] == []

    def test_list_profiles_action(self, skill: TelemetryNormalizerSkill):
        res = skill.execute({"action": "list_profiles"})
        assert res["status"] == "ready"
        profiles = res.get("profiles", [])
        names = {p["name"] for p in profiles}
        expected = {
            "robotics_kinematics_imu",
            "environmental_air_quality",
            "energy_battery_fleet",
            "smart_building_hvac",
        }
        assert expected.issubset(names)
        assert res["error"] is None


class TestRoboticsKinematicsProfile:
    def test_imu_telemetry_normalization_with_conversions(
        self, skill: TelemetryNormalizerSkill
    ):
        raw = [
            {
                "node": "robot_chassis_imu",
                "t": 1728648000120,
                "gyro_z_dps": 180.0,
                "temp_f": 113.0,
                "v_batt": 24.2,
                "accel_x": 0.0,
                "accel_z": 9.80665,
            }
        ]
        res = skill.execute(
            {
                "action": "normalize",
                "schema_profile": "robotics_kinematics_imu",
                "raw_telemetry": raw,
            }
        )

        assert res["status"] == "ready"
        assert res["schema_profile"] == "robotics_kinematics_imu"
        assert res["error"] is None

        obs_map = {obs["phenomenon"]: obs for obs in res["observations"]}

        # Check angular velocity: 180 deg/s -> ~3.14159 rad/s
        gyro_z = obs_map["angular_velocity_z"]
        assert gyro_z["sensor_id"] == "robot_chassis_imu"
        assert gyro_z["raw_unit"] == "deg/s"
        assert gyro_z["canonical_unit"] == "rad/s"
        assert pytest.approx(gyro_z["canonical_value"], rel=1e-3) == 3.14159
        assert gyro_z["quality"] == "valid"

        # Check temperature: 113 F -> 45.0 C
        temp = obs_map["temperature"]
        assert temp["raw_unit"] == "degF"
        assert temp["canonical_unit"] == "degC"
        assert pytest.approx(temp["canonical_value"], abs=0.01) == 45.0
        assert temp["quality"] == "valid"

        # Check battery voltage
        v_batt = obs_map["battery_voltage"]
        assert v_batt["canonical_value"] == 24.2
        assert v_batt["canonical_unit"] == "V"

        # Check timestamp normalization
        assert gyro_z["observed_at_utc"].startswith("2024-10-11T12:00:00")

        # Quality metrics
        metrics = res["quality_metrics"]
        assert metrics["total_readings"] == 5
        assert metrics["mapped_count"] == 5
        assert metrics["out_of_bounds_count"] == 0
        assert metrics["sensor_fault_count"] == 0
        assert metrics["coverage_score"] == 1.0


class TestTimestampParsing:
    @pytest.mark.parametrize(
        "raw_ts,expected_prefix",
        [
            (1728648000, "2024-10-11T12:00:00"),  # seconds
            (1728648000000, "2024-10-11T12:00:00"),  # milliseconds
            (1728648000000000, "2024-10-11T12:00:00"),  # microseconds
            (1728648000000000000, "2024-10-11T12:00:00"),  # nanoseconds
            ("2024-10-11T12:00:00Z", "2024-10-11T12:00:00"),
            ("2024-10-11 12:00:00", "2024-10-11T12:00:00"),
            ("2024-10-11T14:00:00+02:00", "2024-10-11T12:00:00"),
        ],
    )
    def test_timestamp_epoch_and_string_scales(self, raw_ts, expected_prefix):
        normalized = normalizer.normalize_timestamp(raw_ts)
        assert normalized is not None
        assert normalized.startswith(expected_prefix)
        assert normalized.endswith("Z")

    def test_invalid_timestamps_return_none(self):
        assert normalizer.normalize_timestamp(None) is None
        assert normalizer.normalize_timestamp("invalid_date_format") is None
        assert normalizer.normalize_timestamp(float("nan")) is None


class TestEnvironmentalAirQualityProfile:
    def test_air_quality_nominal_and_out_of_bounds(
        self, skill: TelemetryNormalizerSkill
    ):
        raw = [
            {
                "sensor_id": "station_alpha",
                "timestamp": "2026-10-12T08:00:00Z",
                "pm25": 18.5,
                "pm10": 34.0,
                "co2_ppm": 12500.0,  # Exceeds max_valid (10000 ppm)
                "temp_c": 21.4,
                "rh": 55.0,
                "unmapped_weather_code": "CLEAR_SKY",
            }
        ]
        res = skill.execute(
            {
                "schema_profile": "environmental_air_quality",
                "raw_telemetry": raw,
            }
        )

        assert res["status"] == "warning"
        metrics = res["quality_metrics"]
        assert metrics["total_readings"] == 5
        assert metrics["mapped_count"] == 5
        assert metrics["out_of_bounds_count"] == 1
        assert metrics["sensor_fault_count"] == 0

        obs_map = {obs["phenomenon"]: obs for obs in res["observations"]}
        assert obs_map["co2"]["quality"] == "out_of_bounds"
        assert obs_map["pm2_5"]["quality"] == "valid"

        assert "unmapped_weather_code" in res["fields_unknown"]


class TestEnergyBatteryFleetProfile:
    def test_battery_fleet_sensor_fault_and_conversions(
        self, skill: TelemetryNormalizerSkill
    ):
        raw = [
            {
                "pack_id": "ev_bus_08",
                "time": "2026-10-12T09:15:00Z",
                "soc": 82.5,
                "voltage": 680.0,
                "current": 45.0,
                "temperature": 99999,  # Stuck sensor fault
            }
        ]
        res = skill.execute(
            {
                "schema_profile": "energy_battery_fleet",
                "raw_telemetry": raw,
            }
        )

        assert res["status"] == "warning"
        metrics = res["quality_metrics"]
        assert metrics["sensor_fault_count"] == 1
        assert metrics["mapped_count"] == 3

        obs_map = {obs["phenomenon"]: obs for obs in res["observations"]}
        temp_obs = obs_map["temperature"]
        assert temp_obs["quality"] == "sensor_fault"
        assert temp_obs["canonical_value"] is None

    def test_battery_conversions_from_millivolts_and_milliamps(
        self, skill: TelemetryNormalizerSkill
    ):
        raw = {
            "battery_id": "cell_stack_01",
            "time": "2026-10-12T10:00:00Z",
            "v_mv": 3600.0,
            "i_ma": 2500.0,
        }
        res = skill.execute(
            {
                "schema_profile": "energy_battery_fleet",
                "raw_telemetry": raw,
            }
        )

        assert res["status"] == "ready"
        obs_map = {obs["phenomenon"]: obs for obs in res["observations"]}
        assert obs_map["voltage"]["canonical_value"] == 3.6
        assert obs_map["voltage"]["canonical_unit"] == "V"
        assert obs_map["current"]["canonical_value"] == 2.5
        assert obs_map["current"]["canonical_unit"] == "A"


class TestSmartBuildingHVACProfile:
    def test_hvac_unit_conversions(self, skill: TelemetryNormalizerSkill):
        raw = {
            "zone_id": "floor_3_conference",
            "timestamp": "2026-10-12T11:00:00Z",
            "airflow_cfm": 500.0,
            "static_pressure_in_wc": 1.5,
            "zone_temp": 22.0,
            "damper_pos": 75.0,
        }
        res = skill.execute(
            {
                "schema_profile": "smart_building_hvac",
                "raw_telemetry": raw,
            }
        )

        assert res["status"] == "ready"
        obs_map = {obs["phenomenon"]: obs for obs in res["observations"]}

        # 500 cfm * 1.6990108 = 849.5054 m3/h
        flow = obs_map["airflow"]
        assert flow["canonical_unit"] == "m3/h"
        assert pytest.approx(flow["canonical_value"], abs=0.1) == 849.5

        # 1.5 in_wc * 249.0889 = 373.633 Pa
        pressure = obs_map["static_pressure"]
        assert pressure["canonical_unit"] == "Pa"
        assert pytest.approx(pressure["canonical_value"], abs=0.1) == 373.63


class TestOutputFormatsAndValidateAction:
    def test_jsonld_sosa_export(self, skill: TelemetryNormalizerSkill):
        raw = {
            "device_id": "sensor_42",
            "timestamp": "2026-10-12T12:00:00Z",
            "pm25": 12.0,
            "co2": 450.0,
        }
        res = skill.execute(
            {
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
        assert len(jsonld["@graph"]) == 2

        entry = jsonld["@graph"][0]
        assert entry["@type"] == "Observation"
        assert entry["madeBySensor"] == "sensor:sensor_42"
        assert "qudt:unit" in entry

    def test_validate_action(self, skill: TelemetryNormalizerSkill):
        valid_raw = {
            "node": "robot_1",
            "t": 1728648000,
            "accel_z": 9.81,
        }
        val_res = skill.execute(
            {
                "action": "validate",
                "schema_profile": "robotics_kinematics_imu",
                "raw_telemetry": valid_raw,
            }
        )
        assert val_res["status"] == "ready"
        assert val_res["is_valid"] is True
        assert val_res["quality_metrics"]["mapped_count"] == 1

        fault_raw = {
            "node": "robot_1",
            "t": 1728648000,
            "accel_z": 99999,
        }
        val_res_bad = skill.execute(
            {
                "action": "validate",
                "schema_profile": "robotics_kinematics_imu",
                "raw_telemetry": fault_raw,
            }
        )
        assert val_res_bad["status"] == "warning"
        assert val_res_bad["is_valid"] is False


class TestEdgeCasesAndErrorHandling:
    def test_empty_raw_telemetry_returns_insufficient_data(
        self, skill: TelemetryNormalizerSkill
    ):
        res = skill.execute(
            {
                "schema_profile": "robotics_kinematics_imu",
                "raw_telemetry": [],
            }
        )
        assert res["status"] == "insufficient_data"
        assert "empty or missing" in res["validation_errors"][0]

    def test_missing_schema_profile_returns_error(
        self, skill: TelemetryNormalizerSkill
    ):
        res = skill.execute({"raw_telemetry": [{"node": "test"}]})
        assert res["status"] == "error"
        assert "Missing required parameter" in res["error"]

    def test_unknown_schema_profile_returns_error(
        self, skill: TelemetryNormalizerSkill
    ):
        res = skill.execute(
            {
                "schema_profile": "non_existent_profile",
                "raw_telemetry": [{"node": "test"}],
            }
        )
        assert res["status"] == "error"
        assert "Unknown schema_profile" in res["error"]

    def test_unsupported_action_returns_error(self, skill: TelemetryNormalizerSkill):
        res = skill.execute({"action": "dance"})
        assert res["status"] == "error"
        assert "Unsupported action" in res["error"]

    def test_unsupported_output_format_returns_error(
        self, skill: TelemetryNormalizerSkill
    ):
        res = skill.execute(
            {
                "schema_profile": "robotics_kinematics_imu",
                "raw_telemetry": [{"node": "test", "t": 123}],
                "output_format": "xml",
            }
        )
        assert res["status"] == "error"
        assert "Unsupported output_format" in res["error"]

    def test_nan_reading_handled_as_sensor_fault(self, skill: TelemetryNormalizerSkill):
        raw = {
            "node": "robot_sensor",
            "t": 1728648000,
            "gyro_z": float("nan"),
        }
        res = skill.execute(
            {
                "schema_profile": "robotics_kinematics_imu",
                "raw_telemetry": raw,
            }
        )
        assert res["status"] == "warning"
        assert res["quality_metrics"]["sensor_fault_count"] == 1
        obs = res["observations"][0]
        assert obs["quality"] == "sensor_fault"
        assert obs["canonical_value"] is None

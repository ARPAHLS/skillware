# SPDX-License-Identifier: MIT
"""Effect implementation for data_engineering/telemetry_normalizer."""

from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

import yaml

from skillware.core.base_skill import BaseSkill

try:
    from . import normalizer
except ImportError:  # pragma: no cover
    sys.path.insert(0, os.path.dirname(__file__))
    import normalizer


class TelemetryNormalizerSkill(BaseSkill):
    """Universal deterministic telemetry normalizer for IoT, robotics, and facility sensors."""

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = Path(__file__).resolve().parent / "manifest.yaml"
        if manifest_path.is_file():
            with open(manifest_path, "r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
                if isinstance(data, dict):
                    return data
        return {
            "name": "data_engineering/telemetry_normalizer",
            "version": "0.1.0",
        }

    def execute(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        action = (params.get("action") or "normalize").strip().lower()

        if action == "list_profiles":
            return self._handle_list_profiles()

        if action == "validate":
            return self._handle_validate(params)

        if action == "normalize":
            return self._handle_normalize(params)

        return self._error_response(
            schema_profile=params.get("schema_profile"),
            error_msg=f"Unsupported action '{action}'. Supported actions: 'normalize', 'list_profiles', 'validate'.",
        )

    def _handle_list_profiles(self) -> Dict[str, Any]:
        profiles = normalizer.list_available_profiles()
        return {
            "status": "ready",
            "schema_profile": None,
            "profiles": profiles,
            "observations": [],
            "quality_metrics": {
                "total_readings": 0,
                "mapped_count": 0,
                "out_of_bounds_count": 0,
                "sensor_fault_count": 0,
                "coverage_score": 1.0 if profiles else 0.0,
            },
            "fields_unknown": [],
            "validation_errors": [],
            "agent_hint": f"Discovered {len(profiles)} bundled telemetry profile(s).",
            "jsonld_payload": None,
            "error": None,
        }

    def _handle_normalize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        schema_profile = params.get("schema_profile")
        if not schema_profile or not isinstance(schema_profile, str):
            available = [p["name"] for p in normalizer.list_available_profiles()]
            return self._error_response(
                schema_profile=None,
                error_msg=f"Missing required parameter 'schema_profile'. Available profiles: {', '.join(available)}.",
            )

        profile_cfg = normalizer.load_profile(schema_profile)
        if not profile_cfg:
            available = [p["name"] for p in normalizer.list_available_profiles()]
            return self._error_response(
                schema_profile=schema_profile,
                error_msg=f"Unknown schema_profile '{schema_profile}'. Available profiles: {', '.join(available)}.",
            )

        raw_telemetry = params.get("raw_telemetry")
        if raw_telemetry is None or (
            isinstance(raw_telemetry, (list, dict)) and len(raw_telemetry) == 0
        ):
            return {
                "status": "insufficient_data",
                "schema_profile": schema_profile,
                "observations": [],
                "quality_metrics": {
                    "total_readings": 0,
                    "mapped_count": 0,
                    "out_of_bounds_count": 0,
                    "sensor_fault_count": 0,
                    "coverage_score": 0.0,
                },
                "fields_unknown": [],
                "validation_errors": ["Parameter 'raw_telemetry' is empty or missing."],
                "agent_hint": "Telemetry normalization skipped: raw_telemetry is empty or missing.",
                "jsonld_payload": None,
                "error": "Parameter 'raw_telemetry' is empty or missing.",
            }

        items: List[Dict[str, Any]]
        if isinstance(raw_telemetry, dict):
            items = [raw_telemetry]
        elif isinstance(raw_telemetry, list):
            items = [item for item in raw_telemetry if isinstance(item, dict)]
            if not items and len(raw_telemetry) > 0:
                return self._error_response(
                    schema_profile=schema_profile,
                    error_msg="Parameter 'raw_telemetry' list must contain dictionary items.",
                )
        else:
            return self._error_response(
                schema_profile=schema_profile,
                error_msg="Parameter 'raw_telemetry' must be a dictionary or list of dictionaries.",
            )

        output_format = (params.get("output_format") or "canonical").strip().lower()
        if output_format not in ("canonical", "jsonld"):
            return self._error_response(
                schema_profile=schema_profile,
                error_msg=f"Unsupported output_format '{output_format}'. Supported: 'canonical', 'jsonld'.",
            )

        unit_system = (params.get("unit_system") or "si").strip().lower()
        if unit_system not in ("si", "canonical"):
            return self._error_response(
                schema_profile=schema_profile,
                error_msg=f"Unsupported unit_system '{unit_system}'. Supported: 'si', 'canonical'.",
            )

        (
            observations,
            quality_metrics,
            fields_unknown,
            validation_errors,
        ) = self._process_items(items, profile_cfg)

        status = "ready"
        if validation_errors:
            status = "warning"
        elif (
            quality_metrics["sensor_fault_count"] > 0
            or quality_metrics["out_of_bounds_count"] > 0
        ):
            status = "warning"

        agent_hint = normalizer.format_agent_hint(
            profile_name=schema_profile,
            mapped_count=quality_metrics["mapped_count"],
            out_of_bounds_count=quality_metrics["out_of_bounds_count"],
            sensor_fault_count=quality_metrics["sensor_fault_count"],
            coverage_score=quality_metrics["coverage_score"],
            validation_errors=validation_errors,
        )

        jsonld_payload = None
        if output_format == "jsonld":
            jsonld_payload = normalizer.build_jsonld_export(observations)

        return {
            "status": status,
            "schema_profile": schema_profile,
            "observations": observations,
            "quality_metrics": quality_metrics,
            "fields_unknown": sorted(list(fields_unknown)),
            "validation_errors": validation_errors,
            "agent_hint": agent_hint,
            "jsonld_payload": jsonld_payload,
            "error": None,
        }

    def _handle_validate(self, params: Dict[str, Any]) -> Dict[str, Any]:
        norm_result = self._handle_normalize(params)
        if norm_result["status"] == "error":
            norm_result["is_valid"] = False
            return norm_result

        metrics = norm_result["quality_metrics"]
        is_valid = (
            norm_result["status"] != "insufficient_data"
            and metrics["sensor_fault_count"] == 0
            and len(norm_result["validation_errors"]) == 0
        )

        return {
            "status": "ready" if is_valid else "warning",
            "is_valid": is_valid,
            "schema_profile": norm_result["schema_profile"],
            "observations": norm_result["observations"],
            "quality_metrics": metrics,
            "fields_unknown": norm_result["fields_unknown"],
            "validation_errors": norm_result["validation_errors"],
            "agent_hint": norm_result["agent_hint"],
            "jsonld_payload": None,
            "error": None,
        }

    def _process_items(
        self,
        items: List[Dict[str, Any]],
        profile_cfg: Dict[str, Any],
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any], Set[str], List[str]]:
        id_fields: List[str] = profile_cfg.get("sensor_id_fields", [])
        ts_fields: List[str] = profile_cfg.get("timestamp_fields", [])
        phenomena: Dict[str, Any] = profile_cfg.get("phenomena", {})

        alias_map: Dict[str, str] = {}
        for phenom_key, phenom_spec in phenomena.items():
            alias_map[phenom_key.lower()] = phenom_key
            for alias in phenom_spec.get("aliases", []):
                alias_map[alias.lower()] = phenom_key

        recognized_control_fields = set(id_fields) | set(ts_fields) | {"unit", "units"}

        observations: List[Dict[str, Any]] = []
        fields_unknown: Set[str] = set()
        validation_errors: List[str] = []

        total_readings = 0
        mapped_count = 0
        out_of_bounds_count = 0
        sensor_fault_count = 0

        for idx, item in enumerate(items):
            sensor_id = normalizer.extract_sensor_id(item, id_fields)
            observed_at = normalizer.extract_timestamp(item, ts_fields)
            if not observed_at:
                validation_errors.append(
                    f"Item {idx}: No valid timestamp recognized among {ts_fields}."
                )

            explicit_unit = item.get("unit") or item.get("units")

            for key, val in item.items():
                if key in recognized_control_fields:
                    continue

                phenom_name = normalizer.resolve_phenomenon(key, alias_map)
                if phenom_name:
                    total_readings += 1
                    phenom_cfg = phenomena[phenom_name]
                    canonical_unit = phenom_cfg.get("canonical_unit", "")

                    is_fault, clean_num = normalizer.check_fault(val)
                    if is_fault or clean_num is None:
                        sensor_fault_count += 1
                        canonical_val = None
                        raw_unit = phenom_cfg.get("canonical_unit", "")
                        quality = "sensor_fault"
                    else:
                        raw_unit = normalizer.infer_raw_unit(
                            key, explicit_unit, phenom_cfg
                        )
                        canonical_val = normalizer.convert_unit(
                            clean_num, raw_unit, canonical_unit, phenom_cfg
                        )
                        quality = normalizer.check_bounds(canonical_val, phenom_cfg)
                        mapped_count += 1
                        if quality == "out_of_bounds":
                            out_of_bounds_count += 1

                    observations.append(
                        {
                            "sensor_id": sensor_id,
                            "observed_at_utc": observed_at,
                            "phenomenon": phenom_name,
                            "raw_value": clean_num if clean_num is not None else val,
                            "raw_unit": raw_unit,
                            "canonical_value": canonical_val,
                            "canonical_unit": canonical_unit,
                            "quality": quality,
                        }
                    )
                else:
                    fields_unknown.add(key)

        coverage_score = (
            round(mapped_count / max(total_readings, 1), 4)
            if total_readings > 0
            else 0.0
        )

        quality_metrics = {
            "total_readings": total_readings,
            "mapped_count": mapped_count,
            "out_of_bounds_count": out_of_bounds_count,
            "sensor_fault_count": sensor_fault_count,
            "coverage_score": coverage_score,
        }

        return observations, quality_metrics, fields_unknown, validation_errors

    def _error_response(
        self,
        schema_profile: Optional[str],
        error_msg: str,
    ) -> Dict[str, Any]:
        return {
            "status": "error",
            "schema_profile": schema_profile,
            "observations": [],
            "quality_metrics": {
                "total_readings": 0,
                "mapped_count": 0,
                "out_of_bounds_count": 0,
                "sensor_fault_count": 0,
                "coverage_score": 0.0,
            },
            "fields_unknown": [],
            "validation_errors": [error_msg],
            "agent_hint": f"Telemetry normalization failed: {error_msg}",
            "jsonld_payload": None,
            "error": error_msg,
        }

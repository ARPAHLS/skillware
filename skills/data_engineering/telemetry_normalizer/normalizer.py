# SPDX-License-Identifier: MIT
"""Pure data engineering and normalization engine for telemetry_normalizer."""

from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple

import yaml

PROFILES_DIR = Path(__file__).resolve().parent / "data" / "profiles"

FAULT_SENTINELS = {99999, 99999.0, -9999, -9999.0, 999.9, -999.9}

UNIT_SUFFIX_RE = re.compile(
    r"(_dps|_deg_s|_degs|_degf|_degc|_f|_c|_k|_mv|_kv|_ma|_g|_ppm|_cfm|_in_wc|_inwc|_bar|_psi|_pct|_percent)$",
    re.IGNORECASE,
)


def load_profile(profile_name: str) -> Optional[Dict[str, Any]]:
    """Load a YAML profile definition from data/profiles/."""
    if not profile_name or not isinstance(profile_name, str):
        return None
    clean_name = Path(profile_name).name
    profile_path = PROFILES_DIR / f"{clean_name}.yaml"
    if not profile_path.is_file():
        return None
    with open(profile_path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else None


def list_available_profiles() -> List[Dict[str, Any]]:
    """List all bundled profiles with phenomena and recognized fields."""
    profiles: List[Dict[str, Any]] = []
    if not PROFILES_DIR.is_dir():
        return profiles

    for path in sorted(PROFILES_DIR.glob("*.yaml")):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = yaml.safe_load(handle)
            if not isinstance(data, dict):
                continue
            phenomena_summary = {}
            for phenom_key, phenom_cfg in data.get("phenomena", {}).items():
                phenomena_summary[phenom_key] = phenom_cfg.get("canonical_unit", "")

            profiles.append(
                {
                    "name": data.get("name", path.stem),
                    "description": data.get("description", ""),
                    "phenomena": phenomena_summary,
                    "sensor_id_fields": data.get("sensor_id_fields", []),
                    "timestamp_fields": data.get("timestamp_fields", []),
                }
            )
        except Exception:
            continue
    return profiles


def normalize_timestamp(raw_time: Any) -> Optional[str]:
    """Convert raw epoch or date string to strict UTC ISO-8601 representation."""
    if raw_time is None:
        return None

    # Numeric epochs (s, ms, us, ns)
    if isinstance(raw_time, (int, float)):
        if math.isnan(raw_time) or math.isinf(raw_time):
            return None
        val = float(raw_time)
        if val > 1e18:  # nanoseconds
            sec = val / 1e9
        elif val > 1e14:  # microseconds
            sec = val / 1e6
        elif val > 1e11:  # milliseconds
            sec = val / 1e3
        else:  # seconds
            sec = val

        try:
            dt = datetime.fromtimestamp(sec, tz=timezone.utc)
            if dt.microsecond == 0:
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        except (OverflowError, OSError, ValueError):
            return None

    # String timestamps
    if isinstance(raw_time, str):
        text = raw_time.strip()
        if not text:
            return None
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            if dt.microsecond == 0:
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        except ValueError:
            pass

        for fmt in (
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ):
            try:
                dt = datetime.strptime(text, fmt).replace(tzinfo=timezone.utc)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue

    return None


def resolve_phenomenon(
    field_name: str,
    alias_map: Dict[str, str],
) -> Optional[str]:
    """Resolve field name to phenomenon key using exact match or suffix stripping."""
    field_lower = field_name.lower()
    if field_lower in alias_map:
        return alias_map[field_lower]

    stripped = UNIT_SUFFIX_RE.sub("", field_lower)
    if stripped and stripped in alias_map:
        return alias_map[stripped]

    return None


def infer_raw_unit(
    field_name: str,
    explicit_unit: Optional[str],
    phenomenon_cfg: Dict[str, Any],
) -> str:
    """Infer raw unit from explicit unit or field name conventions."""
    canonical_unit = phenomenon_cfg.get("canonical_unit", "")
    units_cfg = phenomenon_cfg.get("units", {})

    if explicit_unit and explicit_unit in units_cfg:
        return explicit_unit

    field_lower = field_name.lower()
    suffix_rules: List[Tuple[re.Pattern, str]] = [
        (re.compile(r"(_dps|_deg_s|_degs)$"), "deg/s"),
        (re.compile(r"(_degf|_f)$"), "degF"),
        (re.compile(r"(_degc|_c)$"), "degC"),
        (re.compile(r"(_k)$"), "K"),
        (re.compile(r"(_mv)$"), "mV"),
        (re.compile(r"(_kv)$"), "kV"),
        (re.compile(r"(_ma)$"), "mA"),
        (re.compile(r"(_g)$"), "g"),
        (re.compile(r"(_ppm)$"), "ppm"),
        (re.compile(r"(_cfm)$"), "cfm"),
        (re.compile(r"(_in_wc|_inwc)$"), "in_wc"),
        (re.compile(r"(_bar)$"), "bar"),
        (re.compile(r"(_psi)$"), "psi"),
        (re.compile(r"(_pct|_percent)$"), "%"),
    ]

    for pattern, unit in suffix_rules:
        if pattern.search(field_lower) and unit in units_cfg:
            return unit

    return canonical_unit


def convert_unit(
    raw_value: float,
    raw_unit: str,
    canonical_unit: str,
    phenomenon_cfg: Dict[str, Any],
) -> float:
    """Convert raw value to canonical SI unit deterministically."""
    if raw_unit == canonical_unit:
        return raw_value

    units_cfg = phenomenon_cfg.get("units", {})
    unit_spec = units_cfg.get(raw_unit)
    if not unit_spec:
        return raw_value

    if unit_spec.get("formula") == "fahrenheit_to_celsius":
        celsius = (raw_value - 32.0) * 5.0 / 9.0
        return round(celsius, 5)

    factor = float(unit_spec.get("factor", 1.0))
    offset = float(unit_spec.get("offset", 0.0))
    result = raw_value * factor + offset
    return round(result, 5)


def check_fault(val: Any) -> Tuple[bool, Optional[float]]:
    """Check if value is a hardware sensor fault, NaN, inf, or sentinel."""
    if val is None:
        return True, None

    try:
        num = float(val)
    except (ValueError, TypeError):
        return True, None

    if math.isnan(num) or math.isinf(num) or num in FAULT_SENTINELS:
        return True, None

    return False, num


def check_bounds(
    canonical_val: float,
    phenomenon_cfg: Dict[str, Any],
) -> str:
    """Check whether canonical value falls within physical boundaries."""
    min_valid = phenomenon_cfg.get("min_valid")
    max_valid = phenomenon_cfg.get("max_valid")

    if min_valid is not None and canonical_val < float(min_valid):
        return "out_of_bounds"
    if max_valid is not None and canonical_val > float(max_valid):
        return "out_of_bounds"

    return "valid"


def assess_reading_quality(
    val: Any,
    phenomenon_cfg: Dict[str, Any],
) -> Tuple[str, Optional[float]]:
    """Determine reading quality directly from raw value."""
    is_fault, num = check_fault(val)
    if is_fault or num is None:
        return "sensor_fault", None
    quality = check_bounds(num, phenomenon_cfg)
    return quality, num


def extract_sensor_id(item: Dict[str, Any], id_fields: List[str]) -> str:
    """Extract sensor identifier from telemetry item using recognized fields."""
    for field in id_fields:
        if field in item and item[field] is not None:
            return str(item[field])
    return "unknown_sensor"


def extract_timestamp(item: Dict[str, Any], ts_fields: List[str]) -> Optional[str]:
    """Extract and normalize timestamp using recognized fields."""
    for field in ts_fields:
        if field in item and item[field] is not None:
            norm = normalize_timestamp(item[field])
            if norm:
                return norm
    return None


def build_jsonld_export(observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Export normalized observations into W3C SOSA / SSN JSON-LD format."""
    graph = []
    for obs in observations:
        graph.append(
            {
                "@type": "Observation",
                "madeBySensor": f"sensor:{obs['sensor_id']}",
                "resultTime": obs["observed_at_utc"],
                "observedProperty": f"phenomenon:{obs['phenomenon']}",
                "hasSimpleResult": obs["canonical_value"],
                "qudt:unit": obs["canonical_unit"],
                "quality": obs["quality"],
            }
        )

    return {
        "@context": {
            "sosa": "http://www.w3.org/ns/sosa/",
            "qudt": "http://qudt.org/schema/qudt/",
            "xsd": "http://www.w3.org/2001/XMLSchema#",
            "Observation": "sosa:Observation",
            "observedProperty": {"@id": "sosa:observedProperty", "@type": "@id"},
            "hasSimpleResult": "sosa:hasSimpleResult",
            "resultTime": {"@id": "sosa:resultTime", "@type": "xsd:dateTime"},
            "madeBySensor": {"@id": "sosa:madeBySensor", "@type": "@id"},
        },
        "@graph": graph,
    }


def format_agent_hint(
    profile_name: str,
    mapped_count: int,
    out_of_bounds_count: int,
    sensor_fault_count: int,
    coverage_score: float,
    validation_errors: List[str],
) -> str:
    """Generate deterministic template-based agent hint."""
    if validation_errors:
        return (
            f"Telemetry normalization completed with advisories: "
            f"{'; '.join(validation_errors)}"
        )

    if out_of_bounds_count == 0 and sensor_fault_count == 0:
        return (
            f"All {mapped_count} telemetry observation(s) in '{profile_name}' "
            f"are within nominal physical bounds (coverage: {coverage_score:.1f}). "
            f"Standardized to canonical SI units."
        )

    return (
        f"Normalized {mapped_count} reading(s) in '{profile_name}'. "
        f"Detected {out_of_bounds_count} out-of-bounds reading(s) and "
        f"{sensor_fault_count} sensor fault(s)."
    )

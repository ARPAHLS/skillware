"""Effect for data_engineering/unit_normalizer."""

import math
import os
import re
import sys
from typing import Any, Dict, List, Mapping, Optional, Tuple

import yaml

from skillware.core.base_skill import BaseSkill

try:
    from . import parser, units
except ImportError:  # pragma: no cover - loader executes skill.py without a package
    sys.path.insert(0, os.path.dirname(__file__))
    import parser
    import units

ACTIONS = (
    "normalize",
    "normalize_batch",
    "canonicalize",
    "parse_quantity",
    "normalize_table",
)

DEFAULT_PRECISION = 6

MAX_PRECISION = 12

# Numeric strings are accepted because CSV readers hand every cell over as text.
# Anything carrying a unit is not a number here; parse_quantity is the path for that.
NUMERIC_STRING = re.compile(r"^\s*[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?\s*$")


class UnitNormalizerSkill(BaseSkill):
    """Deterministic unit normalization with an assume-and-declare audit trail."""

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as handle:
                return yaml.safe_load(handle)
        return {"name": "data_engineering/unit_normalizer", "version": "0.1.0"}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        params = params or {}

        raw_action = params.get("action") or "normalize"
        action = raw_action.strip().lower() if isinstance(raw_action, str) else ""
        if action not in ACTIONS:
            return self._failure(
                str(raw_action),
                f"Unsupported action '{raw_action}'. Supported: {', '.join(ACTIONS)}.",
                DEFAULT_PRECISION,
            )

        precision = params.get("precision", DEFAULT_PRECISION)
        if type(precision) is not int or not 0 <= precision <= MAX_PRECISION:
            return self._failure(
                action,
                f"precision must be an integer from 0 to {MAX_PRECISION}.",
                DEFAULT_PRECISION,
            )

        try:
            assume = units.validate_assume(params.get("assume"))
        except units.UnitError as exc:
            return self._failure(action, f"{exc.code}: {exc.detail}", precision)

        if action == "parse_quantity":
            return self._handle_parse(params, assume, precision)

        canonical = action == "canonicalize"
        if action == "normalize" or (canonical and "records" not in params):
            if params.get("value") is None and params.get("from_unit") is None:
                return self._insufficient(
                    action, "Provide value and from_unit.", precision
                )
            record = {
                key: params[key]
                for key in ("id", "value", "from_unit", "to_unit")
                if key in params
            }
            records: Any = [record]
        else:
            records = params.get("records")
            if records is None or records == []:
                return self._insufficient(
                    action, "Parameter 'records' is empty or missing.", precision
                )
            if not isinstance(records, list):
                return self._failure(
                    action, "Parameter 'records' must be a list of objects.", precision
                )

        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        for index, record in enumerate(records):
            result, error = self._convert_record(
                index, record, assume, precision, canonical
            )
            if result is not None:
                results.append(result)
            else:
                errors.append(error)

        return self._envelope(
            action, results, errors, precision, single=action == "normalize"
        )

    def _convert_record(
        self,
        index: int,
        record: Any,
        assume: Mapping[str, str],
        precision: int,
        canonical: bool,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        if not isinstance(record, dict):
            return None, _error(index, "invalid_record", "Record must be an object.")
        record_id = record.get("id", index)
        if "value" not in record or "from_unit" not in record:
            return None, _error(
                record_id, "invalid_record", "Record needs 'value' and 'from_unit'."
            )

        from_label = record["from_unit"]
        to_label = None if canonical else record.get("to_unit")
        value = _coerce_value(record["value"])
        if value is None:
            return None, _error(
                record_id,
                "invalid_value",
                f"Value {record['value']!r} is not a finite number.",
                from_label,
                to_label,
            )

        try:
            converted, src, to_symbol, assumptions = _convert(
                value, from_label, to_label, assume
            )
        except units.UnitError as exc:
            return None, _error(record_id, exc.code, exc.detail, from_label, to_label)

        result = {
            "id": record_id,
            "value": converted,
            "display_value": _display(converted, precision),
            "from_unit": src.label,
            "to_unit": to_symbol,
            "dimension": units.dimension_name(src.unit.dimension),
        }
        _declare(result, assumptions)
        return result, None

    def _handle_parse(
        self, params: Dict[str, Any], assume: Mapping[str, str], precision: int
    ) -> Dict[str, Any]:
        text = params.get("text")
        if text is None or text == "":
            return self._insufficient(
                "parse_quantity", "Parameter 'text' is empty or missing.", precision
            )

        record_id = params.get("id", 0)
        target_label = params.get("target_unit")
        try:
            dst = units.resolve_unit(target_label, assume) if target_label else None
            parsed = parser.parse_quantity(
                text, assume, dst.unit.dimension if dst else None
            )
            if dst is not None and dst.assumption:
                dst = units.resolve_unit(target_label, assume, parsed.dimension)
            if dst is not None:
                dst_unit, to_symbol = dst.unit, dst.label
            else:
                dst_unit, to_symbol = units.canonical_unit(parsed.dimension)
            _check_dimensions(text, parsed.dimension, to_symbol, dst_unit.dimension)
        except units.UnitError as exc:
            error = _error(record_id, exc.code, exc.detail, None, target_label)
            return self._envelope("parse_quantity", [], [error], precision, single=True)

        value = parsed.si_value / dst_unit.factor - dst_unit.offset
        result = {
            "id": record_id,
            "original_text": text,
            "value": value,
            "display_value": _display(value, precision),
            "from_unit": "+".join(r.label for _, r in parsed.components),
            "to_unit": to_symbol,
            "dimension": units.dimension_name(parsed.dimension),
            "components": [{"value": v, "unit": r.label} for v, r in parsed.components],
        }
        assumptions = list(parsed.assumptions)
        if dst is not None and dst.assumption:
            assumptions.append(dst.assumption)
        _declare(result, assumptions)
        return self._envelope("parse_quantity", [result], [], precision, single=True)

    def _envelope(
        self,
        action: str,
        results: List[Dict[str, Any]],
        errors: List[Dict[str, Any]],
        precision: int,
        single: bool = False,
        skipped: int = 0,
    ) -> Dict[str, Any]:
        assumed = sum(1 for r in results if r.get("assumed"))
        total = len(results) + len(errors) + skipped
        summary = {
            "total": total,
            "converted": len(results),
            "assumed": assumed,
            "errors": len(errors),
            "skipped": skipped,
        }
        return {
            "status": "warning" if errors or assumed else "ready",
            "action": action,
            "result": results[0] if single and results else None,
            "results": results,
            "errors": errors,
            "summary": summary,
            "precision": precision,
            "agent_hint": (
                f"Converted {len(results)} of {total} record(s); {assumed} assumed; "
                f"{len(errors)} error(s)."
            ),
            "error": None,
        }

    def _insufficient(
        self, action: str, message: str, precision: int
    ) -> Dict[str, Any]:
        result = self._failure(action, message, precision)
        result["status"] = "insufficient_data"
        result["agent_hint"] = f"Unit normalization skipped: {message}"
        return result

    def _failure(self, action: str, message: str, precision: int) -> Dict[str, Any]:
        return {
            "status": "error",
            "action": action,
            "result": None,
            "results": [],
            "errors": [],
            "summary": {
                "total": 0,
                "converted": 0,
                "assumed": 0,
                "errors": 0,
                "skipped": 0,
            },
            "precision": precision,
            "agent_hint": f"Unit normalization failed: {message}",
            "error": message,
        }


def _coerce_value(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str) and NUMERIC_STRING.match(value):
        number = float(value)
    else:
        return None
    return number if math.isfinite(number) else None


def _display(value: float, precision: int) -> str:
    return format(value, f".{precision}f")


def _error(
    record_id: Any,
    code: str,
    detail: str,
    from_unit: Any = None,
    to_unit: Any = None,
) -> Dict[str, Any]:
    error = {"id": record_id, "code": code, "detail": detail}
    if from_unit is not None:
        error["from_unit"] = from_unit
    if to_unit is not None:
        error["to_unit"] = to_unit
    return error


def _check_dimensions(
    src_label: str, src_dim: units.Dim, dst_label: str, dst_dim: units.Dim
) -> None:
    if src_dim != dst_dim:
        raise units.UnitError(
            "dimension_mismatch",
            f"{src_label} ({units.dimension_name(src_dim)}) cannot convert to "
            f"{dst_label} ({units.dimension_name(dst_dim)})",
        )


def _convert(
    value: float,
    from_label: Any,
    to_label: Any,
    assume: Mapping[str, str],
) -> Tuple[float, units.Resolved, str, List[Dict[str, Any]]]:
    """Resolve both units, letting an ambiguous side follow the other side's dimension."""
    src = units.resolve_unit(from_label, assume)
    if to_label is None:
        dst_unit, to_symbol = units.canonical_unit(src.unit.dimension)
        dst = None
    else:
        dst = units.resolve_unit(to_label, assume)
        if src.unit.dimension != dst.unit.dimension:
            if src.assumption:
                src = units.resolve_unit(from_label, assume, dst.unit.dimension)
            elif dst.assumption:
                dst = units.resolve_unit(to_label, assume, src.unit.dimension)
        dst_unit, to_symbol = dst.unit, dst.label

    _check_dimensions(src.label, src.unit.dimension, to_symbol, dst_unit.dimension)
    converted = (value + src.unit.offset) * src.unit.factor / dst_unit.factor
    converted -= dst_unit.offset
    assumptions = [a for a in (src.assumption, dst and dst.assumption) if a]
    return converted, src, to_symbol, assumptions


def _declare(result: Dict[str, Any], assumptions: List[Dict[str, Any]]) -> None:
    """Attach the audit trail; a value with a choice behind it is never a bare result."""
    if not assumptions:
        return
    variances = [a["risk_variance"] for a in assumptions if a["risk_variance"]]
    result["assumed"] = True
    result["assumption"] = "; ".join(a["assumption"] for a in assumptions)
    result["alternatives"] = [alt for a in assumptions for alt in a["alternatives"]]
    result["risk_variance"] = (
        max(variances, key=lambda v: float(v.rstrip("%"))) if variances else None
    )

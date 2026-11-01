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

# Results kept under compact: true; errors are always returned in full.
COMPACT_SAMPLE_SIZE = 5

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

        compact = params.get("compact", False)
        if not isinstance(compact, bool):
            return self._failure(action, "compact must be a boolean.", precision)

        if action == "parse_quantity":
            return self._handle_parse(params, assume, precision)

        if action == "normalize_table":
            return self._handle_table(params, assume, precision, compact)

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
            action,
            results,
            errors,
            precision,
            single=action == "normalize",
            compact=compact,
        )

    def _handle_table(
        self,
        params: Dict[str, Any],
        assume: Mapping[str, str],
        precision: int,
        compact: bool,
    ) -> Dict[str, Any]:
        action = "normalize_table"
        table = params.get("table")
        if table is None or table == [] or table == {}:
            return self._insufficient(
                action, "Parameter 'table' is empty or missing.", precision
            )

        columns = params.get("columns")
        if not isinstance(columns, dict) or not columns:
            return self._failure(
                action,
                "Parameter 'columns' must map column names to {from_unit, to_unit}.",
                precision,
            )
        for name, spec in columns.items():
            if not isinstance(spec, dict) or not isinstance(spec.get("from_unit"), str):
                return self._failure(
                    action, f"columns['{name}'] needs a 'from_unit' string.", precision
                )
            try:
                _convert(1.0, spec["from_unit"], spec.get("to_unit"), assume)
            except units.UnitError as exc:
                return self._failure(
                    action, f"columns['{name}']: {exc.code}: {exc.detail}", precision
                )

        columnar = isinstance(table, dict)
        if columnar:
            if not all(isinstance(v, list) for v in table.values()):
                return self._failure(
                    action, "A columnar table maps column names to lists.", precision
                )
            lengths = {len(v) for v in table.values()}
            if len(lengths) > 1:
                return self._failure(
                    action, "Columnar table columns have different lengths.", precision
                )
            rows = [
                {name: values[i] for name, values in table.items()}
                for i in range(lengths.pop())
            ]
        elif isinstance(table, list) and all(isinstance(r, dict) for r in table):
            rows = [dict(row) for row in table]
        else:
            return self._failure(
                action,
                "Parameter 'table' must be a list of row objects or an object of column lists.",
                precision,
            )

        results: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        skipped = 0
        for index, row in enumerate(rows):
            record_id = row.get("id", index)
            for name, spec in columns.items():
                if row.get(name) is None:
                    skipped += 1
                    continue
                cell = {
                    "id": record_id,
                    "value": row[name],
                    "from_unit": spec["from_unit"],
                    "to_unit": spec.get("to_unit"),
                }
                result, error = self._convert_record(
                    index, cell, assume, precision, canonical=False
                )
                if result is not None:
                    result["column"] = name
                    row[name] = result["value"]
                    results.append(result)
                else:
                    error["column"] = name
                    errors.append(error)

        envelope = self._envelope(
            action, results, errors, precision, skipped=skipped, compact=compact
        )
        if not compact:
            envelope["table"] = (
                {name: [row[name] for row in rows] for name in table}
                if columnar
                else rows
            )
        return envelope

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
        compact: bool = False,
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
        envelope = {
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
        if compact:
            stats: Dict[str, Dict[str, Any]] = {}
            for result in results:
                entry = stats.setdefault(
                    result["to_unit"],
                    {"count": 0, "min": result["value"], "max": result["value"]},
                )
                entry["count"] += 1
                entry["min"] = min(entry["min"], result["value"])
                entry["max"] = max(entry["max"], result["value"])
            envelope["results"] = results[:COMPACT_SAMPLE_SIZE]
            envelope["compact"] = True
            envelope["results_omitted"] = max(0, len(results) - COMPACT_SAMPLE_SIZE)
            envelope["stats"] = stats
        return envelope

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

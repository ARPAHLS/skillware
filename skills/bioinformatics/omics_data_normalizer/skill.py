"""Normalize tabular omics data into a FAIR-oriented JSON package."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from skillware.core.base_skill import BaseSkill


REQUIRED_METADATA = (
    "sample_id",
    "organism",
    "tissue",
    "collection_date",
    "assay",
)


def _normalize_column_name(value: Any) -> str:
    """Return a stable snake_case name suitable for metadata headers."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", str(value).strip().lower()).strip("_")
    return normalized or "unnamed_column"


def _unique_column_names(columns: List[Any]) -> List[str]:
    """Normalize headers while retaining deterministic names for duplicates."""
    seen: Dict[str, int] = {}
    result: List[str] = []
    for column in columns:
        base = _normalize_column_name(column)
        seen[base] = seen.get(base, 0) + 1
        result.append(base if seen[base] == 1 else f"{base}_{seen[base]}")
    return result


class OmicsDataNormalizerSkill(BaseSkill):
    """Validate and package CSV/TSV omics data without interpreting biology."""

    @property
    def manifest(self) -> Dict[str, Any]:
        import yaml

        manifest_path = Path(__file__).with_name("manifest.yaml")
        with manifest_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle)

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        self.validate_params(params)

        raw_path = Path(params["raw_csv_path"]).expanduser()
        target_standard = params["target_standard"].strip().upper()
        if not raw_path.is_file():
            return {
                "status": "error",
                "message": f"Input file does not exist: {raw_path}",
            }

        if raw_path.suffix.lower() not in {".csv", ".tsv"}:
            return {
                "status": "error",
                "message": "raw_csv_path must point to a .csv or .tsv file",
            }

        try:
            import pandas as pd

            separator = "\t" if raw_path.suffix.lower() == ".tsv" else ","
            frame = pd.read_csv(raw_path, sep=separator)
            original_columns = list(frame.columns)
            normalized_columns = _unique_column_names(original_columns)
            frame.columns = normalized_columns
            records = json.loads(frame.to_json(orient="records", date_format="iso"))
        except Exception as exc:
            return {"status": "error", "message": f"Could not read input table: {exc}"}

        missing_metadata = [
            field for field in REQUIRED_METADATA if field not in normalized_columns
        ]
        columns = []
        for original, normalized in zip(original_columns, normalized_columns):
            columns.append(
                {
                    "original_name": str(original),
                    "normalized_name": normalized,
                    "dtype": str(frame[normalized].dtype),
                    "missing_values": int(frame[normalized].isna().sum()),
                }
            )

        output_path = raw_path.with_name(f"{raw_path.stem}_fair.json")
        package = {
            "fair_metadata": {
                "target_standard": target_standard,
                "source_file": raw_path.name,
                "row_count": int(len(frame.index)),
                "column_count": int(len(frame.columns)),
                "columns": columns,
            },
            "records": records,
        }
        output_path.write_text(
            json.dumps(package, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        return {
            "status": "normalized",
            "fair_compliant_json_path": str(output_path),
            "missing_metadata_warnings": missing_metadata,
            "row_count": len(frame.index),
            "column_count": len(frame.columns),
        }

"""Jurisdiction crisis resource lookup."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Dict, List

_RESOURCES_PATH = os.path.join(os.path.dirname(__file__), "kb", "crisis_resources.json")

VALID_JURISDICTIONS = frozenset({"US", "UK", "FR", "DE", "ES", "IT", "EU", "GLOBAL"})


@lru_cache(maxsize=1)
def load_resources() -> Dict[str, Any]:
    with open(_RESOURCES_PATH, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def normalize_jurisdiction(value: str) -> str:
    cleaned = (value or "GLOBAL").strip().upper()
    if cleaned in ("UNKNOWN", ""):
        return "GLOBAL"
    if cleaned in VALID_JURISDICTIONS:
        return cleaned
    return "GLOBAL"


def _format_block(label: str, block: Dict[str, Any]) -> List[str]:
    lines: List[str] = []
    if not isinstance(block, dict):
        return lines
    emergency = block.get("emergency")
    if isinstance(emergency, dict):
        lines.append(
            f"{label} emergency: {emergency.get('name', 'Emergency')} "
            f"— {emergency.get('contact', '')}"
        )
    helplines = block.get("helplines", [])
    if isinstance(helplines, list):
        for line in helplines:
            if not isinstance(line, dict):
                continue
            hours = line.get("hours", "")
            flag = "24/7" if line.get("is_24_7") else "not 24/7"
            lines.append(
                f"- {line.get('name', 'Helpline')} ({flag}): "
                f"{line.get('contact', '')} [{line.get('channel', '')}] "
                f"hours={hours} source={line.get('source_url', '')}"
            )
    return lines


def format_crisis_resources(jurisdiction: str) -> str:
    data = load_resources()
    primary_key = normalize_jurisdiction(jurisdiction)
    sections: List[str] = []

    primary = data.get(primary_key)
    if isinstance(primary, dict):
        sections.extend(_format_block(primary_key, primary))

    if primary_key != "GLOBAL":
        global_block = data.get("GLOBAL")
        if isinstance(global_block, dict):
            sections.append("Global fallback resources:")
            sections.extend(_format_block("GLOBAL", global_block))

    return "\n".join(sections)

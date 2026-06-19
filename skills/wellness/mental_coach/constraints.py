"""Load and apply hard constraints from kb/hard_constraints.yaml."""

from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Any, Dict, List, Optional

import yaml

_CONSTRAINTS_PATH = os.path.join(
    os.path.dirname(__file__), "kb", "hard_constraints.yaml"
)

CLINICAL_PATTERNS: Dict[str, List[str]] = {
    "no_diagnosis": [
        r"\bdiagnos(e|is|ing)\b",
        r"\bdo i have (depression|anxiety|bipolar|adhd|ptsd|ocd)\b",
        r"\bwhat (disorder|condition|illness) do i have\b",
        r"\bam i (depressed|bipolar|schizophrenic)\b",
    ],
    "no_medication_advice": [
        r"\b(should i|can i) (take|stop|start) (my )?(medication|meds|antidepressant)\b",
        r"\bwhat medication\b",
        r"\bwhat dose\b",
        r"\bprescribe\b",
        r"\b(increase|decrease) my (dose|dosage)\b",
    ],
    "no_clinical_interpretation": [
        r"\binterpret my (lab|blood test|test results)\b",
        r"\bwhat do my results mean\b",
        r"\bclinical record\b",
    ],
}

INJECTION_PATTERNS = [
    r"ignore (your|all|previous) (rules|instructions|constraints)",
    r"disregard (your|the) (policy|safety|guidelines)",
    r"pretend you are (a )?(doctor|therapist|psychiatrist)",
    r"jailbreak",
    r"bypass (your|the) (rules|safety|filter)",
]


@lru_cache(maxsize=1)
def load_constraints_config() -> Dict[str, Any]:
    with open(_CONSTRAINTS_PATH, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    return data if isinstance(data, dict) else {}


def get_disclaimers(kind: str = "default") -> List[str]:
    config = load_constraints_config()
    disclaimers = config.get("disclaimers_required", {})
    items = disclaimers.get(kind, disclaimers.get("default", []))
    return list(items) if isinstance(items, list) else []


def detect_clinical_violation(text: str) -> Optional[str]:
    normalized = text.lower()
    for constraint_id, patterns in CLINICAL_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, normalized):
                return constraint_id
    return None


def detect_injection_attempt(text: str) -> bool:
    normalized = text.lower()
    return any(re.search(pattern, normalized) for pattern in INJECTION_PATTERNS)


def get_playbook_entry(decision: str) -> Dict[str, Any]:
    config = load_constraints_config()
    playbook = config.get("escalation_playbook", {})
    key = {
        "ESCALATE": "on_escalate",
        "CAUTION": "on_caution",
        "OK": "on_ok",
    }.get(decision, "on_ok")
    entry = playbook.get(key, {})
    return entry if isinstance(entry, dict) else {}


def list_hard_constraint_ids() -> List[str]:
    config = load_constraints_config()
    items = config.get("hard_constraints", [])
    ids: List[str] = []
    for item in items:
        if isinstance(item, dict) and item.get("id"):
            ids.append(str(item["id"]))
    return ids

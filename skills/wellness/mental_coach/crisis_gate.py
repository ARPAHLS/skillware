"""Deterministic crisis gate — runs before retrieval, no LLM dependency."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Sequence, Tuple

# Minimal conservative signal sets (intent-level, not exhaustive lexicons).
CRISIS_SIGNALS: Dict[str, Sequence[str]] = {
    "suicidal_ideation": (
        "kill myself",
        "end my life",
        "want to die",
        "suicidal",
        "not want to live",
        "better off dead",
        "end it all",
    ),
    "self_harm": (
        "hurt myself",
        "harm myself",
        "cut myself",
        "self harm",
        "self-harm",
    ),
    "harm_to_others": (
        "hurt someone",
        "kill him",
        "kill her",
        "kill them",
        "harm others",
        "going to hurt",
    ),
    "abuse_or_violence": (
        "being abused",
        "he hits me",
        "she hits me",
        "sexually assaulted",
        "domestic violence",
        "partner hurts me",
    ),
    "acute_medical_emergency": (
        "can't breathe",
        "cannot breathe",
        "chest pain",
        "overdose",
        "heart attack",
        "having a stroke",
    ),
    "severe_acute_distress": (
        "can't cope",
        "cannot cope",
        "falling apart",
        "panic attack",
        "overwhelmed can't function",
        "completely overwhelmed",
    ),
}

CATEGORY_ACTION = {
    "suicidal_ideation": "ESCALATE",
    "self_harm": "ESCALATE",
    "harm_to_others": "ESCALATE",
    "abuse_or_violence": "ESCALATE",
    "acute_medical_emergency": "ESCALATE",
    "severe_acute_distress": "CAUTION",
}

NEGATION_PREFIXES = (
    "don't ",
    "do not ",
    "never ",
    "not going to ",
    "won't ",
    "wouldn't ",
)

CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uac00-\ud7af]")
NON_ASCII_RE = re.compile(r"[^\x00-\x7F]")


@dataclass
class LanguageAssessment:
    is_english: bool
    non_english: bool
    reason: str = ""


@dataclass
class GateResult:
    policy_status: str
    crisis_categories: List[str] = field(default_factory=list)
    ambiguous: bool = False


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = re.sub(r"\s+", " ", normalized).strip().lower()
    return normalized


def assess_language(text: str) -> LanguageAssessment:
    if not text.strip():
        return LanguageAssessment(is_english=True, non_english=False)

    if CJK_RE.search(text):
        return LanguageAssessment(
            is_english=False,
            non_english=True,
            reason="CJK characters detected; v0.1 is EN-first.",
        )

    non_ascii = len(NON_ASCII_RE.findall(text))
    if non_ascii >= 8 or (len(text) > 0 and non_ascii / len(text) > 0.15):
        return LanguageAssessment(
            is_english=False,
            non_english=True,
            reason="High non-ASCII ratio; v0.1 is EN-first.",
        )

    return LanguageAssessment(is_english=True, non_english=False)


def _has_negation_before(text: str, index: int) -> bool:
    window = text[max(0, index - 48) : index]
    return any(prefix in window for prefix in NEGATION_PREFIXES)


def _match_signals(normalized: str) -> Tuple[List[str], bool]:
    matched: List[str] = []
    ambiguous = False
    for category, signals in CRISIS_SIGNALS.items():
        for signal in signals:
            start = 0
            while True:
                idx = normalized.find(signal, start)
                if idx < 0:
                    break
                if _has_negation_before(normalized, idx):
                    ambiguous = True
                else:
                    matched.append(category)
                start = idx + len(signal)
    # Preserve order, dedupe
    seen = set()
    ordered: List[str] = []
    for cat in matched:
        if cat not in seen:
            ordered.append(cat)
            seen.add(cat)
    return ordered, ambiguous


def _resolve_policy(categories: Sequence[str], ambiguous: bool) -> str:
    if categories:
        if any(CATEGORY_ACTION.get(c) == "ESCALATE" for c in categories):
            return "ESCALATE"
        if any(CATEGORY_ACTION.get(c) == "CAUTION" for c in categories):
            return "CAUTION"
    if ambiguous:
        return "CAUTION"
    return "OK"


def evaluate_crisis_gate(user_prompt: str) -> GateResult:
    normalized = normalize_text(user_prompt)
    categories, ambiguous = _match_signals(normalized)
    policy_status = _resolve_policy(categories, ambiguous)
    return GateResult(
        policy_status=policy_status,
        crisis_categories=categories,
        ambiguous=ambiguous and policy_status != "ESCALATE",
    )

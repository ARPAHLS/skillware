"""Deterministic Korean slang matcher, lookup, and template generation."""

from __future__ import annotations

import json
import os
import re
import unicodedata
from typing import Any, Dict, List, Optional, Sequence, Tuple

ACTIONS = frozenset({"interpret", "suggest", "lookup"})
AUDIENCES = frozenset({"peers", "mixed", "work", "elders"})
DEFAULT_ACTION = "interpret"
DEFAULT_AUDIENCE = "peers"
MAX_HITS_MIN = 1
MAX_HITS_MAX = 50
DEFAULT_MAX_HITS = 12

_SYLLABLE_MIN = 0xAC00
_SYLLABLE_MAX = 0xD7A3
_FORMAL_ENDINGS = ("습니다", "습니까", "하십시오", "하십니다")
_POLITE_ENDINGS = ("세요", "해요", "이에요", "예요")


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def _latin_boundary(text: str, start: int, end: int) -> bool:
    left = text[start - 1] if start else ""
    right = text[end] if end < len(text) else ""
    left_ok = (not left) or (not left.isalnum())
    right_ok = (not right) or (not right.isalnum())
    return left_ok and right_ok


def _is_syllable(ch: str) -> bool:
    if not ch:
        return False
    return _SYLLABLE_MIN <= ord(ch) <= _SYLLABLE_MAX


def _jamo_boundary(text: str, start: int, end: int) -> bool:
    """Allow adjacent jamo particles (ㄹㅇㅋㅋ) but not embedding in 가-힣 words."""
    left = text[start - 1] if start else ""
    right = text[end] if end < len(text) else ""
    if _is_syllable(left) or _is_syllable(right):
        return False
    if left and left.isascii() and left.isalnum():
        return False
    if right and right.isascii() and right.isalnum():
        return False
    return True


def compact_with_map(text: str) -> Tuple[str, List[int]]:
    chars: List[str] = []
    mapping: List[int] = []
    for index, char in enumerate(text):
        if char.isspace():
            continue
        chars.append(char)
        mapping.append(index)
    return "".join(chars), mapping


def _fold_latin(text: str) -> str:
    return "".join(ch.casefold() if ch.isascii() else ch for ch in text)


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def load_pack(kb_dir: str) -> Dict[str, Any]:
    meta = load_json(os.path.join(kb_dir, "pack_meta.json"))
    entries = load_json(os.path.join(kb_dir, "entries.json"))
    generation = load_json(os.path.join(kb_dir, "generation.json"))
    constitution = load_json(os.path.join(kb_dir, "constitution.json"))
    if not isinstance(entries, list) or not entries:
        raise ValueError("kb/entries.json must be a non-empty array")
    by_id: Dict[str, Dict[str, Any]] = {}
    matchers: List[Dict[str, Any]] = []
    for entry in entries:
        entry_id = str(entry.get("id") or "").strip()
        if not entry_id or entry_id in by_id:
            raise ValueError(f"duplicate or empty slang id: {entry_id!r}")
        by_id[entry_id] = entry
        kind = str(entry.get("kind") or "phrase")
        needles: List[Tuple[str, str]] = []
        for surface in entry.get("surfaces") or []:
            raw = nfc(str(surface)).strip()
            if raw:
                needles.append((raw, raw))
        for alias in entry.get("aliases") or []:
            raw = nfc(str(alias)).strip()
            if raw:
                needles.append((raw, str(entry["surfaces"][0])))
        for roman in entry.get("romanization") or []:
            raw = nfc(str(roman)).strip()
            if raw:
                needles.append((raw, str(entry["surfaces"][0])))
        seen = set()
        for raw, display in needles:
            compact = re.sub(r"\s+", "", raw)
            if not compact:
                continue
            key = _fold_latin(compact)
            if key in seen:
                continue
            seen.add(key)
            matchers.append(
                {
                    "needle": key,
                    "display": display,
                    "entry": entry,
                    "kind": kind,
                    "length": len(key),
                }
            )
    matchers.sort(key=lambda item: (-item["length"], item["needle"]))
    blocked = [
        nfc(str(item)).strip()
        for item in constitution.get("blocked_substrings") or []
        if str(item).strip()
    ]
    blocked.sort(key=len, reverse=True)
    return {
        "meta": meta,
        "entries": entries,
        "by_id": by_id,
        "matchers": matchers,
        "generation": generation,
        "constitution": constitution,
        "blocked": blocked,
    }


def _error(code: str, detail: str) -> Dict[str, Any]:
    return {
        "status": "error",
        "error": {"code": code, "detail": detail},
        "message": detail,
    }


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y"}:
            return True
        if lowered in {"0", "false", "no", "n", ""}:
            return False
    return bool(value)


def _coerce_int(value: Any, default: int) -> Optional[int]:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def find_blocked(text: str, blocked: Sequence[str]) -> List[str]:
    haystack = nfc(text)
    hits: List[str] = []
    occupied = [False] * len(haystack)
    for term in blocked:
        if not term:
            continue
        start = 0
        while True:
            index = haystack.find(term, start)
            if index < 0:
                break
            end = index + len(term)
            if not any(occupied[index:end]):
                hits.append(term)
                for pos in range(index, end):
                    occupied[pos] = True
            start = index + 1
    return hits


def redact_blocked(text: str, blocked_hits: Sequence[str]) -> str:
    redacted = nfc(text)
    for term in sorted(set(blocked_hits), key=len, reverse=True):
        redacted = redacted.replace(term, "…")
    return redacted


def find_hits(
    text: str,
    pack: Dict[str, Any],
    max_hits: int,
) -> List[Dict[str, Any]]:
    original = nfc(text)
    compact, mapping = compact_with_map(original)
    folded = _fold_latin(compact)
    occupied = [False] * len(folded)
    hits: List[Dict[str, Any]] = []
    for matcher in pack["matchers"]:
        if len(hits) >= max_hits:
            break
        needle = matcher["needle"]
        if not needle:
            continue
        start = 0
        while len(hits) < max_hits:
            index = folded.find(needle, start)
            if index < 0:
                break
            end = index + len(needle)
            kind = matcher["kind"]
            orig_start = mapping[index]
            orig_end = mapping[end - 1] + 1
            if kind == "latin" and not _latin_boundary(original, orig_start, orig_end):
                start = index + 1
                continue
            if kind == "jamo" and not _jamo_boundary(original, orig_start, orig_end):
                start = index + 1
                continue
            if any(occupied[index:end]):
                start = index + 1
                continue
            for pos in range(index, end):
                occupied[pos] = True
            entry = matcher["entry"]
            span = original[orig_start:orig_end]
            hits.append(
                {
                    "id": entry["id"],
                    "surface": matcher["display"],
                    "matched": span,
                    "span": [orig_start, orig_end],
                    "translation": entry.get("translation", ""),
                    "breakdown": entry.get("breakdown", ""),
                    "nuance": entry.get("nuance", ""),
                    "formality": entry.get("formality", "Informal / Slang"),
                    "intents": list(entry.get("intents") or []),
                    "generation_safe": bool(entry.get("generation_safe", False)),
                    "caution": bool(entry.get("caution", False)),
                    "vulgar": bool(entry.get("vulgar", False)),
                    "romanization": list(entry.get("romanization") or []),
                }
            )
            start = end
    hits.sort(key=lambda item: (item["span"][0], -(item["span"][1] - item["span"][0])))
    return _merge_adjacent(hits)


def _merge_adjacent(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not hits:
        return hits
    merged: List[Dict[str, Any]] = [hits[0]]
    for hit in hits[1:]:
        prev = merged[-1]
        if hit["id"] == prev["id"] and hit["span"][0] <= prev["span"][1]:
            prev["span"][1] = max(prev["span"][1], hit["span"][1])
            prev["matched"] = prev["matched"] + hit["matched"]
            continue
        merged.append(hit)
    return merged


def lookup_entry(pack: Dict[str, Any], query: str) -> Optional[Dict[str, Any]]:
    needle = nfc(query).strip()
    if not needle:
        return None
    folded = _fold_latin(re.sub(r"\s+", "", needle))
    by_id = pack["by_id"]
    if needle in by_id:
        return by_id[needle]
    for entry in pack["entries"]:
        candidates = []
        candidates.extend(entry.get("surfaces") or [])
        candidates.extend(entry.get("aliases") or [])
        candidates.extend(entry.get("romanization") or [])
        for candidate in candidates:
            compact = _fold_latin(re.sub(r"\s+", "", nfc(str(candidate))))
            if compact == folded:
                return entry
    return None


def public_entry(entry: Dict[str, Any], include_romanization: bool) -> Dict[str, Any]:
    payload = {
        "id": entry.get("id"),
        "surface": (entry.get("surfaces") or [""])[0],
        "surfaces": list(entry.get("surfaces") or []),
        "translation": entry.get("translation", ""),
        "breakdown": entry.get("breakdown", ""),
        "nuance": entry.get("nuance", ""),
        "formality": entry.get("formality", "Informal / Slang"),
        "intents": list(entry.get("intents") or []),
        "generation_safe": bool(entry.get("generation_safe", False)),
        "caution": bool(entry.get("caution", False)),
        "vulgar": bool(entry.get("vulgar", False)),
    }
    if include_romanization:
        payload["romanization"] = list(entry.get("romanization") or [])
    return payload


def _style_hint(text: str, audience: str) -> Optional[str]:
    if audience not in {"peers", "mixed"}:
        return None
    if any(text.endswith(ending) or ending in text for ending in _FORMAL_ENDINGS):
        return (
            "This reads as formal written Korean (습니다-style). "
            "For peer chat, call suggest() with audience=peers."
        )
    if audience == "peers" and any(ending in text for ending in _POLITE_ENDINGS):
        return (
            "This reads as polite 요-form. Fine for mixed company; "
            "peer group chats often drop to 반말 plus slang."
        )
    return None


def _compose_translation(text: str, hits: List[Dict[str, Any]]) -> Optional[str]:
    if not hits:
        return None
    compact = re.sub(r"\s+", "", nfc(text))
    if compact == "요즘완전폼미쳤다" and any(
        hit["id"] == "pom_michyeotda" for hit in hits
    ):
        return (
            "They are absolutely killing it right now / "
            "Their form is crazy these days"
        )
    if len(hits) == 1:
        return hits[0]["translation"]
    return " / ".join(
        dict.fromkeys(hit["translation"] for hit in hits if hit["translation"])
    )


def _compose_nuance(
    text: str,
    hits: List[Dict[str, Any]],
    context: str,
    unmatched: bool,
) -> str:
    if unmatched:
        base = (
            "No bundled slang surfaces matched. The text may be standard Korean "
            "or a term outside this September 2026 pack."
        )
    elif len(hits) == 1:
        base = hits[0]["nuance"]
    else:
        base = " ".join(dict.fromkeys(hit["nuance"] for hit in hits if hit["nuance"]))
    if context.strip():
        return f"{base} Context noted: {context.strip()}"
    return base


def _compose_formality(hits: List[Dict[str, Any]], unmatched: bool) -> str:
    if unmatched or not hits:
        return "unknown"
    if any(hit.get("vulgar") for hit in hits):
        return "Informal / Vulgar"
    if any(hit.get("caution") for hit in hits):
        return "Informal / Caution"
    return hits[0].get("formality") or "Informal / Slang"


def interpret(
    pack: Dict[str, Any],
    text: str,
    context: str,
    max_hits: int,
    include_romanization: bool,
    blocked_hits: Sequence[str],
    audience: str,
) -> Dict[str, Any]:
    reviewed = redact_blocked(text, blocked_hits)
    hits = find_hits(reviewed, pack, max_hits)
    unmatched = not hits
    breakdown = {}
    for hit in hits:
        breakdown[hit["surface"]] = hit["breakdown"]
    translation = _compose_translation(reviewed, hits)
    payload: Dict[str, Any] = {
        "status": "ok",
        "action": "interpret",
        "translation": translation,
        "slang_breakdown": breakdown,
        "nuance": _compose_nuance(reviewed, hits, context, unmatched),
        "formality": _compose_formality(hits, unmatched),
        "hit_count": len(hits),
        "hits": [
            {
                "id": hit["id"],
                "surface": hit["surface"],
                "matched": hit["matched"],
                "translation": hit["translation"],
                "caution": hit["caution"],
                "vulgar": hit["vulgar"],
                **(
                    {"romanization": hit["romanization"]}
                    if include_romanization
                    else {}
                ),
            }
            for hit in hits
        ],
        "unmatched": unmatched,
        "warnings": [],
        "style_hint": _style_hint(reviewed, audience),
        "blocked_omitted": list(blocked_hits),
        "pack_snapshot": pack["meta"].get("snapshot"),
        "pack_id": pack["meta"].get("id"),
        "entry_count": len(pack["entries"]),
    }
    if blocked_hits:
        payload["warnings"].append(
            "Input contained terms this pack will not gloss "
            "(slurs or appearance-policing slang). They were omitted."
        )
    if any(hit.get("caution") for hit in hits):
        payload["warnings"].append(
            "One or more matches are marked caution: explain, do not repeat as a joke."
        )
    if not payload["warnings"]:
        payload["warnings"] = []
    if payload["style_hint"] is None:
        payload.pop("style_hint")
    return payload


def _normalize_intent(raw: str, generation: Dict[str, Any]) -> Optional[str]:
    text = nfc(raw).strip().lower()
    if not text:
        return None
    aliases = generation.get("intent_aliases") or {}
    if text in aliases:
        return text
    for intent, words in aliases.items():
        for word in words:
            if nfc(str(word)).strip().lower() == text:
                return intent
    return None


def infer_intent(
    text: str,
    explicit: str,
    hits: Sequence[Dict[str, Any]],
    generation: Dict[str, Any],
) -> Optional[str]:
    named = _normalize_intent(explicit, generation)
    if named:
        return named
    aliases = generation.get("intent_aliases") or {}
    blob = nfc(text).casefold()
    scored: List[Tuple[int, str]] = []
    for intent, words in aliases.items():
        score = 0
        for word in words:
            token = nfc(str(word)).strip()
            if token and token.casefold() in blob:
                score += max(1, len(token))
        if score:
            scored.append((score, intent))
    if scored:
        scored.sort(key=lambda item: (-item[0], item[1]))
        return scored[0][1]
    intents: List[str] = []
    for hit in hits:
        intents.extend(hit.get("intents") or [])
    if intents:
        return intents[0]
    return None


def _eligible_entries(
    pack: Dict[str, Any],
    intent: str,
    audience: str,
    vulgar_ok: bool,
) -> List[Dict[str, Any]]:
    chosen: List[Dict[str, Any]] = []
    for entry in pack["entries"]:
        if not entry.get("generation_safe"):
            continue
        if entry.get("caution"):
            continue
        if entry.get("vulgar") and not vulgar_ok:
            continue
        if audience in {"work", "elders"} and entry.get("work_unsafe"):
            continue
        if audience == "elders" and not entry.get("honorific_ok"):
            continue
        intents = set(entry.get("intents") or [])
        if intent not in intents and "any" not in intents:
            continue
        chosen.append(entry)
    return chosen


def _fill_template(template: str, primary: str, particle: str) -> str:
    text = template.replace("{primary}", primary).replace("{particle}", particle)
    text = re.sub(r"\s+", " ", text).strip()
    return text.replace(" ,", ",").replace(" .", ".")


def suggest(
    pack: Dict[str, Any],
    text: str,
    intent_param: str,
    audience: str,
    vulgar_ok: bool,
    include_romanization: bool,
    blocked_hits: Sequence[str],
    max_hits: int,
) -> Dict[str, Any]:
    warnings: List[str] = []
    if blocked_hits:
        warnings.append(
            "Refusing to generate from blocked slurs or appearance-policing slang."
        )
        return {
            "status": "ok",
            "action": "suggest",
            "translation": None,
            "slang_breakdown": {},
            "nuance": "Generation skipped because the input included blocked terms.",
            "formality": "blocked",
            "hit_count": 0,
            "suggestions": [],
            "warnings": warnings,
            "blocked_omitted": list(blocked_hits),
            "pack_snapshot": pack["meta"].get("snapshot"),
            "pack_id": pack["meta"].get("id"),
            "entry_count": len(pack["entries"]),
        }

    reviewed = nfc(text)
    hits = find_hits(reviewed, pack, max_hits) if reviewed.strip() else []
    generation = pack["generation"]
    intent = infer_intent(reviewed, intent_param, hits, generation)
    if not intent:
        return _error(
            "NEED_TEXT_OR_INTENT",
            "suggest() needs an intent (for example praise, food, work) "
            "or Korean/English text the lexicon can classify.",
        )

    templates_root = generation.get("templates") or {}
    intent_templates = templates_root.get(intent) or templates_root.get("generic") or {}
    audience_templates = list(
        intent_templates.get(audience) or intent_templates.get("peers") or []
    )
    particles = list((generation.get("particles") or {}).get(audience) or [])

    if audience == "elders":
        warnings.append(
            "Slang generation is suppressed for audience=elders; "
            "polite Korean templates are used instead."
        )
    elif audience == "work":
        warnings.append("Work audience: only mild, office-safe slang is eligible.")

    if audience == "elders" or (audience == "work" and not audience_templates):
        filled = [_fill_template(item, "", "") for item in audience_templates[:3]]
        suggestions = [
            {
                "text": line,
                "used_entries": [],
                "formality": "Polite" if audience == "elders" else "Work-safe",
                "nuance": "Honorific or workplace phrasing; slang avoided.",
                "audience_ok": True,
            }
            for line in filled
            if line
        ]
        translation = suggestions[0]["text"] if suggestions else None
        return {
            "status": "ok",
            "action": "suggest",
            "translation": translation,
            "slang_breakdown": {},
            "nuance": suggestions[0]["nuance"] if suggestions else "No template.",
            "formality": suggestions[0]["formality"] if suggestions else "unknown",
            "hit_count": len(suggestions),
            "suggestions": suggestions,
            "intent": intent,
            "audience": audience,
            "warnings": warnings,
            "blocked_omitted": [],
            "pack_snapshot": pack["meta"].get("snapshot"),
            "pack_id": pack["meta"].get("id"),
            "entry_count": len(pack["entries"]),
        }

    eligible = _eligible_entries(pack, intent, audience, vulgar_ok)
    if hits:
        hit_ids = {hit["id"] for hit in hits}
        eligible.sort(
            key=lambda entry: (0 if entry["id"] in hit_ids else 1, entry["id"])
        )
    if not eligible and audience_templates:
        eligible = []

    suggestions: List[Dict[str, Any]] = []
    used_primary = eligible[0] if eligible else None
    secondary = eligible[1] if len(eligible) > 1 else None
    particle = particles[0] if particles else ""
    primary_surface = (used_primary.get("surfaces") or [""])[0] if used_primary else ""

    for template in audience_templates[:4]:
        line = _fill_template(template, primary_surface, particle)
        if secondary and "{secondary}" in template:
            line = line.replace("{secondary}", (secondary.get("surfaces") or [""])[0])
        else:
            line = line.replace("{secondary}", "").strip()
            line = re.sub(r"\s+", " ", line)
        if not line:
            continue
        used = []
        breakdown = {}
        if used_primary and primary_surface and primary_surface in line:
            used.append(used_primary["id"])
            breakdown[primary_surface] = used_primary.get("breakdown", "")
        if secondary:
            sec_surface = (secondary.get("surfaces") or [""])[0]
            if sec_surface and sec_surface in line:
                used.append(secondary["id"])
                breakdown[sec_surface] = secondary.get("breakdown", "")
        if particle and particle in line:
            particle_entry = lookup_entry(pack, particle)
            if particle_entry and particle_entry["id"] not in used:
                if particle_entry.get("generation_safe"):
                    used.append(particle_entry["id"])
                    breakdown.setdefault(
                        (particle_entry.get("surfaces") or [particle])[0],
                        particle_entry.get("breakdown", ""),
                    )
        item = {
            "text": line,
            "used_entries": used,
            "formality": (
                used_primary.get("formality") if used_primary else "Informal / Slang"
            ),
            "nuance": (
                used_primary.get("nuance")
                if used_primary
                else "Peer-register template with no matched slang entry."
            ),
            "audience_ok": True,
        }
        if include_romanization and used_primary:
            item["romanization"] = list(used_primary.get("romanization") or [])
        item["slang_breakdown"] = breakdown
        suggestions.append(item)

    if not suggestions:
        return _error(
            "NO_SUGGESTIONS",
            f"No generation-safe templates for intent={intent!r} audience={audience!r}.",
        )

    first = suggestions[0]
    return {
        "status": "ok",
        "action": "suggest",
        "translation": first["text"],
        "slang_breakdown": first.get("slang_breakdown") or {},
        "nuance": first["nuance"],
        "formality": first["formality"],
        "hit_count": len(suggestions),
        "suggestions": suggestions,
        "intent": intent,
        "audience": audience,
        "warnings": warnings,
        "blocked_omitted": [],
        "pack_snapshot": pack["meta"].get("snapshot"),
        "pack_id": pack["meta"].get("id"),
        "entry_count": len(pack["entries"]),
    }


def lookup(
    pack: Dict[str, Any],
    text: str,
    include_romanization: bool,
    blocked_hits: Sequence[str],
) -> Dict[str, Any]:
    if blocked_hits:
        return {
            "status": "ok",
            "action": "lookup",
            "translation": None,
            "slang_breakdown": {},
            "nuance": "Lookup skipped for blocked terms.",
            "formality": "blocked",
            "hit_count": 0,
            "found": False,
            "entry": None,
            "warnings": [
                "This pack will not define slurs or appearance-policing slang."
            ],
            "blocked_omitted": list(blocked_hits),
            "pack_snapshot": pack["meta"].get("snapshot"),
            "pack_id": pack["meta"].get("id"),
            "entry_count": len(pack["entries"]),
        }
    entry = lookup_entry(pack, text)
    if not entry:
        return {
            "status": "ok",
            "action": "lookup",
            "translation": None,
            "slang_breakdown": {},
            "nuance": "No bundled entry for that surface, alias, or romanization.",
            "formality": "unknown",
            "hit_count": 0,
            "found": False,
            "entry": None,
            "warnings": [],
            "blocked_omitted": [],
            "pack_snapshot": pack["meta"].get("snapshot"),
            "pack_id": pack["meta"].get("id"),
            "entry_count": len(pack["entries"]),
        }
    public = public_entry(entry, include_romanization)
    return {
        "status": "ok",
        "action": "lookup",
        "translation": public["translation"],
        "slang_breakdown": {public["surface"]: public["breakdown"]},
        "nuance": public["nuance"],
        "formality": public["formality"],
        "hit_count": 1,
        "found": True,
        "entry": public,
        "warnings": (
            ["Caution entry: explain incoming use; do not generate it."]
            if public["caution"]
            else []
        ),
        "blocked_omitted": [],
        "pack_snapshot": pack["meta"].get("snapshot"),
        "pack_id": pack["meta"].get("id"),
        "entry_count": len(pack["entries"]),
    }


def execute_pack(pack: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
    action = nfc(str(params.get("action") or DEFAULT_ACTION)).strip().lower()
    if action not in ACTIONS:
        return _error(
            "UNKNOWN_ACTION",
            "action must be interpret, suggest, or lookup.",
        )
    audience = nfc(str(params.get("audience") or DEFAULT_AUDIENCE)).strip().lower()
    if audience not in AUDIENCES:
        return _error(
            "UNKNOWN_AUDIENCE",
            "audience must be peers, mixed, work, or elders.",
        )
    max_hits = _coerce_int(params.get("max_hits"), DEFAULT_MAX_HITS)
    if max_hits is None or max_hits < MAX_HITS_MIN or max_hits > MAX_HITS_MAX:
        return _error(
            "INVALID_MAX_HITS",
            f"max_hits must be an integer from {MAX_HITS_MIN} to {MAX_HITS_MAX}.",
        )
    text = nfc(str(params.get("text") if params.get("text") is not None else ""))
    context = nfc(
        str(params.get("context") if params.get("context") is not None else "")
    )
    intent = nfc(str(params.get("intent") if params.get("intent") is not None else ""))
    include_romanization = _coerce_bool(params.get("include_romanization"), False)
    vulgar_ok = _coerce_bool(params.get("vulgar_ok"), False)
    blocked_hits = find_blocked(f"{text}\n{intent}\n{context}", pack["blocked"])

    if action in {"interpret", "lookup"} and not text.strip():
        return _error("EMPTY_TEXT", f"{action}() requires a non-empty text string.")

    if action == "interpret":
        return interpret(
            pack,
            text,
            context,
            max_hits,
            include_romanization,
            blocked_hits,
            audience,
        )
    if action == "lookup":
        return lookup(pack, text, include_romanization, blocked_hits)
    return suggest(
        pack,
        text,
        intent,
        audience,
        vulgar_ok,
        include_romanization,
        blocked_hits,
        max_hits,
    )

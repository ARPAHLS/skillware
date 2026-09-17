"""Deterministic prompt-injection firewall — local-only, no network, no LLM.

OWASP LLM01 Layer-1 trust-boundary input scanner and sanitizer.
"""

from __future__ import annotations

import base64
import binascii
import codecs
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Literal, Optional, Sequence, Tuple
from urllib.parse import unquote

SensitivityLevel = Literal["strict", "balanced", "lenient"]
RiskLevel = Literal["none", "low", "medium", "high", "critical"]
Severity = Literal["low", "medium", "high", "critical"]
PolicyAction = Literal["allow", "flag", "block"]

_KB_DIR = Path(__file__).resolve().parent / "kb"

# Zero-width, bidi, format, and other non-printing controls (excluding common whitespace).
INVISIBLE_CODEPOINTS = frozenset(
    {
        0x00AD,
        0x034F,
        0x061C,
        0x180E,
        0x200B,
        0x200C,
        0x200D,
        0x200E,
        0x200F,
        0x202A,
        0x202B,
        0x202C,
        0x202D,
        0x202E,
        0x2060,
        0x2066,
        0x2067,
        0x2068,
        0x2069,
        0xFEFF,
    }
)

UNICODE_TAG_START = 0xE0000
UNICODE_TAG_END = 0xE007F
VARIATION_SELECTOR_RANGES = (
    (0xFE00, 0xFE0F),
    (0xE0100, 0xE01EF),
)
VS_RUN_THRESHOLD = 8
MAX_DECODE_DEPTH = 3
MAX_DECODE_BYTES = 8192
MAX_DECODE_CANDIDATES = 50
MAX_SOURCE_TEXT_CHARS = 100_000

HIDDEN_HTML_STYLE_PATTERNS = (
    r"display\s*:\s*none",
    r"visibility\s*:\s*hidden",
    r"opacity\s*:\s*0\b",
    r"font-size\s*:\s*0\b",
    r"height\s*:\s*0\b",
    r"width\s*:\s*0\b",
    r"max-height\s*:\s*0\b",
    r"text-indent\s*:\s*-\d",
    r"position\s*:\s*absolute.{0,40}(left|top)\s*:\s*-\d",
    r"color\s*:\s*(?:#fff(?:fff)?|white|rgb\(\s*255\s*,\s*255\s*,\s*255\s*\))",
)

HIDDEN_HTML_TAG_RE = re.compile(
    r"<(?P<tag>[a-zA-Z][\w:-]*)(?P<attrs>[^>]*)>(?P<body>.*?)</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
MARKDOWN_COMMENT_RE = re.compile(
    r"\[//\]:\s*(?:#|<>)\s*\((?P<body>.*?)\)",
    re.DOTALL,
)
ARIA_HIDDEN_RE = re.compile(
    r"<(?P<tag>[a-zA-Z][\w:-]*)(?P<attrs>[^>]*\baria-hidden\s*=\s*[\"']true[\"'][^>]*)>"
    r"(?P<body>.*?)</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
META_ATTR_RE = re.compile(
    r"\b(?P<attr>alt|title)\s*=\s*[\"'](?P<body>[^\"']{8,})[\"']",
    re.IGNORECASE,
)

MARKDOWN_IMAGE_RE = re.compile(
    r"!\[(?P<alt>.*?)\]\((?P<url>[^\)\s]+)(?:\s+[\"'].*?[\"'])?\)",
    re.IGNORECASE,
)
HTML_IMAGE_RE = re.compile(
    r"<img\s+[^>]*src=[\"'](?P<url>[^\"']+)[\"'][^>]*>",
    re.IGNORECASE,
)

DISCOURSE_MARKERS_RE = re.compile(
    r"(?i)\b("
    r"for example|for instance|such as|attackers? (write|use|craft)|"
    r"an? (example|sample) (of|attack)|quoted below|the (phrase|string)|"
    r"tutorial|demonstration|mitigation|vulnerability|cwe|owasp|"
    r"test case|payload|red team|proof of concept|poc|scenario|"
    r"advisory|cve|exploit|prompt injection|jailbreak example|"
    r"benchmark|detection test|simulation|analysis|research|"
    r"academic|paper|case study|security report|audit"
    r")\b"
)
QUOTE_OR_CODE_RE = re.compile(r"(`[^`]+`|\"[^\"]+\"|'[^']+'|```[\s\S]{0,400}?```)")

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
FAMILY_MESSAGE = {
    "instruction_negation": "Instruction override attempt detected.",
    "role_reset": "Jailbreak or role-play override framing detected.",
    "exfiltration": "System prompt or secret exfiltration attempt detected.",
    "action_hijack": "Action hijack attempt detected.",
    "authority_spoof": "Authority or urgency spoofing detected.",
    "boundary_spoof": "Prompt boundary spoofing detected.",
    "hidden_text": "Hidden prompt override mechanism detected.",
    "unicode_evasion": "Invisible or steganographic Unicode channel detected.",
    "confusables": "Homoglyph / confusable evasion detected.",
    "encoded_payload": "Encoded payload smuggling detected.",
    "context_mismatch": "Instruction-like content in data-like context detected.",
    "leetspeak": "Leetspeak substitution evasion detected.",
    "scramble": "Typoglycemia / keyword scramble evasion detected.",
    "mixed_script": "Mixed-script / homoglyph evasion detected.",
    "exfiltration_channel": "Markdown/HTML exfiltration channel detected.",
    "resource_limit": "Input size exceeds resource limit (DoS protection).",
}

LEET_MAP = {
    "0": "o",
    "1": "i",
    "3": "e",
    "4": "a",
    "5": "s",
    "7": "t",
    "8": "b",
    "@": "a",
    "$": "s",
    "!": "i",
}

HIGH_SIGNAL_KEYWORDS = {
    "ignore",
    "system",
    "disregard",
    "override",
    "exfiltrate",
    "password",
    "prompt",
    "secret",
    "instructions",
    "previous",
    "reveal",
}

_HIDDEN_CHANNELS = frozenset(
    {
        "html_hidden",
        "html_comment",
        "markdown_comment",
        "aria_hidden",
        "meta_alt",
        "meta_title",
        "unicode_tag",
        "variation_selector",
        "zero_width_or_bidi",
        "confusables_skeleton",
        "encoded",
        "rot13",
        "reversed_text",
        "leetspeak",
        "typoglycemia",
        "unicode_mixed_script",
        "markdown_image_exfil",
        "html_image_exfil",
    }
)


@dataclass
class PatternEntry:
    pattern_id: str
    family: str
    regex: re.Pattern[str]
    severity: Severity
    example: str
    notes: str
    source: str


@dataclass
class Finding:
    category: str
    channel: str
    severity: Severity
    span: Tuple[int, int]
    evidence: str
    pattern_id: Optional[str] = None
    decoded_layers: Optional[int] = None
    decode_chain: Optional[List[str]] = None
    decoded_preview: Optional[str] = None
    downgraded: bool = False


@dataclass
class HiddenChannel:
    channel: str
    start: int
    end: int
    body: str
    body_start: int


@dataclass
class CanonicalForm:
    original: str
    visible: str
    skeleton: str
    visible_to_original: List[int]
    hidden_channels: List[HiddenChannel] = field(default_factory=list)


@dataclass
class ScanResult:
    is_safe: bool
    risk_level: RiskLevel
    detected_threat: Optional[str]
    findings: List[Dict[str, object]]
    sanitized_text: str
    offline: bool
    sensitivity: SensitivityLevel
    policy_action: PolicyAction = "allow"
    removed_span_count: int = 0
    sanitized_length_delta: int = 0


_PATTERN_CACHE: Optional[List[PatternEntry]] = None
_CONFUSABLES_CACHE: Optional[Dict[str, str]] = None


def _load_patterns() -> List[PatternEntry]:
    global _PATTERN_CACHE
    if _PATTERN_CACHE is not None:
        return _PATTERN_CACHE
    payload = json.loads(
        (_KB_DIR / "injection_patterns.json").read_text(encoding="utf-8")
    )
    entries: List[PatternEntry] = []
    for raw in payload.get("patterns", []):
        entries.append(
            PatternEntry(
                pattern_id=str(raw["pattern_id"]),
                family=str(raw["family"]),
                regex=re.compile(str(raw["regex"])),
                severity=raw.get("severity", "high"),  # type: ignore[arg-type]
                example=str(raw.get("example", "")),
                notes=str(raw.get("notes", "")),
                source=str(raw.get("source", "")),
            )
        )
    _PATTERN_CACHE = entries
    return entries


def _load_confusables() -> Dict[str, str]:
    global _CONFUSABLES_CACHE
    if _CONFUSABLES_CACHE is not None:
        return _CONFUSABLES_CACHE
    payload = json.loads((_KB_DIR / "confusables.json").read_text(encoding="utf-8"))
    _CONFUSABLES_CACHE = {
        str(k): str(v) for k, v in payload.get("mappings", {}).items()
    }
    return _CONFUSABLES_CACHE


def _is_variation_selector(codepoint: int) -> bool:
    return any(start <= codepoint <= end for start, end in VARIATION_SELECTOR_RANGES)


def _is_format_or_invisible(char: str) -> bool:
    codepoint = ord(char)
    if codepoint in INVISIBLE_CODEPOINTS:
        return True
    if UNICODE_TAG_START <= codepoint <= UNICODE_TAG_END:
        return True
    if _is_variation_selector(codepoint):
        return True
    if unicodedata.category(char) in {"Cf", "Cc"} and char not in "\t\n\r":
        return True
    return False


def _to_skeleton(text: str, mappings: Dict[str, str]) -> str:
    return "".join(mappings.get(ch, ch) for ch in text)


def canonicalize(source_text: str, *, input_mode: str = "auto") -> CanonicalForm:
    """Normalize text, split hidden channels, and build a confusables skeleton."""
    original = source_text or ""
    mappings = _load_confusables()
    hidden_channels: List[HiddenChannel] = []

    if input_mode in {"html", "markdown", "auto"}:
        style_union = "|".join(f"(?:{p})" for p in HIDDEN_HTML_STYLE_PATTERNS)
        style_re = re.compile(style_union, re.IGNORECASE | re.DOTALL)

        for match in HIDDEN_HTML_TAG_RE.finditer(original):
            attrs = match.group("attrs") or ""
            if not style_re.search(attrs):
                continue
            body = match.group("body") or ""
            body_start = match.start("body")
            hidden_channels.append(
                HiddenChannel(
                    channel="html_hidden",
                    start=match.start(),
                    end=match.end(),
                    body=body,
                    body_start=body_start,
                )
            )

        for match in ARIA_HIDDEN_RE.finditer(original):
            body = match.group("body") or ""
            hidden_channels.append(
                HiddenChannel(
                    channel="aria_hidden",
                    start=match.start(),
                    end=match.end(),
                    body=body,
                    body_start=match.start("body"),
                )
            )

        for match in HTML_COMMENT_RE.finditer(original):
            body = match.group(0)
            hidden_channels.append(
                HiddenChannel(
                    channel="html_comment",
                    start=match.start(),
                    end=match.end(),
                    body=body,
                    body_start=match.start(),
                )
            )

        if input_mode in {"markdown", "auto"}:
            for match in MARKDOWN_COMMENT_RE.finditer(original):
                body = match.group("body") or ""
                hidden_channels.append(
                    HiddenChannel(
                        channel="markdown_comment",
                        start=match.start(),
                        end=match.end(),
                        body=body,
                        body_start=match.start("body"),
                    )
                )

        for match in META_ATTR_RE.finditer(original):
            body = match.group("body") or ""
            hidden_channels.append(
                HiddenChannel(
                    channel=f"meta_{match.group('attr').lower()}",
                    start=match.start(),
                    end=match.end(),
                    body=body,
                    body_start=match.start("body"),
                )
            )

    visible_chars: List[str] = []
    visible_to_original: List[int] = []
    pending_break = False
    for index, char in enumerate(original):
        if _is_format_or_invisible(char):
            # Preserve a word break so lexicon \\b patterns still match after
            # zero-width / format-char removal.
            pending_break = True
            continue
        if pending_break and visible_chars and visible_chars[-1] not in " \t\n\r":
            visible_chars.append(" ")
            visible_to_original.append(index)
        pending_break = False
        normalized = unicodedata.normalize("NFKC", char).casefold()
        for piece in normalized:
            if _is_format_or_invisible(piece):
                pending_break = True
                continue
            visible_chars.append(piece)
            visible_to_original.append(index)

    visible = "".join(visible_chars)
    skeleton = _to_skeleton(visible, mappings)
    return CanonicalForm(
        original=original,
        visible=visible,
        skeleton=skeleton,
        visible_to_original=visible_to_original,
        hidden_channels=hidden_channels,
    )


def normalize_text(text: str) -> Tuple[str, List[Tuple[int, int, str]]]:
    """Compatibility helper: NFKC text plus invisible spans in the original string."""
    normalized = unicodedata.normalize("NFKC", text or "")
    invisible_spans: List[Tuple[int, int, str]] = []
    index = 0
    while index < len(text or ""):
        char = text[index]
        codepoint = ord(char)
        if codepoint in INVISIBLE_CODEPOINTS or (
            UNICODE_TAG_START <= codepoint <= UNICODE_TAG_END
        ):
            start = index
            while index < len(text):
                cp = ord(text[index])
                if cp in INVISIBLE_CODEPOINTS or (
                    UNICODE_TAG_START <= cp <= UNICODE_TAG_END
                ):
                    index += 1
                else:
                    break
            label = (
                "unicode_tag_block"
                if UNICODE_TAG_START <= codepoint <= UNICODE_TAG_END
                else "invisible_character"
            )
            invisible_spans.append((start, index, label))
            continue
        if _is_variation_selector(codepoint):
            start = index
            while index < len(text) and _is_variation_selector(ord(text[index])):
                index += 1
            invisible_spans.append((start, index, "variation_selector_run"))
            continue
        if unicodedata.category(char) in {"Cf", "Cc"} and char not in "\t\n\r":
            invisible_spans.append((index, index + 1, "control_character"))
        index += 1
    return normalized, invisible_spans


def _map_visible_span(
    canonical: CanonicalForm, start: int, end: int
) -> Tuple[int, int]:
    if not canonical.visible_to_original:
        return 0, 0
    start = max(0, min(start, len(canonical.visible_to_original) - 1))
    end = max(start + 1, min(end, len(canonical.visible_to_original)))
    orig_start = canonical.visible_to_original[start]
    orig_end = canonical.visible_to_original[end - 1] + 1
    return orig_start, orig_end


def _severity_at_least(severity: Severity, minimum: Severity) -> bool:
    return SEVERITY_RANK[severity] >= SEVERITY_RANK[minimum]


def _downgrade_severity(severity: Severity) -> Severity:
    order: List[Severity] = ["low", "medium", "high", "critical"]
    idx = order.index(severity)
    return order[max(0, idx - 1)]


def _in_quote_with_discourse(original: str, start: int, end: int) -> bool:
    window_start = max(0, start - 250)
    window_end = min(len(original), end + 250)
    window = original[window_start:window_end]
    if not DISCOURSE_MARKERS_RE.search(window):
        return False
    for match in QUOTE_OR_CODE_RE.finditer(original):
        if match.start() <= start and end <= match.end():
            return True
    # Also treat fenced / inline markers immediately wrapping the span.
    left = original[max(0, start - 1) : start]
    right = original[end : min(len(original), end + 1)]
    if left in {"`", '"', "'"} and right in {"`", '"', "'"}:
        return True
    if "```" in window:
        return True
    return False


def _lexicon_hits(text: str) -> List[Tuple[PatternEntry, int, int, str]]:
    hits: List[Tuple[PatternEntry, int, int, str]] = []
    for entry in _load_patterns():
        for match in entry.regex.finditer(text):
            hits.append((entry, match.start(), match.end(), match.group(0)))
    return hits


def _detect_unicode_evasion(canonical: CanonicalForm) -> List[Finding]:
    findings: List[Finding] = []
    text = canonical.original
    index = 0
    while index < len(text):
        codepoint = ord(text[index])
        if UNICODE_TAG_START <= codepoint <= UNICODE_TAG_END:
            start = index
            while index < len(text) and (
                UNICODE_TAG_START <= ord(text[index]) <= UNICODE_TAG_END
            ):
                index += 1
            findings.append(
                Finding(
                    category="unicode_evasion",
                    channel="unicode_tag",
                    severity="high",
                    span=(start, index),
                    evidence=repr(text[start:index])[:240],
                )
            )
            continue
        if _is_variation_selector(codepoint):
            start = index
            while index < len(text) and _is_variation_selector(ord(text[index])):
                index += 1
            run_len = index - start
            if run_len >= VS_RUN_THRESHOLD:
                findings.append(
                    Finding(
                        category="unicode_evasion",
                        channel="variation_selector",
                        severity="high",
                        span=(start, index),
                        evidence=(
                            f"variation-selector run length={run_len} "
                            f"after base context {text[max(0, start - 1):start]!r}"
                        )[:240],
                    )
                )
            continue
        if codepoint in INVISIBLE_CODEPOINTS or (
            unicodedata.category(text[index]) in {"Cf", "Cc"}
            and text[index] not in "\t\n\r"
        ):
            start = index
            while index < len(text):
                ch = text[index]
                cp = ord(ch)
                if cp in INVISIBLE_CODEPOINTS or (
                    unicodedata.category(ch) in {"Cf", "Cc"} and ch not in "\t\n\r"
                ):
                    index += 1
                else:
                    break
            findings.append(
                Finding(
                    category="unicode_evasion",
                    channel="zero_width_or_bidi",
                    severity="medium",
                    span=(start, index),
                    evidence=repr(text[start:index])[:240],
                )
            )
            continue
        index += 1
    return findings


def _detect_hidden_text(canonical: CanonicalForm) -> List[Finding]:
    findings: List[Finding] = []
    patterns = _load_patterns()
    for channel in canonical.hidden_channels:
        body_fold = unicodedata.normalize("NFKC", channel.body).casefold()
        skeleton = _to_skeleton(body_fold, _load_confusables())
        lexicon_hit = None
        for entry in patterns:
            match = entry.regex.search(body_fold) or entry.regex.search(skeleton)
            if match:
                lexicon_hit = entry
                break
        if lexicon_hit is not None:
            findings.append(
                Finding(
                    category="hidden_text+instruction_override",
                    channel=channel.channel,
                    severity=(
                        "high" if lexicon_hit.severity != "critical" else "critical"
                    ),
                    span=(channel.start, channel.end),
                    evidence=(
                        f"{channel.channel} containing {lexicon_hit.family} phrase"
                    )[:240],
                    pattern_id=lexicon_hit.pattern_id,
                )
            )
        else:
            # Hidden channel without lexicon hit: still suspicious at strict.
            findings.append(
                Finding(
                    category="hidden_text",
                    channel=channel.channel,
                    severity="low",
                    span=(channel.start, channel.end),
                    evidence=f"{channel.channel} span without visible counterpart"[
                        :240
                    ],
                )
            )
    return findings


def _detect_lexicon(
    canonical: CanonicalForm,
) -> List[Finding]:
    findings: List[Finding] = []
    visible_hits = {
        (entry.pattern_id, start, end): (entry, start, end, snippet)
        for entry, start, end, snippet in _lexicon_hits(canonical.visible)
    }
    skeleton_hits = _lexicon_hits(canonical.skeleton)

    for entry, start, end, snippet in visible_hits.values():
        orig_start, orig_end = _map_visible_span(canonical, start, end)
        severity: Severity = entry.severity
        downgraded = _in_quote_with_discourse(canonical.original, orig_start, orig_end)
        if downgraded:
            severity = _downgrade_severity(severity)
        findings.append(
            Finding(
                category="instruction_override",
                channel="visible",
                severity=severity,
                span=(orig_start, orig_end),
                evidence=snippet[:240],
                pattern_id=entry.pattern_id,
                downgraded=downgraded,
            )
        )

    for entry, start, end, snippet in skeleton_hits:
        key = (entry.pattern_id, start, end)
        if key in visible_hits:
            continue
        # Skeleton-only match => confusable evasion of a known phrase.
        orig_start, orig_end = _map_visible_span(canonical, start, end)
        findings.append(
            Finding(
                category="confusables+instruction_override",
                channel="confusables_skeleton",
                severity="high" if entry.severity != "critical" else "critical",
                span=(orig_start, orig_end),
                evidence=f"skeleton match for {entry.pattern_id}: {snippet[:120]}",
                pattern_id=entry.pattern_id,
            )
        )
        findings.append(
            Finding(
                category="confusables",
                channel="confusables_skeleton",
                severity="medium",
                span=(orig_start, orig_end),
                evidence="homoglyph substitution collapsed by confusables skeleton",
            )
        )
    return findings


def _detect_leetspeak(canonical: CanonicalForm) -> List[Finding]:
    """Detect leetspeak digit/symbol substitution on known instruction phrases."""
    findings: List[Finding] = []
    visible = canonical.visible
    leet_chars: List[str] = []
    modified = False
    for ch in visible:
        if ch in LEET_MAP:
            leet_chars.append(LEET_MAP[ch])
            modified = True
        else:
            leet_chars.append(ch)

    if not modified:
        return findings

    leet_text = "".join(leet_chars)
    visible_hit_ids = {entry.pattern_id for entry, _, _, _ in _lexicon_hits(visible)}
    for entry, start, end, snippet in _lexicon_hits(leet_text):
        if entry.pattern_id in visible_hit_ids:
            continue
        orig_start, orig_end = _map_visible_span(canonical, start, end)
        findings.append(
            Finding(
                category="leetspeak+instruction_override",
                channel="leetspeak",
                severity="high" if entry.severity != "critical" else "critical",
                span=(orig_start, orig_end),
                evidence=f"leetspeak substitution for {entry.pattern_id}: '{snippet[:120]}'",
                pattern_id=entry.pattern_id,
            )
        )
    return findings


def _detect_typoglycemia(canonical: CanonicalForm) -> List[Finding]:
    """Detect scrambled/typoglycemia keyword mutations (e.g. ignroe -> ignore)."""
    findings: List[Finding] = []
    visible = canonical.visible
    tokens = re.split(r"(\W+)", visible)
    replaced_tokens: List[str] = []
    has_scramble = False
    scramble_notes: List[str] = []

    for token in tokens:
        word = token.lower()
        if len(word) >= 5 and word.isalpha() and word not in HIGH_SIGNAL_KEYWORDS:
            first_ch = word[0]
            last_ch = word[-1]
            middle_sorted = sorted(word[1:-1])
            matched_kw = None
            for kw in HIGH_SIGNAL_KEYWORDS:
                if (
                    len(kw) == len(word)
                    and kw[0] == first_ch
                    and kw[-1] == last_ch
                    and sorted(kw[1:-1]) == middle_sorted
                ):
                    matched_kw = kw
                    break
            if matched_kw:
                replaced_tokens.append(matched_kw)
                has_scramble = True
                scramble_notes.append(f"{token}->{matched_kw}")
                continue
        replaced_tokens.append(token)

    if not has_scramble:
        return findings

    unscrambled = "".join(replaced_tokens)
    visible_hit_ids = {entry.pattern_id for entry, _, _, _ in _lexicon_hits(visible)}
    for entry, start, end, snippet in _lexicon_hits(unscrambled):
        if entry.pattern_id in visible_hit_ids:
            continue
        orig_start, orig_end = _map_visible_span(canonical, start, end)
        findings.append(
            Finding(
                category="scramble+instruction_override",
                channel="typoglycemia",
                severity="high" if entry.severity != "critical" else "critical",
                span=(orig_start, orig_end),
                evidence=f"typoglycemia keyword scramble ({', '.join(scramble_notes[:3])}): '{snippet[:120]}'",
                pattern_id=entry.pattern_id,
            )
        )
    return findings


def _detect_mixed_script(canonical: CanonicalForm) -> List[Finding]:
    """Warn when Latin and lookalike Cyrillic/Greek scripts mix within a single word token."""
    findings: List[Finding] = []
    confusables = _load_confusables()
    for match in re.finditer(r"\b\w{3,}\b", canonical.original):
        word = match.group(0)
        has_latin = False
        has_lookalike = False
        for ch in word:
            try:
                name = unicodedata.name(ch, "")
            except Exception:
                continue
            if "LATIN" in name:
                has_latin = True
            elif "CYRILLIC" in name or "GREEK" in name:
                has_lookalike = True
        if has_latin and has_lookalike:
            mapped_word = "".join(confusables.get(ch, ch) for ch in word.lower())
            is_instruction = any(kw in mapped_word for kw in HIGH_SIGNAL_KEYWORDS)
            findings.append(
                Finding(
                    category=(
                        "mixed_script+instruction_override"
                        if is_instruction
                        else "mixed_script"
                    ),
                    channel="unicode_mixed_script",
                    severity="high" if is_instruction else "medium",
                    span=(match.start(), match.end()),
                    evidence=f"mixed Latin and Cyrillic/Greek scripts in token: {word[:60]!r}",
                )
            )
    return findings


def _detect_exfiltration_channels(canonical: CanonicalForm) -> List[Finding]:
    """Detect suspicious Markdown/HTML image URLs designed to exfiltrate prompt context."""
    findings: List[Finding] = []
    text = canonical.original

    for match in MARKDOWN_IMAGE_RE.finditer(text):
        url = match.group("url")
        if _is_suspicious_exfil_url(url):
            findings.append(
                Finding(
                    category="exfiltration_channel",
                    channel="markdown_image_exfil",
                    severity="high",
                    span=(match.start(), match.end()),
                    evidence=f"markdown image exfiltration url query payload: {url[:120]!r}",
                )
            )

    for match in HTML_IMAGE_RE.finditer(text):
        url = match.group("url")
        if _is_suspicious_exfil_url(url):
            findings.append(
                Finding(
                    category="exfiltration_channel",
                    channel="html_image_exfil",
                    severity="high",
                    span=(match.start(), match.end()),
                    evidence=f"html image exfiltration url query payload: {url[:120]!r}",
                )
            )
    return findings


def _is_suspicious_exfil_url(url: str) -> bool:
    if not url:
        return False
    lower = url.lower()
    if re.search(
        r"(?i)[?&](?:q|leak|data|exfil|token|prompt|key|secret|system_prompt)=(?:[A-Za-z0-9+/=_%-]{8,})",
        lower,
    ):
        return True
    if lower.startswith("data:text/") and ("system" in lower or "prompt" in lower):
        return True
    return False


def _try_decode_layer(token: str) -> Tuple[Optional[str], Optional[str]]:
    """Decode a layer; returns (decoded_text, format_name)."""
    # Base64
    if re.fullmatch(r"[A-Za-z0-9+/]{16,}={0,2}", token):
        try:
            padded = token + "=" * ((4 - len(token) % 4) % 4)
            decoded = base64.b64decode(padded, validate=False)
            if 0 < len(decoded) <= MAX_DECODE_BYTES:
                text = decoded.decode("utf-8")
                if text.isprintable() or any(ch.isspace() for ch in text):
                    return text, "base64"
        except (binascii.Error, UnicodeDecodeError, ValueError):
            pass

    # Hex
    hex_token = token[2:] if token.lower().startswith("0x") else token
    if re.fullmatch(r"[0-9a-fA-F]{24,}", hex_token) and len(hex_token) % 2 == 0:
        try:
            decoded = bytes.fromhex(hex_token)
            if 0 < len(decoded) <= MAX_DECODE_BYTES:
                return decoded.decode("utf-8"), "hex"
        except (ValueError, UnicodeDecodeError):
            pass

    # URL-encoding (require multiple escapes)
    if "%" in token and token.count("%") >= 3:
        try:
            decoded = unquote(token)
            if decoded != token and len(decoded) <= MAX_DECODE_BYTES:
                return decoded, "percent"
        except Exception:
            pass

    # ROT13 check for token
    if len(token) >= 20 and token.replace(" ", "").isalpha():
        try:
            rot13_text = codecs.decode(token, "rot_13")
            if rot13_text != token:
                # Only treat as rot13 layer if it matches patterns or words
                return rot13_text, "rot13"
        except Exception:
            pass

    return None, None


def _scan_decoded_for_lexicon(text: str) -> Optional[PatternEntry]:
    fold = unicodedata.normalize("NFKC", text).casefold()
    skeleton = _to_skeleton(fold, _load_confusables())
    for entry in _load_patterns():
        if entry.regex.search(fold) or entry.regex.search(skeleton):
            return entry
    return None


def _detect_encoded_payload(canonical: CanonicalForm) -> List[Finding]:
    findings: List[Finding] = []
    candidates = list(
        re.finditer(r"\b(?:0x)?[A-Za-z0-9+/_%-]{24,}={0,2}\b", canonical.original)
    )[:MAX_DECODE_CANDIDATES]

    for match in candidates:
        token = match.group(0)
        current = token
        layers = 0
        decode_chain: List[str] = []
        decoded_text = None
        while layers < MAX_DECODE_DEPTH:
            decoded, layer_format = _try_decode_layer(current)
            if decoded is None or layer_format is None:
                break
            layers += 1
            decode_chain.append(layer_format)
            decoded_text = decoded
            current = decoded.strip()
            hit = _scan_decoded_for_lexicon(decoded)
            if hit is not None:
                preview = (
                    f"[{len(decoded)} chars: {decoded[:40]!r}...]"
                    if len(decoded) > 40
                    else repr(decoded)
                )
                findings.append(
                    Finding(
                        category="encoded_payload+instruction_override",
                        channel=(
                            decode_chain[-1] if len(decode_chain) == 1 else "encoded"
                        ),
                        severity="high" if hit.severity != "critical" else "critical",
                        span=(match.start(), match.end()),
                        evidence=f"decode_chain={'→'.join(decode_chain)}; pattern={hit.pattern_id}",
                        pattern_id=hit.pattern_id,
                        decoded_layers=layers,
                        decode_chain=decode_chain,
                        decoded_preview=preview,
                    )
                )
                break
        _ = decoded_text

    # Also scan for standalone ROT13 sentence/paragraphs
    rot_candidates = re.finditer(r"\b[A-Za-z ]{24,}\b", canonical.original)
    for match in list(rot_candidates)[:10]:
        token = match.group(0).strip()
        if len(token) < 24:
            continue
        try:
            rot_decoded = codecs.decode(token, "rot_13")
            if rot_decoded != token:
                hit = _scan_decoded_for_lexicon(rot_decoded)
                if hit is not None:
                    findings.append(
                        Finding(
                            category="encoded_payload+instruction_override",
                            channel="rot13",
                            severity=(
                                "high" if hit.severity != "critical" else "critical"
                            ),
                            span=(match.start(), match.end()),
                            evidence=f"rot13 decoded match for {hit.pattern_id}",
                            pattern_id=hit.pattern_id,
                            decoded_layers=1,
                            decode_chain=["rot13"],
                            decoded_preview=repr(rot_decoded[:60]),
                        )
                    )
        except Exception:
            pass

    return findings


def _detect_context_mismatch(
    canonical: CanonicalForm, findings: Sequence[Finding]
) -> List[Finding]:
    extra: List[Finding] = []
    # Imperative + second-person density heuristic on short data-like blobs.
    text = canonical.visible
    if len(text) < 20 or len(text) > 4000:
        return extra
    second_person = len(re.findall(r"\b(you|your|yourself)\b", text))
    imperatives = len(
        re.findall(
            r"\b(ignore|disregard|forget|override|reveal|print|send|wire|call)\b",
            text,
        )
    )
    has_hidden_instruction = any(
        f.category.startswith("hidden_text") and f.pattern_id for f in findings
    )
    if second_person >= 2 and imperatives >= 2 and not has_hidden_instruction:
        # Only emit when a visible instruction_override already exists.
        if any(f.category == "instruction_override" for f in findings):
            extra.append(
                Finding(
                    category="context_mismatch",
                    channel="visible",
                    severity="medium",
                    span=(0, min(len(canonical.original), 1)),
                    evidence="imperative + second-person density in data-like content",
                )
            )
    return extra


def _max_severity(findings: Sequence[Finding]) -> Severity:
    if not findings:
        return "low"
    return max(findings, key=lambda f: SEVERITY_RANK[f.severity]).severity


def _risk_level_for(findings: Sequence[Finding], is_safe: bool) -> RiskLevel:
    if is_safe or not findings:
        return "none"
    top = _max_severity(findings)
    return top  # type: ignore[return-value]


def _independent_finding_count(findings: Sequence[Finding]) -> int:
    keys = set()
    for finding in findings:
        keys.add((finding.category.split("+")[0], finding.channel, finding.pattern_id))
    return len(keys)


def _is_critical_exfil(finding: Finding) -> bool:
    """True for critical-severity exfiltration hits (pattern family or category)."""
    if finding.severity != "critical":
        return False
    pattern_id = finding.pattern_id or ""
    if pattern_id.startswith("PI-EXFIL"):
        return True
    return "exfiltration" in finding.category


def _verdict(findings: Sequence[Finding], sensitivity: SensitivityLevel) -> bool:
    """Return True when content is considered safe."""
    if not findings:
        return True

    # At strict: even downgraded findings trigger unsafe if medium or above.
    if sensitivity == "strict":
        active = [f for f in findings if not (f.downgraded and f.severity == "low")]
        if not active:
            return True
        critical_hit = any(f.severity == "critical" for f in active)
        high_hit = any(f.severity == "high" for f in active)
        hidden_hit = any(
            f.channel in _HIDDEN_CHANNELS
            or f.category.startswith(
                (
                    "hidden_text",
                    "encoded_payload",
                    "confusables+",
                    "mixed_script",
                    "leetspeak+",
                    "scramble+",
                )
            )
            or f.category
            in {
                "unicode_evasion",
                "leetspeak+instruction_override",
                "scramble+instruction_override",
                "exfiltration_channel",
                "mixed_script",
                "mixed_script+instruction_override",
            }
            for f in active
        )
        return not (
            critical_hit
            or high_hit
            or hidden_hit
            or any(f.severity == "medium" and not f.downgraded for f in active)
        )

    # For balanced and lenient: active findings exclude those safely downgraded via discourse markers.
    active = [f for f in findings if not f.downgraded]
    if not active:
        return True

    # Floor: a lone non-downgraded critical exfiltration finding fails at balanced and lenient.
    if any(_is_critical_exfil(f) for f in active):
        return False

    hidden_hit = any(
        f.channel in _HIDDEN_CHANNELS
        or f.category.startswith(
            (
                "hidden_text",
                "encoded_payload",
                "confusables+",
                "mixed_script",
                "leetspeak+",
                "scramble+",
            )
        )
        or f.category
        in {
            "unicode_evasion",
            "leetspeak+instruction_override",
            "scramble+instruction_override",
            "exfiltration_channel",
            "mixed_script",
            "mixed_script+instruction_override",
        }
        for f in active
    )
    critical_hit = any(f.severity == "critical" for f in active)
    high_hit = any(f.severity == "high" for f in active)
    independent = _independent_finding_count(active)

    if sensitivity == "lenient":
        hidden_with_instruction = any(
            f.category.startswith(
                (
                    "hidden_text+",
                    "encoded_payload+",
                    "confusables+",
                    "leetspeak+",
                    "scramble+",
                )
            )
            for f in active
        )
        return not (hidden_with_instruction or independent >= 3)

    # balanced (default):
    return not (hidden_hit or independent >= 2 or critical_hit)


def _primary_message(findings: Sequence[Finding]) -> str:
    if not findings:
        return ""
    ordered = sorted(
        findings,
        key=lambda f: (-SEVERITY_RANK[f.severity], f.span[0]),
    )
    top = ordered[0]
    family = top.category.split("+")[0]
    if "hidden_text" in top.category:
        return FAMILY_MESSAGE["hidden_text"]
    if "encoded_payload" in top.category:
        return FAMILY_MESSAGE["encoded_payload"]
    if "confusables" in top.category and "instruction_override" in top.category:
        return FAMILY_MESSAGE["confusables"]
    if "leetspeak" in top.category:
        return FAMILY_MESSAGE["leetspeak"]
    if "scramble" in top.category:
        return FAMILY_MESSAGE["scramble"]
    if "exfiltration_channel" in top.category:
        return FAMILY_MESSAGE["exfiltration_channel"]
    if "resource_limit" in top.category:
        return FAMILY_MESSAGE["resource_limit"]
    if top.pattern_id:
        for entry in _load_patterns():
            if entry.pattern_id == top.pattern_id:
                return FAMILY_MESSAGE.get(
                    entry.family, FAMILY_MESSAGE["instruction_negation"]
                )
    return FAMILY_MESSAGE.get(family, "Potential prompt injection detected.")


def _merge_spans(spans: Sequence[Tuple[int, int]]) -> List[Tuple[int, int]]:
    if not spans:
        return []
    ordered = sorted(spans, key=lambda item: item[0])
    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def _sanitize_text(original: str, findings: Sequence[Finding]) -> Tuple[str, int, int]:
    """Strip hidden channels and threat spans. Returns (cleaned_text, removed_span_count, length_delta)."""
    spans = [(f.span[0], f.span[1]) for f in findings if f.span[1] > f.span[0]]
    spans = _merge_spans(spans)
    if not spans:
        return original, 0, 0

    parts: List[str] = []
    cursor = 0
    for start, end in spans:
        parts.append(original[cursor:start])
        cursor = end
    parts.append(original[cursor:])
    cleaned = "".join(parts)
    cleaned = HTML_COMMENT_RE.sub("", cleaned)
    cleaned = MARKDOWN_COMMENT_RE.sub("", cleaned)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    if original.endswith(" ") and cleaned and not cleaned.endswith(" "):
        cleaned += " "

    removed_span_count = len(spans)
    delta = len(original) - len(cleaned)
    return cleaned, removed_span_count, delta


def _finding_to_dict(finding: Finding) -> Dict[str, object]:
    payload: Dict[str, object] = {
        "category": finding.category,
        "channel": finding.channel,
        "severity": finding.severity,
        "span": [finding.span[0], finding.span[1]],
        "evidence": finding.evidence,
    }
    if finding.pattern_id is not None:
        payload["pattern_id"] = finding.pattern_id
    if finding.decoded_layers is not None:
        payload["decoded_layers"] = finding.decoded_layers
    if finding.decode_chain is not None:
        payload["decode_chain"] = finding.decode_chain
    if finding.decoded_preview is not None:
        payload["decoded_preview"] = finding.decoded_preview
    if finding.downgraded:
        payload["downgraded"] = True
    return payload


def scan_source_text(
    source_text: str,
    *,
    sensitivity: SensitivityLevel = "balanced",
    input_mode: str = "auto",
) -> ScanResult:
    if not source_text:
        return ScanResult(
            is_safe=True,
            risk_level="none",
            detected_threat=None,
            findings=[],
            sanitized_text="",
            offline=True,
            sensitivity=sensitivity,
            policy_action="allow",
            removed_span_count=0,
            sanitized_length_delta=0,
        )

    # DoS / Resource soft caps
    if len(source_text) > MAX_SOURCE_TEXT_CHARS:
        finding = Finding(
            category="resource_limit",
            channel="input_size",
            severity="high",
            span=(0, len(source_text)),
            evidence=f"Input size {len(source_text)} exceeds maximum allowed {MAX_SOURCE_TEXT_CHARS} characters.",
        )
        return ScanResult(
            is_safe=False,
            risk_level="high",
            detected_threat=FAMILY_MESSAGE["resource_limit"],
            findings=[_finding_to_dict(finding)],
            sanitized_text="",
            offline=True,
            sensitivity=sensitivity,
            policy_action="block",
            removed_span_count=1,
            sanitized_length_delta=len(source_text),
        )

    canonical = canonicalize(source_text, input_mode=input_mode)
    findings: List[Finding] = []
    findings.extend(_detect_unicode_evasion(canonical))
    findings.extend(_detect_hidden_text(canonical))
    findings.extend(_detect_lexicon(canonical))
    findings.extend(_detect_leetspeak(canonical))
    findings.extend(_detect_typoglycemia(canonical))
    findings.extend(_detect_mixed_script(canonical))
    findings.extend(_detect_exfiltration_channels(canonical))
    findings.extend(_detect_encoded_payload(canonical))
    findings.extend(_detect_context_mismatch(canonical, findings))

    # Drop bare low-severity hidden shells at non-strict sensitivity when
    # no instruction content was found inside them.
    if sensitivity != "strict":
        findings = [
            f
            for f in findings
            if not (f.category == "hidden_text" and f.severity == "low")
        ]

    deduped: List[Finding] = []
    seen = set()
    for finding in sorted(findings, key=lambda item: (item.span[0], -item.span[1])):
        key = (
            finding.category,
            finding.channel,
            finding.span,
            finding.pattern_id,
            finding.evidence[:80],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)

    is_safe = _verdict(deduped, sensitivity)
    risk_level = _risk_level_for(deduped, is_safe)
    detected = None if is_safe and not deduped else _primary_message(deduped)

    if is_safe:
        detected = None
        sanitized = source_text
        removed_count = 0
        delta = 0
        policy_action: PolicyAction = "flag" if deduped else "allow"
    else:
        sanitized, removed_count, delta = _sanitize_text(source_text, deduped)
        policy_action = "block"

    return ScanResult(
        is_safe=is_safe,
        risk_level=risk_level if not is_safe else "none",
        detected_threat=detected,
        findings=[_finding_to_dict(f) for f in deduped],
        sanitized_text=sanitized,
        offline=True,
        sensitivity=sensitivity,
        policy_action=policy_action,
        removed_span_count=removed_count,
        sanitized_length_delta=delta,
    )


def load_pattern_catalog() -> Dict[str, object]:
    """Expose bundled KB metadata for tests and documentation."""
    patterns = _load_patterns()
    return {
        "pattern_ids": [p.pattern_id for p in patterns],
        "families": sorted({p.family for p in patterns}),
        "confusable_count": len(_load_confusables()),
        "hidden_html_styles": list(HIDDEN_HTML_STYLE_PATTERNS),
        "version": "0.2.0",
    }

"""Deterministic deceptive UI surface scanner — local analysis, optional URL fetch."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
from dataclasses import dataclass
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

SensitivityLevel = Literal["strict", "balanced", "lenient"]
RiskLevel = Literal["none", "low", "medium", "high", "critical"]
StatusLevel = Literal["ok", "caution", "warning", "blocked"]
SurfaceIntegrity = Literal["ok", "degraded", "compromised"]

_KB_DIR = Path(__file__).resolve().parent / "kb"
MAX_HTML_BYTES = 2_000_000
FETCH_TIMEOUT = 15
SNIPPET_MAX = 160

HIDDEN_STYLE_PATTERNS = (
    re.compile(r"display\s*:\s*none", re.I),
    re.compile(r"visibility\s*:\s*hidden", re.I),
    re.compile(r"opacity\s*:\s*0\b", re.I),
    re.compile(r"font-size\s*:\s*0\b", re.I),
    re.compile(r"(?:^|[;\s])height\s*:\s*0\b", re.I),
    re.compile(r"(?:^|[;\s])width\s*:\s*0\b", re.I),
    re.compile(r"text-indent\s*:\s*-\d", re.I),
    re.compile(r"position\s*:\s*absolute.{0,60}(?:left|top)\s*:\s*-\d", re.I),
)

WHITE_COLOR = re.compile(
    r"color\s*:\s*(?:#fff(?:fff)?|white|rgb\(\s*255\s*,\s*255\s*,\s*255\s*\))",
    re.I,
)
WHITE_BG = re.compile(
    r"background(?:-color)?\s*:\s*(?:#fff(?:fff)?|white|rgb\(\s*255\s*,\s*255\s*,\s*255\s*\))",
    re.I,
)

CHECKOUT_CONTEXT = re.compile(
    r"(?i)\b(checkout|payment|subscribe|billing|credit\s+card|place\s+order|"
    r"complete\s+purchase|cart)\b"
)

IMPERATIVE_LEXICON = re.compile(
    r"(?i)\b(ignore\s+(all\s+)?(previous|prior)\s+instructions|"
    r"disregard\s+(the\s+)?(above|system)|click\s+accept|do\s+not\s+ask|"
    r"you\s+must\s+click|override\s+safety)\b"
)

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


@dataclass
class RawSignal:
    signal_type: str
    subtype: str
    severity: RiskLevel
    selector: str
    snippet: str
    channels: List[str]
    evidence: Dict[str, Any]
    zone: str = "general"


@dataclass
class ScanResult:
    status: StatusLevel
    trust_score: int
    surface_integrity: SurfaceIntegrity
    is_safe: bool
    risk_level: RiskLevel
    detected_threat: str
    findings: List[Dict[str, Any]]
    agent_guidance: Dict[str, Any]
    sanitized_excerpt: str
    fetch_status: str
    offline: bool
    sensitivity: str


def _load_lexicon() -> Dict[str, List[str]]:
    path = _KB_DIR / "deception_lexicon.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {
        "confirm_shaming": [],
        "urgency": [],
        "hidden_fee": [],
    }


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text or "")).strip()


def _element_selector(element: Tag) -> str:
    if element.get("id"):
        return f"{element.name}#{element['id']}"
    classes = element.get("class") or []
    if classes:
        return f"{element.name}.{classes[0]}"
    return element.name or "node"


def _style_hidden(style: str) -> bool:
    if not style:
        return False
    return any(pattern.search(style) for pattern in HIDDEN_STYLE_PATTERNS)


def _is_hidden_element(element: Tag) -> bool:
    if element.name in {"script", "style", "noscript", "template"}:
        return True
    if element.has_attr("hidden"):
        return True
    aria_hidden = str(element.get("aria-hidden", "")).lower()
    if aria_hidden == "true":
        return True
    style = str(element.get("style", ""))
    if _style_hidden(style):
        return True
    return False


def _element_zone(element: Tag) -> str:
    context = " ".join(
        _normalize_space(str(node))[:200]
        for node in element.parents
        if isinstance(node, Tag)
    )
    if CHECKOUT_CONTEXT.search(context):
        return "checkout"
    return "general"


def _direct_text(element: Tag) -> str:
    parts: List[str] = []
    for child in element.children:
        if isinstance(child, NavigableString):
            parts.append(str(child))
    return _normalize_space(" ".join(parts))


def _is_safe_public_url(url: str) -> Tuple[bool, str]:
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return False, "Only http and https URLs are allowed."
    hostname = parsed.hostname
    if not hostname:
        return False, "URL must include a hostname."
    lowered = hostname.lower()
    if lowered in {"localhost", "127.0.0.1", "::1"} or lowered.endswith(".local"):
        return False, "Local or loopback hosts are blocked."
    try:
        for info in socket.getaddrinfo(hostname, None):
            ip = ipaddress.ip_address(info[4][0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
            ):
                return False, "Private or non-public host addresses are blocked."
    except socket.gaierror:
        return False, "Hostname could not be resolved."
    return True, ""


def fetch_url_html(url: str) -> Tuple[str, str]:
    ok, reason = _is_safe_public_url(url)
    if not ok:
        return "", reason
    response = requests.get(
        url,
        timeout=FETCH_TIMEOUT,
        headers={"User-Agent": "Skillware-DeceptiveUIGuard/1.0"},
        allow_redirects=True,
    )
    response.raise_for_status()
    content = response.content[:MAX_HTML_BYTES]
    return content.decode(response.encoding or "utf-8", errors="replace"), "ok"


def _contrast_signal(element: Tag) -> Optional[RawSignal]:
    style = str(element.get("style", ""))
    if WHITE_COLOR.search(style) and WHITE_BG.search(style):
        text = _direct_text(element)
        if len(text) < 4:
            return None
        return RawSignal(
            signal_type="low_contrast",
            subtype="white_on_white",
            severity="low",
            selector=_element_selector(element),
            snippet=text[:SNIPPET_MAX],
            channels=["structural", "visual_style"],
            evidence={"style": style[:200]},
            zone=_element_zone(element),
        )
    return None


def _mislabeled_cta_signal(element: Tag) -> Optional[RawSignal]:
    if element.name not in {"a", "button", "input"}:
        return None
    visible = _direct_text(element)
    aria = _normalize_space(str(element.get("aria-label", "")))
    title = _normalize_space(str(element.get("title", "")))
    value = _normalize_space(str(element.get("value", "")))
    label_text = visible or value
    alt_label = aria or title
    if not label_text or not alt_label:
        return None
    if label_text.lower() == alt_label.lower():
        return None
    # Different accessible name vs visible label on an interactive control.
    return RawSignal(
        signal_type="mislabeled_cta",
        subtype="label_aria_mismatch",
        severity="medium",
        selector=_element_selector(element),
        snippet=f"visible={label_text!r} aria/title={alt_label!r}"[:SNIPPET_MAX],
        channels=["structural", "accessibility"],
        evidence={"visible": label_text, "accessible_name": alt_label},
        zone=_element_zone(element),
    )


def _lexicon_hits(text: str, lexicon: Dict[str, List[str]]) -> List[str]:
    lowered = text.lower()
    hits: List[str] = []
    for category, phrases in lexicon.items():
        for phrase in phrases:
            if phrase.lower() in lowered:
                hits.append(category)
                break
    return hits


def _channel_mismatch_signal(
    element: Tag, visible_aggregate: str, lexicon: Dict[str, List[str]]
) -> Optional[RawSignal]:
    if not _is_hidden_element(element):
        return None
    hidden_text = _normalize_space(element.get_text(" ", strip=True))
    if len(hidden_text) < 8:
        return None
    if hidden_text.lower() in visible_aggregate.lower():
        return None
    lex_hits = _lexicon_hits(hidden_text, lexicon)
    imperative = bool(IMPERATIVE_LEXICON.search(hidden_text))
    if not lex_hits and not imperative:
        return RawSignal(
            signal_type="channel_mismatch",
            subtype="hidden_non_visible_text",
            severity="low",
            selector=_element_selector(element),
            snippet=hidden_text[:SNIPPET_MAX],
            channels=["dom_text", "hidden_surface"],
            evidence={"hidden_only": True},
            zone=_element_zone(element),
        )
    severity: RiskLevel = "high"
    if imperative and _element_zone(element) == "checkout":
        severity = "critical"
    subtype = "hidden_imperative_text" if imperative else "hidden_deception_lexicon"
    return RawSignal(
        signal_type="channel_mismatch",
        subtype=subtype,
        severity=severity,
        selector=_element_selector(element),
        snippet=hidden_text[:SNIPPET_MAX],
        channels=["dom_text", "hidden_surface"],
        evidence={"lexicon_hits": lex_hits, "imperative": imperative},
        zone=_element_zone(element),
    )


def _lexical_signal(element: Tag, lexicon: Dict[str, List[str]]) -> List[RawSignal]:
    text = _normalize_space(element.get_text(" ", strip=True))
    if len(text) < 6:
        return []
    hits = _lexicon_hits(text, lexicon)
    if not hits:
        return []
    hidden = _is_hidden_element(element)
    severity: RiskLevel = "medium" if hidden else "low"
    if "hidden_fee" in hits and _element_zone(element) == "checkout":
        severity = "high"
    return [
        RawSignal(
            signal_type="deception_lexicon",
            subtype=hits[0],
            severity=severity,
            selector=_element_selector(element),
            snippet=text[:SNIPPET_MAX],
            channels=["textual"],
            evidence={"categories": hits, "hidden": hidden},
            zone=_element_zone(element),
        )
    ]


def _corroborate(
    signals: List[RawSignal], sensitivity: SensitivityLevel
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for signal in signals:
        corroborated_by: List[str] = []
        publish = False
        confidence = 0.55

        if signal.signal_type == "channel_mismatch":
            if signal.subtype in {"hidden_imperative_text", "hidden_deception_lexicon"}:
                publish = True
                confidence = 0.9 if signal.subtype == "hidden_imperative_text" else 0.82
                corroborated_by = ["channel_mismatch", "textual"]
            elif sensitivity == "lenient":
                continue
            elif sensitivity == "balanced" and signal.zone == "checkout":
                publish = True
                confidence = 0.7
                corroborated_by = ["channel_mismatch", "checkout_zone"]
            elif sensitivity == "strict":
                publish = True
                confidence = 0.65
                corroborated_by = ["channel_mismatch"]

        elif signal.signal_type == "mislabeled_cta":
            publish = True
            confidence = 0.78
            corroborated_by = ["accessibility", "structural"]

        elif signal.signal_type == "deception_lexicon":
            if signal.severity in {"high", "critical"}:
                publish = True
                confidence = 0.8
                corroborated_by = ["textual", signal.zone]
            elif signal.subtype == "hidden_fee" and signal.zone == "checkout":
                publish = True
                confidence = 0.75
                corroborated_by = ["textual", "checkout_zone"]
            elif sensitivity == "strict":
                publish = True
                confidence = 0.6
                corroborated_by = ["textual"]

        elif signal.signal_type == "low_contrast":
            if sensitivity == "strict" and signal.zone == "checkout":
                publish = True
                confidence = 0.55
                corroborated_by = ["visual_style", "checkout_zone"]
            else:
                continue

        if not publish:
            continue

        findings.append(
            {
                "type": signal.signal_type,
                "subtype": signal.subtype,
                "severity": signal.severity,
                "confidence": round(confidence, 2),
                "channels": signal.channels,
                "selector": signal.selector,
                "snippet": signal.snippet,
                "evidence": signal.evidence,
                "corroborated_by": corroborated_by,
                "zone": signal.zone,
            }
        )
    return findings


def _visible_excerpt(soup: BeautifulSoup) -> str:
    parts: List[str] = []
    for element in soup.find_all(True):
        if _is_hidden_element(element):
            continue
        text = _direct_text(element)
        if text:
            parts.append(text)
    excerpt = _normalize_space(" ".join(parts))
    return excerpt[:4000]


def _aggregate_risk(
    findings: List[Dict[str, Any]],
) -> Tuple[RiskLevel, int, SurfaceIntegrity]:
    if not findings:
        return "none", 100, "ok"
    max_severity = max(SEVERITY_RANK[str(item["severity"])] for item in findings)
    inverse = {value: key for key, value in SEVERITY_RANK.items()}
    risk: RiskLevel = inverse[max_severity]  # type: ignore[assignment]
    penalty = sum(SEVERITY_RANK[str(item["severity"])] * 8 for item in findings)
    trust = max(0, min(100, 100 - penalty))
    integrity: SurfaceIntegrity = "ok"
    if trust < 80:
        integrity = "degraded"
    if trust < 45 or max_severity >= SEVERITY_RANK["critical"]:
        integrity = "compromised"
    return risk, trust, integrity


def _status_for(
    trust: int, risk: RiskLevel, sensitivity: SensitivityLevel
) -> StatusLevel:
    if risk == "critical":
        return "blocked"
    if trust < 40 or risk == "high":
        return "warning"
    if trust < 70 or risk == "medium":
        return "caution"
    if sensitivity == "strict" and trust < 85:
        return "caution"
    return "ok"


def _build_guidance(
    findings: List[Dict[str, Any]], intended_action: str
) -> Dict[str, Any]:
    selectors: Set[str] = set()
    verify_payment = False
    for item in findings:
        selectors.add(str(item.get("selector", "")))
        if item.get("zone") == "checkout" or item.get("subtype") == "hidden_fee":
            verify_payment = True
        if item.get("type") == "mislabeled_cta":
            selectors.add(str(item.get("selector", "")))

    summary_parts = []
    if any(f.get("type") == "channel_mismatch" for f in findings):
        summary_parts.append(
            "Hidden text is present that does not appear in the visible surface."
        )
    if any(f.get("type") == "mislabeled_cta" for f in findings):
        summary_parts.append(
            "Interactive controls expose mismatched visible and accessible labels."
        )
    if any(f.get("subtype") == "hidden_fee" for f in findings):
        summary_parts.append("Copy suggests fees may appear late in checkout.")

    action_lower = (intended_action or "").lower()
    if (
        "pay" in action_lower
        or "checkout" in action_lower
        or "subscribe" in action_lower
    ):
        verify_payment = True

    return {
        "do_not_click": sorted(s for s in selectors if s),
        "verify_before_payment": verify_payment,
        "summary": " ".join(summary_parts)
        or "No deceptive UI signals crossed the publish threshold.",
        "skill_chain_hint": (
            "Optionally run security/prompt_injection_firewall on sanitized_excerpt "
            "before feeding page text to the host LLM."
        ),
    }


def scan_surface(
    *,
    html_content: str = "",
    url: str = "",
    sensitivity: SensitivityLevel = "balanced",
    intended_action: str = "",
) -> ScanResult:
    fetch_status = "skipped"
    offline = True
    html = html_content or ""

    if url and not html:
        offline = False
        try:
            html, fetch_status = fetch_url_html(url)
        except requests.RequestException as exc:
            return ScanResult(
                status="blocked",
                trust_score=0,
                surface_integrity="compromised",
                is_safe=False,
                risk_level="high",
                detected_threat=f"Fetch failed: {exc}",
                findings=[],
                agent_guidance={
                    "do_not_click": [],
                    "verify_before_payment": True,
                    "summary": "Page could not be fetched safely.",
                    "skill_chain_hint": "",
                },
                sanitized_excerpt="",
                fetch_status=f"error: {exc}",
                offline=False,
                sensitivity=sensitivity,
            )

    if not html.strip():
        return ScanResult(
            status="blocked",
            trust_score=0,
            surface_integrity="compromised",
            is_safe=False,
            risk_level="medium",
            detected_threat="No HTML content supplied.",
            findings=[],
            agent_guidance={
                "do_not_click": [],
                "verify_before_payment": False,
                "summary": "Provide html_content or a public url.",
                "skill_chain_hint": "",
            },
            sanitized_excerpt="",
            fetch_status=fetch_status,
            offline=offline,
            sensitivity=sensitivity,
        )

    soup = BeautifulSoup(html, "html.parser")
    lexicon = _load_lexicon()
    visible_aggregate = _visible_excerpt(soup)
    signals: List[RawSignal] = []

    for element in soup.find_all(True):
        if not isinstance(element, Tag):
            continue
        contrast = _contrast_signal(element)
        if contrast:
            signals.append(contrast)
        mislabeled = _mislabeled_cta_signal(element)
        if mislabeled:
            signals.append(mislabeled)
        mismatch = _channel_mismatch_signal(element, visible_aggregate, lexicon)
        if mismatch:
            signals.append(mismatch)
        signals.extend(_lexical_signal(element, lexicon))

    findings = _corroborate(signals, sensitivity)
    risk, trust, integrity = _aggregate_risk(findings)
    status = _status_for(trust, risk, sensitivity)
    is_safe = status == "ok" and risk in {"none", "low"}

    detected = ""
    if findings:
        top = max(findings, key=lambda item: SEVERITY_RANK[str(item["severity"])])
        detected = f"{top['type']}:{top['subtype']} ({top['severity']})"

    guidance = _build_guidance(findings, intended_action)

    return ScanResult(
        status=status,
        trust_score=trust,
        surface_integrity=integrity,
        is_safe=is_safe,
        risk_level=risk,
        detected_threat=detected,
        findings=findings,
        agent_guidance=guidance,
        sanitized_excerpt=visible_aggregate,
        fetch_status=fetch_status,
        offline=offline,
        sensitivity=sensitivity,
    )

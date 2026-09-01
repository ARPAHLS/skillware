"""Deterministic deceptive UI surface scanner — local analysis, optional URL fetch, render lane."""

from __future__ import annotations

import importlib.util
import ipaddress
import json
import re
import socket
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

SensitivityLevel = Literal["strict", "balanced", "lenient"]
RenderMode = Literal["off", "auto", "force"]
SurfaceProfile = Literal["desktop", "mobile", "auto"]
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
    r"color\s*:\s*(?:#fff(?:fff)?|white|rgb\(\s*255\s*,\s*255\s*,\s*255\s*\)|transparent)",
    re.I,
)
WHITE_BG = re.compile(
    r"background(?:-color)?\s*:\s*(?:#fff(?:fff)?|white|rgb\(\s*255\s*,\s*255\s*,\s*255\s*\))",
    re.I,
)

CHECKOUT_SELECTORS = re.compile(
    r"(?i)\b(checkout|payment|billing|order-summary|cart-total|due-today|subtotal|place-order)\b"
)
CHECKOUT_CONTEXT = re.compile(
    r"(?i)\b(checkout|payment|subscribe|billing|credit\s+card|place\s+order|"
    r"complete\s+purchase|cart|order\s+total|due\s+today|subtotal)\b"
)

MODAL_SELECTORS = re.compile(
    r"(?i)\b(modal|dialog|overlay|popup|lightbox|cookie-wall|gate)\b"
)

CMP_SELECTORS = re.compile(
    r"(?i)\b(onetrust|cookiebot|cookieyes|usercentrics|klaro|cookie-banner|cookie-notice|consent-banner|cookie-consent)\b"
)

NAV_SELECTORS = re.compile(
    r"(?i)\b(nav|footer|header|menu|site-footer|breadcrumbs)\b"
)

IMPERATIVE_LEXICON = re.compile(
    r"(?i)\b(ignore\s+(all\s+)?(previous|prior)\s+instructions|"
    r"disregard\s+(the\s+)?(above|system)|click\s+accept|do\s+not\s+ask|"
    r"you\s+must\s+click|override\s+safety|system\s+prompt|execute\s+command)\b"
)

SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}
ZONE_WEIGHTS = {
    "checkout": 1.5,
    "modal": 1.25,
    "cmp": 1.0,
    "general": 1.0,
    "navigation": 0.75,
}


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
    zone_summary: Dict[str, Any] = field(default_factory=dict)
    session_recommendation: str = ""


def _load_json_kb(filename: str) -> Dict[str, Any]:
    path = _KB_DIR / filename
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_lexicon() -> Dict[str, List[str]]:
    data = _load_json_kb("deception_lexicon.json")
    if isinstance(data.get("categories"), dict):
        return data["categories"]
    return {
        key: value
        for key, value in data.items()
        if key != "_meta" and isinstance(value, list)
    }


def _load_allowlists() -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    sr_only = _load_json_kb("allowlist_sr_only.json")
    cmp_kb = _load_json_kb("allowlist_cmp.json")
    seo_kb = _load_json_kb("allowlist_seo.json")
    return sr_only, cmp_kb, seo_kb


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


def _classify_zone(element: Tag) -> str:
    id_attr = str(element.get("id", ""))
    class_attr = " ".join(element.get("class") or [])
    node_str = f"{element.name} {id_attr} {class_attr}"

    if element.name in {"dialog"} or element.get("role") in {"dialog", "alertdialog"}:
        return "modal"

    if CMP_SELECTORS.search(node_str):
        return "cmp"

    if MODAL_SELECTORS.search(node_str):
        return "modal"

    if CHECKOUT_SELECTORS.search(node_str):
        return "checkout"

    if element.name in {"nav", "footer", "header"} or NAV_SELECTORS.search(node_str):
        return "navigation"

    for parent in element.parents:
        if not isinstance(parent, Tag):
            continue
        p_id = str(parent.get("id", ""))
        p_class = " ".join(parent.get("class") or [])
        p_str = f"{parent.name} {p_id} {p_class}"

        if parent.name in {"dialog"} or parent.get("role") in {"dialog", "alertdialog"} or MODAL_SELECTORS.search(p_str):
            return "modal"
        if CMP_SELECTORS.search(p_str):
            return "cmp"
        if CHECKOUT_SELECTORS.search(p_str) or CHECKOUT_CONTEXT.search(p_id) or CHECKOUT_CONTEXT.search(p_class):
            return "checkout"
        if parent.name in {"nav", "footer", "header"} or NAV_SELECTORS.search(p_str):
            return "navigation"

    return "general"


def _is_allowlisted(
    element: Tag,
    sr_allowlist: Dict[str, Any],
    cmp_allowlist: Dict[str, Any],
    seo_allowlist: Dict[str, Any],
) -> Tuple[bool, str]:
    classes = element.get("class") or []
    sr_classes = set(sr_allowlist.get("classes", []))
    if any(c in sr_classes for c in classes):
        return True, "sr_only_class"

    for attr in sr_allowlist.get("attributes", []):
        if element.has_attr(attr):
            return True, "sr_only_attribute"

    text = _normalize_space(element.get_text(" ", strip=True)).lower()
    for pattern in sr_allowlist.get("patterns", []):
        if pattern.lower() in text and len(text) < 80:
            return True, "sr_only_pattern"

    id_attr = str(element.get("id", ""))
    class_str = " ".join(classes)
    for sel in cmp_allowlist.get("selectors", []):
        if sel.startswith("#") and sel[1:] == id_attr:
            return True, "cmp_selector"
        if sel.startswith(".") and sel[1:] in classes:
            return True, "cmp_selector"
        if sel in id_attr or sel in class_str:
            return True, "cmp_selector"

    for phrase in cmp_allowlist.get("benign_phrases", []):
        if phrase in text and len(text) < 150:
            return True, "cmp_benign_copy"

    if element.name in seo_allowlist.get("tags", []):
        return True, "seo_tag"

    if element.name == "script":
        stype = str(element.get("type", "")).lower()
        if stype in seo_allowlist.get("script_types", []):
            return True, "seo_script_type"

    for attr in seo_allowlist.get("attributes", []):
        if element.has_attr(attr):
            return True, "seo_attribute"

    return False, ""


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


def _contrast_signal(element: Tag, zone: str) -> Optional[RawSignal]:
    style = str(element.get("style", ""))
    if WHITE_COLOR.search(style) and (WHITE_BG.search(style) or "background" not in style.lower()):
        text = _direct_text(element)
        if len(text) < 4:
            return None
        return RawSignal(
            signal_type="low_contrast",
            subtype="white_on_white",
            severity="low" if zone != "checkout" else "medium",
            selector=_element_selector(element),
            snippet=text[:SNIPPET_MAX],
            channels=["structural", "visual_style"],
            evidence={"style": style[:200]},
            zone=zone,
        )
    return None


def _mislabeled_cta_signal(element: Tag, zone: str) -> Optional[RawSignal]:
    if element.name not in {"a", "button", "input"}:
        return None
    visible = _direct_text(element)
    aria = _normalize_space(str(element.get("aria-label", "")))
    title = _normalize_space(str(element.get("title", "")))
    value = _normalize_space(str(element.get("value", "")))

    if element.name == "input" and element.get("type") in {"submit", "button"}:
        label_text = value or visible
    else:
        label_text = visible or value

    alt_label = aria or title
    if not label_text or not alt_label:
        return None
    if label_text.lower() == alt_label.lower():
        return None

    severity: RiskLevel = "medium"
    if zone == "checkout" or ("continue" in label_text.lower() and any(k in alt_label.lower() for k in ["buy", "charge", "pay", "order"])):
        severity = "high"

    return RawSignal(
        signal_type="mislabeled_cta",
        subtype="label_aria_mismatch",
        severity=severity,
        selector=_element_selector(element),
        snippet=f"visible={label_text!r} aria/title={alt_label!r}"[:SNIPPET_MAX],
        channels=["structural", "accessibility"],
        evidence={"visible": label_text, "accessible_name": alt_label},
        zone=zone,
    )


def _prechecked_opt_in_signal(element: Tag, zone: str) -> Optional[RawSignal]:
    if element.name != "input" or str(element.get("type", "")).lower() != "checkbox":
        return None

    is_checked = element.has_attr("checked") or str(element.get("checked", "")).lower() in {"true", "checked"}
    if not is_checked:
        return None

    parent_text = _normalize_space(element.parent.get_text(" ", strip=True) if element.parent else "")
    input_id = str(element.get("id", ""))
    input_name = str(element.get("name", "")).lower()

    opt_in_terms = re.compile(
        r"(?i)\b(subscribe|newsletter|marketing|updates|recurring|insurance|protection\s+plan|monthly|donation|membership|auto-renew|trial)\b"
    )
    if opt_in_terms.search(parent_text) or opt_in_terms.search(input_name) or opt_in_terms.search(input_id):
        severity: RiskLevel = "high" if zone == "checkout" else "medium"
        return RawSignal(
            signal_type="prechecked_opt_in",
            subtype="preselected_subscription",
            severity=severity,
            selector=_element_selector(element),
            snippet=parent_text[:SNIPPET_MAX] or f"input[name={input_name}]",
            channels=["structural", "form_input"],
            evidence={"checked": True, "context": parent_text[:120]},
            zone=zone,
        )
    return None


def _drip_pricing_signal(element: Tag, zone: str) -> Optional[RawSignal]:
    if zone != "checkout":
        return None
    text = _normalize_space(element.get_text(" ", strip=True))
    drip_patterns = re.compile(
        r"(?i)\b(mandatory\s+service\s+fee|processing\s+fee\s+added|administrative\s+fee|drip\s+pricing|undisclosed\s+charge|due\s+at\s+checkout)\b"
    )
    if drip_patterns.search(text) and len(text) < 140:
        return RawSignal(
            signal_type="drip_pricing",
            subtype="undisclosed_checkout_fee",
            severity="high",
            selector=_element_selector(element),
            snippet=text[:SNIPPET_MAX],
            channels=["textual", "checkout_zone"],
            evidence={"matched_fee_text": text},
            zone=zone,
        )
    return None


def _fake_urgency_timer_signal(element: Tag, zone: str) -> Optional[RawSignal]:
    text = _normalize_space(element.get_text(" ", strip=True))
    timer_pattern = re.compile(
        r"(?i)\b(deal\s+expires\s+in|cart\s+reserved\s+for|price\s+locked\s+for|offer\s+ends\s+in)\s+\d{1,2}:\d{2}\b"
    )
    is_hidden = _is_hidden_element(element)
    if timer_pattern.search(text):
        severity: RiskLevel = "high" if is_hidden else "medium"
        return RawSignal(
            signal_type="fake_urgency_timer",
            subtype="hidden_scarcity_timer" if is_hidden else "countdown_urgency",
            severity=severity,
            selector=_element_selector(element),
            snippet=text[:SNIPPET_MAX],
            channels=["textual", "structural"],
            evidence={"hidden_branch": is_hidden, "text": text},
            zone=zone,
        )
    return None


def _nag_loop_signal(element: Tag, zone: str) -> Optional[RawSignal]:
    text = _normalize_space(element.get_text(" ", strip=True)).lower()
    nag_patterns = re.compile(
        r"(?i)\b(no\s+thanks,\s+i\s+prefer\s+paying\s+full|no\s+thanks,\s+i\s+hate\s+saving|i\s+don't\s+want\s+to\s+save|remind\s+me\s+later|wait!\s+don't\s+go)\b"
    )
    if nag_patterns.search(text) and len(text) < 120:
        return RawSignal(
            signal_type="nag_loop",
            subtype="confirm_shaming_asymmetry",
            severity="medium",
            selector=_element_selector(element),
            snippet=text[:SNIPPET_MAX],
            channels=["textual", "copywriting"],
            evidence={"nag_phrase": text},
            zone=zone,
        )
    return None


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
    element: Tag,
    visible_aggregate: str,
    lexicon: Dict[str, List[str]],
    allowlists: Tuple[Dict, Dict, Dict],
    zone: str,
) -> Optional[RawSignal]:
    if not _is_hidden_element(element):
        return None
    hidden_text = _normalize_space(element.get_text(" ", strip=True))
    if len(hidden_text) < 8:
        return None
    if hidden_text.lower() in visible_aggregate.lower():
        return None

    sr_allow, cmp_allow, seo_allow = allowlists
    allowlisted, allow_reason = _is_allowlisted(element, sr_allow, cmp_allow, seo_allow)

    imperative = bool(IMPERATIVE_LEXICON.search(hidden_text))
    lex_hits = _lexicon_hits(hidden_text, lexicon)

    if allowlisted and not imperative:
        return None

    if not lex_hits and not imperative:
        return RawSignal(
            signal_type="channel_mismatch",
            subtype="hidden_non_visible_text",
            severity="low",
            selector=_element_selector(element),
            snippet=hidden_text[:SNIPPET_MAX],
            channels=["dom_text", "hidden_surface"],
            evidence={"hidden_only": True, "allowlisted": allowlisted},
            zone=zone,
        )

    severity: RiskLevel = "high"
    if imperative and zone == "checkout":
        severity = "critical"
    subtype = "hidden_imperative_text" if imperative else "hidden_deception_lexicon"
    return RawSignal(
        signal_type="channel_mismatch",
        subtype=subtype,
        severity=severity,
        selector=_element_selector(element),
        snippet=hidden_text[:SNIPPET_MAX],
        channels=["dom_text", "hidden_surface"],
        evidence={"lexicon_hits": lex_hits, "imperative": imperative, "allowlisted": allowlisted},
        zone=zone,
    )


def _lexical_signal(element: Tag, lexicon: Dict[str, List[str]], zone: str) -> List[RawSignal]:
    text = _normalize_space(element.get_text(" ", strip=True))
    if len(text) < 6:
        return []
    hits = _lexicon_hits(text, lexicon)
    if not hits:
        return []
    hidden = _is_hidden_element(element)
    severity: RiskLevel = "medium" if hidden else "low"
    checkout_lexicon = {"hidden_fee", "forced_continuity", "drip_pricing"}
    if checkout_lexicon.intersection(hits) and zone == "checkout":
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
            zone=zone,
        )
    ]


def _mobile_profile_signal(element: Tag, profile: SurfaceProfile, zone: str) -> Optional[RawSignal]:
    if profile != "mobile":
        return None
    style = str(element.get("style", "")).lower()
    if "-webkit-tap-highlight-color: transparent" in style or "-webkit-tap-highlight-color: rgba(0,0,0,0)" in style:
        if "position: absolute" in style or "position: fixed" in style:
            return RawSignal(
                signal_type="mobile_overlay_trap",
                subtype="transparent_tap_overlay",
                severity="medium",
                selector=_element_selector(element),
                snippet=style[:SNIPPET_MAX],
                channels=["mobile_heuristics", "visual_style"],
                evidence={"style": style},
                zone=zone,
            )
    return None


def _render_dom_diff_lane(
    html: str,
    render_mode: RenderMode,
    soup: BeautifulSoup,
) -> List[RawSignal]:
    if render_mode == "off":
        return []

    playwright_available = importlib.util.find_spec("playwright") is not None
    if not playwright_available:
        if render_mode == "force":
            raise ImportError(
                "render_mode='force' requires Playwright. Install the extra with: pip install 'skillware[security_deceptive_ui_guard_render]'"
            )
        return []

    signals: List[RawSignal] = []
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.set_content(html, wait_until="domcontentloaded")

            elements_data = page.evaluate("""() => {
                const results = [];
                const all = document.querySelectorAll('*');
                for (const el of all) {
                    const style = window.getComputedStyle(el);
                    const rect = el.getBoundingClientRect();
                    const isZeroSize = rect.width === 0 || rect.height === 0;
                    const isTransparent = style.opacity === '0' || style.visibility === 'hidden' || style.display === 'none' || style.color === 'rgba(0, 0, 0, 0)' || style.color === 'transparent';
                    const text = el.innerText || '';
                    if (text.length > 5 && (isZeroSize || isTransparent)) {
                        results.push({
                            tagName: el.tagName.toLowerCase(),
                            id: el.id || '',
                            className: el.className || '',
                            text: text.substring(0, 160),
                            isZeroSize: isZeroSize,
                            isTransparent: isTransparent,
                            opacity: style.opacity,
                            visibility: style.visibility,
                            display: style.display
                        });
                    }
                }
                return results;
            }""")
            browser.close()

            for item in elements_data:
                tag_sel = f"{item['tagName']}#{item['id']}" if item['id'] else f"{item['tagName']}.{item['className']}" if item['className'] else item['tagName']
                signals.append(
                    RawSignal(
                        signal_type="render_dom_divergence",
                        subtype="render_css_hidden_element",
                        severity="high",
                        selector=tag_sel,
                        snippet=item["text"],
                        channels=["render_computed_style", "dom_divergence"],
                        evidence={
                            "opacity": item.get("opacity"),
                            "visibility": item.get("visibility"),
                            "display": item.get("display"),
                            "zero_size": item.get("isZeroSize"),
                        },
                        zone="checkout" if "fee" in item["text"].lower() or "price" in item["text"].lower() else "general",
                    )
                )
    except Exception as exc:
        if render_mode == "force":
            raise RuntimeError(f"Playwright render execution failed: {exc}") from exc
    return signals


def _corroborate(
    signals: List[RawSignal],
    sensitivity: SensitivityLevel,
    intended_action: str = "",
) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    action_lower = (intended_action or "").lower()
    is_checkout_action = any(k in action_lower for k in ["checkout", "pay", "buy", "order", "subscribe"])

    for signal in signals:
        corroborated_by: List[str] = []
        publish = False
        confidence = 0.55

        zone_weight = ZONE_WEIGHTS.get(signal.zone, 1.0)
        if is_checkout_action and signal.zone == "checkout":
            zone_weight *= 1.2

        if signal.signal_type == "channel_mismatch":
            if signal.subtype in {"hidden_imperative_text", "hidden_deception_lexicon"}:
                publish = True
                confidence = 0.9 if signal.subtype == "hidden_imperative_text" else 0.82
                corroborated_by = ["channel_mismatch", "textual"]
            elif sensitivity == "lenient":
                continue
            elif sensitivity == "balanced" and (signal.zone in {"checkout", "modal"} or zone_weight >= 1.25):
                publish = True
                confidence = 0.72
                corroborated_by = ["channel_mismatch", f"{signal.zone}_zone"]
            elif sensitivity == "strict":
                publish = True
                confidence = 0.65
                corroborated_by = ["channel_mismatch"]

        elif signal.signal_type == "mislabeled_cta":
            publish = True
            confidence = 0.85 if signal.zone == "checkout" else 0.78
            corroborated_by = ["accessibility", "structural", signal.zone]

        elif signal.signal_type == "prechecked_opt_in":
            publish = True
            confidence = 0.88 if signal.zone == "checkout" else 0.75
            corroborated_by = ["form_structure", signal.zone]

        elif signal.signal_type == "drip_pricing":
            publish = True
            confidence = 0.85
            corroborated_by = ["checkout_pricing", "textual"]

        elif signal.signal_type == "fake_urgency_timer":
            publish = True
            confidence = 0.80
            corroborated_by = ["timer_structure", "textual"]

        elif signal.signal_type == "nag_loop":
            if sensitivity in {"strict", "balanced"}:
                publish = True
                confidence = 0.75
                corroborated_by = ["copywriting_asymmetry"]

        elif signal.signal_type == "render_dom_divergence":
            publish = True
            confidence = 0.92
            corroborated_by = ["render_computed_style", "dom_divergence"]

        elif signal.signal_type == "mobile_overlay_trap":
            if sensitivity in {"strict", "balanced"}:
                publish = True
                confidence = 0.70
                corroborated_by = ["mobile_heuristics"]

        elif signal.signal_type == "deception_lexicon":
            if signal.severity in {"high", "critical"}:
                publish = True
                confidence = 0.82
                corroborated_by = ["textual", signal.zone]
            elif (
                signal.subtype in {"hidden_fee", "forced_continuity", "drip_pricing", "preselected_opt_in"}
                and signal.zone in {"checkout", "modal"}
            ):
                publish = True
                confidence = 0.78
                corroborated_by = ["textual", f"{signal.zone}_zone"]
            elif sensitivity == "strict":
                publish = True
                confidence = 0.62
                corroborated_by = ["textual"]

        elif signal.signal_type == "low_contrast":
            if sensitivity in {"strict", "balanced"} and signal.zone in {"checkout", "modal"}:
                publish = True
                confidence = 0.65
                corroborated_by = ["visual_style", f"{signal.zone}_zone"]
            elif sensitivity == "strict":
                publish = True
                confidence = 0.55
                corroborated_by = ["visual_style"]

        if not publish:
            continue

        findings.append(
            {
                "type": signal.signal_type,
                "subtype": signal.subtype,
                "severity": signal.severity,
                "confidence": round(min(0.99, confidence), 2),
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


def _build_zone_summary(soup: BeautifulSoup, findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Dict[str, Any]] = {
        zone: {"element_count": 0, "findings_count": 0, "weight": weight}
        for zone, weight in ZONE_WEIGHTS.items()
    }
    for element in soup.find_all(True):
        if isinstance(element, Tag):
            z = _classify_zone(element)
            if z in summary:
                summary[z]["element_count"] += 1

    for f in findings:
        fz = str(f.get("zone", "general"))
        if fz in summary:
            summary[fz]["findings_count"] += 1
    return summary


def _build_session_recommendation(
    session_fingerprint: str,
    findings: List[Dict[str, Any]],
) -> str:
    if not session_fingerprint:
        return ""
    has_nag = any(f.get("type") in {"nag_loop", "fake_urgency_timer"} or f.get("subtype") in {"confirm_shaming"} for f in findings)
    if has_nag:
        return f"Recurring nag or urgency pattern detected for session fingerprint '{session_fingerprint[:16]}...'. Recommend bypassing modal prompts and enforcing strict payment review."
    return f"Session fingerprint '{session_fingerprint[:16]}...' verified clean of recurring nag loops."


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
        if item.get("zone") == "checkout" or item.get("subtype") in {
            "hidden_fee",
            "forced_continuity",
            "drip_pricing",
            "preselected_subscription",
        }:
            verify_payment = True
        if item.get("type") in {"mislabeled_cta", "prechecked_opt_in"}:
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
    if any(f.get("type") == "prechecked_opt_in" for f in findings):
        summary_parts.append("Pre-checked subscription or recurring opt-in box detected.")
    if any(f.get("subtype") in {"hidden_fee", "drip_pricing"} for f in findings):
        summary_parts.append("Copy suggests hidden or drip fees may appear late in checkout.")
    if any(f.get("subtype") == "forced_continuity" for f in findings):
        summary_parts.append("Copy suggests automatic renewal or post-trial billing.")
    if any(f.get("type") == "render_dom_divergence" for f in findings):
        summary_parts.append("Computed style rendering reveals text or interactive elements hidden by external stylesheets.")

    action_lower = (intended_action or "").lower()
    if any(k in action_lower for k in ["pay", "checkout", "subscribe", "buy", "order"]):
        verify_payment = True

    return {
        "do_not_click": sorted(s for s in selectors if s),
        "verify_before_payment": verify_payment,
        "summary": " ".join(summary_parts)
        or "No deceptive UI signals crossed the publish threshold.",
    }


def scan_surface(
    *,
    html_content: str = "",
    url: str = "",
    sensitivity: SensitivityLevel = "balanced",
    intended_action: str = "",
    render_mode: RenderMode = "off",
    surface_profile: SurfaceProfile = "desktop",
    session_fingerprint: str = "",
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
                },
                sanitized_excerpt="",
                fetch_status=f"error: {exc}",
                offline=False,
                sensitivity=sensitivity,
                zone_summary={},
                session_recommendation="",
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
            },
            sanitized_excerpt="",
            fetch_status=fetch_status,
            offline=offline,
            sensitivity=sensitivity,
            zone_summary={},
            session_recommendation="",
        )

    soup = BeautifulSoup(html, "html.parser")
    lexicon = _load_lexicon()
    allowlists = _load_allowlists()
    visible_aggregate = _visible_excerpt(soup)
    signals: List[RawSignal] = []

    effective_profile = surface_profile
    if surface_profile == "auto":
        viewport_meta = soup.find("meta", attrs={"name": "viewport"})
        effective_profile = "mobile" if viewport_meta else "desktop"

    for element in soup.find_all(True):
        if not isinstance(element, Tag):
            continue
        zone = _classify_zone(element)

        contrast = _contrast_signal(element, zone)
        if contrast:
            signals.append(contrast)

        mislabeled = _mislabeled_cta_signal(element, zone)
        if mislabeled:
            signals.append(mislabeled)

        prechecked = _prechecked_opt_in_signal(element, zone)
        if prechecked:
            signals.append(prechecked)

        drip = _drip_pricing_signal(element, zone)
        if drip:
            signals.append(drip)

        urgency_timer = _fake_urgency_timer_signal(element, zone)
        if urgency_timer:
            signals.append(urgency_timer)

        nag = _nag_loop_signal(element, zone)
        if nag:
            signals.append(nag)

        mobile_sig = _mobile_profile_signal(element, effective_profile, zone)
        if mobile_sig:
            signals.append(mobile_sig)

        mismatch = _channel_mismatch_signal(element, visible_aggregate, lexicon, allowlists, zone)
        if mismatch:
            signals.append(mismatch)

        signals.extend(_lexical_signal(element, lexicon, zone))

    render_signals = _render_dom_diff_lane(html, render_mode, soup)
    signals.extend(render_signals)

    findings = _corroborate(signals, sensitivity, intended_action)
    risk, trust, integrity = _aggregate_risk(findings)
    status = _status_for(trust, risk, sensitivity)
    is_safe = status == "ok" and risk in {"none", "low"}

    detected = ""
    if findings:
        top = max(findings, key=lambda item: SEVERITY_RANK[str(item["severity"])])
        detected = f"{top['type']}:{top['subtype']} ({top['severity']})"

    guidance = _build_guidance(findings, intended_action)
    zone_summary = _build_zone_summary(soup, findings)
    session_rec = _build_session_recommendation(session_fingerprint, findings)

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
        zone_summary=zone_summary,
        session_recommendation=session_rec,
    )

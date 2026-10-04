"""HTML DOM parsing and form schema extraction for office/web_form_mapper."""

from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from bs4 import BeautifulSoup, Tag

try:
    from .models import FormField, FormMetadata
except (ImportError, ValueError):
    try:
        from skills.office.web_form_mapper.models import (
            FormField,
            FormMetadata,
        )
    except (ImportError, ValueError):
        from models import FormField, FormMetadata

# Signatures for known anti-bot, WAF challenges, or CAPTCHA providers
CAPTCHA_SIGNATURES: Dict[str, List[str]] = {
    "recaptcha": ["g-recaptcha", "recaptcha-token", "www.google.com/recaptcha"],
    "turnstile": ["cf-turnstile", "challenges.cloudflare.com/turnstile"],
    "hcaptcha": ["h-captcha", "hcaptcha", "hcaptcha.com"],
    "arkose": ["arkose", "funcaptcha"],
}

CHALLENGE_TITLE_PATTERNS = [
    r"just a moment\.\.\.",
    r"attention required!",
    r"security check",
    r"verify you are human",
    r"cloudflare",
]


def detect_bot_protection(soup: BeautifulSoup) -> Tuple[bool, Optional[str]]:
    """Detect if the page or form is gated by a CAPTCHA or anti-bot challenge."""
    html_text = str(soup)

    # Check for challenge title/heading signatures
    title_tag = soup.find("title")
    if title_tag and title_tag.string:
        t = title_tag.string.strip().casefold()
        for pat in CHALLENGE_TITLE_PATTERNS:
            if re.search(pat, t):
                return True, "waf_challenge"

    # Check script / iframe / div signatures
    for c_type, sigs in CAPTCHA_SIGNATURES.items():
        for sig in sigs:
            if sig in html_text:
                return True, c_type

    # Check for recaptcha / turnstile element classes or data-sitekey
    if soup.find(attrs={"data-sitekey": True}) or soup.find(
        attrs={"data-turnstile-sitekey": True}
    ):
        return True, "turnstile_or_recaptcha"

    return False, None


def _find_field_label(tag: Tag, soup: BeautifulSoup) -> str:
    """Resolve the most accurate human-readable label for a form field."""
    # 1. aria-label
    aria_label = tag.get("aria-label")
    if aria_label and aria_label.strip():
        return aria_label.strip()

    # 2. aria-labelledby
    aria_labelledby = tag.get("aria-labelledby")
    if aria_labelledby:
        elem = soup.find(id=aria_labelledby.strip())
        if elem and elem.get_text():
            text = elem.get_text().strip()
            if text:
                return text

    # 3. Label tag via for="<id>"
    field_id = tag.get("id")
    if field_id:
        label = soup.find("label", attrs={"for": field_id})
        if label and label.get_text():
            text = label.get_text().strip()
            if text:
                return text

    # 4. Enclosing parent <label>
    parent_label = tag.find_parent("label")
    if parent_label and parent_label.get_text():
        # Strip out the input's own text if any
        text = parent_label.get_text().strip()
        if text:
            return text

    # 5. Preceding sibling or adjacent text/label
    prev = tag.find_previous_sibling("label")
    if prev and prev.get_text():
        text = prev.get_text().strip()
        if text:
            return text

    # 6. Fallback to placeholder or title
    placeholder = tag.get("placeholder")
    if placeholder and placeholder.strip():
        return placeholder.strip()

    title = tag.get("title")
    if title and title.strip():
        return title.strip()

    # 7. Fallback to name or id
    return tag.get("name") or field_id or "unlabeled_field"


def _build_field_selector(tag: Tag, form_index: int) -> str:
    """Build a deterministic CSS selector for a form element."""
    tag_name = tag.name
    field_id = tag.get("id")
    if field_id:
        return f"#{field_id}"

    field_name = tag.get("name")
    if field_name:
        return f"{tag_name}[name='{field_name}']"

    return f"form:nth-of-type({form_index + 1}) {tag_name}"


def parse_forms_from_html(html: str) -> List[FormMetadata]:
    """Extract all web forms and their constituent input schemas from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    has_captcha, captcha_type = detect_bot_protection(soup)

    form_nodes = soup.find_all("form")
    if not form_nodes:
        # Check if loose inputs exist outside of a formal <form> tag (common in SPAs)
        loose_inputs = soup.find_all(["input", "select", "textarea"])
        if loose_inputs:
            # Create a synthetic virtual form
            virtual_form = soup.new_tag(
                "form", attrs={"action": "", "method": "POST", "id": "virtual_spa_form"}
            )
            for inp in loose_inputs:
                virtual_form.append(inp.extract())
            form_nodes = [virtual_form]
        else:
            return []

    parsed_forms: List[FormMetadata] = []

    for idx, form in enumerate(form_nodes):
        form_id = form.get("id") or ""
        form_name = form.get("name") or ""
        action = form.get("action") or ""
        method = (form.get("method") or "POST").upper()
        enctype = form.get("enctype") or "application/x-www-form-urlencoded"

        fields: List[FormField] = []
        hidden_fields: Dict[str, str] = {}

        # Scan for input, select, textarea
        control_tags = form.find_all(["input", "select", "textarea"])
        for ctrl in control_tags:
            tag_name = ctrl.name
            ctrl_type = (
                ctrl.get("type") or ("select" if tag_name == "select" else "text")
            ).lower()
            name = ctrl.get("name") or ""
            cid = ctrl.get("id") or ""
            val = ctrl.get("value") or ""
            placeholder = ctrl.get("placeholder") or ""
            required = ctrl.has_attr("required") or ctrl.get("aria-required") == "true"
            pattern = ctrl.get("pattern")
            selector = _build_field_selector(ctrl, idx)

            is_hidden = ctrl_type == "hidden" or ctrl.has_attr("hidden")

            options: List[Dict[str, str]] = []
            if tag_name == "select":
                for opt in ctrl.find_all("option"):
                    opt_val = opt.get("value", opt.get_text().strip())
                    opt_txt = opt.get_text().strip()
                    options.append({"value": opt_val, "text": opt_txt})

            if tag_name == "textarea" and not val:
                val = ctrl.get_text()

            # Preserve hidden inputs (CSRF, __VIEWSTATE, tokens)
            if is_hidden and name:
                hidden_fields[name] = val

            label = _find_field_label(ctrl, soup)

            field_obj = FormField(
                name=name,
                id=cid,
                tag=tag_name,
                type=ctrl_type,
                label=label,
                value=val,
                placeholder=placeholder,
                required=required,
                pattern=pattern,
                options=options,
                is_hidden=is_hidden,
                selector=selector,
            )
            fields.append(field_obj)

        parsed_forms.append(
            FormMetadata(
                form_index=idx,
                form_id=form_id,
                form_name=form_name,
                action=action,
                method=method,
                enctype=enctype,
                fields=fields,
                hidden_fields=hidden_fields,
                has_captcha=has_captcha,
                captcha_type=captcha_type,
            )
        )

    return parsed_forms

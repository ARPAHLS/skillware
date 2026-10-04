"""Form preview diff generation and gated submission execution for office/web_form_mapper."""

from __future__ import annotations

import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from .models import FillPlanItem, FormMetadata, PreviewDiffItem
except (ImportError, ValueError):
    try:
        from skills.office.web_form_mapper.models import (
            FillPlanItem,
            FormMetadata,
            PreviewDiffItem,
        )
    except (ImportError, ValueError):
        from models import FillPlanItem, FormMetadata, PreviewDiffItem


def generate_preview_diff(
    form: FormMetadata, fill_plan: List[FillPlanItem]
) -> List[PreviewDiffItem]:
    """Generate a side-by-side human review diff table."""
    plan_map: Dict[str, FillPlanItem] = {item.selector: item for item in fill_plan}
    # Also index by field_name for fallback lookup
    by_name: Dict[str, FillPlanItem] = {
        item.field_name: item for item in fill_plan if item.field_name
    }

    diffs: List[PreviewDiffItem] = []

    for field in form.fields:
        if field.is_hidden:
            continue

        item = (
            plan_map.get(field.selector)
            or by_name.get(field.name)
            or by_name.get(field.id)
        )
        if item:
            diffs.append(
                PreviewDiffItem(
                    label=field.label,
                    selector=field.selector,
                    current_value=field.value,
                    proposed_value=str(item.proposed_value),
                    source=item.source,
                    confidence=item.confidence,
                    required=field.required,
                )
            )
        elif field.required:
            diffs.append(
                PreviewDiffItem(
                    label=field.label,
                    selector=field.selector,
                    current_value=field.value,
                    proposed_value="[MISSING - REQUIRED]",
                    source="unmapped",
                    confidence=0.0,
                    required=True,
                )
            )

    return diffs


def assemble_submission_payload(
    form: FormMetadata, fill_plan: List[FillPlanItem]
) -> Dict[str, Any]:
    """Combine preserved hidden fields (CSRF tokens) with populated fill plan values."""
    payload: Dict[str, Any] = {}

    # 1. Base: all preserved hidden fields (CSRF, __VIEWSTATE, tokens)
    payload.update(form.hidden_fields)

    # 2. Add existing default values from form fields
    for field in form.fields:
        if field.name and field.value and field.name not in payload:
            payload[field.name] = field.value

    # 3. Apply planned values from fill_plan
    for item in fill_plan:
        if item.field_name:
            payload[item.field_name] = item.proposed_value

    return payload


def execute_http_submission(
    form: FormMetadata,
    payload: Dict[str, Any],
    base_url: Optional[str] = None,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Execute standard HTTP POST/GET submission preserving all hidden fields."""
    target_url = form.action or base_url
    if not target_url:
        raise ValueError(
            "Cannot submit form: form action is empty and no base URL was provided."
        )

    if base_url and not (
        target_url.startswith("http://") or target_url.startswith("https://")
    ):
        target_url = urllib.parse.urljoin(base_url, target_url)

    out_dir = output_dir or Path(os.environ.get("SKILLWARE_SCRATCH_DIR", "."))
    out_dir.mkdir(parents=True, exist_ok=True)
    receipt_file = out_dir / "submission_receipt.html"

    # Encode payload
    data_bytes = urllib.parse.urlencode(payload).encode("utf-8")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Skillware/0.5.8"
        ),
        "Content-Type": form.enctype or "application/x-www-form-urlencoded",
    }

    if form.method == "GET":
        delim = "&" if "?" in target_url else "?"
        full_url = f"{target_url}{delim}{urllib.parse.urlencode(payload)}"
        req = urllib.request.Request(full_url, headers=headers, method="GET")
    else:
        req = urllib.request.Request(
            target_url, data=data_bytes, headers=headers, method="POST"
        )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            resp_body = resp.read().decode("utf-8", errors="replace")
            status_code = resp.status
            receipt_file.write_text(resp_body, encoding="utf-8")

            return {
                "success": 200 <= status_code < 400,
                "status_code": status_code,
                "target_url": target_url,
                "receipt_path": str(receipt_file.resolve()),
                "response_snippet": resp_body[:500],
            }
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        receipt_file.write_text(body, encoding="utf-8")
        return {
            "success": False,
            "status_code": e.code,
            "target_url": target_url,
            "error": f"HTTP {e.code}: {e.reason}",
            "receipt_path": str(receipt_file.resolve()),
            "response_snippet": body[:500],
        }
    except Exception as e:
        return {
            "success": False,
            "target_url": target_url,
            "error": str(e),
        }


def execute_browser_submission(
    form: FormMetadata,
    fill_plan: List[FillPlanItem],
    target_url: str,
    output_dir: Optional[Path] = None,
    save_screenshot: bool = True,
) -> Dict[str, Any]:
    """Execute live headless browser submission via Playwright if available."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "success": False,
            "error": "OPTIONAL_DEPENDENCY_MISSING",
            "message": (
                "Playwright is required for browser execution engine. "
                "Install with: pip install 'skillware[office_web_form_mapper_browser]'"
            ),
        }

    out_dir = output_dir or Path(os.environ.get("SKILLWARE_SCRATCH_DIR", "."))
    out_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = (
        out_dir / "submission_confirmation.png" if save_screenshot else None
    )
    receipt_file = out_dir / "browser_submission_receipt.html"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(target_url, wait_until="domcontentloaded")

            # Fill inputs with synthetic event triggers
            for item in fill_plan:
                val = str(item.proposed_value)
                try:
                    locator = page.locator(item.selector).first
                    if locator.count() > 0:
                        if item.field_type == "checkbox":
                            if val.lower() in ("true", "1", "yes", "on"):
                                locator.check()
                            else:
                                locator.uncheck()
                        elif item.field_type == "select":
                            locator.select_option(value=val)
                        else:
                            locator.fill(val)
                except Exception:
                    continue

            # Submit
            submit_btn = page.locator(
                "button[type='submit'], input[type='submit']"
            ).first
            if submit_btn.count() > 0:
                submit_btn.click()
            else:
                page.evaluate("document.querySelector('form').submit()")

            page.wait_for_load_state("networkidle", timeout=10000)

            if screenshot_path:
                page.screenshot(path=str(screenshot_path))

            content = page.content()
            receipt_file.write_text(content, encoding="utf-8")

            return {
                "success": True,
                "target_url": page.url,
                "receipt_path": str(receipt_file.resolve()),
                "screenshot_path": (
                    str(screenshot_path.resolve()) if screenshot_path else None
                ),
                "response_snippet": content[:500],
            }
        finally:
            browser.close()

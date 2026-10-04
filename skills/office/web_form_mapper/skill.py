"""Main implementation of office/web_form_mapper."""

from __future__ import annotations

import asyncio
import json
import os
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from skillware.core.base_skill import BaseSkill
from skillware.core.mail_config import (
    load_addressbook_yaml,
    resolve_addressbook_path,
)

try:
    from .dom_parser import parse_forms_from_html
    from .matcher import (
        extract_flattened_identity,
        generate_fill_plan,
        load_curated_profile,
    )
    from .models import FillPlanItem, FormMetadata
    from .submitter import (
        assemble_submission_payload,
        execute_browser_submission,
        execute_http_submission,
        generate_preview_diff,
    )
except (ImportError, ValueError):
    try:
        from skills.office.web_form_mapper.dom_parser import (
            parse_forms_from_html,
        )
        from skills.office.web_form_mapper.matcher import (
            extract_flattened_identity,
            generate_fill_plan,
            load_curated_profile,
        )
        from skills.office.web_form_mapper.models import (
            FillPlanItem,
            FormMetadata,
        )
        from skills.office.web_form_mapper.submitter import (
            assemble_submission_payload,
            execute_browser_submission,
            execute_http_submission,
            generate_preview_diff,
        )
    except (ImportError, ValueError):
        import sys

        _skill_dir = os.path.dirname(os.path.abspath(__file__))
        if _skill_dir not in sys.path:
            sys.path.insert(0, _skill_dir)
        from dom_parser import parse_forms_from_html
        from matcher import (
            extract_flattened_identity,
            generate_fill_plan,
            load_curated_profile,
        )
        from models import FillPlanItem, FormMetadata
        from submitter import (
            assemble_submission_payload,
            execute_browser_submission,
            execute_http_submission,
            generate_preview_diff,
        )


class WebFormMapperSkill(BaseSkill):
    """
    Skill for inspecting, mapping identity profiles to, previewing,
    and deterministically submitting web forms with confirmation safety gates.
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        addressbook_path: Optional[str | Path] = None,
        profiles_dir: Optional[str | Path] = None,
        scratch_dir: Optional[str | Path] = None,
    ):
        super().__init__(config=config)
        self._addressbook_path = (
            Path(addressbook_path).resolve() if addressbook_path else None
        )
        self._profiles_dir = (
            Path(profiles_dir).resolve()
            if profiles_dir
            else Path(__file__).resolve().parent / "kb" / "form_profiles"
        )
        self._scratch_dir = Path(scratch_dir).resolve() if scratch_dir else None

    @property
    def manifest(self) -> Dict[str, Any]:
        """Return parsed manifest.yaml dictionary."""
        manifest_path = Path(__file__).resolve().parent / "manifest.yaml"
        if manifest_path.is_file():
            import yaml

            return yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        return {}

    def _resolve_identity_data(
        self,
        contact_id: Optional[str],
        use_self: bool,
        payload: Optional[Dict[str, Any]],
        explicit_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resolve contact from addressbook.yaml and/or merge with direct payload."""
        identity: Dict[str, Any] = {}

        book_path = (
            Path(explicit_path).resolve()
            if explicit_path
            else (
                self._addressbook_path
                if self._addressbook_path
                else resolve_addressbook_path()
            )
        )

        if (use_self or contact_id) and book_path and book_path.is_file():
            data = load_addressbook_yaml(book_path)
            contacts = data.get("contacts") or {}

            matched_contact = None
            if contact_id and contact_id in contacts:
                matched_contact = contacts[contact_id]
            elif use_self:
                # Find contact with is_self: True or ID 'self' / 'me'
                for cid, c in contacts.items():
                    if isinstance(c, dict) and (
                        c.get("is_self") is True or cid.lower() in ("self", "me")
                    ):
                        matched_contact = c
                        break

            if matched_contact and isinstance(matched_contact, dict):
                identity.update(extract_flattened_identity(matched_contact))

        if payload and isinstance(payload, dict):
            identity.update(payload)

        return identity

    def _fetch_html(self, url: str) -> str:
        """Fetch raw HTML from target URL."""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Skillware/0.5.8"
            )
        }
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read().decode("utf-8", errors="replace")

    def execute(
        self,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Synchronous skill entrypoint."""
        merged_params: Dict[str, Any] = {}
        if isinstance(params, dict):
            merged_params.update(params)
        merged_params.update(kwargs)

        action = merged_params.get("action", "inspect")
        html_content = merged_params.get("html_content")
        url = merged_params.get("url")
        form_index = int(merged_params.get("form_index", 0))

        # 1. Obtain HTML content
        if not html_content and url:
            try:
                html_content = self._fetch_html(url)
            except Exception as e:
                return {
                    "status": "error",
                    "action": action,
                    "error": f"Failed to fetch HTML from URL {url!r}: {e}",
                }

        if not html_content and action in ("inspect", "map"):
            return {
                "status": "error",
                "action": action,
                "error": "Either 'html_content' or 'url' must be provided.",
            }

        # 2. Parse forms from HTML (if provided)
        forms: List[FormMetadata] = []
        target_form: Optional[FormMetadata] = None

        if html_content:
            forms = parse_forms_from_html(html_content)
            if not forms:
                return {
                    "status": "error",
                    "action": action,
                    "error": "No web forms or input controls discovered in the provided HTML.",
                }
            if form_index >= len(forms):
                form_index = 0
            target_form = forms[form_index]

            # Fail-closed anti-bot / CAPTCHA check
            if target_form.has_captcha:
                return {
                    "status": "blocked",
                    "action": action,
                    "error": "CAPTCHA_DETECTED",
                    "captcha_type": target_form.captcha_type,
                    "message": (
                        "Form is protected by anti-bot challenge (CAPTCHA / Turnstile). "
                        "Automated submission blocked."
                    ),
                }

        # --- Action Dispatch ---

        if action == "inspect":
            assert target_form is not None
            return {
                "status": "success",
                "action": "inspect",
                "form_id": target_form.form_id,
                "form_action": target_form.action,
                "form_method": target_form.method,
                "fields": [f.to_dict() for f in target_form.fields],
                "hidden_fields": target_form.hidden_fields,
            }

        elif action == "map":
            assert target_form is not None
            contact_id = merged_params.get("contact_id")
            use_self = bool(merged_params.get("use_self", False))
            payload = merged_params.get("payload")
            form_profile_id = merged_params.get("form_profile_id")
            addressbook_path = merged_params.get("addressbook_path")

            identity_data = self._resolve_identity_data(
                contact_id, use_self, payload, explicit_path=addressbook_path
            )
            curated_profile = (
                load_curated_profile(self._profiles_dir, form_profile_id)
                if form_profile_id
                else None
            )

            source_label = (
                f"addressbook:{contact_id or 'me'}"
                if (use_self or contact_id)
                else "payload"
            )
            fill_plan, unmapped_required = generate_fill_plan(
                target_form,
                identity_data,
                source_label=source_label,
                curated_profile=curated_profile,
            )

            status = "needs_input" if unmapped_required else "success"
            return {
                "status": status,
                "action": "map",
                "form_id": target_form.form_id,
                "form_action": target_form.action,
                "form_method": target_form.method,
                "fill_plan": [item.to_dict() for item in fill_plan],
                "unmapped_fields": unmapped_required,
                "hidden_fields": target_form.hidden_fields,
            }

        elif action == "preview":
            raw_plan = merged_params.get("fill_plan") or []
            fill_plan_items = [
                FillPlanItem(**item) if isinstance(item, dict) else item
                for item in raw_plan
            ]

            if not target_form:
                return {
                    "status": "error",
                    "action": "preview",
                    "error": "HTML content required to render preview diff against original form fields.",
                }

            diff_items = generate_preview_diff(target_form, fill_plan_items)
            return {
                "status": "success",
                "action": "preview",
                "form_id": target_form.form_id,
                "form_action": target_form.action,
                "preview_table": [d.to_dict() for d in diff_items],
            }

        elif action == "submit":
            confirmed = bool(merged_params.get("confirmed", False))
            dry_run = bool(merged_params.get("dry_run", True))
            engine = merged_params.get("execution_engine", "http_post")
            save_screenshot = bool(merged_params.get("save_screenshot", True))

            raw_plan = merged_params.get("fill_plan") or []
            fill_plan_items = [
                FillPlanItem(**item) if isinstance(item, dict) else item
                for item in raw_plan
            ]

            # If target_form wasn't parsed from HTML, try reconstituting from parameters
            if not target_form:
                return {
                    "status": "error",
                    "action": "submit",
                    "error": (
                        "Original form HTML is required to preserve hidden state and "
                        "CSRF tokens during submission."
                    ),
                }

            # Safety enforcement gate
            if not dry_run and not confirmed:
                return {
                    "status": "error",
                    "action": "submit",
                    "error": "CONFIRMATION_REQUIRED",
                    "message": (
                        "Explicit user confirmation (confirmed: true) is required before "
                        "executing live form submission."
                    ),
                    "agent_hint": (
                        "Present the preview diff to the operator and request confirmation "
                        "before re-invoking with confirmed: true."
                    ),
                }

            # Determine output directory for artifacts
            out_dir = (
                Path(params.get("output_dir"))
                if params.get("output_dir")
                else (
                    self._scratch_dir
                    or Path(os.environ.get("SKILLWARE_SCRATCH_DIR", "."))
                )
            )
            out_dir.mkdir(parents=True, exist_ok=True)

            if dry_run:
                simulated_payload = assemble_submission_payload(
                    target_form, fill_plan_items
                )
                receipt_path = out_dir / "simulated_submission_receipt.json"
                receipt_path.write_text(
                    json.dumps(
                        {
                            "simulated": True,
                            "action": target_form.action,
                            "method": target_form.method,
                            "payload": simulated_payload,
                        },
                        indent=2,
                    ),
                    encoding="utf-8",
                )
                return {
                    "status": "success",
                    "action": "submit",
                    "dry_run": True,
                    "form_action": target_form.action,
                    "submission_result": {
                        "simulated": True,
                        "receipt_path": str(receipt_path.resolve()),
                        "payload": simulated_payload,
                    },
                }

            # Live submission
            if engine == "browser":
                result = execute_browser_submission(
                    form=target_form,
                    fill_plan=fill_plan_items,
                    target_url=url or target_form.action,
                    output_dir=out_dir,
                    save_screenshot=save_screenshot,
                )
            else:
                assembled_payload = assemble_submission_payload(
                    target_form, fill_plan_items
                )
                result = execute_http_submission(
                    form=target_form,
                    payload=assembled_payload,
                    base_url=url,
                    output_dir=out_dir,
                )

            status = "success" if result.get("success") else "error"
            return {
                "status": status,
                "action": "submit",
                "dry_run": False,
                "form_action": target_form.action,
                "submission_result": result,
                "error": result.get("error"),
            }

        return {
            "status": "error",
            "action": action,
            "error": f"Unknown action: {action!r}",
        }

    async def aexecute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Asynchronous execution parity (runs blocking parse/dispatch in threadpool)."""
        return await asyncio.to_thread(self.execute, params)

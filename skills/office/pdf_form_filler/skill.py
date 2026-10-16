# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

from typing import Dict, Any, Optional
import os
import json
import warnings
import fitz
import yaml
from skillware.core.base_skill import BaseSkill

# Optional lazy reference for deprecated legacy one-shot prompt execution
try:
    import anthropic
except ImportError:
    import types

    anthropic = types.ModuleType("anthropic")
    anthropic.Anthropic = None
# works when the bundle is imported as a package. Fall back to the package path,
# then load the sibling utils.py under a unique module name. Do not modify
# sys.path or import a top-level "utils" module, which can clash with the host.
try:
    from .utils import (
        detect_form_fields,
        apply_edits,
        apply_edits_detailed,
        validate_edits,
        is_xfa_form,
        FieldEdit,
    )
except (ImportError, ValueError):
    try:
        from skills.office.pdf_form_filler.utils import (
            detect_form_fields,
            apply_edits,
            apply_edits_detailed,
            validate_edits,
            is_xfa_form,
            FieldEdit,
        )
    except (ImportError, ValueError):
        import importlib.util

        _utils_spec = importlib.util.spec_from_file_location(
            "pdf_form_filler_utils",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "utils.py"),
        )
        if _utils_spec and _utils_spec.loader:
            _utils_module = importlib.util.module_from_spec(_utils_spec)
            _utils_spec.loader.exec_module(_utils_module)
            detect_form_fields = _utils_module.detect_form_fields
            apply_edits = _utils_module.apply_edits
            apply_edits_detailed = _utils_module.apply_edits_detailed
            validate_edits = _utils_module.validate_edits
            is_xfa_form = _utils_module.is_xfa_form
            FieldEdit = _utils_module.FieldEdit
        else:
            raise ImportError("Could not load utils.py for office/pdf_form_filler")


class PDFFormFillerSkill(BaseSkill):
    """
    Host-agnostic deterministic AcroForm PDF inspection, validation, and filling engine.

    Supports discrete actions ('inspect', 'validate', 'fill') with XFA guards,
    radio group normalization, and optional permanent page flattening.
    """

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def execute(self, params: Dict[str, Any]) -> Any:
        if not isinstance(params, dict):
            return {"status": "error", "message": "Parameters must be a dictionary."}

        action = params.get("action")
        pdf_path = params.get("pdf_path")

        # Backward compatibility shim: if no explicit action provided
        if not action:
            if "edits" in params:
                action = "fill"
            elif "instructions" in params:
                return self._legacy_execute(params)
            else:
                return {
                    "status": "error",
                    "message": (
                        "Missing 'action' parameter. Supported actions: 'inspect', 'validate', 'fill'. "
                        "For legacy one-shot prompt filling, supply 'instructions'."
                    ),
                }

        action = str(action).strip().lower()

        if not pdf_path:
            return {
                "status": "error",
                "message": "Missing required parameter 'pdf_path'.",
            }

        if not os.path.exists(pdf_path):
            return {
                "status": "error",
                "error": f"PDF file not found: {pdf_path}",
                "message": f"PDF file not found: {pdf_path}",
            }

        try:
            with open(pdf_path, "rb") as f:
                pdf_bytes = f.read()
        except Exception as e:
            return {
                "status": "error",
                "message": f"Failed to read PDF file '{pdf_path}': {str(e)}",
            }

        if action == "inspect":
            return self._action_inspect(pdf_bytes, pdf_path)
        elif action == "validate":
            edits = params.get("edits")
            if edits is None or not isinstance(edits, dict):
                return {
                    "status": "error",
                    "message": "Missing or invalid 'edits' dictionary for action 'validate'.",
                }
            return self._action_validate(pdf_bytes, edits)
        elif action == "fill":
            edits = params.get("edits")
            if edits is None or not isinstance(edits, dict):
                return {
                    "status": "error",
                    "message": "Missing or invalid 'edits' dictionary for action 'fill'.",
                }
            if not edits:
                return {"status": "no_change", "message": "No edits provided to fill."}
            output_path = params.get("output_path")
            confirmed = bool(params.get("confirmed", False))
            flatten = bool(params.get("flatten", False))
            return self._action_fill(
                pdf_bytes, pdf_path, edits, output_path, confirmed, flatten
            )
        else:
            return {
                "status": "error",
                "message": f"Unknown action '{action}'. Supported actions: 'inspect', 'validate', 'fill'.",
            }

    def _action_inspect(self, pdf_bytes: bytes, pdf_path: str) -> Dict[str, Any]:
        """Inspect PDF form fields with early XFA dynamic form detection."""
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as exc:
            return {"status": "error", "message": f"Invalid PDF format: {str(exc)}"}

        try:
            if is_xfa_form(doc):
                return {
                    "status": "error",
                    "error_code": "unsupported_xfa_form",
                    "message": (
                        "Dynamic XFA (Adobe LiveCycle) forms are not supported for direct widget "
                        "manipulation. Please convert or flatten the form to standard static AcroForm "
                        "before filling."
                    ),
                }
            page_count = len(doc)
        finally:
            doc.close()

        fields = detect_form_fields(pdf_bytes)
        return {
            "status": "ok",
            "page_count": page_count,
            "field_count": len(fields),
            "is_xfa": False,
            "fields": [f.to_dict() for f in fields],
        }

    def _action_validate(
        self, pdf_bytes: bytes, edits: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate proposed field edits without writing to disk."""
        return validate_edits(pdf_bytes, edits)

    def _action_fill(
        self,
        pdf_bytes: bytes,
        pdf_path: str,
        edits: Dict[str, Any],
        output_path: Optional[str],
        confirmed: bool,
        flatten: bool,
    ) -> Dict[str, Any]:
        """Fill form fields with safety confirmation gate and optional vector flattening."""
        if not output_path:
            base, ext = os.path.splitext(pdf_path)
            output_path = f"{base}_filled{ext}"

        # Safety Gate
        if not confirmed:
            return {
                "status": "needs_input",
                "message": "Confirmation required before filling PDF. Set confirmed=True to proceed.",
                "preview": {
                    "pdf_path": pdf_path,
                    "proposed_edits": edits,
                    "output_path": output_path,
                    "flatten": flatten,
                    "field_count": len(edits),
                },
            }

        try:
            filled_bytes, applied_fields = apply_edits_detailed(
                pdf_bytes, edits, flatten=flatten
            )
        except ValueError as ve:
            if "XFA" in str(ve):
                return {
                    "status": "error",
                    "error_code": "unsupported_xfa_form",
                    "message": str(ve),
                }
            return {"status": "error", "message": str(ve)}
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to apply edits to PDF: {str(e)}",
                "message": f"Failed to apply edits to PDF: {str(e)}",
            }

        try:
            with open(output_path, "wb") as f:
                f.write(filled_bytes)
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to write output PDF '{output_path}': {str(e)}",
                "message": f"Failed to write output PDF '{output_path}': {str(e)}",
            }

        return {
            "status": "success",
            "output_path": output_path,
            "filled_fields": applied_fields,
            "message": f"Successfully filled {len(applied_fields)} fields.",
            "flattened": flatten,
        }

    def _legacy_execute(self, params: Dict[str, Any]) -> Any:
        """Deprecated legacy one-shot prompt execution path."""
        pdf_path = params.get("pdf_path")
        instructions = params.get("instructions")
        output_path = params.get("output_path")

        if not pdf_path or not os.path.exists(pdf_path):
            return {"error": f"PDF file not found: {pdf_path}"}

        if not instructions:
            return {"error": "No instructions provided."}

        api_key = self.credential("ANTHROPIC_API_KEY")
        if not api_key:
            return {
                "error": "Missing ANTHROPIC_API_KEY environment variable.",
                "message": (
                    "Missing ANTHROPIC_API_KEY for legacy one-shot prompt mode. "
                    "In Skillware, the host model drives reasoning: use action='inspect' to "
                    "discover fields, map values in your host loop, and call action='fill' with 'edits'."
                ),
            }

        warnings.warn(
            "office/pdf_form_filler: One-shot prompt execution with 'instructions' and internal "
            "Anthropic client is deprecated. Please migrate to the host-agnostic multi-action "
            "protocol ('inspect' -> 'validate' -> 'fill').",
            DeprecationWarning,
            stacklevel=2,
        )

        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()

        fields = detect_form_fields(pdf_bytes)
        if not fields:
            return {"status": "warning", "message": "No fillable fields found in PDF."}

        if getattr(anthropic, "Anthropic", None) is None:
            return {
                "error": (
                    "anthropic package is required for legacy instructions mode. "
                    "Install with: pip install 'skillware[claude]'"
                ),
            }

        client = anthropic.Anthropic(api_key=api_key)

        inst_path = os.path.join(os.path.dirname(__file__), "instructions.md")
        system_prompt = "You are a form filling assistant."
        if os.path.exists(inst_path):
            with open(inst_path, "r", encoding="utf-8") as f:
                system_prompt = f.read()

        fields_context = [f.to_dict() for f in fields]
        user_message = f"""
        User Instructions: {instructions}

        Detected Fields:
        {json.dumps(fields_context, indent=2)}

        Return a JSON object mapping field_ids to values.
        """

        try:
            message = client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=4096,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            response_text = message.content[0].text

            json_str = response_text.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            edits = json.loads(json_str)
        except Exception as e:
            return {"error": f"LLM processing failed: {str(e)}"}

        if not edits:
            return {
                "status": "no_change",
                "message": "LLM determined no fields needed to be changed.",
            }

        try:
            edits_list = [FieldEdit(field_id=k, value=v) for k, v in edits.items()]
            filled_pdf_bytes = apply_edits(pdf_bytes, edits_list)

            if not output_path:
                base, ext = os.path.splitext(pdf_path)
                output_path = f"{base}_filled{ext}"

            with open(output_path, "wb") as f:
                f.write(filled_pdf_bytes)

            return {
                "status": "success",
                "output_path": output_path,
                "filled_fields": list(edits.keys()),
                "message": f"Successfully filled {len(edits)} fields.",
            }
        except Exception as e:
            return {"error": f"Failed to apply edits to PDF: {str(e)}"}

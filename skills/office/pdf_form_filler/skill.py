# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

from datetime import datetime, timezone
import importlib.util
import os
from pathlib import Path
from typing import Any, Dict, Optional

import fitz
import yaml
from skillware.core.base_skill import BaseSkill

try:
    from .utils import (
        FieldEdit,
        apply_edits,
        apply_edits_detailed,
        detect_form_fields,
        is_xfa_form,
        validate_edits,
    )
    from .kb.registry import (
        build_default_output_path,
        get_template_schema,
        list_templates,
        load_schema_file,
        map_edits_with_schema,
        redact_sensitive_edits,
    )
    from .session import (
        DEFAULT_SESSION_TTL_SECONDS,
        build_session_fields_from_schema,
        compute_session_progress,
        create_session_record,
        load_session_record,
        resolve_sessions_dir,
        save_session_record,
    )
except (ImportError, ValueError):
    try:
        from skills.office.pdf_form_filler.utils import (
            FieldEdit,
            apply_edits,
            apply_edits_detailed,
            detect_form_fields,
            is_xfa_form,
            validate_edits,
        )
        from skills.office.pdf_form_filler.kb.registry import (
            build_default_output_path,
            get_template_schema,
            list_templates,
            load_schema_file,
            map_edits_with_schema,
            redact_sensitive_edits,
        )
        from skills.office.pdf_form_filler.session import (
            DEFAULT_SESSION_TTL_SECONDS,
            build_session_fields_from_schema,
            compute_session_progress,
            create_session_record,
            load_session_record,
            resolve_sessions_dir,
            save_session_record,
        )
    except (ImportError, ValueError):
        _base_dir = os.path.dirname(os.path.abspath(__file__))

        def _load_sibling(name: str, rel_path: str):
            spec = importlib.util.spec_from_file_location(
                name, os.path.join(_base_dir, rel_path)
            )
            if not spec or not spec.loader:
                raise ImportError(
                    f"Could not load {rel_path} for office/pdf_form_filler"
                )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod

        _utils_module = _load_sibling("pdf_form_filler_utils", "utils.py")
        detect_form_fields = _utils_module.detect_form_fields
        apply_edits = _utils_module.apply_edits
        apply_edits_detailed = _utils_module.apply_edits_detailed
        validate_edits = _utils_module.validate_edits
        is_xfa_form = _utils_module.is_xfa_form
        FieldEdit = _utils_module.FieldEdit

        _reg_module = _load_sibling(
            "pdf_form_filler_kb_registry", os.path.join("kb", "registry.py")
        )
        list_templates = _reg_module.list_templates
        get_template_schema = _reg_module.get_template_schema
        load_schema_file = _reg_module.load_schema_file
        map_edits_with_schema = _reg_module.map_edits_with_schema
        redact_sensitive_edits = _reg_module.redact_sensitive_edits
        build_default_output_path = _reg_module.build_default_output_path

        _sess_module = _load_sibling("pdf_form_filler_session", "session.py")
        DEFAULT_SESSION_TTL_SECONDS = _sess_module.DEFAULT_SESSION_TTL_SECONDS
        build_session_fields_from_schema = _sess_module.build_session_fields_from_schema
        compute_session_progress = _sess_module.compute_session_progress
        create_session_record = _sess_module.create_session_record
        load_session_record = _sess_module.load_session_record
        resolve_sessions_dir = _sess_module.resolve_sessions_dir
        save_session_record = _sess_module.save_session_record


class PDFFormFillerSkill(BaseSkill):
    """
    Host-agnostic deterministic AcroForm PDF inspection, validation, and filling engine.

    Supports curated static AcroForm KB templates ('list_templates', 'get_template_schema')
    and form operations ('inspect', 'validate', 'fill') with XFA guards, PII redaction,
    radio group normalization, and optional permanent page flattening.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
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
        if not action:
            if "edits" in params:
                action = "fill"
            elif params.get("template_id") and not params.get("pdf_path"):
                action = "get_template_schema"
            else:
                action = "inspect"

        action = str(action).strip().lower()
        supported = (
            "list_templates",
            "get_template_schema",
            "session_init",
            "session_update",
            "session_preview",
            "session_finalize",
            "inspect",
            "validate",
            "fill",
        )
        if action not in supported:
            return {
                "status": "error",
                "message": (
                    f"Unsupported action '{action}'. "
                    f"Supported actions: {', '.join(supported)}."
                ),
            }

        if action == "list_templates":
            return self._action_list_templates(
                category=params.get("category"),
                jurisdiction=params.get("jurisdiction"),
            )

        if action == "get_template_schema":
            template_id = params.get("template_id")
            if not template_id:
                return {
                    "status": "error",
                    "message": "Missing required parameter 'template_id' for action 'get_template_schema'.",
                }
            return self._action_get_template_schema(
                template_id=str(template_id),
                section=params.get("section"),
            )

        if action == "session_init":
            return self._action_session_init(params)

        if action == "session_update":
            return self._action_session_update(params)

        if action == "session_preview":
            return self._action_session_preview(params)

        if action == "session_finalize":
            return self._action_session_finalize(params)

        # Resolve PDF path + optional schema from template_id or explicit paths
        pdf_path = params.get("pdf_path")
        template_id = params.get("template_id")
        schema_path = params.get("schema_path")
        schema: Optional[Dict[str, Any]] = None

        if schema_path:
            sp = Path(str(schema_path))
            if not sp.is_file():
                return {
                    "status": "error",
                    "message": f"Schema file not found: {schema_path}",
                }
            try:
                schema = load_schema_file(sp)
            except Exception as exc:
                return {
                    "status": "error",
                    "message": f"Invalid schema '{schema_path}': {exc}",
                }

        if template_id and not pdf_path:
            try:
                schema = get_template_schema(
                    str(template_id),
                    env_templates_dir=self.credential("PDF_TEMPLATES_DIR"),
                )
            except KeyError as exc:
                return {"status": "error", "message": str(exc)}
            pdf_path = schema.get("_pdf_path") or ""

        if not pdf_path:
            return {
                "status": "error",
                "message": "Missing required parameter 'pdf_path' (or 'template_id').",
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

        edits = params.get("edits")
        if edits is None or not isinstance(edits, dict):
            return {
                "status": "error",
                "message": f"Missing or invalid 'edits' dictionary for action '{action}'.",
            }

        if action == "validate":
            return self._action_validate(
                pdf_bytes,
                edits,
                schema=schema,
                auto_date=bool(params.get("auto_date", True)),
                check_required=bool(params.get("check_required", schema is not None)),
            )

        # action == "fill"
        if not edits:
            return {"status": "no_change", "message": "No edits provided to fill."}

        return self._action_fill(
            pdf_bytes,
            pdf_path,
            edits,
            output_path=params.get("output_path"),
            output_dir=params.get("output_dir"),
            filler_name=params.get("filler_name"),
            confirmed=bool(params.get("confirmed", False)),
            flatten=bool(params.get("flatten", False)),
            schema=schema,
            template_id=str(template_id) if template_id else None,
            auto_date=bool(params.get("auto_date", True)),
        )

    def _action_list_templates(
        self,
        *,
        category: Optional[str] = None,
        jurisdiction: Optional[str] = None,
    ) -> Dict[str, Any]:
        templates = list_templates(
            category=category,
            jurisdiction=jurisdiction,
            env_templates_dir=self.credential("PDF_TEMPLATES_DIR"),
        )
        return {
            "status": "ok",
            "count": len(templates),
            "templates": templates,
        }

    def _action_get_template_schema(
        self,
        *,
        template_id: str,
        section: Optional[str] = None,
    ) -> Dict[str, Any]:
        try:
            data = get_template_schema(
                template_id=template_id,
                section=section,
                env_templates_dir=self.credential("PDF_TEMPLATES_DIR"),
            )
        except KeyError as exc:
            return {"status": "error", "message": str(exc)}
        # Strip internal filesystem path before returning to callers
        public_data = {k: v for k, v in data.items() if not k.startswith("_")}
        return {"status": "ok", **public_data}

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
        self,
        pdf_bytes: bytes,
        edits: Dict[str, Any],
        *,
        schema: Optional[Dict[str, Any]] = None,
        auto_date: bool = True,
        check_required: bool = False,
    ) -> Dict[str, Any]:
        """Validate proposed field edits without writing to disk."""
        if schema is not None:
            mapped, sensitive_keys, schema_errors = map_edits_with_schema(
                schema, edits, auto_date=auto_date, check_required=check_required
            )
            if schema_errors:
                return {
                    "status": "error",
                    "valid": False,
                    "errors": schema_errors,
                    "sensitive_fields": sorted(sensitive_keys),
                    "message": f"Schema validation failed for {len(schema_errors)} field(s).",
                }
            res = validate_edits(pdf_bytes, mapped)
            res["sensitive_fields"] = sorted(sensitive_keys)
            return res

        return validate_edits(pdf_bytes, edits)

    def _action_fill(
        self,
        pdf_bytes: bytes,
        pdf_path: str,
        edits: Dict[str, Any],
        output_path: Optional[str],
        output_dir: Optional[str],
        filler_name: Optional[str],
        confirmed: bool,
        flatten: bool,
        schema: Optional[Dict[str, Any]] = None,
        template_id: Optional[str] = None,
        auto_date: bool = True,
    ) -> Dict[str, Any]:
        """Fill form fields with safety confirmation gate, PII redaction, and optional flattening."""
        sensitive_keys: set[str] = set()
        mapped_edits = edits

        if schema is not None:
            mapped_edits, sensitive_keys, schema_errors = map_edits_with_schema(
                schema, edits, auto_date=auto_date, check_required=True
            )
            if schema_errors:
                return {
                    "status": "error",
                    "valid": False,
                    "errors": schema_errors,
                    "message": f"Schema validation failed for {len(schema_errors)} field(s).",
                }

        if not output_path:
            if template_id:
                output_path = build_default_output_path(
                    template_id,
                    edits,
                    filler_name=filler_name,
                    output_dir=output_dir,
                )
            else:
                base, ext = os.path.splitext(pdf_path)
                output_path = f"{base}_filled{ext}"

        # Safety Gate (redact sensitive PII in preview)
        if not confirmed:
            preview_edits = (
                redact_sensitive_edits(edits, sensitive_keys)
                if sensitive_keys
                else edits
            )
            return {
                "status": "needs_input",
                "message": "Confirmation required before filling PDF. Set confirmed=True to proceed.",
                "preview": {
                    "pdf_path": pdf_path,
                    "template_id": template_id,
                    "proposed_edits": preview_edits,
                    "redacted_fields": sorted(k for k in edits if k in sensitive_keys),
                    "output_path": output_path,
                    "flatten": flatten,
                    "field_count": len(mapped_edits),
                },
            }

        try:
            filled_bytes, applied_fields = apply_edits_detailed(
                pdf_bytes, mapped_edits, flatten=flatten
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
            out_parent = os.path.dirname(os.path.abspath(output_path))
            if out_parent:
                os.makedirs(out_parent, exist_ok=True)
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

    # ------------------------------------------------------------------
    # Conversational Interview Session State Machine (#405)
    # ------------------------------------------------------------------

    def _sessions_dir(self, params: Dict[str, Any]) -> Path:
        return resolve_sessions_dir(
            session_dir=params.get("session_dir"),
            env_sessions_dir=self.credential("PDF_SESSIONS_DIR"),
        )

    def _action_session_init(self, params: Dict[str, Any]) -> Dict[str, Any]:
        template_id = params.get("template_id")
        pdf_path = params.get("pdf_path")
        schema_path = params.get("schema_path")
        ttl_seconds = int(params.get("ttl_seconds", DEFAULT_SESSION_TTL_SECONDS))

        schema: Optional[Dict[str, Any]] = None
        if schema_path:
            sp = Path(str(schema_path))
            if not sp.is_file():
                return {
                    "status": "error",
                    "message": f"Schema file not found: {schema_path}",
                }
            try:
                schema = load_schema_file(sp)
            except Exception as exc:
                return {
                    "status": "error",
                    "message": f"Invalid schema '{schema_path}': {exc}",
                }

        if template_id and not pdf_path:
            try:
                schema = get_template_schema(
                    str(template_id),
                    env_templates_dir=self.credential("PDF_TEMPLATES_DIR"),
                )
            except KeyError as exc:
                return {"status": "error", "message": str(exc)}
            pdf_path = schema.get("_pdf_path") or ""

        if not pdf_path or not os.path.exists(str(pdf_path)):
            return {
                "status": "error",
                "message": "Missing or invalid 'pdf_path' / 'template_id' for session_init.",
            }

        if schema is not None:
            fields_meta = build_session_fields_from_schema(schema)
            sections_index = schema.get("sections_index") or [
                {
                    "id": s.get("id"),
                    "title": s.get("title"),
                    "field_count": len(s.get("fields") or []),
                }
                for s in (schema.get("sections") or [])
                if isinstance(s, dict)
            ]
        else:
            pdf_bytes = Path(str(pdf_path)).read_bytes()
            detected = detect_form_fields(pdf_bytes)
            fields_meta = [
                {
                    "id": f.field_id,
                    "pdf_field_name": f.native_name,
                    "section_id": f"page_{f.page}",
                    "field_type": f.type,
                    "label": f.label_context or f.field_id,
                    "required": False,
                    "sensitive": False,
                    "signature_mode": None,
                    "date_format": None,
                    "options": f.options,
                }
                for f in detected
            ]
            sections_index = []

        record = create_session_record(
            template_id=str(template_id) if template_id else None,
            pdf_path=str(pdf_path),
            schema_path=str(schema_path) if schema_path else None,
            fields_meta=fields_meta,
            sections_index=sections_index,
            sessions_dir=self._sessions_dir(params),
            ttl_seconds=ttl_seconds,
        )
        progress_info = compute_session_progress(record)
        return {
            "status": "ok",
            "session_id": record["session_id"],
            "template_id": record["template_id"],
            "expires_at": record["expires_at"],
            "sections_index": sections_index,
            **progress_info,
        }

    def _action_session_update(self, params: Dict[str, Any]) -> Dict[str, Any]:
        session_id = params.get("session_id")
        if not session_id:
            return {
                "status": "error",
                "message": "Missing required parameter 'session_id'.",
            }

        sdir = self._sessions_dir(params)
        record, err = load_session_record(str(session_id), sdir)
        if err or record is None:
            return err or {"status": "error", "message": "Session load failed."}

        if record.get("finalized"):
            return {
                "status": "error",
                "error_code": "session_finalized",
                "message": f"Session '{session_id}' is already finalized.",
            }

        meta_by_id = {f["id"]: f for f in record.get("fields_meta") or []}
        states = record.setdefault("field_states", {})
        now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        values = params.get("values") or {}
        skip_fields = params.get("skip_fields") or []
        defer_fields = params.get("defer_fields") or []

        if values:
            if not isinstance(values, dict):
                return {"status": "error", "message": "'values' must be a dictionary."}
            # Validate against schema if template_id/schema_path is present
            schema = None
            if record.get("template_id"):
                schema = get_template_schema(
                    str(record["template_id"]),
                    env_templates_dir=self.credential("PDF_TEMPLATES_DIR"),
                )
            elif record.get("schema_path"):
                schema = load_schema_file(Path(str(record["schema_path"])))

            if schema is not None:
                _, _, schema_errors = map_edits_with_schema(
                    schema, values, auto_date=False, check_required=False
                )
                if schema_errors:
                    return {
                        "status": "error",
                        "valid": False,
                        "errors": schema_errors,
                        "message": f"Validation failed for {len(schema_errors)} field(s).",
                    }

            for fid, val in values.items():
                if fid not in meta_by_id:
                    return {
                        "status": "error",
                        "message": f"Unknown field '{fid}' for session '{session_id}'.",
                    }
                states[fid] = {"status": "filled", "value": val, "updated_at": now_iso}

        for fid in skip_fields:
            if fid not in meta_by_id:
                return {
                    "status": "error",
                    "message": f"Unknown field '{fid}' in skip_fields.",
                }
            states[fid] = {
                "status": "skipped",
                "reason": "user_opt_out",
                "updated_at": now_iso,
            }

        if isinstance(defer_fields, dict):
            defer_items = list(defer_fields.items())
        else:
            defer_items = [(fid, "deferred_by_user") for fid in defer_fields]

        for fid, note in defer_items:
            if fid not in meta_by_id:
                return {
                    "status": "error",
                    "message": f"Unknown field '{fid}' in defer_fields.",
                }
            states[fid] = {
                "status": "to_revise",
                "note": str(note),
                "updated_at": now_iso,
            }

        save_session_record(record, sdir)
        progress_info = compute_session_progress(record)
        return {
            "status": (
                "needs_input"
                if progress_info["progress"]["remaining_required_count"] > 0
                or progress_info["progress"]["to_revise_count"] > 0
                else "ready"
            ),
            "session_id": record["session_id"],
            **progress_info,
        }

    def _action_session_preview(self, params: Dict[str, Any]) -> Dict[str, Any]:
        session_id = params.get("session_id")
        if not session_id:
            return {
                "status": "error",
                "message": "Missing required parameter 'session_id'.",
            }

        sdir = self._sessions_dir(params)
        record, err = load_session_record(str(session_id), sdir)
        if err or record is None:
            return err or {"status": "error", "message": "Session load failed."}

        unmask = bool(params.get("unmask", False))
        states = record.get("field_states") or {}
        today_mmddyyyy = datetime.now(timezone.utc).strftime("%m-%d-%Y")

        summary_table: Dict[str, Any] = {}
        all_required_resolved = True

        for f in record.get("fields_meta") or []:
            fid = f["id"]
            label = f.get("label") or fid
            st_obj = states.get(fid, {"status": "empty"})
            st = st_obj.get("status", "empty")

            if st == "filled":
                val = st_obj.get("value")
                if f.get("sensitive") and not unmask and val is not None:
                    s = str(val)
                    val_disp: Any = f"***{s[-4:]}" if len(s) > 4 else "***REDACTED***"
                elif (
                    f.get("signature_mode") == "typed_e_sign"
                    and f.get("field_type") == "signature"
                ):
                    val_disp = f"/s/ {val} (typed e-signature)"
                else:
                    val_disp = val
                summary_table[label] = val_disp
            elif st == "skipped":
                summary_table[label] = "[SKIPPED]"
            elif st == "to_revise":
                summary_table[label] = "[TO REVISE]"
                if f.get("required"):
                    all_required_resolved = False
            else:
                if f.get("signature_mode") == "auto_date":
                    summary_table[label] = f"{today_mmddyyyy} (Auto-date)"
                elif f.get("signature_mode") == "leave_blank_for_wet_sign":
                    summary_table[label] = "[BLANK FOR WET SIGNATURE]"
                else:
                    summary_table[label] = "[EMPTY]"
                    if f.get("required"):
                        all_required_resolved = False

        return {
            "status": "preview",
            "session_id": record["session_id"],
            "all_required_resolved": all_required_resolved,
            "summary_table": summary_table,
            "message": (
                "All required fields addressed. Review the values and pass confirmed=True to session_finalize."
                if all_required_resolved
                else "Some required fields are still empty or marked to_revise."
            ),
        }

    def _action_session_finalize(self, params: Dict[str, Any]) -> Dict[str, Any]:
        session_id = params.get("session_id")
        if not session_id:
            return {
                "status": "error",
                "message": "Missing required parameter 'session_id'.",
            }

        sdir = self._sessions_dir(params)
        record, err = load_session_record(str(session_id), sdir)
        if err or record is None:
            return err or {"status": "error", "message": "Session load failed."}

        if not bool(params.get("confirmed", False)):
            return {
                "status": "needs_input",
                "error_code": "confirmation_required",
                "session_id": record["session_id"],
                "message": "Explicit confirmed=True is required before finalizing and writing the PDF.",
            }

        states = record.get("field_states") or {}
        today_mmddyyyy = datetime.now(timezone.utc).strftime("%m-%d-%Y")
        native_edits: Dict[str, Any] = {}
        semantic_edits: Dict[str, Any] = {}

        for f in record.get("fields_meta") or []:
            fid = f["id"]
            pname = f.get("pdf_field_name") or fid
            st_obj = states.get(fid, {"status": "empty"})
            st = st_obj.get("status", "empty")
            sig_mode = f.get("signature_mode")

            if st == "filled":
                val = st_obj.get("value")
                if sig_mode == "typed_e_sign" and f.get("field_type") == "signature":
                    val_s = str(val).strip()
                    val = val_s if val_s.startswith("/s/") else f"/s/ {val_s}"
                native_edits[pname] = val
                semantic_edits[fid] = val
            elif st == "empty" and sig_mode == "auto_date":
                native_edits[pname] = today_mmddyyyy
                semantic_edits[fid] = today_mmddyyyy
            elif sig_mode == "leave_blank_for_wet_sign":
                continue

        pdf_path = record["pdf_path"]
        pdf_bytes = Path(pdf_path).read_bytes()
        flatten = bool(params.get("flatten", True))
        output_path = params.get("output_path")
        if not output_path:
            if record.get("template_id"):
                output_path = build_default_output_path(
                    str(record["template_id"]),
                    semantic_edits,
                    filler_name=params.get("filler_name"),
                    output_dir=params.get("output_dir"),
                )
            else:
                base, ext = os.path.splitext(pdf_path)
                output_path = f"{base}_filled{ext}"

        filled_bytes, applied_fields = apply_edits_detailed(
            pdf_bytes, native_edits, flatten=flatten
        )
        out_parent = os.path.dirname(os.path.abspath(output_path))
        if out_parent:
            os.makedirs(out_parent, exist_ok=True)
        Path(output_path).write_bytes(filled_bytes)

        record["finalized"] = True
        record["output_path"] = output_path
        save_session_record(record, sdir)

        return {
            "status": "success",
            "session_id": record["session_id"],
            "output_path": output_path,
            "filled_fields": applied_fields,
            "flattened": flatten,
            "message": f"Successfully finalized session and filled {len(applied_fields)} fields.",
        }

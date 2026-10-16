# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

from dataclasses import dataclass
from enum import Enum
import re
from typing import List, Optional, Dict, Any, Tuple, Union

import fitz  # PyMuPDF


class FieldType(Enum):
    TEXT = "text"
    CHECKBOX = "checkbox"
    DROPDOWN = "dropdown"
    RADIO = "radio"


@dataclass
class DetectedField:
    """Represents a detected form field in the PDF."""

    field_id: str
    native_name: str
    type: str  # "text", "checkbox", "dropdown", "radio"
    page: int
    bbox: List[float]  # [x0, y0, x1, y1]
    label_context: str  # nearby text for semantic understanding
    current_value: Optional[Any] = None
    options: Optional[Any] = None

    @property
    def field_type(self) -> FieldType:
        try:
            return FieldType(self.type)
        except ValueError:
            return FieldType.TEXT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "field_id": self.field_id,
            "native_name": self.native_name,
            "type": self.type,
            "field_type": self.type,  # backward compatibility alias
            "page": self.page,
            "bbox": self.bbox,
            "label_context": self.label_context,
            "current_value": self.current_value,
            "options": self.options,
        }


@dataclass
class FieldEdit:
    """Legacy and typed edit descriptor."""

    field_id: str
    value: Any


def is_xfa_form(doc: fitz.Document) -> bool:
    """Check if the PDF contains a dynamic XFA (Adobe LiveCycle) form."""
    if hasattr(doc, "is_xfa") and getattr(doc, "is_xfa"):
        return True
    try:
        cat_xref = doc.pdf_catalog()
        acro_val = doc.xref_get_key(cat_xref, "AcroForm/XFA")
        if acro_val[0] not in ("null", "undefined"):
            return True

        acro_type, acro_str = doc.xref_get_key(cat_xref, "AcroForm")
        if acro_type == "xref":
            acro_xref = int(acro_str.replace("0 R", "").strip())
            xfa_val = doc.xref_get_key(acro_xref, "XFA")
            if xfa_val[0] not in ("null", "undefined"):
                return True
    except Exception:
        pass
    return False


def _widget_type_to_field_type(widget_type: int) -> FieldType:
    mapping = {
        7: FieldType.TEXT,  # PDF_WIDGET_TYPE_TEXT
        2: FieldType.CHECKBOX,  # PDF_WIDGET_TYPE_CHECKBOX
        3: FieldType.DROPDOWN,  # PDF_WIDGET_TYPE_COMBOBOX
        4: FieldType.DROPDOWN,  # PDF_WIDGET_TYPE_LISTBOX
        5: FieldType.RADIO,  # PDF_WIDGET_TYPE_RADIOBUTTON
    }
    return mapping.get(widget_type, FieldType.TEXT)


def _extract_nearby_text(page: fitz.Page, rect: fitz.Rect, radius: int = 100) -> str:
    """Extract text near a bounding box to understand field context."""
    search_rect = fitz.Rect(rect)
    search_rect.x0 -= radius
    search_rect.y0 -= radius
    search_rect.x1 += radius
    search_rect.y1 += radius

    # Clip to page bounds
    page_rect = page.rect
    search_rect.intersect(page_rect)

    text = page.get_text("text", clip=search_rect).strip()
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    return " | ".join(lines)


def _clean_field_id_name(raw_name: str) -> str:
    """Extract a clean short identifier from hierarchical AcroForm field names."""
    if not raw_name:
        return "unnamed"
    parts = raw_name.replace("]", "").split(".")
    leaf = parts[-1].split("[")[0] if parts else raw_name
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", leaf).strip("_")
    if not clean or clean.isdigit():
        clean = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_name).strip("_")
    return clean or "field"


def _extract_radio_export_value(widget: fitz.Widget) -> str:
    """Safely extract the on/export value for a radio button widget."""
    try:
        on_val = widget.on_state()
        if on_val and on_val not in (True, False, "Off"):
            return str(on_val).lstrip("/")
    except Exception:
        pass

    try:
        states = widget.button_states()
        if states and isinstance(states, dict) and "normal" in states:
            for s in states["normal"] or []:
                if s and str(s).lower() not in ("off", "/off"):
                    return str(s).lstrip("/")
    except Exception:
        pass

    caption = getattr(widget, "button_caption", None)
    if caption:
        return str(caption).strip()

    return "Yes"


def detect_form_fields(pdf_bytes: bytes) -> List[DetectedField]:
    """
    Detect and normalize all fillable AcroForm fields in the PDF.

    Groups radio buttons sharing the same field_name on each page into a
    single cohesive radio field with options and export values.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    fields: List[DetectedField] = []

    try:
        if is_xfa_form(doc):
            return []

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Separate radio button widgets from other widgets to group them
            radio_groups: Dict[str, List[Tuple[fitz.Widget, fitz.Rect]]] = {}
            standard_widgets: List[fitz.Widget] = []

            for widget in page.widgets():
                if not widget.field_name:
                    continue

                if widget.field_type == 5:  # PDF_WIDGET_TYPE_RADIOBUTTON
                    group_name = widget.field_name
                    if group_name not in radio_groups:
                        radio_groups[group_name] = []
                    radio_groups[group_name].append((widget, fitz.Rect(widget.rect)))
                else:
                    standard_widgets.append(widget)

            # Process standard widgets (text, checkbox, dropdown)
            used_ids_on_page: set[str] = set()
            for widget in standard_widgets:
                ftype = _widget_type_to_field_type(widget.field_type)
                clean_name = _clean_field_id_name(widget.field_name)
                candidate_id = f"page{page_num}_{clean_name}"

                counter = 1
                unique_id = candidate_id
                while unique_id in used_ids_on_page:
                    unique_id = f"{candidate_id}_{counter}"
                    counter += 1
                used_ids_on_page.add(unique_id)

                options = None
                if widget.field_type in (3, 4):  # COMBOBOX, LISTBOX
                    if hasattr(widget, "choice_values") and widget.choice_values:
                        options = list(widget.choice_values)
                    else:
                        options = []

                cur_val = widget.field_value
                if ftype == FieldType.CHECKBOX:
                    if isinstance(cur_val, bool):
                        cur_val = cur_val
                    elif isinstance(cur_val, str):
                        cur_val = cur_val.lower() in ("true", "yes", "1", "on")
                    else:
                        cur_val = False
                elif cur_val is not None:
                    cur_val = str(cur_val)

                label = _extract_nearby_text(page, widget.rect)
                bbox = [round(float(c), 2) for c in widget.rect]

                fields.append(
                    DetectedField(
                        field_id=unique_id,
                        native_name=widget.field_name,
                        type=ftype.value,
                        page=page_num,
                        bbox=bbox,
                        label_context=label,
                        current_value=cur_val,
                        options=options,
                    )
                )

            # Process radio groups
            for group_name, button_tuples in radio_groups.items():
                clean_name = _clean_field_id_name(group_name)
                candidate_id = f"page{page_num}_{clean_name}"
                unique_id = candidate_id
                counter = 1
                while unique_id in used_ids_on_page:
                    unique_id = f"{candidate_id}_{counter}"
                    counter += 1
                used_ids_on_page.add(unique_id)

                group_options = []
                active_export_value = None
                union_rect = None

                for idx, (btn_widget, btn_rect) in enumerate(button_tuples):
                    if union_rect is None:
                        union_rect = fitz.Rect(btn_rect)
                    else:
                        union_rect = union_rect | btn_rect

                    export_val = _extract_radio_export_value(btn_widget)
                    btn_label = _extract_nearby_text(page, btn_rect, radius=50)
                    if not btn_label:
                        btn_label = export_val

                    group_options.append(
                        {
                            "label": btn_label,
                            "export_value": export_val,
                        }
                    )

                    raw_val = btn_widget.field_value
                    if raw_val not in (None, False, "Off", "/Off", 0, ""):
                        active_export_value = export_val

                # Overall group label context (search around whole union bounding box)
                group_label = _extract_nearby_text(
                    page, union_rect or button_tuples[0][1], radius=80
                )
                bbox = (
                    [round(float(c), 2) for c in union_rect]
                    if union_rect
                    else [0.0, 0.0, 0.0, 0.0]
                )

                fields.append(
                    DetectedField(
                        field_id=unique_id,
                        native_name=group_name,
                        type=FieldType.RADIO.value,
                        page=page_num,
                        bbox=bbox,
                        label_context=group_label,
                        current_value=active_export_value,
                        options=group_options,
                    )
                )
    finally:
        doc.close()

    return fields


def validate_edits(pdf_bytes: bytes, edits: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate proposed edits against the PDF form without modifying bytes.

    Verifies field existence, option validity, and radio button export values.
    """
    if not isinstance(edits, dict):
        return {
            "status": "error",
            "valid": False,
            "errors": [{"field": "(root)", "reason": "Edits must be a dictionary."}],
            "message": "Edits must be a dictionary.",
        }

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        if is_xfa_form(doc):
            return {
                "status": "error",
                "valid": False,
                "error_code": "unsupported_xfa_form",
                "message": (
                    "Dynamic XFA (Adobe LiveCycle) forms are not supported for direct widget "
                    "manipulation. Please convert or flatten the form to standard static AcroForm "
                    "before filling."
                ),
            }
    finally:
        doc.close()

    fields = detect_form_fields(pdf_bytes)
    if not fields:
        return {
            "status": "error",
            "valid": False,
            "errors": [
                {"field": "(root)", "reason": "No fillable form fields found in PDF."}
            ],
            "message": "No fillable form fields found in PDF.",
        }

    # Build lookup by both field_id and native_name
    field_map: Dict[str, DetectedField] = {}
    for f in fields:
        field_map[f.field_id] = f
        field_map[f.native_name] = f

    errors: List[Dict[str, str]] = []

    for key, value in edits.items():
        if key not in field_map:
            errors.append(
                {
                    "field": key,
                    "reason": f"Field '{key}' does not exist in the PDF form.",
                }
            )
            continue

        target_field = field_map[key]

        if target_field.type == FieldType.CHECKBOX.value:
            if not isinstance(value, bool):
                val_str = str(value).lower()
                if val_str not in ("true", "false", "1", "0", "yes", "no", "on", "off"):
                    errors.append(
                        {
                            "field": key,
                            "reason": f"Value '{value}' for checkbox '{key}' must be a boolean or boolean string.",
                        }
                    )

        elif target_field.type == FieldType.RADIO.value:
            opts = target_field.options or []
            valid_exports = [
                opt.get("export_value") for opt in opts if isinstance(opt, dict)
            ]
            valid_labels = [opt.get("label") for opt in opts if isinstance(opt, dict)]
            val_str = str(value).strip().lstrip("/")

            matched = False
            for exp in valid_exports:
                if exp and exp.lstrip("/").lower() == val_str.lower():
                    matched = True
                    break
            if not matched:
                for lbl in valid_labels:
                    if lbl and val_str.lower() in lbl.lower():
                        matched = True
                        break

            if not matched:
                errors.append(
                    {
                        "field": key,
                        "reason": (
                            f"Value '{value}' is not a valid option for radio field '{key}'. "
                            f"Allowed export values: {valid_exports}"
                        ),
                    }
                )

        elif target_field.type == FieldType.DROPDOWN.value:
            if target_field.options:
                val_str = str(value).strip()
                if val_str not in target_field.options:
                    errors.append(
                        {
                            "field": key,
                            "reason": (
                                f"Value '{value}' is not among dropdown choices for '{key}'. "
                                f"Allowed choices: {target_field.options}"
                            ),
                        }
                    )

    if errors:
        return {
            "status": "error",
            "valid": False,
            "errors": errors,
            "message": f"Validation failed for {len(errors)} field(s).",
        }

    return {
        "status": "ok",
        "valid": True,
        "field_count": len(edits),
        "validated_fields": list(edits.keys()),
        "message": f"All {len(edits)} proposed edits are valid.",
    }


def apply_edits_detailed(
    pdf_bytes: bytes,
    edits: Union[Dict[str, Any], List[FieldEdit]],
    flatten: bool = False,
) -> Tuple[bytes, List[str]]:
    """
    Apply edits to AcroForm widgets and optionally bake/flatten into permanent graphics.

    Returns tuple of (modified_pdf_bytes, list_of_applied_field_ids).
    """
    if isinstance(edits, list):
        edit_dict = {e.field_id: e.value for e in edits}
    elif isinstance(edits, dict):
        edit_dict = dict(edits)
    else:
        edit_dict = {}

    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    if is_xfa_form(doc):
        doc.close()
        raise ValueError(
            "Dynamic XFA (Adobe LiveCycle) forms are not supported for direct widget manipulation."
        )

    applied_fields: set[str] = set()

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]

            for widget in page.widgets():
                if not widget.field_name:
                    continue

                field_id = f"page{page_num}_{widget.field_name}"
                clean_id = f"page{page_num}_{_clean_field_id_name(widget.field_name)}"
                native_name = widget.field_name

                # Check if this widget is targeted by any edit key
                matched_val = None
                matched_key = None

                for cand_key in (field_id, clean_id, native_name):
                    if cand_key in edit_dict:
                        matched_val = edit_dict[cand_key]
                        matched_key = cand_key
                        break

                if matched_key is None:
                    continue

                # 1. Radio Button Group Handling
                if widget.field_type == 5:  # PDF_WIDGET_TYPE_RADIOBUTTON
                    exp_val = _extract_radio_export_value(widget)
                    target_str = str(matched_val).strip().lstrip("/")

                    # Also check if user passed the label
                    btn_label = _extract_nearby_text(page, widget.rect, radius=50)

                    is_target = False
                    if exp_val and exp_val.lstrip("/").lower() == target_str.lower():
                        is_target = True
                    elif btn_label and target_str.lower() in btn_label.lower():
                        is_target = True

                    if is_target:
                        widget.field_value = exp_val
                    else:
                        widget.field_value = "Off"

                    widget.update()
                    applied_fields.add(matched_key)

                # 2. Checkbox Handling
                elif widget.field_type == 2:  # PDF_WIDGET_TYPE_CHECKBOX
                    if isinstance(matched_val, bool):
                        bool_val = matched_val
                    elif isinstance(matched_val, str):
                        bool_val = matched_val.lower() in (
                            "true",
                            "yes",
                            "1",
                            "on",
                            "checked",
                        )
                    else:
                        bool_val = bool(matched_val)

                    widget.field_value = bool_val
                    widget.update()
                    applied_fields.add(matched_key)

                # 3. Text, Dropdown & other fields
                else:
                    widget.field_value = str(matched_val)
                    widget.update()
                    applied_fields.add(matched_key)

        # 4. Flattening Guard (Convert widgets to permanent page vector graphics)
        if flatten:
            doc.bake(widgets=True, annots=True)

        result_bytes = doc.tobytes()
    finally:
        doc.close()

    return result_bytes, sorted(list(applied_fields))


def apply_edits(
    pdf_bytes: bytes,
    edits: Union[Dict[str, Any], List[FieldEdit]],
    flatten: bool = False,
) -> bytes:
    """Backward-compatible helper returning bytes directly."""
    pdf_out, _ = apply_edits_detailed(pdf_bytes, edits, flatten=flatten)
    return pdf_out

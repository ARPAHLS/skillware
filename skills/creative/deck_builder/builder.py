"""Core PowerPoint (.pptx) builder, validator, and inspector for creative/deck_builder."""

from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import jsonschema
from PIL import Image
import pptx
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches, Pt

_HERE = Path(__file__).resolve().parent
_TEMPLATES_DIR = _HERE / "templates"
_SCHEMA_PATH = _HERE / "schemas" / "deck_spec.schema.json"

TEMPLATES: Dict[str, Dict[str, Any]] = {
    "pitch_v1": {
        "template_id": "pitch_v1",
        "name": "Modern Pitch Deck",
        "description": "Vibrant modern aesthetic with bold typography and purple/indigo accents.",
        "aspect_ratio": "16:9",
        "default_accent": "#6E57E0",
        "default_heading_font": "Calibri",
        "default_body_font": "Calibri",
        "filename": "pitch_v1.pptx",
    },
    "corporate_v1": {
        "template_id": "corporate_v1",
        "name": "Executive Corporate",
        "description": "Structured executive presentation layout with navy and slate accents.",
        "aspect_ratio": "16:9",
        "default_accent": "#1E3A8A",
        "default_heading_font": "Calibri",
        "default_body_font": "Calibri",
        "filename": "corporate_v1.pptx",
    },
    "minimal_v1": {
        "template_id": "minimal_v1",
        "name": "Clean Minimalist",
        "description": "Monochrome high-contrast typography-forward layout for technical decks.",
        "aspect_ratio": "16:9",
        "default_accent": "#262626",
        "default_heading_font": "Arial",
        "default_body_font": "Arial",
        "filename": "minimal_v1.pptx",
    },
}

SUPPORTED_LAYOUT_TYPES = [
    "title",
    "section",
    "bullets",
    "two_column",
    "image",
    "image_caption",
    "quote",
    "table",
    "chart",
    "blank",
]


def _load_schema() -> Dict[str, Any]:
    with open(_SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _hex_to_rgb(hex_str: str) -> RGBColor:
    hex_clean = hex_str.lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join(c * 2 for c in hex_clean)
    if len(hex_clean) != 6:
        return RGBColor(110, 87, 224)
    r = int(hex_clean[0:2], 16)
    g = int(hex_clean[2:4], 16)
    b = int(hex_clean[4:6], 16)
    return RGBColor(r, g, b)


def list_templates() -> Dict[str, Any]:
    """Return bundled templates, descriptions, and aspect ratios."""
    template_list = []
    for tid, info in TEMPLATES.items():
        template_list.append(
            {
                "template_id": tid,
                "name": info["name"],
                "description": info["description"],
                "aspect_ratio": info["aspect_ratio"],
                "default_accent": info["default_accent"],
                "supported_layouts": SUPPORTED_LAYOUT_TYPES,
            }
        )
    return {
        "success": True,
        "action": "list_templates",
        "templates": template_list,
        "error_code": None,
    }


def validate_spec(deck_spec: Any, strict: bool = False) -> Dict[str, Any]:
    """Validate deck specification against schema and business rules."""
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    if not isinstance(deck_spec, dict):
        return {
            "success": False,
            "action": "validate_spec",
            "valid": False,
            "template_id": "unknown",
            "slide_count": 0,
            "warnings": [],
            "errors": [
                {
                    "code": "INVALID_SPEC",
                    "slide_index": -1,
                    "message": "deck_spec must be a JSON object",
                }
            ],
            "error_code": "INVALID_SPEC",
        }

    # 1. JSON Schema validation
    schema = _load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    schema_errors = list(validator.iter_errors(deck_spec))
    if schema_errors:
        for err in schema_errors:
            errors.append(
                {
                    "code": "INVALID_SPEC",
                    "slide_index": -1,
                    "message": f"Schema violation at '{err.json_path}': {err.message}",
                }
            )
        return {
            "success": False,
            "action": "validate_spec",
            "valid": False,
            "template_id": deck_spec.get("template_id", "pitch_v1"),
            "slide_count": len(deck_spec.get("slides") or []),
            "warnings": [],
            "errors": errors,
            "error_code": "INVALID_SPEC",
        }

    template_id = deck_spec.get("template_id", "pitch_v1")
    if template_id not in TEMPLATES:
        warnings.append(
            {
                "code": "TEMPLATE_NOT_FOUND",
                "slide_index": -1,
                "message": f"Unknown template_id '{template_id}'; will fall back to pitch_v1.",
            }
        )

    slides = deck_spec.get("slides") or []
    for idx, slide in enumerate(slides):
        stype = slide.get("type")

        # Soft character limit on bullets
        if stype == "bullets":
            bullets = slide.get("bullets") or []
            for b_idx, bullet in enumerate(bullets):
                if len(bullet) > 120:
                    warnings.append(
                        {
                            "code": "BULLET_TRUNCATED",
                            "slide_index": idx,
                            "message": (
                                f"Bullet {b_idx + 1} exceeded 120 chars ({len(bullet)} chars); "
                                "will wrap or truncate on render."
                            ),
                        }
                    )

        elif stype == "two_column":
            for col_key in ("left", "right"):
                col_content = slide.get(col_key)
                if isinstance(col_content, list):
                    for c_idx, item in enumerate(col_content):
                        if len(item) > 120:
                            warnings.append(
                                {
                                    "code": "BULLET_TRUNCATED",
                                    "slide_index": idx,
                                    "message": (
                                        f"Column {col_key} item {c_idx + 1} exceeded 120 chars; "
                                        "will wrap or truncate."
                                    ),
                                }
                            )

        # Asset verification for images
        if stype in {"image", "image_caption", "title"}:
            img_obj = slide.get("image")
            if img_obj:
                img_path = img_obj.get("path")
                b64_data = img_obj.get("base64")
                if img_path:
                    if not os.path.exists(img_path):
                        warnings.append(
                            {
                                "code": "ASSET_NOT_FOUND",
                                "slide_index": idx,
                                "message": f"Image file not found at path: {img_path}",
                            }
                        )
                elif b64_data:
                    try:
                        raw_bytes = base64.b64decode(b64_data)
                        with Image.open(io.BytesIO(raw_bytes)) as pil_img:
                            pil_img.verify()
                    except Exception as exc:
                        warnings.append(
                            {
                                "code": "ASSET_INVALID",
                                "slide_index": idx,
                                "message": f"Invalid base64 image data: {exc}",
                            }
                        )

        # Chart verification
        if stype == "chart":
            chart_obj = slide.get("chart") or {}
            cats = chart_obj.get("categories") or []
            series_list = chart_obj.get("series") or []
            for s in series_list:
                vals = s.get("values") or []
                if len(vals) != len(cats):
                    errors.append(
                        {
                            "code": "CHART_DIMENSION_MISMATCH",
                            "slide_index": idx,
                            "message": (
                                f"Series '{s.get('name')}' length ({len(vals)}) "
                                f"does not match categories count ({len(cats)})."
                            ),
                        }
                    )

        # Table verification
        if stype == "table":
            cols = slide.get("columns") or []
            rows = slide.get("rows") or []
            for r_idx, row in enumerate(rows):
                if len(row) != len(cols):
                    warnings.append(
                        {
                            "code": "TABLE_DIMENSION_MISMATCH",
                            "slide_index": idx,
                            "message": (
                                f"Row {r_idx + 1} length ({len(row)}) does not match "
                                f"column headers count ({len(cols)})."
                            ),
                        }
                    )

    if strict and warnings:
        for w in warnings:
            errors.append(
                {
                    "code": f"STRICT_{w['code']}",
                    "slide_index": w.get("slide_index", -1),
                    "message": f"Strict mode validation failure: {w['message']}",
                }
            )

    is_valid = len(errors) == 0
    return {
        "success": is_valid,
        "action": "validate_spec",
        "valid": is_valid,
        "template_id": template_id,
        "slide_count": len(slides),
        "warnings": warnings,
        "errors": errors,
        "error_code": (
            None if is_valid else (errors[0]["code"] if errors else "VALIDATION_FAILED")
        ),
    }


def _validate_output_path(output_path: str) -> str:
    if not output_path or not output_path.strip():
        raise ValueError("output_path must be a non-empty string.")

    raw_parts = output_path.replace("\\", "/").split("/")
    if ".." in raw_parts:
        raise ValueError(
            "output_path contains prohibited path traversal sequences ('..')."
        )

    norm = os.path.normpath(output_path)
    if "\x00" in norm:
        raise ValueError("output_path contains invalid characters.")

    if not norm.lower().endswith(".pptx"):
        raise ValueError("output_path must have a .pptx extension.")

    parent = os.path.dirname(os.path.abspath(norm))
    os.makedirs(parent, exist_ok=True)
    return os.path.abspath(norm)


def _load_image_stream(img_obj: Dict[str, Any]) -> Optional[io.BytesIO]:
    if not img_obj:
        return None
    if img_obj.get("path"):
        p = img_obj["path"]
        if os.path.exists(p):
            with open(p, "rb") as f:
                return io.BytesIO(f.read())
    elif img_obj.get("base64"):
        try:
            data = base64.b64decode(img_obj["base64"])
            return io.BytesIO(data)
        except Exception:
            return None
    return None


def render_deck(
    deck_spec: Dict[str, Any],
    output_path: str,
    template_id: Optional[str] = None,
    theme: Optional[Dict[str, Any]] = None,
    strict: bool = False,
) -> Dict[str, Any]:
    """Render presentation from deck specification to target .pptx file."""
    try:
        safe_output_path = _validate_output_path(output_path)
    except ValueError as exc:
        return {
            "success": False,
            "action": "render",
            "output_path": output_path,
            "template_id": template_id or "unknown",
            "slide_count": 0,
            "file_size_bytes": 0,
            "slides": [],
            "warnings": [],
            "errors": [
                {"code": "OUTPUT_PATH_UNSAFE", "slide_index": -1, "message": str(exc)}
            ],
            "error_code": "OUTPUT_PATH_UNSAFE",
        }

    val_res = validate_spec(deck_spec, strict=strict)
    if not val_res["valid"]:
        return {
            "success": False,
            "action": "render",
            "output_path": safe_output_path,
            "template_id": val_res["template_id"],
            "slide_count": val_res["slide_count"],
            "file_size_bytes": 0,
            "slides": [],
            "warnings": val_res["warnings"],
            "errors": val_res["errors"],
            "error_code": val_res["error_code"] or "INVALID_SPEC",
        }

    effective_template_id = template_id or deck_spec.get("template_id", "pitch_v1")
    if effective_template_id not in TEMPLATES:
        effective_template_id = "pitch_v1"

    template_meta = TEMPLATES[effective_template_id]
    template_file = _TEMPLATES_DIR / template_meta["filename"]

    try:
        if template_file.is_file():
            prs = pptx.Presentation(str(template_file))
        else:
            prs = pptx.Presentation()
            prs.slide_width = Inches(13.333)
            prs.slide_height = Inches(7.5)
    except Exception as exc:
        return {
            "success": False,
            "action": "render",
            "output_path": safe_output_path,
            "template_id": effective_template_id,
            "slide_count": 0,
            "file_size_bytes": 0,
            "slides": [],
            "warnings": val_res["warnings"],
            "errors": [
                {"code": "RENDER_FAILED", "slide_index": -1, "message": str(exc)}
            ],
            "error_code": "RENDER_FAILED",
        }

    theme_spec = deck_spec.get("theme") or {}
    if theme:
        theme_spec.update(theme)

    accent_hex = theme_spec.get("accent_color", template_meta["default_accent"])
    accent_rgb = _hex_to_rgb(accent_hex)
    font_heading = theme_spec.get("font_heading", template_meta["default_heading_font"])
    font_body = theme_spec.get("font_body", template_meta["default_body_font"])

    slides = deck_spec.get("slides") or []
    rendered_slides_summary: List[Dict[str, Any]] = []

    for s_idx, slide_data in enumerate(slides):
        stype = slide_data.get("type", "blank")
        title_text = slide_data.get("title", "")

        # 1. Title Slide
        if stype == "title":
            slide = prs.slides.add_slide(prs.slide_layouts[0])
            if slide.shapes.title:
                slide.shapes.title.text = title_text
                for p in slide.shapes.title.text_frame.paragraphs:
                    p.font.name = font_heading
                    p.font.color.rgb = accent_rgb
                    p.font.bold = True
            subtitle_text = slide_data.get("subtitle", "")
            if len(slide.placeholders) > 1 and subtitle_text:
                slide.placeholders[1].text = subtitle_text
                for p in slide.placeholders[1].text_frame.paragraphs:
                    p.font.name = font_body

            img_stream = _load_image_stream(slide_data.get("image"))
            if img_stream:
                try:
                    slide.shapes.add_picture(
                        img_stream, Inches(9.5), Inches(2.0), width=Inches(3.0)
                    )
                except Exception:
                    pass

        # 2. Section Divider
        elif stype == "section":
            slide = prs.slides.add_slide(prs.slide_layouts[2])
            if slide.shapes.title:
                slide.shapes.title.text = title_text
                for p in slide.shapes.title.text_frame.paragraphs:
                    p.font.name = font_heading
                    p.font.color.rgb = accent_rgb
            subtitle_text = slide_data.get("subtitle", "")
            if len(slide.placeholders) > 1 and subtitle_text:
                slide.placeholders[1].text = subtitle_text
                for p in slide.placeholders[1].text_frame.paragraphs:
                    p.font.name = font_body

        # 3. Bullets
        elif stype == "bullets":
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            if slide.shapes.title:
                slide.shapes.title.text = title_text
                for p in slide.shapes.title.text_frame.paragraphs:
                    p.font.name = font_heading
                    p.font.color.rgb = accent_rgb
            bullets = slide_data.get("bullets") or []
            if len(slide.placeholders) > 1 and bullets:
                tf = slide.placeholders[1].text_frame
                tf.clear()
                for b_idx, bullet in enumerate(bullets):
                    p = tf.paragraphs[0] if b_idx == 0 else tf.add_paragraph()
                    p.text = bullet
                    p.font.name = font_body
                    p.level = 0

        # 4. Two Column
        elif stype == "two_column":
            slide = prs.slides.add_slide(prs.slide_layouts[3])
            if slide.shapes.title:
                slide.shapes.title.text = title_text
                for p in slide.shapes.title.text_frame.paragraphs:
                    p.font.name = font_heading
                    p.font.color.rgb = accent_rgb
            for p_idx, col_key in enumerate(("left", "right")):
                col_content = slide_data.get(col_key)
                if len(slide.placeholders) > (p_idx + 1) and col_content:
                    tf = slide.placeholders[p_idx + 1].text_frame
                    tf.clear()
                    if isinstance(col_content, list):
                        for item_idx, item in enumerate(col_content):
                            p = (
                                tf.paragraphs[0]
                                if item_idx == 0
                                else tf.add_paragraph()
                            )
                            p.text = item
                            p.font.name = font_body
                    else:
                        tf.paragraphs[0].text = str(col_content)
                        tf.paragraphs[0].font.name = font_body

        # 5. Image
        elif stype == "image":
            slide = prs.slides.add_slide(prs.slide_layouts[5])
            if slide.shapes.title and title_text:
                slide.shapes.title.text = title_text
                for p in slide.shapes.title.text_frame.paragraphs:
                    p.font.name = font_heading
                    p.font.color.rgb = accent_rgb
            img_stream = _load_image_stream(slide_data.get("image"))
            if img_stream:
                try:
                    top_offset = Inches(1.8) if title_text else Inches(1.0)
                    slide.shapes.add_picture(
                        img_stream,
                        Inches(2.0),
                        top_offset,
                        width=Inches(9.333),
                    )
                except Exception:
                    pass
            caption = slide_data.get("caption")
            if caption:
                tb = slide.shapes.add_textbox(
                    Inches(2.0), Inches(6.2), Inches(9.333), Inches(0.8)
                )
                p = tb.text_frame.paragraphs[0]
                p.text = caption
                p.font.name = font_body
                p.font.italic = True

        # 6. Image with Caption Body
        elif stype == "image_caption":
            slide = prs.slides.add_slide(prs.slide_layouts[5])
            if slide.shapes.title:
                slide.shapes.title.text = title_text
                for p in slide.shapes.title.text_frame.paragraphs:
                    p.font.name = font_heading
                    p.font.color.rgb = accent_rgb
            img_stream = _load_image_stream(slide_data.get("image"))
            if img_stream:
                try:
                    slide.shapes.add_picture(
                        img_stream,
                        Inches(1.0),
                        Inches(1.8),
                        width=Inches(5.5),
                    )
                except Exception:
                    pass
            body_text = slide_data.get("body", "")
            if body_text:
                tb = slide.shapes.add_textbox(
                    Inches(7.0), Inches(1.8), Inches(5.333), Inches(4.5)
                )
                tf = tb.text_frame
                tf.word_wrap = True
                p = tf.paragraphs[0]
                p.text = body_text
                p.font.name = font_body

        # 7. Quote Slide
        elif stype == "quote":
            slide = prs.slides.add_slide(prs.slide_layouts[6])
            tb = slide.shapes.add_textbox(
                Inches(1.8), Inches(2.0), Inches(9.7), Inches(3.5)
            )
            tf = tb.text_frame
            tf.word_wrap = True
            quote_text = slide_data.get("quote", "")
            p_q = tf.paragraphs[0]
            p_q.text = f'"{quote_text}"'
            p_q.font.name = font_heading
            p_q.font.size = Pt(26)
            p_q.font.bold = True
            p_q.font.color.rgb = accent_rgb
            attrib_text = slide_data.get("attribution", "")
            if attrib_text:
                p_a = tf.add_paragraph()
                p_a.text = f"— {attrib_text}"
                p_a.font.name = font_body
                p_a.font.size = Pt(18)
                p_a.font.italic = True

        # 8. Table
        elif stype == "table":
            slide = prs.slides.add_slide(prs.slide_layouts[5])
            if slide.shapes.title:
                slide.shapes.title.text = title_text
                for p in slide.shapes.title.text_frame.paragraphs:
                    p.font.name = font_heading
                    p.font.color.rgb = accent_rgb
            cols = slide_data.get("columns") or []
            rows = slide_data.get("rows") or []
            num_rows = len(rows) + 1
            num_cols = len(cols)
            if num_cols > 0 and num_rows > 1:
                table_shape = slide.shapes.add_table(
                    num_rows,
                    num_cols,
                    Inches(1.0),
                    Inches(1.8),
                    Inches(11.333),
                    Inches(0.6 * num_rows),
                )
                tbl = table_shape.table
                for c_idx, c_name in enumerate(cols):
                    cell = tbl.cell(0, c_idx)
                    cell.text = str(c_name)
                    for p in cell.text_frame.paragraphs:
                        p.font.name = font_heading
                        p.font.bold = True
                for r_idx, row_items in enumerate(rows):
                    for c_idx, val in enumerate(row_items[:num_cols]):
                        cell = tbl.cell(r_idx + 1, c_idx)
                        cell.text = str(val)
                        for p in cell.text_frame.paragraphs:
                            p.font.name = font_body

        # 9. Chart
        elif stype == "chart":
            slide = prs.slides.add_slide(prs.slide_layouts[5])
            if slide.shapes.title:
                slide.shapes.title.text = title_text
                for p in slide.shapes.title.text_frame.paragraphs:
                    p.font.name = font_heading
                    p.font.color.rgb = accent_rgb
            chart_spec = slide_data.get("chart") or {}
            kind = chart_spec.get("kind", "bar")
            cats = chart_spec.get("categories") or []
            series_list = chart_spec.get("series") or []

            chart_data = CategoryChartData()
            chart_data.categories = cats
            for s in series_list:
                chart_data.add_series(s.get("name", ""), s.get("values", []))

            chart_type_map = {
                "bar": XL_CHART_TYPE.COLUMN_CLUSTERED,
                "line": XL_CHART_TYPE.LINE_MARKERS,
                "pie": XL_CHART_TYPE.PIE,
            }
            xl_type = chart_type_map.get(kind, XL_CHART_TYPE.COLUMN_CLUSTERED)
            slide.shapes.add_chart(
                xl_type,
                Inches(1.5),
                Inches(1.8),
                Inches(10.333),
                Inches(5.0),
                chart_data,
            )

        # 10. Blank
        else:
            slide = prs.slides.add_slide(prs.slide_layouts[6])

        # Attach speaker notes if present
        speaker_notes = slide_data.get("speaker_notes")
        if speaker_notes:
            slide.notes_slide.notes_text_frame.text = speaker_notes

        rendered_slides_summary.append(
            {
                "index": s_idx,
                "type": stype,
                "title": title_text,
            }
        )

    prs.save(safe_output_path)
    file_size = os.path.getsize(safe_output_path)

    return {
        "success": True,
        "action": "render",
        "output_path": safe_output_path,
        "template_id": effective_template_id,
        "slide_count": len(slides),
        "file_size_bytes": file_size,
        "slides": rendered_slides_summary,
        "warnings": val_res["warnings"],
        "error_code": None,
    }


def inspect_deck(input_path: str) -> Dict[str, Any]:
    """Inspect an existing .pptx presentation and return its slide manifest."""
    if not input_path or not os.path.exists(input_path):
        return {
            "success": False,
            "action": "inspect",
            "slide_count": 0,
            "slides": [],
            "error_code": "INSPECT_FAILED",
            "errors": [
                {
                    "code": "FILE_NOT_FOUND",
                    "slide_index": -1,
                    "message": f"File not found at input_path: {input_path}",
                }
            ],
        }

    try:
        prs = pptx.Presentation(input_path)
        slides_manifest: List[Dict[str, Any]] = []
        for idx, s in enumerate(prs.slides):
            has_notes = False
            try:
                has_notes = bool(
                    s.has_notes_slide and s.notes_slide.notes_text_frame.text.strip()
                )
            except Exception:
                pass
            title_text = (
                s.shapes.title.text
                if (s.shapes.title and s.shapes.title.text)
                else None
            )
            layout_name = getattr(s.slide_layout, "name", "Custom")
            slides_manifest.append(
                {
                    "index": idx,
                    "layout_name": layout_name,
                    "title": title_text,
                    "has_notes": has_notes,
                    "shape_count": len(s.shapes),
                }
            )

        return {
            "success": True,
            "action": "inspect",
            "slide_count": len(slides_manifest),
            "slides": slides_manifest,
            "error_code": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "action": "inspect",
            "slide_count": 0,
            "slides": [],
            "error_code": "INSPECT_FAILED",
            "errors": [
                {
                    "code": "CORRUPT_OR_UNREADABLE",
                    "slide_index": -1,
                    "message": f"Failed to inspect .pptx file: {exc}",
                }
            ],
        }

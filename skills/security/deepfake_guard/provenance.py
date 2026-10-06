"""Metadata, EXIF, XMP, and C2PA Content Credentials provenance audit."""

from __future__ import annotations

import io
from typing import Any, Dict, List, Optional

from PIL import ExifTags, Image

try:
    from .constants import (
        AI_GENERATOR_KEYWORDS,
        C2PA_BOX_SIGNATURES,
        SUSPICIOUS_SOFTWARE_SIGNATURES,
    )
except (ImportError, ValueError):
    import os
    import sys

    _pkg_dir = os.path.dirname(os.path.abspath(__file__))
    if _pkg_dir not in sys.path:
        sys.path.insert(0, _pkg_dir)
    from constants import (
        AI_GENERATOR_KEYWORDS,
        C2PA_BOX_SIGNATURES,
        SUSPICIOUS_SOFTWARE_SIGNATURES,
    )


def extract_metadata_and_provenance(
    image: Image.Image,
    raw_bytes: Optional[bytes] = None,
) -> Dict[str, Any]:
    """
    Extracts EXIF, XMP, and C2PA binary headers to detect manipulation software,
    AI generation parameters, and provenance credentials.
    """
    exif_data: Dict[str, Any] = {}
    software_found: List[str] = []
    ai_cues: List[str] = []
    c2pa_signals: Dict[str, Any] = {
        "c2pa_manifest_present": False,
        "is_ai_generated_claim": False,
        "detected_boxes": [],
    }

    # 1. EXIF extraction via Pillow
    try:
        raw_exif = image.getexif()
        if raw_exif:
            for tag_id, value in raw_exif.items():
                tag_name = ExifTags.TAGS.get(tag_id, str(tag_id))
                val_str = str(value).strip()
                if val_str:
                    exif_data[tag_name] = val_str

                if tag_name.lower() in (
                    "software",
                    "processingsoftware",
                    "imagehistory",
                ):
                    for sig in SUSPICIOUS_SOFTWARE_SIGNATURES:
                        if sig in val_str.lower():
                            software_found.append(f"{tag_name}: {val_str}")
    except Exception:
        pass

    # Check image info dictionary (PNG chunks, text metadata, XMP)
    for info_key, info_val in (image.info or {}).items():
        val_str = str(info_val).lower()
        for kw in AI_GENERATOR_KEYWORDS:
            if kw in val_str:
                ai_cues.append(f"{info_key} contains {kw}")

        for sig in SUSPICIOUS_SOFTWARE_SIGNATURES:
            if sig in val_str:
                software_found.append(f"{info_key}: {info_val}")

    # 2. Binary buffer scan for raw XMP and C2PA JUMBF boxes
    buffer_bytes = raw_bytes
    if buffer_bytes is None:
        try:
            buf = io.BytesIO()
            fmt = image.format or "JPEG"
            image.save(buf, format=fmt)
            buffer_bytes = buf.getvalue()
        except Exception:
            buffer_bytes = b""

    if buffer_bytes:
        # Check C2PA JUMBF signatures
        for sig in C2PA_BOX_SIGNATURES:
            if sig in buffer_bytes:
                c2pa_signals["c2pa_manifest_present"] = True
                c2pa_signals["detected_boxes"].append(
                    sig.decode("ascii", errors="ignore")
                )

        # Check for trainedAlgorithmicMedia / AI provenance assertion in C2PA
        if (
            b"trainedAlgorithmicMedia" in buffer_bytes
            or b"compositeWithTrainedAlgorithmicMedia" in buffer_bytes
        ):
            c2pa_signals["c2pa_manifest_present"] = True
            c2pa_signals["is_ai_generated_claim"] = True
            ai_cues.append("C2PA assertion: trainedAlgorithmicMedia")

        # Scan for XMP textual markers
        lower_blob = buffer_bytes.lower()
        if b"photoshop" in lower_blob and not any(
            "photoshop" in s.lower() for s in software_found
        ):
            software_found.append("XMP stream contains Photoshop signature")
        if b"midjourney" in lower_blob:
            ai_cues.append("XMP stream contains Midjourney signature")
        if b"stable diffusion" in lower_blob or b"stablediffusion" in lower_blob:
            ai_cues.append("XMP stream contains Stable Diffusion signature")
        if b"dall-e" in lower_blob or b"dalle" in lower_blob:
            ai_cues.append("XMP stream contains DALL-E signature")

    # Deduplicate findings
    unique_software = sorted(list(set(software_found)))
    unique_ai_cues = sorted(list(set(ai_cues)))

    has_manipulation_software = len(unique_software) > 0
    has_ai_provenance = len(unique_ai_cues) > 0 or c2pa_signals["is_ai_generated_claim"]

    return {
        "has_exif": bool(exif_data),
        "camera_make": exif_data.get("Make"),
        "camera_model": exif_data.get("Model"),
        "software": exif_data.get("Software"),
        "date_original": exif_data.get("DateTimeOriginal") or exif_data.get("DateTime"),
        "has_manipulation_software": has_manipulation_software,
        "manipulation_tools": unique_software,
        "has_ai_provenance_cues": has_ai_provenance,
        "ai_generation_cues": unique_ai_cues,
        "c2pa": c2pa_signals,
    }

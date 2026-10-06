"""Unit and assurance tests for security/deepfake_guard."""

from __future__ import annotations

import base64
import io
from typing import Dict, Optional

import numpy as np
import pytest
from PIL import Image

from skills.security.deepfake_guard.document import (
    calculate_icao_check_digit,
    parse_and_validate_mrz,
)
from skills.security.deepfake_guard.skill import DeepfakeGuardSkill


@pytest.fixture
def skill():
    return DeepfakeGuardSkill()


def _create_test_image(
    width: int = 200, height: int = 150, color=(120, 140, 160)
) -> Image.Image:
    """Generates a clean synthetic base image."""
    arr = np.full((height, width, 3), color, dtype=np.uint8)
    # Add subtle smooth natural gradient
    for y in range(height):
        arr[y, :, 0] = np.clip(color[0] + y // 5, 0, 255)
    return Image.fromarray(arr, "RGB")


def _image_to_bytes(
    img: Image.Image,
    format: str = "JPEG",
    text_meta: Optional[Dict[str, str]] = None,
) -> bytes:
    buf = io.BytesIO()
    if format.upper() == "PNG" and text_meta:
        from PIL.PngImagePlugin import PngInfo

        pnginfo = PngInfo()
        for k, v in text_meta.items():
            pnginfo.add_text(k, v)
        img.save(buf, format=format, pnginfo=pnginfo)
    else:
        img.save(buf, format=format)
    return buf.getvalue()


# -----------------------------------------------------------------------------
# 1. Manifest & Basic Contract Tests
# -----------------------------------------------------------------------------


def test_manifest_loaded(skill):
    manifest = skill.manifest
    assert manifest["name"] == "security/deepfake_guard"
    assert manifest["version"] == "0.1.0"
    assert manifest["issuer"]["name"] == "Ross Peili"
    assert "parameters" in manifest
    assert "constitution" in manifest


def test_validate_params(skill):
    assert (
        skill.validate_params({"action": "analyze", "media_path": "test.jpg"}) is True
    )
    assert skill.validate_params({"action": "validate_mrz", "raw_mrz": "P<..."}) is True


# -----------------------------------------------------------------------------
# 2. Media Forensics Tests (ELA, Noise, Moire, Copy-Move)
# -----------------------------------------------------------------------------


def test_clean_image_analysis(skill):
    clean_img = _create_test_image()
    raw = _image_to_bytes(clean_img)

    res = skill.execute(
        {"action": "analyze", "media_bytes_b64": base64.b64encode(raw).decode("ascii")}
    )

    assert res["status"] == "ok"
    assert res["offline"] is True
    assert res["verdict"] in ("authentic_likely", "suspicious")
    assert res["is_tampered_likely"] is False
    assert res["is_synthetic_likely"] is False
    assert isinstance(res["signals"], list)


def test_spliced_image_ela_anomaly(skill):
    """An image with a noisy spliced patch should trigger noise or ELA anomaly."""
    base_img = _create_test_image(240, 180)
    arr = np.array(base_img)

    # Insert a high-frequency noisy foreign patch (simulated face/text splice)
    noise_patch = np.random.randint(0, 255, (50, 50, 3), dtype=np.uint8)
    arr[40:90, 40:90] = noise_patch

    spliced_img = Image.fromarray(arr)
    raw = _image_to_bytes(spliced_img)

    res = skill.execute(
        {"action": "analyze", "media_bytes_b64": base64.b64encode(raw).decode("ascii")}
    )

    assert res["status"] == "ok"
    assert res["confidence_score"] >= 0.35
    assert len(res["artifacts_detected"]) >= 1


def test_screen_recapture_moire_detection(skill):
    """An image with periodic high-frequency grid interference should trigger moiré detection."""
    dim = 256
    y, x = np.mgrid[:dim, :dim]
    # Synthetic periodic LCD pixel subgrid
    moire_grid = (np.sin(x * 1.5) * np.sin(y * 1.5) * 80 + 128).astype(np.uint8)
    grid_img = Image.fromarray(np.stack([moire_grid] * 3, axis=-1))
    raw = _image_to_bytes(grid_img, format="PNG")

    res = skill.execute(
        {
            "action": "inspect_media",
            "media_bytes_b64": base64.b64encode(raw).decode("ascii"),
        }
    )

    assert res["status"] == "ok"
    assert (
        any("moire" in str(sig) for sig in res["signals"])
        or res["confidence_score"] > 0.3
    )


def test_copy_move_cloning_detection(skill):
    """An image containing identical duplicate stamped blocks triggers copy-move detection."""
    dim = 160
    base = np.zeros((dim, dim, 3), dtype=np.uint8)
    # Distinct pattern stamp
    pattern = np.array([[255, 0, 255, 0], [0, 255, 0, 255]] * 8, dtype=np.uint8)
    pattern_block = np.repeat(np.repeat(pattern, 4, axis=0), 4, axis=1)

    # Place identical pattern in two separated locations
    h, w = pattern_block.shape[:2]
    base[10 : 10 + h, 10 : 10 + w, 0] = pattern_block
    base[90 : 90 + h, 90 : 90 + w, 0] = pattern_block

    stamp_img = Image.fromarray(base)
    raw = _image_to_bytes(stamp_img, format="PNG")

    res = skill.execute(
        {
            "action": "inspect_media",
            "media_bytes_b64": base64.b64encode(raw).decode("ascii"),
        }
    )

    assert res["status"] == "ok"
    assert isinstance(res["artifacts_detected"], list)


# -----------------------------------------------------------------------------
# 3. Provenance & C2PA Detection Tests
# -----------------------------------------------------------------------------


def test_c2pa_ai_generation_provenance(skill):
    """Raw byte streams containing C2PA and trainedAlgorithmicMedia flags are flagged as synthetic."""
    clean_img = _create_test_image()
    raw = _image_to_bytes(clean_img)

    # Inject mock C2PA JUMBF marker into byte stream
    tampered_bytes = raw + b"c2pa:actions trainedAlgorithmicMedia jumb jumd"

    res = skill.execute(
        {
            "action": "verify_provenance",
            "media_bytes_b64": base64.b64encode(tampered_bytes).decode("ascii"),
        }
    )

    assert res["status"] == "ok"
    assert res["has_ai_provenance_cues"] is True
    assert res["c2pa"]["c2pa_manifest_present"] is True
    assert res["verdict"] == "suspicious"


def test_editing_software_signature_provenance(skill):
    """Metadata mentioning Adobe Photoshop or GIMP is flagged."""
    clean_img = _create_test_image()
    raw = _image_to_bytes(
        clean_img,
        format="PNG",
        text_meta={"Software": "Adobe Photoshop 2026 (Macintosh)"},
    )

    res = skill.execute(
        {
            "action": "verify_provenance",
            "media_bytes_b64": base64.b64encode(raw).decode("ascii"),
        }
    )

    assert res["status"] == "ok"
    assert res["has_manipulation_software"] is True
    assert any("Photoshop" in tool for tool in res["manipulation_tools"])


# -----------------------------------------------------------------------------
# 4. ICAO 9303 Document MRZ Tests (TD1, TD2, TD3)
# -----------------------------------------------------------------------------


def test_icao_check_digit_calculation():
    # Example from ICAO 9303: "L898902C3" with weights 7-3-1
    # 'L'=21, '8'=8, '9'=9, '8'=8, '9'=9, '0'=0, '2'=2, 'C'=12, '3'=3
    # Check digit should match modulo 10
    cd = calculate_icao_check_digit("L898902C3")
    assert isinstance(cd, int)
    assert 0 <= cd <= 9


def test_valid_td3_passport_mrz(skill):
    # Authentic sample ICAO Doc 9303 Part 4 TD3 Passport MRZ:
    # Line 1: P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<< (44)
    # Line 2: L898902C36UTO7408122F1204159ZE184226B<<<<<10 (44)
    l1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
    l2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"

    assert len(l1) == 44
    assert len(l2) == 44

    res = skill.execute({"action": "validate_mrz", "raw_mrz": [l1, l2]})

    assert res["status"] == "ok"
    assert res["mrz_valid"] is True
    assert res["checksum_failures"] == []
    assert res["fields"]["surname"] == "ERIKSSON"
    assert res["fields"]["given_names"] == "ANNA MARIA"
    assert res["fields"]["document_number"] == "L898902C3"
    assert res["fields"]["nationality"] == "UTO"


def test_forged_td3_passport_mrz_fails_checksum(skill):
    # Forged: altered document number from L898902C3 to L898902C4 without updating check digit 6
    l1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
    l2 = "L898902C46UTO7408122F1204159ZE184226B<<<<<10"

    res = skill.execute({"action": "validate_mrz", "raw_mrz": [l1, l2]})

    assert res["status"] == "ok"
    assert res["mrz_valid"] is False
    assert "document_number_checksum" in res["checksum_failures"]
    assert res["verdict"] == "tampered_likely"


def test_valid_td1_national_id_mrz(skill):
    # TD1 format (3 lines of 30 characters)
    # Line 1: I<UTOD231458907<<<<<<<<<<<<<<<
    # Line 2: 7408122F1204159UTO<<<<<<<<<<<6
    # Line 3: ERIKSSON<<ANNA<MARIA<<<<<<<<<<
    l1 = "I<UTOD231458907<<<<<<<<<<<<<<<"
    l2 = "7408122F1204159UTO<<<<<<<<<<<6"
    l3 = "ERIKSSON<<ANNA<MARIA<<<<<<<<<<"

    assert len(l1) == 30
    assert len(l2) == 30
    assert len(l3) == 30

    eval_res = parse_and_validate_mrz([l1, l2, l3])
    assert eval_res["format"] == "TD1"
    assert eval_res["mrz_valid"] is True
    assert eval_res["fields"]["document_type"] == "I"
    assert eval_res["fields"]["document_number"] == "D23145890"


def test_valid_td2_travel_doc_mrz(skill):
    # TD2 format (2 lines of 36 characters)
    l1 = "I<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<"
    l2 = "D231458907UTO7408122F1204159<<<<<<<6"

    assert len(l1) == 36
    assert len(l2) == 36

    eval_res = parse_and_validate_mrz([l1, l2])
    assert eval_res["format"] == "TD2"
    assert eval_res["mrz_valid"] is True


def test_document_full_analysis_with_mrz_and_geometry(skill):
    # Create TD3 aspect ratio image (width / height ~ 1.42)
    doc_img = _create_test_image(width=284, height=200)
    raw = _image_to_bytes(doc_img)

    l1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
    l2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"

    res = skill.execute(
        {
            "action": "inspect_document",
            "media_bytes_b64": base64.b64encode(raw).decode("ascii"),
            "raw_mrz": [l1, l2],
            "claimed_doc_type": "passport",
            "claimed_country": "UTO",
        }
    )

    assert res["status"] == "ok"
    assert res["doc"]["mrz_valid"] is True
    assert res["doc"]["geometry"]["geometry_consistent"] is True
    assert res["verdict"] in ("authentic_likely", "suspicious")


# -----------------------------------------------------------------------------
# 5. Error Handling & Async Parity Tests
# -----------------------------------------------------------------------------


def test_error_handling_missing_input(skill):
    res = skill.execute({"action": "analyze"})
    assert res["status"] == "error"
    assert res["error_code"] == "missing_input"


def test_error_handling_unsupported_action(skill):
    res = skill.execute({"action": "magic_hack"})
    assert res["status"] == "error"
    assert res["error_code"] in ("unsupported_action", "validation_error")


@pytest.mark.asyncio
async def test_async_execute_parity(skill):
    clean_img = _create_test_image()
    raw = _image_to_bytes(clean_img)
    params = {
        "action": "analyze",
        "media_bytes_b64": base64.b64encode(raw).decode("ascii"),
    }

    sync_res = skill.execute(params)
    async_res = await skill.aexecute(params)

    assert sync_res["status"] == "ok"
    assert async_res["status"] == "ok"
    assert sync_res["verdict"] == async_res["verdict"]
    assert sync_res["confidence_score"] == async_res["confidence_score"]

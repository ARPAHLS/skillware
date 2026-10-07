"""Simulations, edge-case stress tests, and adversarial forensics for security/deepfake_guard."""

from __future__ import annotations

import asyncio
import base64
import io
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


def _make_test_image(w: int, h: int, color=(130, 150, 170)) -> Image.Image:
    arr = np.full((h, w, 3), color, dtype=np.uint8)
    return Image.fromarray(arr, "RGB")


def _to_b64(img: Image.Image, format: str = "JPEG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=format)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# -----------------------------------------------------------------------------
# 1. Image Robustness & Corrupted Payload Stress Tests
# -----------------------------------------------------------------------------


def test_stress_corrupt_truncated_bytes(skill):
    """Passing truncated or garbage bytes must return a structured error, never crash."""
    garbage_cases = [
        b"NOT_AN_IMAGE_DATA",
        b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 20,  # Truncated JPEG header
        b"%PDF-1.4 Fake document pretending to be image",
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 15,  # Incomplete PNG header
    ]
    for raw in garbage_cases:
        res = skill.execute(
            {
                "action": "analyze",
                "media_bytes_b64": base64.b64encode(raw).decode("ascii"),
            }
        )
        assert res["status"] == "error"
        assert res["error_code"] in ("execution_failed", "validation_error")
        assert "message" in res


def test_stress_micro_and_massive_dimensions(skill):
    """Extreme image sizes (1x1, 2x2, large high-res) execute deterministically."""
    # Micro 1x1 and 2x2
    micro_1 = _make_test_image(1, 1)
    res_1 = skill.execute(
        {"action": "analyze", "media_bytes_b64": _to_b64(micro_1, "PNG")}
    )
    assert res_1["status"] == "ok"
    assert res_1["offline"] is True

    micro_2 = _make_test_image(2, 2)
    res_2 = skill.execute(
        {"action": "analyze", "media_bytes_b64": _to_b64(micro_2, "PNG")}
    )
    assert res_2["status"] == "ok"

    # Larger dimension
    large_img = _make_test_image(800, 600)
    res_large = skill.execute(
        {"action": "analyze", "media_bytes_b64": _to_b64(large_img, "JPEG")}
    )
    assert res_large["status"] == "ok"
    assert res_large["verdict"] in ("authentic_likely", "suspicious")


def test_stress_extreme_aspect_ratios(skill):
    """Extreme aspect ratios (10:1 panoramic, 1:10 tall strip) handled gracefully."""
    wide_banner = _make_test_image(600, 60)
    res_wide = skill.execute(
        {"action": "analyze", "media_bytes_b64": _to_b64(wide_banner, "PNG")}
    )
    assert res_wide["status"] == "ok"

    tall_strip = _make_test_image(50, 500)
    res_tall = skill.execute(
        {"action": "analyze", "media_bytes_b64": _to_b64(tall_strip, "PNG")}
    )
    assert res_tall["status"] == "ok"


# -----------------------------------------------------------------------------
# 2. Multi-Jurisdiction Passport & ID Simulations
# -----------------------------------------------------------------------------


def test_simulation_multi_jurisdiction_passports(skill):
    """Validates real-world format TD3 passport MRZ patterns across jurisdictions."""
    jurisdictions = [
        # Country: GRC (Greece)
        (
            "P<GRCGEORGIOU<<DIMITRIOS<<<<<<<<<<<<<<<<<<<<",
            "AO12345670GRC8505202M3001019<<<<<<<<<<<<<<<8",
        ),
        # Country: DEU (Germany)
        (
            "P<DEUSCHMIDT<<HANS<WERNER<<<<<<<<<<<<<<<<<<<",
            "C01X00T478DEU6408125M2702283<<<<<<<<<<<<<<<4",
        ),
        # Country: FRA (France)
        (
            "P<FRADUPONT<<JEAN<PIERRE<<<<<<<<<<<<<<<<<<<<",
            "12AB345673FRA7804159M2906106<<<<<<<<<<<<<<<2",
        ),
    ]

    for l1, l2 in jurisdictions:
        assert len(l1) == 44
        assert len(l2) == 44
        eval_res = parse_and_validate_mrz([l1, l2])
        assert eval_res["format"] == "TD3"
        assert eval_res["mrz_valid"] is True
        doc_num = l2[0:9]
        assert int(l2[9]) == calculate_icao_check_digit(doc_num)
        dob = l2[13:19]
        assert int(l2[19]) == calculate_icao_check_digit(dob)
        exp = l2[21:27]
        assert int(l2[27]) == calculate_icao_check_digit(exp)


def test_simulation_expired_document_detection():
    """Documents with expired expiration dates flag is_expired=True."""
    # Expiry date: 15 Dec 2012 (121215) -> Expired
    l1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
    l2 = "L898902C36UTO7408122F1212159ZE184226B<<<<<10"

    res = parse_and_validate_mrz([l1, l2])
    assert res["fields"]["is_expired"] is True

    # Expiry date: 15 Dec 2038 (381215) -> Not expired
    l2_future = f"L898902C36UTO7408122F381215{calculate_icao_check_digit('381215')}ZE184226B<<<<<10"
    res_future = parse_and_validate_mrz([l1, l2_future])
    assert res_future["fields"]["is_expired"] is False


def test_simulation_adversarial_mrz_tampering(skill):
    """Adversarial edits to name, document number, or birth date fail checksums."""
    l1_orig = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"

    # Case A: Attacker edits document number from L898902C3 to L898902C7
    l2_tampered_doc = "L898902C76UTO7408122F1204159ZE184226B<<<<<10"
    res_a = skill.execute(
        {"action": "validate_mrz", "raw_mrz": [l1_orig, l2_tampered_doc]}
    )
    assert res_a["mrz_valid"] is False
    assert "document_number_checksum" in res_a["checksum_failures"]

    # Case B: Attacker edits birth date from 740812 to 740815 (check digit 2 fails)
    l2_tampered_dob = "L898902C36UTO7408152F1204159ZE184226B<<<<<10"
    res_b = skill.execute(
        {"action": "validate_mrz", "raw_mrz": [l1_orig, l2_tampered_dob]}
    )
    assert res_b["mrz_valid"] is False
    assert "date_of_birth_checksum" in res_b["checksum_failures"]

    # Case C: Attacker edits expiration date from 120415 to 250415
    l2_tampered_exp = "L898902C36UTO7408122F2504159ZE184226B<<<<<10"
    res_c = skill.execute(
        {"action": "validate_mrz", "raw_mrz": [l1_orig, l2_tampered_exp]}
    )
    assert res_c["mrz_valid"] is False
    assert "expiry_date_checksum" in res_c["checksum_failures"]


# -----------------------------------------------------------------------------
# 3. Document Splicing & Moire Simulation
# -----------------------------------------------------------------------------


def test_simulation_spliced_photo_patch(skill):
    """A document containing an inserted face photo with divergent noise is caught."""
    w, h = 320, 220
    # Clean document substrate with mild texture
    base_arr = np.random.normal(160, 4, (h, w, 3)).clip(0, 255).astype(np.uint8)

    # Insert a foreign pasted photo patch with significantly higher noise variance
    face_patch = np.random.normal(120, 28, (70, 60, 3)).clip(0, 255).astype(np.uint8)
    base_arr[30:100, 20:80] = face_patch

    spliced_doc = Image.fromarray(base_arr)
    raw = _to_b64(spliced_doc, "JPEG")

    res = skill.execute({"action": "inspect_document", "media_bytes_b64": raw})
    assert res["status"] == "ok"
    assert res["confidence_score"] >= 0.35
    assert res["is_tampered_likely"] is True or len(res["artifacts_detected"]) >= 1


def test_simulation_screen_recapture_grid_variants(skill):
    """Tests various periodic screen grid frequencies for moiré recapture detection."""
    dim = 256
    y, x = np.mgrid[:dim, :dim]

    # Diagonal LCD screen subpixel interference pattern
    diag_moire = (np.sin((x + y) * 1.8) * 90 + 128).astype(np.uint8)
    grid_img = Image.fromarray(np.stack([diag_moire] * 3, axis=-1))
    raw = _to_b64(grid_img, "PNG")

    res = skill.execute({"action": "inspect_media", "media_bytes_b64": raw})
    assert res["status"] == "ok"
    assert (
        any("moire" in a for a in res["artifacts_detected"])
        or res["confidence_score"] >= 0.30
    )


# -----------------------------------------------------------------------------
# 4. Strictness & Concurrency Stress
# -----------------------------------------------------------------------------


def test_simulation_strictness_paranoid_vs_balanced(skill):
    """Paranoid strictness lowers detection thresholds."""
    w, h = 200, 150
    arr = np.full((h, w, 3), (120, 130, 140), dtype=np.uint8)
    # Mild localized disturbance
    arr[20:40, 20:40] = 200
    img = Image.fromarray(arr)
    b64_str = _to_b64(img, "JPEG")

    res_balanced = skill.execute(
        {"action": "analyze", "media_bytes_b64": b64_str, "strictness": "balanced"}
    )
    res_paranoid = skill.execute(
        {"action": "analyze", "media_bytes_b64": b64_str, "strictness": "paranoid"}
    )

    assert res_balanced["status"] == "ok"
    assert res_paranoid["status"] == "ok"
    # Paranoid is equal or more sensitive
    assert res_paranoid["confidence_score"] >= res_balanced[
        "confidence_score"
    ] or res_paranoid["verdict"] in (
        "suspicious",
        "tampered_likely",
    )


@pytest.mark.asyncio
async def test_stress_concurrent_async_load(skill):
    """Executes 15 simultaneous analyses under asyncio.gather without interference."""
    clean_img = _make_test_image(150, 100)
    b64_str = _to_b64(clean_img, "JPEG")

    tasks = [
        skill.aexecute({"action": "analyze", "media_bytes_b64": b64_str})
        for _ in range(15)
    ]
    results = await asyncio.gather(*tasks)

    assert len(results) == 15
    for res in results:
        assert res["status"] == "ok"
        assert res["offline"] is True
        assert res["verdict"] in ("authentic_likely", "suspicious")

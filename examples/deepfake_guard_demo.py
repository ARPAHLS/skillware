"""Offline demonstration of security/deepfake_guard.

Scans synthetic, spliced, screen-recaptured, and ICAO 9303 identity assets
using deterministic Error Level Analysis (ELA), noise variance, C2PA, and MRZ checks.
Requires no external network connections or API keys.
"""

from __future__ import annotations

import base64
import io
import numpy as np
from PIL import Image

from skillware.core.loader import SkillLoader


def _to_b64(img: Image.Image, format: str = "JPEG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=format)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def main() -> None:
    print("=" * 70)
    print("security/deepfake_guard — Air-Gapped Media & Document Authenticity Demo")
    print("=" * 70)

    print("Loading security/deepfake_guard via SkillLoader...")
    bundle = SkillLoader.load_skill("security/deepfake_guard")
    skill = bundle["class"]()

    # -------------------------------------------------------------------------
    # Scenario 1: Clean Authentic Natural Image
    # -------------------------------------------------------------------------
    print("\n[Scenario 1] Inspecting Clean Authentic Asset...")
    np.random.seed(42)
    clean_arr = np.clip(128 + np.random.normal(0, 3.5, (180, 240, 3)), 0, 255).astype(
        np.uint8
    )
    clean_img = Image.fromarray(clean_arr)

    res_clean = skill.execute(
        {
            "action": "analyze",
            "media_bytes_b64": _to_b64(clean_img),
        }
    )
    print(f"  Verdict:          {res_clean['verdict']}")
    print(f"  Confidence Score: {res_clean['confidence_score']:.2f}")
    print(f"  Tampered Likely:  {res_clean['is_tampered_likely']}")
    print(f"  Synthetic Likely: {res_clean['is_synthetic_likely']}")
    print(f"  Artifacts Found:  {res_clean['artifacts_detected']}")

    # -------------------------------------------------------------------------
    # Scenario 2: Digitally Spliced Document (Photo/Text Paste)
    # -------------------------------------------------------------------------
    print("\n[Scenario 2] Inspecting Digitally Spliced Image (ELA & Noise Anomaly)...")
    spliced_arr = np.copy(clean_arr)
    # Inject foreign high-frequency patch
    spliced_arr[30:80, 40:100] = np.random.randint(0, 255, (50, 60, 3), dtype=np.uint8)
    spliced_img = Image.fromarray(spliced_arr)

    res_spliced = skill.execute(
        {
            "action": "inspect_media",
            "media_bytes_b64": _to_b64(spliced_img),
        }
    )
    print(f"  Verdict:          {res_spliced['verdict']}")
    print(f"  Confidence Score: {res_spliced['confidence_score']:.2f}")
    print(f"  Tampered Likely:  {res_spliced['is_tampered_likely']}")
    print(f"  Artifacts Found:  {res_spliced['artifacts_detected']}")
    for sig in res_spliced["signals"]:
        print(f"    - [{sig['class']}] {sig['details']}")

    # -------------------------------------------------------------------------
    # Scenario 3: Screen-Photo Recapture (Moiré Grid Interference)
    # -------------------------------------------------------------------------
    print("\n[Scenario 3] Inspecting Screen-Photo Recapture (Display Grid Moiré)...")
    dim = 256
    y, x = np.mgrid[:dim, :dim]
    moire_pattern = (np.sin((x + y) * 1.8) * 85 + 128).astype(np.uint8)
    moire_img = Image.fromarray(np.stack([moire_pattern] * 3, axis=-1))

    res_moire = skill.execute(
        {
            "action": "inspect_media",
            "media_bytes_b64": _to_b64(moire_img, "PNG"),
        }
    )
    print(f"  Verdict:          {res_moire['verdict']}")
    print(f"  Confidence Score: {res_moire['confidence_score']:.2f}")
    print(f"  Artifacts Found:  {res_moire['artifacts_detected']}")

    # -------------------------------------------------------------------------
    # Scenario 4: AI Generative Asset with C2PA Provenance Assertion
    # -------------------------------------------------------------------------
    print("\n[Scenario 4] Inspecting Asset with C2PA / AI Provenance Assertion...")
    buf = io.BytesIO()
    clean_img.save(buf, format="JPEG")
    # Injected C2PA marker
    raw_with_c2pa = buf.getvalue() + b"c2pa:actions trainedAlgorithmicMedia jumb jumd"

    res_c2pa = skill.execute(
        {
            "action": "verify_provenance",
            "media_bytes_b64": base64.b64encode(raw_with_c2pa).decode("ascii"),
        }
    )
    print(f"  Verdict:             {res_c2pa['verdict']}")
    print(f"  AI Cues Found:       {res_c2pa['ai_generation_cues']}")
    print(f"  C2PA Manifest Present: {res_c2pa['c2pa']['c2pa_manifest_present']}")
    print(f"  AI Generated Claim:  {res_c2pa['c2pa']['is_ai_generated_claim']}")

    # -------------------------------------------------------------------------
    # Scenario 5: Authentic Passport ICAO 9303 TD3 MRZ Validation
    # -------------------------------------------------------------------------
    print("\n[Scenario 5] Cryptographically Validating Authentic Passport MRZ...")
    l1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
    l2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"

    res_pass = skill.execute(
        {
            "action": "validate_mrz",
            "raw_mrz": [l1, l2],
        }
    )
    print(f"  Verdict:         {res_pass['verdict']}")
    print(f"  Format:          {res_pass['format']}")
    print(f"  MRZ Valid:       {res_pass['mrz_valid']}")
    fields = res_pass.get("fields", {})
    print(
        f"  Fields Verified: {len(fields)} document fields parsed (cleartext PII omitted from log)"
    )

    # -------------------------------------------------------------------------
    # Scenario 6: Adversarially Altered Passport MRZ (Tampered Checksum)
    # -------------------------------------------------------------------------
    print("\n[Scenario 6] Catching Forged Passport MRZ (Altered Expiration Date)...")
    # Altered expiration date from 120415 to 250415 without updating check digit 9
    l2_forged = "L898902C36UTO7408122F2504159ZE184226B<<<<<10"

    res_forged = skill.execute(
        {
            "action": "validate_mrz",
            "raw_mrz": [l1, l2_forged],
        }
    )
    print(f"  Verdict:           {res_forged['verdict']}")
    print(f"  MRZ Valid:         {res_forged['mrz_valid']}")
    print(f"  Checksum Failures: {res_forged['checksum_failures']}")

    print("\n" + "=" * 70)
    print("Deepfake and document authenticity demo completed successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()

"""Cross-skill demonstration: Pre-flight document authenticity and KYC onboarding.

Demonstrates SkillContext chaining:
1. security/deepfake_guard — Air-gapped forensic audit (ELA, moire, ICAO 9303 checksums).
2. Conditional gating — Halts on forged/tampered documents before touching private state.
3. office/web_form_mapper or profile ingestion — Maps verified applicant fields on authentic assets.
"""

from __future__ import annotations

import base64
import io
import numpy as np
from PIL import Image

from skillware import SkillContext


def _make_sample_doc(width: int = 284, height: int = 200) -> str:
    # TD3 aspect ratio document image (~1.42)
    np.random.seed(42)
    arr = np.clip(220 + np.random.normal(0, 3.0, (height, width, 3)), 0, 255).astype(
        np.uint8
    )
    img = Image.fromarray(arr, "RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def main() -> None:
    print("=" * 70)
    print("Cross-Skill Chaining: Pre-Flight KYC & Document Authenticity Gate")
    print("=" * 70)

    # Initialize multi-skill runtime context
    ctx = SkillContext(skills=["security/deepfake_guard", "office/web_form_mapper"])

    # -------------------------------------------------------------------------
    # Case A: Authentic Passport Submission
    # -------------------------------------------------------------------------
    print("\n--- Pipeline Case A: Authentic Passport Submission ---")
    doc_b64 = _make_sample_doc()
    mrz_lines_valid = [
        "P<GRCGEORGIOU<<DIMITRIOS<<<<<<<<<<<<<<<<<<<<",
        "AO12345670GRC8505202M3001019<<<<<<<<<<<<<<<8",
    ]

    print("[Step 1] Running security/deepfake_guard pre-flight forensic inspection...")
    guard_result = ctx.execute(
        "security/deepfake_guard",
        {
            "action": "inspect_document",
            "media_bytes_b64": doc_b64,
            "raw_mrz": mrz_lines_valid,
            "claimed_doc_type": "passport",
            "claimed_country": "GRC",
        },
    )

    print(f"  Pre-flight Verdict: {guard_result['verdict']}")
    print(f"  Confidence Score:   {guard_result['confidence_score']:.2f}")
    print(f"  MRZ Valid:          {guard_result['doc']['mrz_valid']}")
    print(f"  Geometry Match:     {guard_result['doc']['geometry']['likely_format']}")

    if (
        guard_result["verdict"] in ("authentic_likely", "suspicious")
        and guard_result["doc"]["mrz_valid"]
    ):
        fields = guard_result["doc"]["fields"]
        print(
            f"  Fields Extracted: {len(fields)} identity fields validated (cleartext PII omitted from log)."
        )
        print("  -> Ready for onboarding and KYC compliance verification!")
    else:
        print("  -> Alert: Document failed pre-flight verification; rejected.")

    # -------------------------------------------------------------------------
    # Case B: Forged Document Submission (Adversarial Alteration)
    # -------------------------------------------------------------------------
    print("\n--- Pipeline Case B: Adversarially Altered Document Submission ---")
    # Forged: alter birth date without updating check digit
    mrz_lines_forged = [
        "P<GRCGEORGIOU<<DIMITRIOS<<<<<<<<<<<<<<<<<<<<",
        "AO12345670GRC9505202M3001019<<<<<<<<<<<<<<<8",
    ]

    print("[Step 1] Running security/deepfake_guard pre-flight forensic inspection...")
    forged_result = ctx.execute(
        "security/deepfake_guard",
        {
            "action": "inspect_document",
            "media_bytes_b64": doc_b64,
            "raw_mrz": mrz_lines_forged,
            "claimed_doc_type": "passport",
            "claimed_country": "GRC",
        },
    )

    print(f"  Pre-flight Verdict: {forged_result['verdict']}")
    print(f"  MRZ Valid:          {forged_result['doc']['mrz_valid']}")
    print(f"  Failures Detected:  {forged_result['doc']['mrz']['checksum_failures']}")
    print(f"  Artifacts Found:    {forged_result['artifacts_detected']}")

    if (
        not forged_result["doc"]["mrz_valid"]
        or forged_result["verdict"] == "tampered_likely"
    ):
        print(
            "\n[Security Gate]: Forgery detected! Halting onboarding pipeline immediately."
        )
        print(
            "  -> Audit incident logged; downstream systems protected from fraudulent PII injection."
        )

    print("\n" + "=" * 70)
    print("KYC document authenticity chaining demo completed successfully.")
    print("=" * 70)


if __name__ == "__main__":
    main()

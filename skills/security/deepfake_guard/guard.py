"""Orchestrator for security/deepfake_guard multi-signal forensic analysis."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Union

from PIL import Image

try:
    from .constants import (
        VERDICT_AUTHENTIC,
        VERDICT_SUSPICIOUS,
        VERDICT_SYNTHETIC,
        VERDICT_TAMPERED,
    )
    from .document import analyze_document_geometry, parse_and_validate_mrz
    from .forensics import (
        analyze_spectral_synthetic,
        compute_ela,
        compute_noise_residuals,
        detect_copy_move,
        detect_screen_moire,
        load_image,
    )
    from .provenance import extract_metadata_and_provenance
except (ImportError, ValueError):
    import sys

    _pkg_dir = os.path.dirname(os.path.abspath(__file__))
    if _pkg_dir not in sys.path:
        sys.path.insert(0, _pkg_dir)
    from constants import (
        VERDICT_AUTHENTIC,
        VERDICT_SUSPICIOUS,
        VERDICT_SYNTHETIC,
        VERDICT_TAMPERED,
    )
    from document import analyze_document_geometry, parse_and_validate_mrz
    from forensics import (
        analyze_spectral_synthetic,
        compute_ela,
        compute_noise_residuals,
        detect_copy_move,
        detect_screen_moire,
        load_image,
    )
    from provenance import extract_metadata_and_provenance


def analyze_asset(
    source: Optional[Union[str, bytes, Image.Image]] = None,
    raw_mrz: Optional[Union[str, List[str]]] = None,
    raw_bytes: Optional[bytes] = None,
    mode: str = "auto",
    claimed_doc_type: Optional[str] = None,
    claimed_country: Optional[str] = None,
    strictness: str = "balanced",
) -> Dict[str, Any]:
    """
    Executes multi-signal local forensic inspection on an image or document asset.
    Returns a structured, explainable evidence bundle with signals and verdict.
    """
    signals: List[Dict[str, Any]] = []
    artifacts_detected: List[str] = []
    limitations: List[str] = [
        (
            "Air-gapped optical/pixel analysis only; physical NFC chip / optical variable ink (OVI) "
            "requires specialized hardware."
        ),
        "Signals represent forensic anomalies, not legal proof of authorship.",
    ]

    image: Optional[Image.Image] = None

    if source is not None:
        if isinstance(source, bytes) and raw_bytes is None:
            raw_bytes = source
        image = load_image(source)

    # 1. Provenance & Metadata Scan
    prov_result: Dict[str, Any] = {}
    if image is not None:
        prov_result = extract_metadata_and_provenance(image, raw_bytes=raw_bytes)

        if prov_result.get("has_manipulation_software"):
            tools = ", ".join(prov_result["manipulation_tools"])
            signals.append(
                {
                    "class": "manipulation_software_metadata",
                    "score": 0.85,
                    "details": f"Editing software signatures detected in metadata: {tools}",
                }
            )
            artifacts_detected.append("manipulation_software_trace")

        if prov_result.get("has_ai_provenance_cues"):
            cues = ", ".join(prov_result["ai_generation_cues"])
            signals.append(
                {
                    "class": "c2pa_ai_generated_claim",
                    "score": 0.95,
                    "details": f"AI generation / synthetic media assertion found in metadata: {cues}",
                }
            )
            artifacts_detected.append("ai_provenance_metadata")

    # 2. Classical Image Forensics
    ela_res: Dict[str, Any] = {}
    noise_res: Dict[str, Any] = {}
    moire_res: Dict[str, Any] = {}
    copy_res: Dict[str, Any] = {}
    spectral_res: Dict[str, Any] = {}

    if image is not None:
        # Error Level Analysis
        ela_res = compute_ela(image)
        if ela_res.get("is_anomalous"):
            signals.append(
                {
                    "class": "ela_hotspot_inconsistency",
                    "score": ela_res["anomaly_score"],
                    "details": f"Detected {ela_res['hotspot_count']} localized compression anomaly hotspots.",
                }
            )
            artifacts_detected.append("jpeg_ela_inconsistency")

        # High-pass Noise Residuals
        noise_res = compute_noise_residuals(image)
        if noise_res.get("is_inconsistent"):
            signals.append(
                {
                    "class": "noise_variance_divergence",
                    "score": noise_res["noise_score"],
                    "details": (
                        f"Local noise variance divergence ratio is {noise_res['variance_ratio']:.2f}x "
                        "(splicing cue)."
                    ),
                }
            )
            artifacts_detected.append("noise_residual_inconsistency")

        # Screen Moire / Recapture Grid
        moire_res = detect_screen_moire(image)
        if moire_res.get("moire_detected"):
            signals.append(
                {
                    "class": "screen_recapture_moire",
                    "score": moire_res["score"],
                    "details": (
                        f"Periodic frequency delta peak ratio is {moire_res['peak_ratio']:.2f} "
                        "(screen-photo recapture cue)."
                    ),
                }
            )
            artifacts_detected.append("screen_recapture_moire")

        # Copy-Move Block Matching
        copy_res = detect_copy_move(image)
        if copy_res.get("copy_move_detected"):
            signals.append(
                {
                    "class": "copy_move_cloning",
                    "score": copy_res["score"],
                    "details": f"Identified {copy_res['duplicate_pairs_found']} matching spatial block clusters.",
                }
            )
            artifacts_detected.append("copy_move_cloning")

        # Frequency Domain Synthetic Slope
        spectral_res = analyze_spectral_synthetic(image)
        if spectral_res.get("synthetic_cue_detected"):
            signals.append(
                {
                    "class": "spectral_synthetic_profile",
                    "score": spectral_res["spectral_anomaly_score"],
                    "details": (
                        f"Radial spectral slope ({spectral_res['spectral_slope']}) indicates "
                        "synthetic diffusion frequency roll-off."
                    ),
                }
            )
            artifacts_detected.append("synthetic_spectral_roll_off")

    # 3. Document Analysis & MRZ Verification
    doc_result: Dict[str, Any] = {}
    is_doc_mode = (
        (mode == "document") or (raw_mrz is not None) or (claimed_doc_type is not None)
    )

    if raw_mrz:
        mrz_eval = parse_and_validate_mrz(raw_mrz)
        doc_result["mrz"] = mrz_eval
        doc_result["mrz_valid"] = mrz_eval["mrz_valid"]
        doc_result["detected_type"] = mrz_eval["fields"].get("document_type")
        doc_result["jurisdiction"] = mrz_eval["fields"].get("issuer")
        doc_result["fields"] = mrz_eval["fields"]

        if not mrz_eval["mrz_valid"]:
            failures = ", ".join(mrz_eval["checksum_failures"])
            signals.append(
                {
                    "class": "mrz_checksum_failure",
                    "score": 0.95,
                    "details": f"ICAO 9303 checksum verification failed: {failures}",
                }
            )
            artifacts_detected.append("mrz_checksum_mismatch")

        # Check claimed jurisdiction match
        if claimed_country and doc_result.get("jurisdiction"):
            claimed_code = claimed_country.strip().upper()
            mrz_code = str(doc_result["jurisdiction"]).upper()
            if claimed_code not in mrz_code and mrz_code not in claimed_code:
                signals.append(
                    {
                        "class": "claimed_jurisdiction_mismatch",
                        "score": 0.80,
                        "details": f"Claimed country '{claimed_country}' does not match MRZ issuer code '{mrz_code}'.",
                    }
                )
                artifacts_detected.append("jurisdiction_mismatch")

    # Document Geometry
    if image is not None and is_doc_mode:
        geo = analyze_document_geometry(image, claimed_doc_type=claimed_doc_type)
        doc_result["geometry"] = geo
        if not geo["geometry_consistent"]:
            signals.append(
                {
                    "class": "document_geometry_inconsistency",
                    "score": 0.65,
                    "details": (
                        f"Document aspect ratio ({geo['aspect_ratio']}) is inconsistent with "
                        f"claimed type '{claimed_doc_type}'."
                    ),
                }
            )
            artifacts_detected.append("document_geometry_inconsistency")

    # 4. Synthesize Verdict & Risk Scoring
    is_paranoid = strictness.strip().lower() == "paranoid"
    tamper_threshold = 0.50 if is_paranoid else 0.65
    synthetic_threshold = 0.55 if is_paranoid else 0.70

    # Calculate sub-scores
    tamper_scores = [
        s["score"]
        for s in signals
        if s["class"]
        in (
            "ela_hotspot_inconsistency",
            "noise_variance_divergence",
            "copy_move_cloning",
            "manipulation_software_metadata",
            "mrz_checksum_failure",
        )
    ]
    max_tamper = max(tamper_scores) if tamper_scores else 0.0

    synthetic_scores = [
        s["score"]
        for s in signals
        if s["class"]
        in (
            "c2pa_ai_generated_claim",
            "spectral_synthetic_profile",
        )
    ]
    max_synthetic = max(synthetic_scores) if synthetic_scores else 0.0

    # Composite confidence score
    all_scores = [s["score"] for s in signals]
    if all_scores:
        confidence_score = round(
            min(1.0, max(all_scores) * 0.8 + (len(signals) * 0.06)), 2
        )
    else:
        confidence_score = 0.10

    is_tampered_likely = max_tamper >= tamper_threshold
    is_synthetic_likely = max_synthetic >= synthetic_threshold

    # Verdict assignment
    if is_tampered_likely and is_synthetic_likely:
        verdict = VERDICT_TAMPERED
    elif is_tampered_likely:
        verdict = VERDICT_TAMPERED
    elif is_synthetic_likely:
        verdict = VERDICT_SYNTHETIC
    elif len(signals) >= 1 or confidence_score >= 0.40:
        verdict = VERDICT_SUSPICIOUS
    else:
        verdict = VERDICT_AUTHENTIC

    # Generate human/operator readable summary
    if verdict == VERDICT_AUTHENTIC:
        summary = (
            "Asset appears authentic: no significant digital tampering, synthetic artifacts, "
            "or checksum anomalies detected."
        )
    elif verdict == VERDICT_TAMPERED:
        reasons = [s["details"] for s in signals if s.get("score", 0) >= 0.6] or [
            s["details"] for s in signals
        ]
        summary = (
            f"Digital tampering detected: {reasons[0]}"
            if reasons
            else "Digital tampering detected."
        )
    elif verdict == VERDICT_SYNTHETIC:
        reasons = [s["details"] for s in signals if s.get("score", 0) >= 0.6] or [
            s["details"] for s in signals
        ]
        summary = (
            f"Synthetic media detected: {reasons[0]}"
            if reasons
            else "Synthetic media markers detected."
        )
    elif verdict == VERDICT_SUSPICIOUS:
        reasons = [s["details"] for s in signals]
        summary = (
            f"Suspicious cues detected: {reasons[0]}"
            if reasons
            else "Suspicious anomalies detected; manual review recommended."
        )
    else:
        summary = f"Forensic analysis completed with verdict '{verdict}'."

    return {
        "offline": True,
        "verdict": verdict,
        "summary": summary,
        "is_synthetic_likely": is_synthetic_likely,
        "is_tampered_likely": is_tampered_likely,
        "confidence_score": confidence_score,
        "signals": signals,
        "artifacts_detected": artifacts_detected,
        "doc": doc_result if doc_result else None,
        "provenance": prov_result if prov_result else None,
        "limitations": limitations,
    }

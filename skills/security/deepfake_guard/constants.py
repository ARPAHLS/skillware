"""Constants, schemas, and signatures for security/deepfake_guard."""

from __future__ import annotations

from typing import Tuple

# -----------------------------------------------------------------------------
# ICAO 9303 Machine Readable Travel Document (MRTD) Constants
# -----------------------------------------------------------------------------

# Cyclical 7-3-1 weight pattern prescribed by ICAO 9303 Doc Part 3
ICAO_WEIGHTS: Tuple[int, int, int] = (7, 3, 1)

# Standard MRZ dimensions (characters per line x number of lines)
MRZ_TD1_SHAPE: Tuple[int, int] = (30, 3)  # ID-1 National ID (90 chars total)
MRZ_TD2_SHAPE: Tuple[int, int] = (
    36,
    2,
)  # ID-2 Official travel doc / Visa (72 chars total)
MRZ_TD3_SHAPE: Tuple[int, int] = (44, 2)  # ID-3 Passport data page (88 chars total)

# Document physical aspect ratios (width / height) defined in ISO/IEC 7810
ASPECT_RATIO_TD1: float = 85.60 / 53.98  # ~1.586 (Credit card / modern ID card)
ASPECT_RATIO_TD2: float = 105.0 / 74.0  # ~1.419 (A7 format / French ID)
ASPECT_RATIO_TD3: float = 125.0 / 88.0  # ~1.420 (Passport data page)
ASPECT_RATIO_TOLERANCE: float = 0.25

# -----------------------------------------------------------------------------
# Metadata & Software Signatures
# -----------------------------------------------------------------------------

# Known digital manipulation software tags in EXIF / XMP / TIFF headers
SUSPICIOUS_SOFTWARE_SIGNATURES: Tuple[str, ...] = (
    "adobe photoshop",
    "photoshop",
    "adobe firefly",
    "gimp",
    "canva",
    "paint.net",
    "pixelmator",
    "affinity photo",
    "coreldraw",
    "midjourney",
    "stable diffusion",
    "stablediffusion",
    "dall-e",
    "dalle",
    "comfyui",
    "automatic1111",
    "fooocus",
    "novelai",
    "flux.1",
    "faceapp",
    "deepfacelab",
    "roop",
    "faceswap",
)

# Known AI generation model keywords found in XMP, prompt metadata, or PNG chunks
AI_GENERATOR_KEYWORDS: Tuple[str, ...] = (
    "prompt",
    "negative_prompt",
    "sampler",
    "cfg_scale",
    "seed",
    "steps",
    "model_hash",
    "clip_skip",
    "denoising_strength",
    "midjourney",
    "stable-diffusion",
    "dall-e-3",
    "dall-e-2",
    "flux",
    "c2pa.actions",
    "trainedalgorithmicmedia",
    "compositeWithTrainedAlgorithmicMedia",
)

# C2PA (Coalition for Content Provenance and Authenticity) JUMBF box signatures
C2PA_BOX_SIGNATURES: Tuple[bytes, ...] = (
    b"c2pa",
    b"jumd",
    b"jumb",
    b"c2bi",
    b"c2ma",
)

# -----------------------------------------------------------------------------
# Forensic Thresholds
# -----------------------------------------------------------------------------

DEFAULT_JPEG_ELA_QUALITY: int = 90
ELA_SCALE_FACTOR: float = 15.0
ELA_ANOMALY_ZSCORE: float = 2.4

# High-frequency noise anomaly threshold (ratio of max to median tile variance)
NOISE_INCONSISTENCY_THRESHOLD: float = 3.8

# Periodic frequency peak threshold for screen moire / LCD recapture detection
MOIRE_PEAK_RATIO_THRESHOLD: float = 4.2

# Synthetic frequency roll-off threshold
SPECTRAL_SLOPE_ANOMALY_THRESHOLD: float = 2.8

# -----------------------------------------------------------------------------
# Verdict Classifications
# -----------------------------------------------------------------------------

VERDICT_AUTHENTIC: str = "authentic_likely"
VERDICT_SUSPICIOUS: str = "suspicious"
VERDICT_TAMPERED: str = "tampered_likely"
VERDICT_SYNTHETIC: str = "synthetic_likely"

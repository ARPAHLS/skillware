# Deepfake & Document Authenticity Guard (`security/deepfake_guard`)

Deterministic forensic and document authenticity verification engine. Inspects images, scans, and identity credentials (passports, national IDs, residence permits) for synthetic AI generation, digital tampering (photoshop, ELA hotspots, copy-move), and document forgery without calling third-party cloud APIs.

## Input Entry Points

Pass media and documents through whichever channel fits your host agent workflow:
1. **Local upload / dropped file**: Supply `image_path` (or `media_path`) with the filesystem path.
2. **In-memory bytes / browser snapshot**: Supply `image_base64` (or `media_bytes_b64`) as raw base64 or a data URI.
3. **Public web link**: Supply `url` (or `image_url`) to fetch an image behind internal SSRF guards.
4. **Machine Readable Zone text**: Supply `mrz_string` (or `raw_mrz`) with 2 or 3 lines of passport/ID MRZ text.

## What This Skill Can Do (Action Choices)

- `action: "analyze"` (Default) — Full multi-signal forensic inspection combining metadata, ELA, noise residual variance, Fourier moiré spectrum, and document structure/MRZ.
- `action: "inspect_document"` — Specialized KYC document authenticity pipeline (ICAO 9303 checksums, facial photo splicing check, and ISO 7810 ID-1 aspect ratio geometry).
- `action: "inspect_media"` — Image-only pixel forensics (Error Level Analysis, high-pass noise residuals, and copy-move block matching).
- `action: "verify_provenance"` — Fast header inspection for EXIF editing software tags, XMP generator cues, and C2PA Content Credentials manifests.
- `action: "validate_mrz"` — Standalone cryptographic validation of ICAO 9303 MRZ strings (TD1, TD2, TD3).

## What It Checks in Each Case

1. **Digital Tampering & Splicing**:
   - Evaluates high-pass Laplacian noise residual variance and Median Absolute Deviation (MAD) across tiles to detect spliced facial patches or pasted elements.
   - Computes Error Level Analysis (ELA) differential JPEG compression variance to uncover digitally altered regions.
   - Scans 16×16 spatial blocks for copy-move cloning used to conceal text, serial numbers, or features.
2. **Synthetic Media & AI Generation**:
   - Detects C2PA JUMBF headers, `c2pa` manifests, and Adobe Content Credentials.
   - Extracts EXIF/XMP markers for generative AI tools (Midjourney, DALL-E, Stable Diffusion, ComfyUI, `trainedAlgorithmicMedia`).
   - Analyzes radial power spectrum slope for unnatural high-frequency roll-off characteristic of diffusion models.
3. **Document Forgery & Recapture Fraud**:
   - Calculates cyclic `(7, 3, 1)` modulo-10 check digits across TD1 (3×30), TD2 (2×36), and TD3 (2×44) machine-readable zones.
   - Verifies expiration dates and checks document number integrity.
   - Inspects 2D Fast Fourier Transform (FFT) peak ratios to catch screen-photo recapture grids when someone photographs an LCD/OLED monitor displaying an ID.
   - Verifies ISO/IEC 7810 ID-1 geometry conformity (~1.586 ± 5%).

## Output Interpretations & Cases XYZ

- **Case Authentic (`verdict: "authentic_likely"`)**:
  - `confidence_score` ≤ 0.30, `artifacts_detected`: `[]`.
  - `summary`: "Asset appears authentic: no significant digital tampering, synthetic artifacts, or checksum anomalies detected."
  - **Host Action**: Proceed with automated approval or KYC onboarding.
- **Case Spliced / Tampered (`verdict: "tampered_likely"`)**:
  - `confidence_score` ≥ 0.50, `artifacts_detected` includes `noise_residual_inconsistency`, `jpeg_ela_inconsistency`, `copy_move_cloning`, or `mrz_checksum_mismatch`.
  - `summary`: Explains specific discrepancy (e.g. "Digital tampering detected: Local noise variance divergence ratio is 5.56x (splicing cue).").
  - **Host Action**: Reject automated onboarding; quarantine asset; route to fraud department.
- **Case AI Generated (`verdict: "synthetic_likely"`)**:
  - `artifacts_detected` includes `c2pa_ai_generated_claim` or `synthetic_spectral_roll_off`.
  - `summary`: Explains AI generation markers detected.
  - **Host Action**: Flag synthetic origin; disallow as real identity document.
- **Case Recaptured / Inconsistent Geometry (`verdict: "suspicious"`)**:
  - `artifacts_detected` includes `screen_recapture_moire` or `document_geometry_inconsistency`.
  - `summary`: Identifies physical-to-digital capture anomalies.
  - **Host Action**: Prompt applicant to provide a direct physical document scan or high-resolution photo without glare/screen reflection.

# Deepfake & Synthetic Media Guard

**Domain:** `security`
**Skill ID:** `security/deepfake_guard`
**Issuer:** [@rosspeili](https://github.com/rosspeili) ([@ARPAHLS](https://github.com/ARPAHLS))
<!-- skill-doc-meta:begin -->
**Version**: `0.1.0` — 6 Oct 2026
<!-- skill-doc-meta:end -->
<!-- skill-intent:begin -->
**Solves:** Deterministic offline forensic verification of media and KYC documents for AI generation, digital tampering, C2PA provenance, and ICAO 9303 MRZ forgery.
**Works with:** Gemini, Claude, OpenAI, DeepSeek, Ollama, and Bedrock-compatible host loops.
**Runtime:** Hard-offline. No API keys, no external SaaS calls.
<!-- skill-intent:end -->
**Recommended install:** `pip install "skillware[security_deepfake_guard]"`. See [Install extras](../../usage/install_extras.md).

[Skill Library](../README.md) · [Security](README.md) · [Testing](../../TESTING.md)

An offline, air-gapped forensic verification engine designed to protect autonomous AI agents, KYC pipelines, and document-processing workflows against **deepfakes, synthetic media, digital tampering, and forged identity documents**.

Unlike probabilistic cloud models that leak sensitive credentials to external endpoints or hallucinate under distribution shift, `security/deepfake_guard` executes **deterministic signal processing and mathematical validation** entirely in-memory:
1. **ICAO 9303 Check Digit Validation:** Computes cyclic `(7, 3, 1)` check digits across TD1 (ID cards/residence permits), TD2, and TD3 (passports) to detect forged numbers, expiration dates, and birth dates.
2. **C2PA / Content Credentials & Provenance:** Parses JUMBF boxes, digital watermarks, generative AI metadata tags (`trainedAlgorithmicMedia`, Midjourney, ComfyUI, DALL-E, Stable Diffusion), and photo editing markers (Photoshop, GIMP).
3. **Forensic Signal Analysis:** Evaluates Error Level Analysis (ELA) JPEG recompression residuals, high-pass Laplacian noise variance consistency, spatial copy-move cloning, radial spectral slope decay (diffusion artifact fingerprinting), and 2D FFT moiré peak ratios (detecting recaptured screens in KYC photos).

> **Disclaimer:** Heuristic and signal processing forensics provide high-confidence anomaly indicators and check digit guarantees, but cannot replace cryptographic Public Key Infrastructure (PKI) chip authentication for ePassports. Use in defense-in-depth pipelines alongside [`security/prompt_injection_firewall`](prompt_injection_firewall.md) and [`compliance/pii_masker`](../compliance/pii_masker.md).

## What It Checks

1. **ICAO 9303 Check Digit & Document Integrity** — Validates 7-3-1 weights for document number, birth date, expiration date, optional data, and composite overall checksum across TD1 (3×30), TD2 (2×36), and TD3 (2×44) machine-readable zones. Flags expired documents and invalid checksums.
2. **ISO/IEC 7810 ID-1 Geometry Verification** — Validates aspect ratio conformity (target ~1.586 ± 5%) when document dimensions are provided.
3. **Moiré Recapture Detection** — High-frequency 2D Fast Fourier Transform (FFT) peak ratio analysis to detect screen raster grids when a fraudster photographs an LCD/OLED monitor displaying someone else's ID.
4. **C2PA Content Credentials & AI Metadata** — Detects C2PA JUMBF manifests, `c2pa`, `jumd` signatures, Adobe Content Credentials, and explicit AI tool tags.
5. **Editing Software Footprints** — Flags EXIF and XMP metadata traces left by Photoshop, GIMP, Canva, InDesign, and other desktop manipulation software.
6. **Error Level Analysis (ELA)** — Measures differential JPEG compression error variance across image regions to uncover digitally spliced or edited elements.
7. **Laplacian Noise Residual Variance** — High-pass filtering to measure spatial consistency of sensor noise. Spliced or cloned regions exhibit sharp noise discontinuities.
8. **Copy-Move Forgery Detection** — Spatial block-matching hash indexing across 16×16 blocks to detect cloned or stamped pixels concealing text or features.
9. **Radial Spectral Slope Analysis** — Azimuthally averaged power spectrum slope calculation; diffusion models commonly exhibit anomalous high-frequency falloff or unnatural smoothness.

## Bundle layout

The skill lives in `skills/security/deepfake_guard/`. Roles: [Skill anatomy](../../introduction.md#skill-anatomy) and the [glossary](../../glossary.md). **Contract** — see Manifest Details below. **Directive** — `instructions.md`. **Effect** — `skill.py`. **Assurance** — `test_skill.py`.

## Manifest Details

**Parameters Schema:**
* `action` (string, optional): Target operation (`analyze` [default], `inspect_media`, `inspect_document`, `verify_provenance`, `validate_mrz`).
* `image_path` / `media_path` (string, optional): Local filesystem path to the media or document image.
* `image_base64` / `media_bytes_b64` (string, optional): Base64-encoded image payload or data URI for in-memory processing.
* `url` / `image_url` (string, optional): Public HTTP(S) URL to fetch image data behind SSRF protection.
* `mrz_string` / `raw_mrz` (string, optional): Raw 2-line or 3-line ICAO 9303 MRZ string or line list.
* `expected_document_type` / `claimed_doc_type` (string, optional): Expected document format (`passport`, `national_id`, `drivers_license`, `certificate`, `auto` [default]).
* `strictness` (string, optional): Forensic sensitivity threshold (`balanced` [default], `paranoid`).

**Outputs Schema:**
* `status` (string): Execution status (`ok` or `error`).
* `verdict` (string): Overall assessment (`authentic_likely`, `suspicious`, `tampered_likely`, `synthetic_likely`, `inconclusive`).
* `confidence_score` (number): Composite forensic risk score between `0.0` (clean) and `1.0` (severe anomalies).
* `is_synthetic_likely` (boolean): Whether indicators flag generative AI origin.
* `is_tampered_likely` (boolean): Whether indicators flag digital manipulation or splicing.
* `artifacts_detected` (array of strings): Specific anomaly codes detected.
* `signals` (array of objects): Granular forensic signal findings.
* `summary` (string): Human-readable verdict summary and key findings.
* `offline` (boolean): True for local processing; false only if external URL was fetched.
* `limitations` (array of strings): Disclaimers and forensic boundary conditions.

## Environment

No environment variables or API keys are required. All image processing, Fourier analysis, and check digit calculations run strictly offline.

## Example Usage (Direct)

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("security/deepfake_guard")
skill = bundle["class"]()

# Validate passport MRZ with ICAO 9303 check digits
result = skill.execute(
    {
        "action": "validate_mrz",
        "mrz_string": (
            "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\n"
            "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
        ),
        "expected_document_type": "passport",
    }
)

print(result["verdict"])  # authentic_likely
print(result["mrz_valid"])  # True
print(result["summary"])
```

## Usage Examples

Guides: [Usage index](../../usage/README.md) · [Agent loops](../../usage/agent_loops.md)

Sample user message: *Verify this uploaded passport photo and MRZ string before proceeding with KYC onboarding.*

### Runnable examples

- Local execute: [`examples/deepfake_guard_demo.py`](../../../examples/deepfake_guard_demo.py)
- Pre-flight KYC chain: [`examples/kyc_authenticity_chain_demo.py`](../../../examples/kyc_authenticity_chain_demo.py)

### Direct execute

```python
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("security/deepfake_guard")
skill = bundle["class"]()
result = skill.execute({
    "action": "validate_mrz",
    "mrz_string": (
        "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\n"
        "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
    ),
})
print(result["verdict"], result["mrz_valid"])
```

### Gemini

```python
import google.genai as genai
from google.genai import types
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("security/deepfake_guard")
skill = bundle["class"]()
tool = SkillLoader.to_gemini_tool(bundle)
client = genai.Client()

mrz = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\nL898902C36UTO7408122F1204159ZE184226B<<<<<10"
response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=f"Verify this identity document MRZ for authenticity: {mrz}",
    config=types.GenerateContentConfig(
        tools=[tool],
        system_instruction=bundle["instructions"],
    ),
)
for part in response.candidates[0].content.parts:
    if part.function_call:
        result = skill.execute(dict(part.function_call.args))
        print(result["verdict"], result["summary"])
```

### Claude

```python
import os
import anthropic
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("security/deepfake_guard")
skill = bundle["class"]()
tool = SkillLoader.to_claude_tool(bundle)
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

mrz = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\nL898902C36UTO7408122F1204159ZE184226B<<<<<10"
response = client.messages.create(
    model="claude-3-7-sonnet-20250219",
    max_tokens=1024,
    system=bundle["instructions"],
    tools=[tool],
    messages=[{"role": "user", "content": f"Inspect this document MRZ: {mrz}"}],
)
for block in response.content:
    if block.type == "tool_use":
        result = skill.execute(dict(block.input))
        print(result["verdict"], result["confidence_score"])
```

### OpenAI

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("security/deepfake_guard")
skill = bundle["class"]()
openai_tool = SkillLoader.to_openai_tool(bundle)
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

mrz = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\nL898902C36UTO7408122F1204159ZE184226B<<<<<10"
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": f"Verify this identity document MRZ: {mrz}"},
    ],
    tools=[openai_tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result["verdict"], result["artifacts_detected"])
```

### DeepSeek

```python
import json
import os
from openai import OpenAI
from skillware.core.env import load_env_file
from skillware.core.loader import SkillLoader

load_env_file()
bundle = SkillLoader.load_skill("security/deepfake_guard")
skill = bundle["class"]()
deepseek_tool = SkillLoader.to_deepseek_tool(bundle)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
)

mrz = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\nL898902C36UTO7408122F1204159ZE184226B<<<<<10"
response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": bundle["instructions"]},
        {"role": "user", "content": f"Audit media document authenticity: {mrz}"},
    ],
    tools=[deepseek_tool],
)
message = response.choices[0].message
if message.tool_calls:
    args = json.loads(message.tool_calls[0].function.arguments)
    result = skill.execute(args)
    print(result["verdict"], result["summary"])
```

### Ollama (prompt mode)

```python
import json
from skillware.core.loader import SkillLoader

bundle = SkillLoader.load_skill("security/deepfake_guard")
skill = bundle["class"]()
prompt = (
    "You may call tools as JSON blocks.\n"
    f"Tool: {bundle['manifest']['name']}\n"
    f"Instructions:\n{bundle['instructions']}\n"
    "User: Check this passport MRZ for forgery:\n"
    "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\n"
    "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
)
print(prompt)
result = skill.execute({
    "action": "validate_mrz",
    "mrz_string": (
        "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<\n"
        "L898902C36UTO7408122F1204159ZE184226B<<<<<10"
    ),
})
print(json.dumps(result, indent=2))
```

---

<!-- skill-history:begin -->
## Skill history

Commits that touched this skill bundle or its catalog page ([`security/deepfake_guard`](https://github.com/ARPAHLS/skillware/tree/main/skills/security/deepfake_guard)).

| Commit | Description | Date | Version | Contributors |
| :--- | :--- | :--- | :--- | :--- |
| [`4692d22`](https://github.com/ARPAHLS/skillware/commit/4692d2262c1e4549ed3979accab9487822cbd331) | feat(security): add deepfake_guard — air-gapped media & document authenticity guard (#48) (#418) | 07 Oct 2026 | `0.1.0` | [@rosspeili](https://github.com/rosspeili) |
<!-- skill-history:end -->

## Enterprise disclaimer

This skill is provided for demonstration and integration purposes. It is intended as a starting point that you can adapt to your own data, schemas, and operational requirements. For an enterprise-grade version of this skill with dedicated support, SLAs, and customization, contact skills@arpacorp.net.

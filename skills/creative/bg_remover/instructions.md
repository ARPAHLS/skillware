# Background Remover (`creative/bg_remover`)

Removes backgrounds from **still images** locally using rembg. Accepts base64 or a local file path; returns a transparent PNG in `image_base64` and optionally writes to `output_path`. Does not fetch URLs or call cloud APIs.

## When to use

Invoke when the user asks to:

- remove the background from an image
- create a transparent PNG or PNG with alpha
- cut out, isolate, or extract a product, person, logo, or subject
- prepare an image for design, e-commerce, or compositing workflows

Trigger phrases include: "remove background", "transparent background", "cut out", "isolate product/person", "PNG with alpha", "no background".

## When not to use

Do **not** invoke for:

- videos or animated media
- batch folders or bulk directory processing
- requests to edit only in Photoshop, Canva, or other cloud editors when no local image bytes are available to pass in
- workflows where neither `image` nor `input_path` can be supplied

## Before calling

If the user wants background removal but has **not** provided an image, file path, or chat attachment, **ask** for one first. Do not call until input exists.

This skill does **not** fetch URLs. When the user provides an `https://…` link, download to a temp file first, then pass `input_path`.

For S3, GCS, Azure Blob, or Cloudflare R2: download the object to a temp file → `input_path` → after success upload from `output_path`. Auth and SDK calls stay in the host; this skill is local-only.

On the **first run** in a fresh environment, processing may take a few minutes while rembg downloads the ONNX model (~176 MB for `isnet-general-use`). Later runs reuse the cache and are much faster.

## Input (one required: `image` OR `input_path`)

| Scenario | Parameter |
| :--- | :--- |
| Uploaded, pasted, or **attached** image in chat | `image` (base64 from host encoding) |
| Local path (e.g. `D:\photos\cat.png`) | `input_path` (absolute path preferred on Windows) |
| URL | Download to temp file, then `input_path` |
| Cloud object storage | Download object → temp file → `input_path` |

If **both** `image` and `input_path` are sent, **`image` wins** (do not double-submit).

### Example payloads

Chat / attachment:

```json
{"image": "<base64>"}
```

Local file with output beside source:

```json
{
  "input_path": "D:\\photos\\1223.png",
  "output_path": "D:\\photos\\1223_no_bg.png"
}
```

URL (host downloads first; URL is not a skill parameter):

1. Download `https://example.com/product.jpg` → `/tmp/product.jpg`
2. Execute:

```json
{
  "input_path": "/tmp/product.jpg",
  "output_path": "/tmp/product_no_bg.png"
}
```

## Model and quality options

| User intent | Suggested args |
| :--- | :--- |
| General product, logo, or scene (default) | `model`: `isnet-general-use` |
| Person, portrait, or human subject | `model`: `u2net_human_seg` |
| Legacy / simple scenes | `model`: `u2net` or `silueta` |
| Hair, fur, glass, or fine edges need cleaner alpha | `alpha_matting`: `true` (slower) |

Omit `model` for default `isnet-general-use`. Set `alpha_matting` only when edge quality matters or the user mentions hair, fur, or wispy details.

## Output

| Scenario | Parameters / handling |
| :--- | :--- |
| File on disk | Set `output_path`. Prefer `{same_dir}/{stem}_no_bg.png`. Do **not** overwrite the source unless asked. |
| Chat or API only | Omit `output_path`; use `image_base64` from the result (always present on success). |
| Save next to original | Same directory, new name (e.g. `1223_no_bg.png`). |

## Interpreting a successful result

When `success` is `true`:

- `image_base64` — transparent PNG bytes (always set); decode or attach for the user when no file path was requested
- `mime_type` — always `image/png`
- `width`, `height` — output dimensions; mention when useful
- `model_used` — rembg model that ran
- `output_path` — echo of the path written when provided; confirm the file exists on disk

Do not call again for the same request unless the user asks for another image or different settings.

## Dependencies

Runtime: `rembg`, `pillow`, `onnxruntime`. Install: `pip install "skillware[creative_bg_remover]"` or `pip install "skillware[creative]"`.

First `execute()` downloads the ONNX model to the rembg cache (`~/.u2net/` on Linux/macOS, `%USERPROFILE%\.u2net\` on Windows).

## Errors

| `error_code` | Response |
| :--- | :--- |
| `INVALID_INPUT` | Ask for an upload, attachment, base64 payload, or local `input_path`. |
| `MISSING_DEPENDENCY` | Ask the user to run `pip install "skillware[creative_bg_remover]"` (or `pip install rembg pillow onnxruntime`), then retry. |
| `PROCESSING_FAILED` | Surface the `error` string; input may be missing, corrupt, or unsupported. |

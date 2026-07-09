# Background Remover

## Overview

`creative/bg_remover` removes the background from still images locally using rembg and returns a transparent PNG.

## Inputs

- image (Base64)
- input_path
- output_path
- model
- alpha_matting

## Outputs

- success
- image_base64
- mime_type
- width
- height
- model_used

## Example

```json
{
  "image": "<base64>"
}
```

Returns

```json
{
  "success": true,
  "mime_type": "image/png"
}
```

## Notes

- Runs completely offline.
- First execution may download the ONNX model.
- Unit tests mock rembg and do not download models.
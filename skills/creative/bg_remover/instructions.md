# Background Remover

Use this skill whenever a user asks to:

- remove the background from an image
- isolate an object or person
- create a transparent PNG
- cut out a product
- prepare an image for design or e-commerce workflows

Do not use this skill for:

- videos
- batch image processing
- cloud-only editing workflows

Accepted inputs:

- Base64 image data (`image`)
- Local file (`input_path`)

If `output_path` is supplied, save the generated transparent PNG there.

Otherwise return the PNG as a Base64 string.

This skill processes images locally using `rembg` and produces PNG output with transparency.
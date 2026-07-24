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

Input validation includes:

- Invalid Base64 detection
- Missing input files
- Empty input files
- Invalid or corrupt images
- Directory path rejection
- Maximum input size enforcement (25 MB)

If `output_path` is supplied, parent directories are created automatically if needed, and the generated transparent PNG is saved there.

Otherwise, the PNG is returned as a Base64 string.

This skill processes images entirely locally using `rembg`, reuses cached inference sessions for improved performance, and always produces PNG output with transparency.
"""Deterministic offline placeholder generation for creative/deck_builder."""

from __future__ import annotations

import io
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

_DEFAULT_BG = (240, 243, 246)
_DEFAULT_BORDER = (203, 213, 225)
_DEFAULT_TEXT = (100, 116, 139)
_ACCENT_COLOR = (110, 87, 224)


def generate_placeholder(
    kind: str = "hero",
    prompt: Optional[str] = None,
    width: int = 800,
    height: int = 450,
    watermark: bool = True,
) -> io.BytesIO:
    """
    Generates a deterministic, neutral placeholder image.

    Supported kinds:
    - hero: Wide 16:9 scenic/graphic backdrop with subtle geometric styling
    - logo: Square/badge frame for brand marks
    - icon: Minimal badge placeholder
    - chart_backdrop: Subtle coordinate axes / grid visualization
    - headshot: Neutral silhouette profile for team slides
    """
    kind = (kind or "hero").lower().strip()
    if kind == "logo":
        width, height = min(width, 400), min(height, 400)
    elif kind == "headshot":
        width, height = min(width, 400), min(height, 400)
    elif kind == "icon":
        width, height = min(width, 256), min(height, 256)

    img = Image.new("RGBA", (width, height), color=_DEFAULT_BG)
    draw = ImageDraw.Draw(img)

    # Outer border
    draw.rectangle([(0, 0), (width - 1, height - 1)], outline=_DEFAULT_BORDER, width=2)

    font = ImageFont.load_default()

    if kind == "hero":
        # Draw soft abstract geometric layers
        draw.polygon(
            [
                (0, height),
                (width // 3, height // 2),
                (width * 2 // 3, height * 3 // 4),
                (width, height // 3),
                (width, height),
            ],
            fill=(226, 232, 240),
        )
        draw.polygon(
            [
                (0, height),
                (width // 4, height * 2 // 3),
                (width // 2, height),
                (width, height),
            ],
            fill=(241, 245, 249),
        )
    elif kind == "logo":
        # Centered shield / badge
        cx, cy = width // 2, height // 2
        pad = min(width, height) // 4
        draw.rounded_rectangle(
            [(cx - pad, cy - pad), (cx + pad, cy + pad)],
            radius=12,
            outline=_ACCENT_COLOR,
            width=3,
            fill=(248, 250, 252),
        )
    elif kind == "headshot":
        # Silhouette head & shoulders
        cx, cy = width // 2, height // 2
        r = min(width, height) // 5
        # Head
        draw.ellipse(
            [(cx - r, cy - r - r // 2), (cx + r, cy + r - r // 2)], fill=(203, 213, 225)
        )
        # Shoulders
        draw.ellipse(
            [(cx - r * 2, cy + r // 2), (cx + r * 2, cy + r * 3)],
            fill=(203, 213, 225),
        )
    elif kind == "chart_backdrop":
        # Axes and subtle grid
        pad = 40
        draw.line([(pad, pad), (pad, height - pad)], fill=_DEFAULT_BORDER, width=2)
        draw.line(
            [(pad, height - pad), (width - pad, height - pad)],
            fill=_DEFAULT_BORDER,
            width=2,
        )
        for i in range(1, 4):
            y = pad + (height - 2 * pad) * i // 4
            draw.line([(pad, y), (width - pad, y)], fill=(226, 232, 240), width=1)

    # Caption / label
    label = prompt if prompt else f"Placeholder: {kind.capitalize()}"
    if len(label) > 60:
        label = label[:57] + "..."

    # Center text
    bbox = font.getbbox(label)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (width - tw) // 2
    ty = height - th - 24

    # Label background pill
    draw.rounded_rectangle(
        [(tx - 12, ty - 6), (tx + tw + 12, ty + th + 6)],
        radius=6,
        fill=(255, 255, 255, 220),
        outline=_DEFAULT_BORDER,
        width=1,
    )
    draw.text((tx, ty), label, fill=_DEFAULT_TEXT, font=font)

    if watermark:
        wm_text = "REPLACE BEFORE DISTRIBUTION"
        wm_bbox = font.getbbox(wm_text)
        wm_w = wm_bbox[2] - wm_bbox[0]
        draw.text(((width - wm_w) // 2, 12), wm_text, fill=(148, 163, 184), font=font)

    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    buf.seek(0)
    return buf

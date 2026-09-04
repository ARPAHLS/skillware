"""Chain execution demo for creative/bg_remover and creative/deck_builder.

Demonstrates host orchestration via SkillContext:
1. Suggest deck outline via archetype (creative/deck_builder)
2. Remove background from raw brand mark to produce transparent PNG (creative/bg_remover)
3. Quality lint the presentation specification (creative/deck_builder)
4. Render the final presentation to an editable .pptx (creative/deck_builder)
Runs entirely offline without remote API keys.
"""

from pathlib import Path
import tempfile
from PIL import Image
import io
import base64

from skillware import SkillContext


def run_demo():
    print("Loading SkillContext with creative/bg_remover and creative/deck_builder...")
    ctx = SkillContext(skills=["creative/bg_remover", "creative/deck_builder"])

    # Step 1: Suggest outline via archetype
    print("\n=== Step 1: Suggest Outline via Archetype ===")
    outline_res = ctx.execute(
        "creative/deck_builder",
        {
            "action": "suggest_outline",
            "archetype": "product_launch",
            "topic": "Skillware Autonomous Runtime",
            "constraints": ["no pricing"],
        },
    )
    print(f"  archetype: {outline_res.get('archetype')}")
    print(f"  recommended_slides: {outline_res.get('recommended_slide_count')}")
    deck_spec = outline_res["deck_spec_skeleton"]

    # Step 2: Background removal on brand mark
    print("\n=== Step 2: Background Removal on Brand Mark ===")
    sample_img_path = Path("examples/sample_input.png")
    if sample_img_path.exists():
        bg_res = ctx.execute(
            "creative/bg_remover", {"input_path": str(sample_img_path)}
        )
        transparent_logo_b64 = bg_res.get("image_base64")
        print(
            f"  bg_remover processed {sample_img_path}: success={bg_res.get('success')}"
        )
    else:
        print("  sample_input.png not present; using synthetic transparent brand asset")
        logo_img = Image.new("RGBA", (120, 120), color=(110, 87, 224, 255))
        buf = io.BytesIO()
        logo_img.save(buf, format="PNG")
        transparent_logo_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
        print(f"  transparent_logo length: {len(transparent_logo_b64)} chars")

    # Embed transparent logo into cover slide
    deck_spec["slides"][0]["image"] = {
        "base64": transparent_logo_b64,
        "mime_type": "image/png",
        "fit": "contain",
    }

    # Step 3: Lint deck specification
    print("\n=== Step 3: Lint Deck Specification ===")
    lint_res = ctx.execute(
        "creative/deck_builder",
        {
            "action": "lint_deck",
            "deck_spec": deck_spec,
            "min_score": 70,
        },
    )
    print(f"  lint_score: {lint_res.get('score')}/100")
    print(f"  passed: {lint_res.get('passed')}")
    print(f"  findings_count: {lint_res.get('findings_count')}")

    # Step 4: Render final presentation
    print("\n=== Step 4: Render Final Presentation ===")
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_pptx = Path(tmp_dir) / "skillware_launch.pptx"
        render_res = ctx.execute(
            "creative/deck_builder",
            {
                "action": "render",
                "deck_spec": deck_spec,
                "output_path": str(output_pptx),
            },
        )
        print(f"  render success: {render_res.get('success')}")
        print(f"  output_path: {render_res.get('output_path')}")
        print(f"  file_size_bytes: {render_res.get('file_size_bytes')}")
        print(f"  rendered_slides: {len(render_res.get('slides', []))}")

    print("\nChain demo complete.")


if __name__ == "__main__":
    run_demo()

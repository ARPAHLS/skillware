import base64
from pathlib import Path

from skillware.core.loader import SkillLoader


def run_demo():
    print("Loading Background Remover...")

    skill_bundle = SkillLoader.load_skill("creative/bg_remover")
    skill_instance = skill_bundle["class"]()

    input_path = "examples/sample_input.png"
    output_path = "examples/sample_output_no_bg.png"

    if not Path(input_path).exists():
        print(f"Input image not found: {input_path}")
        print("Place a sample PNG at the above path before running this demo.")
        return

    print(f"Removing background from: {input_path}")

    result = skill_instance.execute(
        {
            "input_path": input_path,
            "output_path": output_path,
        }
    )

    if result["success"]:
        print("Background removed successfully!")
        print(f"Saved to: {result['output_path']}")
        print(f"Output size: {result['width']} x {result['height']}")
        print(f"Model: {result['model_used']}")
        print(f"Base64 length: {len(result['image_base64'])}")
    else:
        print(f"Failed: {result['error']}")
        print(f"Error code: {result['error_code']}")


if __name__ == "__main__":
    run_demo()
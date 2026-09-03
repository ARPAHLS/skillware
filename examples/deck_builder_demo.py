"""Local execute demo for creative/deck_builder.

Demonstrates deterministic assembly of an editable Microsoft PowerPoint (.pptx)
presentation from a structured JSON deck specification. Runs entirely offline
without network or LLM APIs.
"""

from pathlib import Path
import tempfile

from skillware.core.loader import SkillLoader


def run_demo():
    print("Loading creative/deck_builder...")
    bundle = SkillLoader.load_skill("creative/deck_builder")
    skill = bundle["class"]()

    # Step 1: List bundled templates
    print("\n=== Step 1: List Bundled Templates ===")
    templates_res = skill.execute({"action": "list_templates"})
    for tpl in templates_res.get("templates", []):
        print(
            f"  - [{tpl['template_id']}] {tpl['name']} ({tpl['aspect_ratio']}): {tpl['description']}"
        )

    # Step 2: Validate deck specification
    print("\n=== Step 2: Validate Deck Specification ===")
    deck_spec = {
        "title": "Skillware Executive Briefing",
        "template_id": "pitch_v1",
        "theme": {
            "accent_color": "#6E57E0",
            "font_heading": "Calibri",
            "font_body": "Calibri",
        },
        "metadata": {
            "author": "ARPA Hellenic Logical Systems",
            "subject": "Platform Architecture",
        },
        "slides": [
            {
                "type": "title",
                "title": "Skillware Platform",
                "subtitle": "Deterministic AI Skills for Production Agent Systems",
            },
            {
                "type": "section",
                "title": "Part 1: The Trust Boundary",
                "subtitle": "Why agents require governed capabilities",
            },
            {
                "type": "bullets",
                "title": "Core Tenets",
                "bullets": [
                    "Deterministic, local execution for mission-critical actions",
                    "Offline-first verification with zero network dependency in execute()",
                    "Strict input schema validation and fail-closed security contracts",
                ],
                "speaker_notes": "Emphasize reproducibility and local unit testing across providers.",
            },
            {
                "type": "two_column",
                "title": "Architectural Comparison",
                "left": [
                    "Legacy Tool Calling",
                    "Monolithic prompts",
                    "Unchecked hallucinations",
                ],
                "right": [
                    "Skillware Architecture",
                    "Contract + Effect + Assurance",
                    "Provider-agnostic loaders",
                ],
            },
            {
                "type": "quote",
                "quote": "Deterministic skills are the foundation of agent reliability.",
                "attribution": "ARPA HLS Engineering",
            },
            {
                "type": "table",
                "title": "Registry Growth (2026)",
                "columns": ["Category", "Skills Shipped", "Status"],
                "rows": [
                    ["Security", "2 skills", "Production"],
                    ["Creative", "2 skills", "Production"],
                    ["Compliance", "3 skills", "Production"],
                ],
            },
            {
                "type": "chart",
                "title": "Quarterly Agent Executions",
                "chart": {
                    "kind": "bar",
                    "categories": ["Q1", "Q2", "Q3", "Q4"],
                    "series": [
                        {"name": "Executions (k)", "values": [120, 280, 540, 920]}
                    ],
                },
                "speaker_notes": "Growth reflects developer adoption of standard contracts.",
            },
            {
                "type": "blank",
                "speaker_notes": "Open the floor for technical Q&A.",
            },
        ],
    }

    val_res = skill.execute({"action": "validate_spec", "deck_spec": deck_spec})
    print(f"  valid: {val_res.get('valid')}")
    print(f"  slide_count: {val_res.get('slide_count')}")
    print(f"  warnings: {len(val_res.get('warnings', []))}")
    print(f"  errors: {len(val_res.get('errors', []))}")

    # Step 3: Render presentation
    print("\n=== Step 3: Render Presentation ===")
    with tempfile.TemporaryDirectory() as tmp_dir:
        output_pptx = Path(tmp_dir) / "skillware_executive_briefing.pptx"
        render_res = skill.execute(
            {
                "action": "render",
                "deck_spec": deck_spec,
                "output_path": str(output_pptx),
            }
        )
        print(f"  success: {render_res.get('success')}")
        print(f"  output_path: {render_res.get('output_path')}")
        print(f"  file_size_bytes: {render_res.get('file_size_bytes')}")
        print(f"  rendered_slides: {len(render_res.get('slides', []))}")

        # Step 4: Inspect generated presentation
        print("\n=== Step 4: Inspect Generated PPTX ===")
        inspect_res = skill.execute(
            {"action": "inspect", "input_path": str(output_pptx)}
        )
        print(f"  inspected_slides: {inspect_res.get('slide_count')}")
        for s in inspect_res.get("slides", [])[:4]:
            print(
                f"    - Slide {s['index'] + 1} ({s['layout_name']}): title='{s['title']}', notes={s['has_notes']}"
            )

    print("\nDemo complete.")


if __name__ == "__main__":
    run_demo()

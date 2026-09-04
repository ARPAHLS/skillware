"""Integration tests for creative/deck_builder through SkillLoader."""

from pathlib import Path
from skillware.core.loader import SkillLoader


def test_deck_builder_manifest_and_bundle_load():
    bundle = SkillLoader.load_skill("creative/deck_builder")
    assert bundle["manifest"]["name"] == "creative/deck_builder"
    assert bundle["manifest"]["category"] == "creative"
    assert bundle["manifest"]["version"] == "0.1.0"
    assert "pitch_v1" in bundle["instructions"]
    assert bundle["card"]["name"] == "Deck Builder"


def test_deck_builder_loader_execute_workflow(tmp_path: Path):
    bundle = SkillLoader.load_skill("creative/deck_builder")
    skill = bundle["class"]()

    out_file = tmp_path / "integration_deck.pptx"
    spec = {
        "title": "Loader Integration Presentation",
        "template_id": "pitch_v1",
        "slides": [
            {
                "type": "title",
                "title": "Skillware Presentation",
                "subtitle": "Built via SkillLoader",
            },
            {
                "type": "bullets",
                "title": "Key Features",
                "bullets": ["Offline-first", "100% Deterministic"],
            },
            {
                "type": "quote",
                "quote": "Reliability at scale.",
                "attribution": "ARPA HLS",
            },
        ],
    }

    # 1. Validate
    val_res = skill.execute({"action": "validate_spec", "deck_spec": spec})
    assert val_res["success"] is True
    assert val_res["valid"] is True
    assert val_res["slide_count"] == 3

    # 2. Render
    render_res = skill.execute(
        {"action": "render", "deck_spec": spec, "output_path": str(out_file)}
    )
    assert render_res["success"] is True
    assert render_res["slide_count"] == 3
    assert out_file.is_file()
    assert out_file.stat().st_size > 1000

    # 3. Inspect
    inspect_res = skill.execute({"action": "inspect", "input_path": str(out_file)})
    assert inspect_res["success"] is True
    assert inspect_res["slide_count"] == 3
    assert inspect_res["slides"][0]["title"] == "Skillware Presentation"

    # 4. List templates
    tpl_res = skill.execute({"action": "list_templates"})
    assert tpl_res["success"] is True
    assert len(tpl_res["templates"]) >= 3

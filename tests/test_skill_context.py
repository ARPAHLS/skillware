"""Tests for SkillContext."""

import pytest

from skillware import SkillContext
from skillware.core.loader import SkillLoader


def test_skill_context_single_skill():
    ctx = SkillContext(skill="optimization/prompt_rewriter")
    assert ctx.skill_ids == ["optimization/prompt_rewriter"]
    system = ctx.merge_system("Host prompt")
    assert "Host prompt" in system
    assert "prompt_rewriter" in system.lower() or "optimization" in system


def test_skill_context_tools_openai_matches_loader():
    ctx = SkillContext(skill="optimization/prompt_rewriter", mode="brief")
    bundle = SkillLoader.load_skill(
        "optimization/prompt_rewriter",
        execute_module=False,
    )
    expected = SkillLoader.to_openai_tool(bundle)
    tools = ctx.tools("openai")
    assert len(tools) == 1
    assert tools[0] == expected


def test_skill_context_tools_bedrock_matches_loader():
    ctx = SkillContext(skill="optimization/prompt_rewriter", mode="brief")
    bundle = SkillLoader.load_skill(
        "optimization/prompt_rewriter",
        execute_module=False,
    )
    expected = SkillLoader.to_bedrock_tool(bundle)
    tools = ctx.tools("bedrock")
    assert len(tools) == 1
    assert tools[0] == expected


def test_skill_context_tools_unknown_provider():
    ctx = SkillContext(skill="optimization/prompt_rewriter")
    with pytest.raises(
        ValueError, match="choose gemini, claude, openai, deepseek, or bedrock"
    ):
        ctx.tools("ollama")


def test_skill_context_prepare_and_execute():
    ctx = SkillContext(skill="optimization/prompt_rewriter")
    prep = ctx.prepare("optimization/prompt_rewriter")
    assert prep.directive
    out = ctx.execute(
        "optimization/prompt_rewriter",
        {
            "raw_text": "Please summarize this long repetitive prompt about compliance.",
            "compression_aggression": "low",
        },
    )
    assert "compressed_text" in out


def test_skill_context_directives_mode_includes_instructions():
    ctx = SkillContext(skill="optimization/prompt_rewriter", mode="directives")
    merged = ctx.merge_system("")
    prep = ctx.prepare("optimization/prompt_rewriter")
    assert prep.directive.strip()[:40] in merged


def test_skill_context_filter_allowed_shapes():
    # Only atomic skills: should include prompt_rewriter, exclude wallet_screening (workflow)
    ctx_atomic = SkillContext(
        skills=["optimization/prompt_rewriter", "finance/wallet_screening"],
        allowed_shapes=["atomic"],
    )
    assert ctx_atomic.skill_ids == ["optimization/prompt_rewriter"]

    # Only workflow skills: should include wallet_screening, exclude prompt_rewriter
    ctx_workflow = SkillContext(
        skills=["optimization/prompt_rewriter", "finance/wallet_screening"],
        allowed_shapes=["workflow"],
    )
    assert ctx_workflow.skill_ids == ["finance/wallet_screening"]


def test_skill_context_filter_tags():
    # Tag 'aml' should match finance/wallet_screening
    ctx_aml = SkillContext(
        skills=["optimization/prompt_rewriter", "finance/wallet_screening"],
        tags=["aml"],
    )
    assert ctx_aml.skill_ids == ["finance/wallet_screening"]

    # Unknown tag matches nothing
    ctx_none = SkillContext(
        skills=["optimization/prompt_rewriter", "finance/wallet_screening"],
        tags=["nonexistent_xyz_tag"],
    )
    assert ctx_none.skill_ids == []


def test_skill_context_filter_allowed_targets():
    ctx = SkillContext(
        skills=["optimization/prompt_rewriter"],
        allowed_targets=["software"],
    )
    assert ctx.skill_ids == ["optimization/prompt_rewriter"]


def test_skill_context_brief_taxonomy_badge():
    ctx = SkillContext(skill="optimization/prompt_rewriter")
    line = ctx.brief("optimization/prompt_rewriter")
    assert "[core:atomic:software]" in line


def test_skill_context_hardware_safety_warning(tmp_path, monkeypatch):
    from skillware.core.manifest_schema import SkillwareHardwareSafetyWarning

    # Set discovery path to tmp_path
    monkeypatch.setenv("SKILLWARE_SKILL_PATH", str(tmp_path))

    # Create mock hardware skill
    robotics_dir = tmp_path / "robotics" / "arm_controller"
    robotics_dir.mkdir(parents=True)
    (robotics_dir / "manifest.yaml").write_text(
        "name: robotics/arm_controller\n"
        "version: 0.1.0\n"
        "tier: core\n"
        "shape: atomic\n"
        "target:\n"
        "  - software\n"
        "  - hardware\n"
        "tags:\n"
        "  - robotics\n"
        "  - hardware\n"
        "description: Actuates robotic arm joints.\n",
        encoding="utf-8",
    )
    (robotics_dir / "skill.py").write_text(
        "from skillware.core.base_skill import BaseSkill\n"
        "class ArmController(BaseSkill):\n"
        "    @property\n"
        "    def manifest(self):\n"
        "        return self.load_manifest_from_dir(__file__)\n"
        "    def execute(self, params):\n"
        "        return {'status': 'moved'}\n",
        encoding="utf-8",
    )

    # 1. Without allow_hardware_execution: warns on prepare()
    ctx_safe = SkillContext(
        skill="robotics/arm_controller",
        allow_hardware_execution=False,
    )
    with pytest.warns(
        SkillwareHardwareSafetyWarning, match="physical execution target"
    ):
        ctx_safe.prepare("robotics/arm_controller")

    # 2. With allow_hardware_execution=True: no warning
    ctx_allowed = SkillContext(
        skill="robotics/arm_controller",
        allow_hardware_execution=True,
    )
    import warnings

    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always")
        ctx_allowed.prepare("robotics/arm_controller")
        hw_warnings = [
            w
            for w in recorded
            if issubclass(w.category, SkillwareHardwareSafetyWarning)
        ]
        assert len(hw_warnings) == 0

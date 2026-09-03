"""Tests for SkillContext."""

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

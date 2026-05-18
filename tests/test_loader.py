import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from skillware.core.loader import SKILLWARE_SKILL_PATH_ENV, SkillLoader

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_load_skill_not_found():
    with pytest.raises(FileNotFoundError):
        SkillLoader.load_skill("nonexistent_skill_path_12345")


def test_load_skill_registry_has_manifest():
    bundle = SkillLoader.load_skill("optimization/prompt_rewriter")
    assert bundle["manifest"].get("name") == "optimization/prompt_rewriter"


def test_resolve_skill_from_project_skills_dir(tmp_path, monkeypatch):
    skill_dir = tmp_path / "skills" / "local_skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "manifest.yaml").write_text(
        "name: local_skill\nversion: 0.1.0\ndescription: test\n"
        "parameters:\n  type: object\n  properties: {}\n",
        encoding="utf-8",
    )
    (skill_dir / "skill.py").write_text(
        "from skillware.core.base_skill import BaseSkill\n"
        "class LocalSkill(BaseSkill):\n"
        "    def execute(self, **kwargs):\n"
        "        return {}\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    bundle = SkillLoader.load_skill("local_skill")
    assert bundle["manifest"]["name"] == "local_skill"


def test_resolve_skill_from_env_path(tmp_path, monkeypatch):
    root = tmp_path / "custom_skills"
    skill_dir = root / "env_skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "manifest.yaml").write_text(
        "name: env_skill\nversion: 0.1.0\ndescription: test\n"
        "parameters:\n  type: object\n  properties: {}\n",
        encoding="utf-8",
    )
    (skill_dir / "skill.py").write_text(
        "from skillware.core.base_skill import BaseSkill\n"
        "class EnvSkill(BaseSkill):\n"
        "    def execute(self, **kwargs):\n"
        "        return {}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv(SKILLWARE_SKILL_PATH_ENV, str(root))
    monkeypatch.chdir(tmp_path)
    bundle = SkillLoader.load_skill("env_skill")
    assert bundle["manifest"]["name"] == "env_skill"


def test_resolve_skill_prefers_env_over_cwd(tmp_path, monkeypatch):
    env_root = tmp_path / "env_root"
    env_skill = env_root / "shared_id"
    env_skill.mkdir(parents=True)
    (env_skill / "manifest.yaml").write_text(
        "name: from_env\nversion: 0.1.0\ndescription: test\n"
        "parameters:\n  type: object\n  properties: {}\n",
        encoding="utf-8",
    )
    (env_skill / "skill.py").write_text(
        "from skillware.core.base_skill import BaseSkill\n"
        "class EnvSkill(BaseSkill):\n"
        "    def execute(self, **kwargs):\n"
        "        return {'source': 'env'}\n",
        encoding="utf-8",
    )

    cwd_skill = tmp_path / "skills" / "shared_id"
    cwd_skill.mkdir(parents=True)
    (cwd_skill / "manifest.yaml").write_text(
        "name: from_cwd\nversion: 0.1.0\ndescription: test\n"
        "parameters:\n  type: object\n  properties: {}\n",
        encoding="utf-8",
    )
    (cwd_skill / "skill.py").write_text(
        "from skillware.core.base_skill import BaseSkill\n"
        "class CwdSkill(BaseSkill):\n"
        "    def execute(self, **kwargs):\n"
        "        return {'source': 'cwd'}\n",
        encoding="utf-8",
    )

    monkeypatch.setenv(SKILLWARE_SKILL_PATH_ENV, str(env_root))
    monkeypatch.chdir(tmp_path)
    bundle = SkillLoader.load_skill("shared_id")
    assert bundle["manifest"]["name"] == "from_env"


def test_wheel_includes_skill_manifest(tmp_path):
    wheel_dir = tmp_path / "wheels"
    wheel_dir.mkdir()

    subprocess.run(
        [sys.executable, "-m", "pip", "wheel", str(REPO_ROOT), "--no-deps", "-w", str(wheel_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    wheels = list(wheel_dir.glob("skillware-*.whl"))
    assert len(wheels) == 1
    wheel_path = wheels[0]

    with zipfile.ZipFile(wheel_path) as archive:
        names = archive.namelist()
        assert any(n.endswith("skills/compliance/tos_evaluator/manifest.yaml") for n in names)
        assert any(n.endswith("skills/office/pdf_form_filler/manifest.yaml") for n in names)


def test_to_ollama_prompt():
    dummy_bundle = {
        "manifest": {
            "name": "test_ollama_skill",
            "description": "A very useful test skill.",
            "parameters": {
                "type": "object",
                "properties": {
                    "arg1": {"type": "string", "description": "The first arg"}
                },
                "required": ["arg1"]
            }
        }
    }

    prompt = SkillLoader.to_ollama_prompt(dummy_bundle)
    assert "### Tool: `test_ollama_skill`" in prompt
    assert "**Description:** A very useful test skill." in prompt
    assert "- `arg1` (string): The first arg [Required]" in prompt


def test_to_gemini_tool():
    dummy_bundle = {
        "manifest": {
            "name": "test_gemini_skill",
            "parameters": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string"}
                }
            }
        }
    }
    tool = SkillLoader.to_gemini_tool(dummy_bundle)
    assert tool["name"] == "test_gemini_skill"
    # Gemini requires UPPERCASE types for Protobufs
    assert tool["parameters"]["type"] == "OBJECT"
    assert tool["parameters"]["properties"]["param1"]["type"] == "STRING"


def test_to_claude_tool():
    dummy_bundle = {
        "manifest": {
            "name": "test_claude_skill",
            "description": "desc",
            "parameters": {
                "type": "object",
                "properties": {"arg_claude": {"type": "string"}}
            }
        }
    }
    tool = SkillLoader.to_claude_tool(dummy_bundle)
    assert tool["name"] == "test_claude_skill"
    assert tool["input_schema"]["type"] == "object"


def test_sanitize_openai_tool_name():
    assert (
        SkillLoader._sanitize_openai_tool_name("compliance/tos_evaluator")
        == "compliance_tos_evaluator"
    )
    assert SkillLoader._sanitize_openai_tool_name("wallet_screening") == "wallet_screening"
    assert SkillLoader._sanitize_openai_tool_name("") == "unknown_tool"
    assert SkillLoader._sanitize_openai_tool_name("a" * 80).startswith("a")
    assert len(SkillLoader._sanitize_openai_tool_name("a" * 80)) == 64


def test_to_openai_tool():
    dummy_bundle = {
        "manifest": {
            "name": "compliance/tos_evaluator",
            "description": "Evaluate site policy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_url": {"type": "string", "description": "URL"}
                },
                "required": ["target_url"],
            },
        }
    }
    tool = SkillLoader.to_openai_tool(dummy_bundle)
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "compliance_tos_evaluator"
    assert tool["function"]["description"] == "Evaluate site policy."
    assert tool["function"]["parameters"]["type"] == "object"
    assert "target_url" in tool["function"]["parameters"]["properties"]


def test_sanitize_deepseek_tool_name():
    assert (
        SkillLoader._sanitize_deepseek_tool_name("compliance/tos_evaluator")
        == "compliance_tos_evaluator"
    )


def test_to_deepseek_tool():
    dummy_bundle = {
        "manifest": {
            "name": "compliance/tos_evaluator",
            "description": "Evaluate site policy.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_url": {"type": "string", "description": "URL"}
                },
                "required": ["target_url"],
            },
        }
    }
    tool = SkillLoader.to_deepseek_tool(dummy_bundle)
    assert tool["type"] == "function"
    assert tool["function"]["name"] == "compliance_tos_evaluator"

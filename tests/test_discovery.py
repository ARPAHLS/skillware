import os
from pathlib import Path

import pytest

from skillware.core.discovery import (
    SKILLWARE_SKILL_PATH_ENV,
    SkillRootTier,
    build_skill_not_found_message,
    bundled_skills_root,
    find_shadow_conflicts,
    get_skill_roots,
    list_registry_skill_ids,
)
from skillware.core.loader import SkillLoader


def _write_registry_skill(root: Path, category: str, name: str) -> None:
    skill_dir = root / category / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "skill.py").write_text(
        "from skillware.core.base_skill import BaseSkill\n"
        "class S(BaseSkill):\n"
        "    @property\n"
        "    def manifest(self): return {'name': '%s/%s'}\n"
        "    def execute(self, p): return {}\n" % (category, name),
        encoding="utf-8",
    )
    (skill_dir / "manifest.yaml").write_text(
        f"name: {category}/{name}\nversion: 0.1.0\n",
        encoding="utf-8",
    )


def test_get_skill_roots_order_env_project_bundled(tmp_path, monkeypatch):
    env_root = tmp_path / "external"
    env_root.mkdir()
    project_root = tmp_path / "project" / "skills"
    project_root.mkdir(parents=True)
    monkeypatch.chdir(tmp_path / "project")
    monkeypatch.setenv(SKILLWARE_SKILL_PATH_ENV, str(env_root))

    roots = get_skill_roots()
    tiers = [root.tier for root in roots]

    assert tiers[0] == SkillRootTier.EXTERNAL
    assert tiers[1] == SkillRootTier.PROJECT
    assert tiers[-1] == SkillRootTier.BUNDLED
    assert roots[-1].path == bundled_skills_root()


def test_get_skill_roots_override_single_root(tmp_path):
    override = tmp_path / "only"
    override.mkdir()
    roots = get_skill_roots(override)
    assert len(roots) == 1
    assert roots[0].tier == SkillRootTier.OVERRIDE
    assert roots[0].path == override.resolve()


def test_for_display_shows_missing_env_path(tmp_path, monkeypatch):
    missing = tmp_path / "missing-external"
    monkeypatch.setenv(SKILLWARE_SKILL_PATH_ENV, str(missing))
    monkeypatch.chdir(tmp_path)

    roots = get_skill_roots(for_display=True)
    external = [r for r in roots if r.tier == SkillRootTier.EXTERNAL]
    assert len(external) == 1
    assert external[0].exists is False


def test_find_shadow_conflicts_first_root_wins(tmp_path, monkeypatch):
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    _write_registry_skill(first, "office", "dup_skill")
    _write_registry_skill(second, "office", "dup_skill")

    monkeypatch.setenv(SKILLWARE_SKILL_PATH_ENV, f"{first}{os.pathsep}{second}")
    monkeypatch.chdir(tmp_path)

    roots = get_skill_roots(for_display=True)
    conflicts = find_shadow_conflicts(roots)
    assert len(conflicts) == 1
    assert conflicts[0].skill_id == "office/dup_skill"
    assert conflicts[0].winner.path == first.resolve()
    assert conflicts[0].shadowed.path == second.resolve()


def test_list_registry_skill_ids_ignores_flat_layout(tmp_path):
    flat = tmp_path / "flat_skill"
    flat.mkdir()
    (flat / "skill.py").write_text("x = 1\n", encoding="utf-8")
    (flat / "manifest.yaml").write_text("name: flat\n", encoding="utf-8")

    assert list_registry_skill_ids(tmp_path) == []


def test_build_skill_not_found_message_includes_paths_tip(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    message = build_skill_not_found_message("missing/skill")
    assert "missing/skill" in message
    assert "skillware paths" in message


def test_loader_uses_discovery_error_message(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(FileNotFoundError) as exc:
        SkillLoader.load_skill("missing/skill")
    assert "skillware paths" in str(exc.value)

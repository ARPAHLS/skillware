"""Tests for Skillware configuration and skill path discovery."""

from pathlib import Path

import pytest

from skillware.core.config import (
    GLOBAL_CONFIG_DIR_ENV,
    PROJECT_CONFIG_FILENAME,
    clear_config_cache,
    find_project_config_file,
    load_merged_config,
)
from skillware.core.discovery import (
    SKILLWARE_SKILL_PATH_ENV,
    SkillRootTier,
    get_skill_roots,
)
from skillware.core.loader import SkillLoader


def _write_config(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


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
        f"name: {category}/{name}\nversion: 0.1.0\n"
        "parameters:\n  type: object\n  properties: {}\n",
        encoding="utf-8",
    )


@pytest.fixture(autouse=True)
def _reset_config_cache():
    clear_config_cache()
    yield
    clear_config_cache()


def test_no_config_files_uses_legacy_order(tmp_path, monkeypatch):
    env_root = tmp_path / "external"
    env_root.mkdir()
    project_root = tmp_path / "project" / "skills"
    project_root.mkdir(parents=True)
    monkeypatch.chdir(tmp_path / "project")
    monkeypatch.setenv(SKILLWARE_SKILL_PATH_ENV, str(env_root))
    monkeypatch.setenv(GLOBAL_CONFIG_DIR_ENV, str(tmp_path / "empty-config"))

    roots = get_skill_roots()
    tiers = [root.tier for root in roots]

    assert tiers[0] == SkillRootTier.EXTERNAL
    assert tiers[1] == SkillRootTier.PROJECT
    assert tiers[-1] == SkillRootTier.BUNDLED


def test_project_config_external_paths(tmp_path, monkeypatch):
    external = tmp_path / "private-skills"
    external.mkdir()
    _write_registry_skill(external, "office", "private_skill")

    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(
        repo / PROJECT_CONFIG_FILENAME,
        "paths:\n  external:\n    - %s\n" % external.as_posix(),
    )
    monkeypatch.chdir(repo)
    monkeypatch.setenv(GLOBAL_CONFIG_DIR_ENV, str(tmp_path / "no-global"))

    config = load_merged_config(refresh=True)
    assert config.has_config_files
    assert Path(config.paths.external[0]) == external.resolve()

    roots = get_skill_roots()
    assert any(root.path == external.resolve() for root in roots)
    assert roots[-1].tier == SkillRootTier.BUNDLED

    bundle = SkillLoader.load_skill("office/private_skill")
    assert bundle["manifest"]["name"] == "office/private_skill"


def test_config_resolution_order_project_before_external(tmp_path, monkeypatch):
    project = tmp_path / "repo" / "skills"
    external = tmp_path / "external"
    project.mkdir(parents=True)
    external.mkdir()
    _write_registry_skill(project, "demo", "from_project")
    _write_registry_skill(external, "demo", "from_external")

    repo = tmp_path / "repo"
    _write_config(
        repo / PROJECT_CONFIG_FILENAME,
        "paths:\n  project: auto\n  external:\n    - %s\n"
        "resolution:\n  order:\n    - project\n    - external\n    - bundled\n"
        % external.as_posix(),
    )
    monkeypatch.chdir(repo)
    monkeypatch.setenv(GLOBAL_CONFIG_DIR_ENV, str(tmp_path / "no-global"))
    monkeypatch.delenv(SKILLWARE_SKILL_PATH_ENV, raising=False)

    bundle = SkillLoader.load_skill("demo/from_project")
    assert bundle["manifest"]["name"] == "demo/from_project"


def test_honor_skillware_skill_path_false_ignores_env(tmp_path, monkeypatch):
    env_root = tmp_path / "env-skills"
    env_root.mkdir()
    _write_registry_skill(env_root, "demo", "env_skill")

    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(
        repo / PROJECT_CONFIG_FILENAME,
        "paths:\n  external: []\nlegacy:\n  honor_skillware_skill_path: false\n",
    )
    monkeypatch.chdir(repo)
    monkeypatch.setenv(SKILLWARE_SKILL_PATH_ENV, str(env_root))
    monkeypatch.setenv(GLOBAL_CONFIG_DIR_ENV, str(tmp_path / "no-global"))

    roots = get_skill_roots()
    assert not any(root.tier == SkillRootTier.EXTERNAL for root in roots)

    with pytest.raises(FileNotFoundError):
        SkillLoader.load_skill("demo/env_skill")


def test_global_and_project_config_merge(tmp_path, monkeypatch):
    global_dir = tmp_path / "global-config"
    global_external = tmp_path / "global-external"
    global_external.mkdir()
    _write_config(
        global_dir / "config.yaml",
        "paths:\n  external:\n    - %s\n" % global_external.as_posix(),
    )

    project_external = tmp_path / "project-external"
    project_external.mkdir()
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(
        repo / PROJECT_CONFIG_FILENAME,
        "paths:\n  external:\n    - %s\n" % project_external.as_posix(),
    )

    monkeypatch.chdir(repo)
    monkeypatch.setenv(GLOBAL_CONFIG_DIR_ENV, str(global_dir))

    config = load_merged_config(refresh=True)
    assert len(config.layers) == 2
    assert Path(config.paths.external[0]) == global_external.resolve()
    assert Path(config.paths.external[1]) == project_external.resolve()


def test_find_project_config_walks_up(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    nested = repo / "a" / "b"
    nested.mkdir(parents=True)
    _write_config(repo / PROJECT_CONFIG_FILENAME, "paths:\n  project: auto\n")
    monkeypatch.chdir(nested)

    assert find_project_config_file() == (repo / PROJECT_CONFIG_FILENAME).resolve()


def test_extra_config_sections_preserved(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    _write_config(
        repo / PROJECT_CONFIG_FILENAME,
        "paths:\n  project: auto\n"
        "theme:\n  preset: dark\n"
        "chains:\n  default: []\n",
    )
    monkeypatch.chdir(repo)
    monkeypatch.setenv(GLOBAL_CONFIG_DIR_ENV, str(tmp_path / "no-global"))

    config = load_merged_config(refresh=True)
    assert "theme" in config.extra
    assert "chains" in config.extra


def test_cmd_config_show_reports_no_files(tmp_path, monkeypatch):
    import io
    from rich.console import Console

    from skillware.cli import cmd_config_show

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(GLOBAL_CONFIG_DIR_ENV, str(tmp_path / "empty"))

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=100)
    assert cmd_config_show(console=console) == 0
    output = buf.getvalue()
    assert "No config files found" in output
    assert "legacy resolution" in output

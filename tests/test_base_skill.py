"""Tests for BaseSkill helpers."""

from skillware.core.base_skill import BaseSkill


class _CredentialProbeSkill(BaseSkill):
    @property
    def manifest(self):
        return {"name": "test/credential_probe"}

    def execute(self, params):
        return {}


def test_credential_prefers_config_over_environ(monkeypatch):
    monkeypatch.setenv("ETHERSCAN_API_KEY", "from-env")
    skill = _CredentialProbeSkill(config={"ETHERSCAN_API_KEY": "from-config"})
    assert skill.credential("ETHERSCAN_API_KEY") == "from-config"


def test_credential_falls_back_to_environ(monkeypatch):
    monkeypatch.setenv("ETHERSCAN_API_KEY", "from-env")
    skill = _CredentialProbeSkill()
    assert skill.credential("ETHERSCAN_API_KEY") == "from-env"


def test_credential_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
    skill = _CredentialProbeSkill()
    assert skill.credential("ETHERSCAN_API_KEY") is None


def test_load_manifest_from_dir(tmp_path):
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text("name: test/sample\nversion: 1.0.0\n", encoding="utf-8")

    # Load via directory path
    assert BaseSkill.load_manifest_from_dir(tmp_path) == {
        "name": "test/sample",
        "version": "1.0.0",
    }

    # Load via direct file path
    assert BaseSkill.load_manifest_from_dir(manifest_file) == {
        "name": "test/sample",
        "version": "1.0.0",
    }

    # Non-existent path returns {}
    assert BaseSkill.load_manifest_from_dir(tmp_path / "nonexistent") == {}


def test_load_manifest_from_dir_instance_property(tmp_path):
    manifest_file = tmp_path / "manifest.yaml"
    manifest_file.write_text("name: test/instance_prop\nversion: 2.0.0\n", encoding="utf-8")

    class _SampleSkill(BaseSkill):
        @property
        def manifest(self):
            return self.load_manifest_from_dir(tmp_path)

        def execute(self, params):
            return {}

    skill = _SampleSkill()
    assert skill.manifest == {"name": "test/instance_prop", "version": "2.0.0"}


def test_load_manifest_from_dir_missing_and_invalid(tmp_path):
    # Empty dir returns {}
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    assert BaseSkill.load_manifest_from_dir(empty_dir) == {}

    # Non-mapping YAML returns {}
    invalid_file = tmp_path / "invalid" / "manifest.yaml"
    invalid_file.parent.mkdir()
    invalid_file.write_text("- item1\n- item2\n", encoding="utf-8")
    assert BaseSkill.load_manifest_from_dir(invalid_file.parent) == {}

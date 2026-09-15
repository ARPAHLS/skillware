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

"""Tests for pluggable secret providers."""

from __future__ import annotations

from skillware import SkillContext
from skillware.core.loader import SkillLoader
from skillware.core.secrets import (
    EnvSecretProvider,
    MappingSecretProvider,
    resolve_manifest_env_vars,
)

MANIFEST_WITH_ENV = {
    "env_vars": {
        "ETHERSCAN_API_KEY": {"description": "Required", "required": True},
        "COINGECKO_API_KEY": {"description": "Optional", "required": False},
    }
}


def test_mapping_secret_provider_returns_injected_values():
    provider = MappingSecretProvider({"ETHERSCAN_API_KEY": "vault-key"})
    assert provider.get("ETHERSCAN_API_KEY") == "vault-key"
    assert provider.get("COINGECKO_API_KEY") is None


def test_env_secret_provider_reads_os_environ(monkeypatch):
    monkeypatch.setenv("ETHERSCAN_API_KEY", "from-env")
    provider = EnvSecretProvider()
    assert provider.get("ETHERSCAN_API_KEY") == "from-env"


def test_env_secret_provider_treats_blank_as_missing(monkeypatch):
    monkeypatch.setenv("ETHERSCAN_API_KEY", "   ")
    provider = EnvSecretProvider()
    assert provider.get("ETHERSCAN_API_KEY") is None


def test_resolve_manifest_env_vars_uses_provider():
    provider = MappingSecretProvider(
        {"ETHERSCAN_API_KEY": "injected", "COINGECKO_API_KEY": ""}
    )
    resolved = resolve_manifest_env_vars(MANIFEST_WITH_ENV, provider)
    assert resolved == {"ETHERSCAN_API_KEY": "injected"}


def test_skill_loader_resolve_env_vars_defaults_to_env(monkeypatch):
    monkeypatch.setenv("ETHERSCAN_API_KEY", "loader-env")
    resolved = SkillLoader.resolve_env_vars(MANIFEST_WITH_ENV)
    assert resolved["ETHERSCAN_API_KEY"] == "loader-env"


def test_skill_loader_resolve_env_vars_empty_manifest():
    assert SkillLoader.resolve_env_vars({}) == {}
    assert SkillLoader.resolve_env_vars({"env_vars": "invalid"}) == {}


def test_skill_context_accepts_secret_mapping(monkeypatch):
    monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
    ctx = SkillContext(
        skill="finance/wallet_screening",
        secret_provider={"ETHERSCAN_API_KEY": "host-injected"},
    )
    prep = ctx.prepare("finance/wallet_screening")
    skill_cls = SkillLoader.get_skill_class(dict(prep.bundle))
    captured: list[str | None] = []

    def fake_execute(self, params):
        captured.append(self.etherscan_api_key)
        return {"status": "mocked"}

    monkeypatch.setattr(skill_cls, "execute", fake_execute)
    ctx.execute(
        "finance/wallet_screening",
        {"address": "0x0000000000000000000000000000000000000001"},
    )
    assert captured == ["host-injected"]

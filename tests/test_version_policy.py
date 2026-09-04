import pytest
from packaging.version import Version

from skillware import version_policy


@pytest.fixture(autouse=True)
def clear_version_check_env(monkeypatch):
    monkeypatch.delenv("SKILLWARE_NO_VERSION_CHECK", raising=False)


def test_get_installed_version_parses_release(monkeypatch):
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "0.3.2",
    )
    assert version_policy.get_installed_version() == Version("0.3.2")


def test_get_installed_version_dev_returns_none(monkeypatch):
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "dev",
    )
    assert version_policy.get_installed_version() is None


def test_get_installed_version_literal_none_returns_none(monkeypatch):
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "None",
    )
    assert version_policy.get_installed_version() is None


def test_get_installed_version_empty_returns_none(monkeypatch):
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "",
    )
    assert version_policy.get_installed_version() is None


def test_get_installed_version_unparseable_returns_none(monkeypatch):
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "not-a-version",
    )
    assert version_policy.get_installed_version() is None


def test_should_emit_only_below_min_unsupported():
    assert version_policy.should_emit_unsupported_advisory(Version("0.4.5")) is True
    assert version_policy.should_emit_unsupported_advisory(Version("0.3.4")) is True
    assert version_policy.should_emit_unsupported_advisory(Version("0.2.9")) is True
    assert version_policy.should_emit_unsupported_advisory(Version("0.4.6")) is False
    assert version_policy.should_emit_unsupported_advisory(Version("0.5.0")) is False
    assert version_policy.should_emit_unsupported_advisory(Version("0.5.2")) is False
    assert version_policy.should_emit_unsupported_advisory(Version("0.5.3")) is False
    assert version_policy.should_emit_unsupported_advisory(Version("0.5.4")) is False


def test_emit_advisory_silent_for_current_release(monkeypatch, capsys):
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "0.5.4",
    )
    version_policy.emit_upgrade_advisory()
    assert capsys.readouterr().err == ""


def test_emit_advisory_silent_for_security_supported_floor(monkeypatch, capsys):
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "0.5.4",
    )
    version_policy.emit_upgrade_advisory()
    assert capsys.readouterr().err == ""


def test_emit_advisory_silent_for_outdated_but_supported_band(monkeypatch, capsys):
    for version in ("0.4.6", "0.5.0", "0.5.2", "0.5.3"):
        monkeypatch.setattr(
            version_policy.metadata,
            "version",
            lambda _name, v=version: v,
        )
        version_policy.emit_upgrade_advisory()
        assert capsys.readouterr().err == ""


def test_emit_advisory_warns_for_unsupported(monkeypatch, capsys):
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "0.4.5",
    )
    version_policy.emit_upgrade_advisory()
    err = capsys.readouterr().err
    assert "0.4.5" in err
    assert "unsupported" in err.lower()
    assert ">=0.5.4" in err


def test_emit_advisory_respects_opt_out(monkeypatch, capsys):
    monkeypatch.setenv("SKILLWARE_NO_VERSION_CHECK", "1")
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "0.4.5",
    )
    version_policy.emit_upgrade_advisory()
    assert capsys.readouterr().err == ""


def test_cli_main_calls_advisory_once(monkeypatch):
    import sys

    calls = []
    from skillware import cli as cli_module

    monkeypatch.setattr(
        cli_module,
        "emit_upgrade_advisory",
        lambda: calls.append(True),
    )
    monkeypatch.setattr(cli_module, "cmd_list", lambda **kwargs: None)
    monkeypatch.setattr(sys, "argv", ["skillware", "list"])

    cli_module.main()
    assert len(calls) == 1

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


class _FakeDistribution:
    """Small metadata.Distribution stand-in for install-health unit tests."""

    def __init__(self, version, path, *, editable=False, metadata_version="2.1"):
        self.version = version
        self._path = path
        self.metadata = {"Name": "skillware"}
        if metadata_version is not None:
            self.metadata["Metadata-Version"] = metadata_version
        self._editable = editable

    def read_text(self, name):
        """Return editable metadata only for the direct-url query."""
        if name != "direct_url.json" or not self._editable:
            return None
        return '{"dir_info": {"editable": true}}'


def test_detect_install_conflicts_reports_duplicate_registrations(monkeypatch, tmp_path):
    """Multiple registered distributions produce a duplicate conflict."""
    dists = [
        _FakeDistribution("0.5.5", tmp_path / "skillware-0.5.5.dist-info"),
        _FakeDistribution("0.5.4", tmp_path / "skillware-0.5.4.dist-info"),
    ]
    monkeypatch.setattr(version_policy.metadata, "distributions", lambda: dists)
    monkeypatch.setattr(version_policy, "_skillware_dist_infos", lambda: [])

    assert "duplicate" in {item.code for item in version_policy.detect_install_conflicts()}


def test_detect_install_conflicts_reports_orphan_dist_info(monkeypatch, tmp_path):
    """Incomplete dist-info directories are reported as orphan metadata."""
    orphan = tmp_path / "skillware-0.5.5.dist-info"
    orphan.mkdir()
    monkeypatch.setattr(version_policy.metadata, "distributions", lambda: [])
    monkeypatch.setattr(version_policy, "_skillware_dist_infos", lambda: [orphan])

    conflicts = version_policy.detect_install_conflicts()
    assert [item.code for item in conflicts] == ["orphan"]
    assert "METADATA, RECORD" in conflicts[0].summary


def test_detect_install_conflicts_reports_editable_wheel_mix(monkeypatch, tmp_path):
    """Editable and wheel registrations retain a full-dev Windows repair command."""
    dists = [
        _FakeDistribution("0.5.5", tmp_path / "editable.dist-info", editable=True),
        _FakeDistribution("0.5.5", tmp_path / "wheel.dist-info"),
    ]
    monkeypatch.setattr(version_policy.metadata, "distributions", lambda: dists)
    monkeypatch.setattr(version_policy, "_skillware_dist_infos", lambda: [])

    conflicts = version_policy.detect_install_conflicts()
    mix = next(item for item in conflicts if item.code == "editable-wheel-mix")
    assert 'py -m pip install -e ".[dev,all]"' in mix.fix_windows


def test_should_emit_only_below_min_unsupported():
    assert version_policy.should_emit_unsupported_advisory(Version("0.4.5")) is True
    assert version_policy.should_emit_unsupported_advisory(Version("0.3.4")) is True
    assert version_policy.should_emit_unsupported_advisory(Version("0.2.9")) is True
    assert version_policy.should_emit_unsupported_advisory(Version("0.4.6")) is False
    assert version_policy.should_emit_unsupported_advisory(Version("0.5.0")) is False
    assert version_policy.should_emit_unsupported_advisory(Version("0.5.2")) is False
    assert version_policy.should_emit_unsupported_advisory(Version("0.5.3")) is False
    assert version_policy.should_emit_unsupported_advisory(Version("0.5.4")) is False
    assert version_policy.should_emit_unsupported_advisory(Version("0.5.5")) is False


def test_emit_advisory_silent_for_current_release(monkeypatch, capsys):
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "0.5.5",
    )
    version_policy.emit_upgrade_advisory()
    assert capsys.readouterr().err == ""


def test_emit_advisory_silent_for_security_supported_floor(monkeypatch, capsys):
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "0.5.5",
    )
    version_policy.emit_upgrade_advisory()
    assert capsys.readouterr().err == ""


def test_emit_advisory_silent_for_outdated_but_supported_band(monkeypatch, capsys):
    for version in ("0.4.6", "0.5.0", "0.5.2", "0.5.3", "0.5.4"):
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
    assert ">=0.5.5" in err


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

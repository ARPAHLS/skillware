import sys

import pytest
from packaging.version import Version

from skillware import version_policy


@pytest.fixture(autouse=True)
def clear_version_check_env(monkeypatch):
    monkeypatch.delenv("SKILLWARE_NO_VERSION_CHECK", raising=False)


class _FakeDist:
    def __init__(
        self,
        *,
        name: str = "skillware",
        version: str = "0.5.6",
        has_record: bool = True,
        editable: bool = False,
        dist_dir_name: str = "skillware-0.5.6.dist-info",
    ):
        self._name = name
        self._version = version
        self._has_record = has_record
        self._editable = editable
        self._dist_dir_name = dist_dir_name
        self.metadata = {"Name": name, "Version": version}

    @property
    def version(self):
        if self._version in ("", "None", None):
            raise version_policy.metadata.PackageNotFoundError
        return self._version

    @property
    def files(self):
        return ["skillware/__init__.py"] if self._has_record else None

    def locate_file(self, path: str):
        base = f"/fake/site-packages/{self._dist_dir_name}"
        if path == "METADATA":
            return f"{base}/METADATA"
        raise FileNotFoundError(path)


def _patch_distributions(monkeypatch, dists):
    monkeypatch.setattr(
        version_policy,
        "iter_skillware_distributions",
        lambda: iter(dists),
    )


def test_get_installed_version_parses_release(monkeypatch):
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "0.3.2",
    )
    monkeypatch.setattr(
        version_policy,
        "iter_skillware_distributions",
        lambda: iter([]),
    )
    assert version_policy.get_installed_version() == Version("0.3.2")


def test_get_installed_version_dev_returns_none(monkeypatch):
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "dev",
    )
    monkeypatch.setattr(
        version_policy,
        "iter_skillware_distributions",
        lambda: iter([]),
    )
    assert version_policy.get_installed_version() is None


def test_get_installed_version_prefers_highest_among_duplicates(monkeypatch):
    dists = [
        _FakeDist(version="0.5.1", dist_dir_name="skillware-0.5.1.dist-info"),
        _FakeDist(version="0.5.6", dist_dir_name="skillware-0.5.6.dist-info"),
    ]
    _patch_distributions(monkeypatch, dists)
    assert version_policy.get_installed_version() == Version("0.5.6")


def test_get_package_version_display_never_none(monkeypatch):
    monkeypatch.setattr(version_policy, "get_installed_version", lambda: None)
    assert version_policy.get_package_version_display() == "dev"


def test_get_package_version_display_uses_parsed_version(monkeypatch):
    monkeypatch.setattr(
        version_policy,
        "get_installed_version",
        lambda: Version("0.5.4"),
    )
    assert version_policy.get_package_version_display() == "0.5.4"


def test_assess_install_health_ok_single_wheel(monkeypatch):
    _patch_distributions(
        monkeypatch,
        [_FakeDist(version="0.5.6", has_record=True, editable=False)],
    )
    report = version_policy.assess_install_health()
    assert report.ok is True
    assert report.display_version == "0.5.6"
    assert report.issues == []


def test_assess_install_health_duplicate_and_orphan(monkeypatch):
    dists = [
        _FakeDist(
            version="0.5.1",
            has_record=False,
            editable=True,
            dist_dir_name="skillware-0.5.1.dist-info",
        ),
        _FakeDist(
            version="0.5.4",
            has_record=True,
            editable=False,
            dist_dir_name="skillware-0.5.4.dist-info",
        ),
    ]
    _patch_distributions(monkeypatch, dists)
    report = version_policy.assess_install_health()
    assert report.ok is False
    codes = {issue.code for issue in report.issues}
    assert "duplicate_distribution" in codes
    assert "orphan_dist_info" in codes


def test_assess_install_health_editable_and_wheel(monkeypatch):
    dists = [
        _FakeDist(
            version="0.5.1",
            has_record=False,
            editable=True,
            dist_dir_name="skillware-0.5.1.dist-info",
        ),
        _FakeDist(
            version="0.5.6",
            has_record=True,
            editable=False,
            dist_dir_name="skillware-0.5.6.dist-info",
        ),
    ]
    _patch_distributions(monkeypatch, dists)
    monkeypatch.setattr(
        version_policy,
        "_distribution_is_editable",
        lambda dist: dist is dists[0],
    )
    report = version_policy.assess_install_health()
    assert any(issue.code == "editable_and_wheel" for issue in report.issues)


def test_assess_install_health_no_parseable_version(monkeypatch):
    _patch_distributions(
        monkeypatch,
        [
            _FakeDist(
                version="None",
                has_record=False,
                editable=True,
                dist_dir_name="skillware-0.5.1.dist-info",
            )
        ],
    )
    report = version_policy.assess_install_health()
    assert report.ok is False
    assert report.display_version == "dev"
    assert any(issue.code == "no_parseable_version" for issue in report.issues)


def test_emit_install_conflict_advisory_warns(monkeypatch, capsys):
    monkeypatch.setattr(
        version_policy,
        "assess_install_health",
        lambda: version_policy.InstallHealth(
            ok=False,
            issues=[
                version_policy.InstallIssue(
                    code="duplicate_distribution",
                    message="duplicate skillware installs",
                )
            ],
        ),
    )
    version_policy.emit_install_conflict_advisory()
    err = capsys.readouterr().err
    assert "duplicate skillware installs" in err
    assert "doctor --install" in err


def test_emit_install_conflict_advisory_silent_when_ok(monkeypatch, capsys):
    monkeypatch.setattr(
        version_policy,
        "assess_install_health",
        lambda: version_policy.InstallHealth(ok=True),
    )
    version_policy.emit_install_conflict_advisory()
    assert capsys.readouterr().err == ""


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
    assert version_policy.should_emit_unsupported_advisory(Version("0.5.6")) is False


def test_emit_advisory_silent_for_current_release(monkeypatch, capsys):
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "0.5.6",
    )
    monkeypatch.setattr(
        version_policy,
        "iter_skillware_distributions",
        lambda: iter([]),
    )
    version_policy.emit_upgrade_advisory()
    assert capsys.readouterr().err == ""


def test_emit_advisory_silent_for_security_supported_floor(monkeypatch, capsys):
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "0.5.6",
    )
    monkeypatch.setattr(
        version_policy,
        "iter_skillware_distributions",
        lambda: iter([]),
    )
    version_policy.emit_upgrade_advisory()
    assert capsys.readouterr().err == ""


def test_emit_advisory_silent_for_outdated_but_supported_band(monkeypatch, capsys):
    for version in ("0.4.6", "0.5.0", "0.5.2", "0.5.3", "0.5.4", "0.5.5"):
        monkeypatch.setattr(
            version_policy.metadata,
            "version",
            lambda _name, v=version: v,
        )
        monkeypatch.setattr(
            version_policy,
            "iter_skillware_distributions",
            lambda: iter([]),
        )
        version_policy.emit_upgrade_advisory()
        assert capsys.readouterr().err == ""


def test_emit_advisory_warns_for_unsupported(monkeypatch, capsys):
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "0.4.5",
    )
    monkeypatch.setattr(
        version_policy,
        "iter_skillware_distributions",
        lambda: iter([]),
    )
    version_policy.emit_upgrade_advisory()
    err = capsys.readouterr().err
    assert "0.4.5" in err
    assert "unsupported" in err.lower()
    assert ">=0.5.6" in err


def test_emit_advisory_respects_opt_out(monkeypatch, capsys):
    monkeypatch.setenv("SKILLWARE_NO_VERSION_CHECK", "1")
    monkeypatch.setattr(
        version_policy.metadata,
        "version",
        lambda _name: "0.4.5",
    )
    version_policy.emit_upgrade_advisory()
    assert capsys.readouterr().err == ""


def test_cli_package_version_str_never_none(monkeypatch):
    from skillware import cli as cli_module

    monkeypatch.setattr(cli_module, "get_package_version_display", lambda: "dev")
    assert cli_module._package_version_str() == "dev"


def test_cli_main_calls_advisories_once(monkeypatch):
    from skillware import cli as cli_module

    upgrade_calls = []
    install_calls = []
    monkeypatch.setattr(
        cli_module,
        "emit_upgrade_advisory",
        lambda: upgrade_calls.append(True),
    )
    monkeypatch.setattr(
        cli_module,
        "emit_install_conflict_advisory",
        lambda: install_calls.append(True),
    )
    monkeypatch.setattr(cli_module, "cmd_list", lambda **kwargs: None)
    monkeypatch.setattr(sys, "argv", ["skillware", "list"])

    cli_module.main()
    assert len(upgrade_calls) == 1
    assert len(install_calls) == 1


def test_cli_doctor_install_exit_code(monkeypatch):
    from skillware import cli as cli_module

    monkeypatch.setattr(
        cli_module,
        "assess_install_health",
        lambda: version_policy.InstallHealth(ok=False),
    )
    assert cli_module.cmd_doctor_install() == 1


def test_cli_doctor_install_ok_exit_code(monkeypatch):
    from skillware import cli as cli_module

    monkeypatch.setattr(
        cli_module,
        "assess_install_health",
        lambda: version_policy.InstallHealth(ok=True, display_version="0.5.6"),
    )
    assert cli_module.cmd_doctor_install() == 0

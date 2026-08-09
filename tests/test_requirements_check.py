"""Tests for manifest requirement validation (loader pre-flight)."""

import importlib.util

import pytest

from skillware.core.extras import (
    build_version_mismatch_message,
    check_manifest_requirements,
    parse_requirement,
    requirement_import_module,
)


def test_parse_requirement_handles_version_specifier():
    parsed = parse_requirement("web3>=6.0.0")
    assert parsed.name == "web3"
    assert str(parsed.specifier) == ">=6.0.0"


def test_requirement_import_module_resolves_aliases():
    assert requirement_import_module("google-genai") == "google.genai"
    assert requirement_import_module("pymupdf>=1.0") == "fitz"


def test_check_manifest_requirements_unpinned_only_checks_importable(monkeypatch):
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda name, package=None: object()
    )

    check_manifest_requirements(["requests"], manifest={"name": "demo/skill"})


def test_check_manifest_requirements_missing_package(monkeypatch):
    monkeypatch.setattr(importlib.util, "find_spec", lambda name, package=None: None)

    with pytest.raises(ImportError, match="missing packages"):
        check_manifest_requirements(
            ["missing_pkg"],
            registry_id="demo/skill",
            manifest={"name": "demo/skill"},
        )


def test_check_manifest_requirements_version_mismatch(monkeypatch):
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda name, package=None: object()
    )
    monkeypatch.setattr("skillware.core.extras.version", lambda _name: "1.0.0")

    with pytest.raises(ImportError, match="unsatisfied version requirements"):
        check_manifest_requirements(
            ["demo_pkg>=2.0.0"],
            registry_id="demo/skill",
            manifest={"name": "demo/skill"},
        )


def test_check_manifest_requirements_satisfied_version(monkeypatch):
    monkeypatch.setattr(
        importlib.util, "find_spec", lambda name, package=None: object()
    )
    monkeypatch.setattr("skillware.core.extras.version", lambda _name: "2.5.0")

    check_manifest_requirements(
        ["demo_pkg>=2.0.0"],
        manifest={"name": "demo/skill"},
    )


def test_check_manifest_requirements_invalid_pep508():
    with pytest.raises(ImportError, match="Invalid requirement"):
        check_manifest_requirements(
            ["not a valid req !!!"], manifest={"name": "demo/skill"}
        )


def test_build_version_mismatch_message_includes_install_hint():
    message = build_version_mismatch_message(
        {"name": "defi/evm_tx_handler"},
        "defi/evm_tx_handler",
        [("web3>=6.0.0", "5.31.0", ">=6.0.0")],
    )
    assert "web3>=6.0.0" in message
    assert "5.31.0" in message
    assert "skillware[defi_evm_tx_handler]" in message

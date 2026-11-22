"""Tests for deterministic bundle fingerprints and lockfile verification."""

import json
from pathlib import Path

import pytest

from skillware.core.integrity import (
    BUNDLE_CORE_FILES,
    LOCKFILE_SCHEMA,
    STATUS_DRIFT,
    STATUS_MISSING,
    STATUS_NEW,
    compute_bundle_fingerprint,
    compute_fingerprints,
    compare_fingerprints,
    load_lockfile,
    verify_bundle_fingerprints,
    write_lockfile,
)


def _write_bundle(root: Path, bundle_id: str = "office/demo") -> Path:
    """Write a minimal bundle with all four core files plus one data file."""
    category, name = bundle_id.split("/")
    bundle_dir = root / category / name
    bundle_dir.mkdir(parents=True)
    (bundle_dir / "manifest.yaml").write_text(
        f"name: {bundle_id}\nversion: 0.1.0\ndescription: test\n"
        "parameters:\n  type: object\n  properties: {}\n",
        encoding="utf-8",
    )
    (bundle_dir / "skill.py").write_text(
        "from skillware.core.base_skill import BaseSkill\n"
        "class DemoSkill(BaseSkill):\n"
        "    def execute(self, **kwargs):\n"
        "        return {}\n",
        encoding="utf-8",
    )
    (bundle_dir / "instructions.md").write_text("# Demo\n", encoding="utf-8")
    (bundle_dir / "card.json").write_text('{"title": "Demo"}\n', encoding="utf-8")
    (bundle_dir / "data.json").write_text('{"rows": 1}\n', encoding="utf-8")
    return bundle_dir


def test_bundle_digest_is_stable_across_locations(tmp_path):
    first = _write_bundle(tmp_path / "one")
    second = _write_bundle(tmp_path / "two" / "deeper")

    first_print = compute_bundle_fingerprint("office/demo", first)
    second_print = compute_bundle_fingerprint("office/demo", second)

    assert first_print.digest == second_print.digest
    assert compute_bundle_fingerprint("office/demo", first).digest == first_print.digest
    assert first_print.files == second_print.files


def test_core_scope_ignores_extra_data_files(tmp_path):
    bundle_dir = _write_bundle(tmp_path)
    before = compute_bundle_fingerprint("office/demo", bundle_dir)

    (bundle_dir / "data.json").write_text('{"rows": 2}\n', encoding="utf-8")
    after = compute_bundle_fingerprint("office/demo", bundle_dir)

    assert before.digest == after.digest
    assert set(before.files) == set(BUNDLE_CORE_FILES)
    assert "data.json" not in before.files


def test_all_files_scope_tracks_extra_data_files(tmp_path):
    bundle_dir = _write_bundle(tmp_path)
    before = compute_bundle_fingerprint("office/demo", bundle_dir, all_files=True)

    (bundle_dir / "data.json").write_text('{"rows": 2}\n', encoding="utf-8")
    after = compute_bundle_fingerprint("office/demo", bundle_dir, all_files=True)

    assert "data.json" in before.files
    assert before.digest != after.digest


def test_missing_core_file_is_reported(tmp_path):
    bundle_dir = _write_bundle(tmp_path)
    (bundle_dir / "card.json").unlink()

    fingerprint = compute_bundle_fingerprint("office/demo", bundle_dir)

    assert fingerprint.missing == ("card.json",)
    assert fingerprint.complete is False


def test_write_lockfile_then_load_round_trips(tmp_path):
    bundle_dir = _write_bundle(tmp_path / "skills")
    fingerprint = compute_bundle_fingerprint("office/demo", bundle_dir)
    lockfile = tmp_path / "skills.lock.json"

    payload = write_lockfile(
        lockfile, {"office/demo": fingerprint}, generated_at="2026-01-01T00:00:00Z"
    )

    assert payload["schema"] == LOCKFILE_SCHEMA
    assert payload["generated_at"] == "2026-01-01T00:00:00Z"
    assert payload["bundles"]["office/demo"]["digest"] == fingerprint.digest
    assert set(payload["bundles"]["office/demo"]["files"]) == set(BUNDLE_CORE_FILES)

    reloaded = load_lockfile(lockfile)
    assert reloaded is not None
    assert reloaded["bundles"]["office/demo"]["digest"] == fingerprint.digest
    assert json.loads(lockfile.read_text(encoding="utf-8"))["schema"] == LOCKFILE_SCHEMA


def test_load_lockfile_rejects_unknown_schema(tmp_path):
    lockfile = tmp_path / "skills.lock.json"
    lockfile.write_text(
        json.dumps({"schema": "other/1", "bundles": {}}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="unsupported schema"):
        load_lockfile(lockfile)


def test_compare_flags_drifted_bundle(tmp_path):
    bundle_dir = _write_bundle(tmp_path / "skills")
    before = compute_bundle_fingerprint("office/demo", bundle_dir)
    lockfile = {"bundles": {"office/demo": before.lockfile_entry()}}

    (bundle_dir / "skill.py").write_text("# changed\n", encoding="utf-8")
    after = compute_bundle_fingerprint("office/demo", bundle_dir)
    verdicts = compare_fingerprints({"office/demo": after}, lockfile)

    assert verdicts[0].status == STATUS_DRIFT
    assert verdicts[0].lockfile_digest == before.digest


def test_compare_marks_untracked_bundle_as_new(tmp_path):
    bundle_dir = _write_bundle(tmp_path / "skills")
    fingerprint = compute_bundle_fingerprint("office/demo", bundle_dir)

    verdicts = compare_fingerprints({"office/demo": fingerprint}, {"bundles": {}})

    assert verdicts[0].status == STATUS_NEW


def test_compare_marks_incomplete_bundle_as_missing(tmp_path):
    bundle_dir = _write_bundle(tmp_path / "skills")
    (bundle_dir / "instructions.md").unlink()
    fingerprint = compute_bundle_fingerprint("office/demo", bundle_dir)

    verdicts = compare_fingerprints({"office/demo": fingerprint}, {"bundles": {}})

    assert verdicts[0].status == STATUS_MISSING


def test_verify_writes_lockfile_when_absent_then_matches(tmp_path):
    bundle_dir = _write_bundle(tmp_path / "skills")
    lockfile = tmp_path / "skills.lock.json"
    bundles = {"office/demo": bundle_dir}

    written = verify_bundle_fingerprints(bundles, lockfile_path=lockfile)
    assert written.written is True
    assert lockfile.is_file()

    checked = verify_bundle_fingerprints(bundles, lockfile_path=lockfile)
    assert checked.written is False
    assert checked.matched == 1
    assert checked.drifted == 0
    assert checked.ok is True


def test_verify_reports_digests_without_a_lockfile(tmp_path):
    bundle_dir = _write_bundle(tmp_path / "skills")
    bundles = {"office/demo": bundle_dir}

    report = verify_bundle_fingerprints(bundles, lockfile_path=None)

    assert report.lockfile is None
    assert report.written is False
    assert report.count("computed") == 1
    assert list(tmp_path.glob("*.json")) == []  # a report-only run writes nothing

    fingerprints = compute_fingerprints(bundles)
    assert fingerprints["office/demo"].digest == report.verdicts[0].digest

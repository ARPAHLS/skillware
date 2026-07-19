"""Registry card.json ui_schema field keys must resolve in execute() output samples."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from skillware.core.ui_schema import (
    is_output_card_ui_schema,
    normalize_fixture_samples,
    validate_card_ui_schema,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"
FIXTURES_ROOT = REPO_ROOT / "tests" / "fixtures" / "card_ui_schema"


def _discover_skill_dirs():
    if not SKILLS_ROOT.is_dir():
        return []
    return sorted(p.parent for p in SKILLS_ROOT.rglob("manifest.yaml"))


def _skill_id(skill_dir: Path) -> str:
    return skill_dir.relative_to(SKILLS_ROOT).as_posix()


def _fixture_path(skill_dir: Path) -> Path:
    return FIXTURES_ROOT / f"{_skill_id(skill_dir).replace('/', '__')}.json"


def _load_card(skill_dir: Path) -> dict | None:
    card_path = skill_dir / "card.json"
    if not card_path.is_file():
        return None
    with open(card_path, encoding="utf-8") as handle:
        return json.load(handle)


def _skills_with_output_card_ui_schema():
    cases = []
    for skill_dir in _discover_skill_dirs():
        card = _load_card(skill_dir)
        if not card:
            continue
        ui_schema = card.get("ui_schema")
        if is_output_card_ui_schema(ui_schema):
            cases.append((_skill_id(skill_dir), skill_dir))
    assert cases, "expected at least one registry skill with output card ui_schema"
    return cases


OUTPUT_CARD_SKILLS = _skills_with_output_card_ui_schema()


@pytest.mark.parametrize(
    "skill_id,skill_dir",
    OUTPUT_CARD_SKILLS,
    ids=[skill_id for skill_id, _ in OUTPUT_CARD_SKILLS],
)
def test_card_ui_schema_keys_match_execute_output_fixture(skill_id, skill_dir):
    rel = skill_dir.relative_to(REPO_ROOT).as_posix()
    card = _load_card(skill_dir)
    ui_schema = card["ui_schema"]

    fixture_path = _fixture_path(skill_dir)
    assert fixture_path.is_file(), (
        f"{rel}: add execute() output fixture at "
        f"{fixture_path.relative_to(REPO_ROOT).as_posix()} "
        f"for card.json ui_schema validation (#199)"
    )

    with open(fixture_path, encoding="utf-8") as handle:
        payload = json.load(handle)

    samples = normalize_fixture_samples(payload)
    missing = validate_card_ui_schema(ui_schema, samples)
    assert not missing, (
        f"{rel} card.json ui_schema keys missing from fixture samples: "
        f"{', '.join(missing)}"
    )


def test_output_card_skills_have_fixture_files():
    """Every output-card skill must ship a co-located CI fixture under tests/fixtures/."""
    missing_fixtures = []
    for skill_id, skill_dir in _skills_with_output_card_ui_schema():
        if not _fixture_path(skill_dir).is_file():
            missing_fixtures.append(skill_id)
    assert not missing_fixtures, "missing card ui_schema fixtures for: " + ", ".join(
        missing_fixtures
    )

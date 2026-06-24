"""Registry skills must declare issuer attribution (name + email required)."""

import json
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"

PLACEHOLDER_NAMES = frozenset({"your name"})
PLACEHOLDER_EMAILS = frozenset({"you@example.com"})
PLACEHOLDER_GITHUB = frozenset({"your_github_username"})
PLACEHOLDER_ORGS = frozenset({"your org"})


def _discover_skill_dirs():
    if not SKILLS_ROOT.is_dir():
        return []
    return sorted(p.parent for p in SKILLS_ROOT.rglob("manifest.yaml"))


def _load_manifest(skill_dir: Path) -> dict:
    with open(skill_dir / "manifest.yaml", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def _assert_real_issuer(issuer: dict, context: str) -> None:
    assert isinstance(issuer, dict), f"{context}: issuer must be a mapping"

    name = (issuer.get("name") or "").strip()
    email = (issuer.get("email") or "").strip()
    assert name, f"{context}: issuer.name is required"
    assert email, f"{context}: issuer.email is required"

    assert (
        name.lower() not in PLACEHOLDER_NAMES
    ), f"{context}: issuer.name must not be a template placeholder"
    assert (
        email.lower() not in PLACEHOLDER_EMAILS
    ), f"{context}: issuer.email must not be a template placeholder"

    github = (issuer.get("github") or "").strip()
    if github:
        assert (
            github.lower() not in PLACEHOLDER_GITHUB
        ), f"{context}: issuer.github must not be a template placeholder"

    org = (issuer.get("org") or "").strip()
    if org:
        assert (
            org.lower() not in PLACEHOLDER_ORGS
        ), f"{context}: issuer.org must not be a template placeholder"


def test_registry_skills_declare_issuer():
    skill_dirs = _discover_skill_dirs()
    assert skill_dirs, "expected at least one skill under skills/"

    for skill_dir in skill_dirs:
        rel = skill_dir.relative_to(REPO_ROOT).as_posix()
        manifest = _load_manifest(skill_dir)
        _assert_real_issuer(manifest.get("issuer"), f"{rel} manifest.yaml")


def test_registry_skills_have_bundle_test():
    """Every registry skill must ship a co-located bundle test (RFC #156)."""
    for skill_dir in _discover_skill_dirs():
        rel = skill_dir.relative_to(REPO_ROOT).as_posix()
        assert (
            skill_dir / "test_skill.py"
        ).is_file(), (
            f"{rel}: add test_skill.py (bundle test required for every registry skill)"
        )


def test_registry_skills_have_packaging_init_files():
    """Each registry skill must be importable under the skills package for pip wheels."""
    assert (
        SKILLS_ROOT / "__init__.py"
    ).is_file(), "skills/__init__.py is required for packaging"

    for skill_dir in _discover_skill_dirs():
        rel = skill_dir.relative_to(REPO_ROOT).as_posix()
        assert (
            skill_dir / "__init__.py"
        ).is_file(), (
            f"{rel}: add an empty __init__.py so non-Python assets ship in PyPI wheels"
        )
        category_dir = skill_dir.parent
        assert (category_dir / "__init__.py").is_file(), (
            f"{category_dir.relative_to(REPO_ROOT).as_posix()}: "
            "add an empty __init__.py for the skill category package"
        )


def test_registry_card_issuer_matches_manifest_when_present():
    for skill_dir in _discover_skill_dirs():
        rel = skill_dir.relative_to(REPO_ROOT).as_posix()
        manifest_issuer = _load_manifest(skill_dir).get("issuer")
        _assert_real_issuer(manifest_issuer, f"{rel} manifest.yaml")

        card_path = skill_dir / "card.json"
        if not card_path.is_file():
            continue

        with open(card_path, encoding="utf-8") as f:
            card = json.load(f)

        card_issuer = card.get("issuer")
        assert card_issuer is not None, f"{rel} card.json should include issuer"
        _assert_real_issuer(card_issuer, f"{rel} card.json")

        assert (card_issuer.get("name") or "").strip() == (
            manifest_issuer.get("name") or ""
        ).strip(), f"{rel}: card issuer.name should match manifest"
        assert (card_issuer.get("email") or "").strip() == (
            manifest_issuer.get("email") or ""
        ).strip(), f"{rel}: card issuer.email should match manifest"

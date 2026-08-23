"""Validate .github/labels.json matches repository label policy."""

import json
import re
from pathlib import Path

LABELS_PATH = Path(__file__).resolve().parent.parent / ".github" / "labels.json"
HEX_COLOR = re.compile(r"^[0-9A-Fa-f]{6}$")

# Keep in sync with .github/ISSUE_TEMPLATE/01_skill_proposal.yml category dropdown.
REGISTRY_CATEGORIES = (
    "compliance",
    "creative",
    "data_engineering",
    "defi",
    "dev_tools",
    "finance",
    "monitoring",
    "office",
    "optimization",
    "security",
    "wellness",
)

CATEGORY_LABEL_PREFIX = "cat: "
CATEGORY_LABEL_COLOR = "E6D9F5"

# Repo-wide `security` is intentional (vulnerabilities/trust model); category uses `cat: security`.
BARE_CATEGORY_NAMES_FORBIDDEN_AS_REPO_LABELS = set(REGISTRY_CATEGORIES) - {"security"}

REQUIRED_LABELS = {
    "bug",
    "documentation",
    "enhancement",
    "good first issue",
    "help wanted",
    "skill request",
    "skill upgrade",
    "core framework",
    "cli",
    "examples",
    "testing",
    "packaging",
    "ci",
    "security",
    "discussion",
    "question",
    "wontfix",
}


def _load_labels() -> list[dict]:
    return json.loads(LABELS_PATH.read_text(encoding="utf-8"))


def _label_map() -> dict[str, dict]:
    return {entry["name"]: entry for entry in _load_labels()}


def test_labels_json_exists_and_is_array():
    labels = _load_labels()
    assert isinstance(labels, list)
    assert len(labels) >= len(REQUIRED_LABELS)


def test_required_labels_present():
    names = set(_label_map())
    missing = REQUIRED_LABELS - names
    assert not missing, f"Missing labels in labels.json: {sorted(missing)}"


def test_label_entries_well_formed():
    names: set[str] = set()
    for entry in _load_labels():
        name = entry.get("name")
        color = entry.get("color", "")
        description = entry.get("description", "")
        assert name and isinstance(name, str)
        assert name not in names, f"Duplicate label: {name}"
        names.add(name)
        assert HEX_COLOR.match(color), f"Bad color for {name}: {color!r}"
        assert description and isinstance(description, str)


def test_rfc_template_labels_exist():
    """Issue template 05_rfc.yml references discussion and core framework."""
    names = set(_label_map())
    assert "discussion" in names
    assert "core framework" in names


def test_registry_category_labels_present():
    """Every registry category has a matching cat: label."""
    names = set(_label_map())
    expected = {
        f"{CATEGORY_LABEL_PREFIX}{category}" for category in REGISTRY_CATEGORIES
    }
    missing = expected - names
    assert not missing, f"Missing category labels in labels.json: {sorted(missing)}"


def test_category_labels_share_color_and_prefix():
    """Category labels use cat: prefix and one shared pastel color."""
    labels = _label_map()
    category_labels = [
        labels[f"{CATEGORY_LABEL_PREFIX}{category}"] for category in REGISTRY_CATEGORIES
    ]
    colors = {entry["color"].upper() for entry in category_labels}
    assert colors == {
        CATEGORY_LABEL_COLOR
    }, f"All cat: labels must use #{CATEGORY_LABEL_COLOR}; got {sorted(colors)}"
    for category in REGISTRY_CATEGORIES:
        name = f"{CATEGORY_LABEL_PREFIX}{category}"
        assert name in labels
        assert labels[name]["name"].startswith(CATEGORY_LABEL_PREFIX)


def test_category_labels_do_not_collide_with_repo_labels():
    """Bare category folder names must not be repo-wide labels (except security)."""
    names = set(_label_map())
    collisions = BARE_CATEGORY_NAMES_FORBIDDEN_AS_REPO_LABELS & names
    assert not collisions, (
        f"Registry category names must use cat: prefix, not repo-wide labels: "
        f"{sorted(collisions)}"
    )
    assert "security" in names
    assert f"{CATEGORY_LABEL_PREFIX}security" in names

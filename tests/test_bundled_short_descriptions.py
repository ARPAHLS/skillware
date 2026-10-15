"""Guard bundled skill short_description lines used for agent routing (#355)."""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
MAX_LEN = 160
TARGET_LEN = 120


def _manifests():
    return sorted(SKILLS.rglob("manifest.yaml"))


def test_every_bundled_skill_has_short_description():
    missing = []
    for path in _manifests():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        value = (data or {}).get("short_description")
        if not isinstance(value, str) or not value.strip():
            missing.append(str(path.relative_to(ROOT)))
    assert missing == []


def test_bundled_short_descriptions_fit_brief_budget():
    too_long = []
    over_target = []
    for path in _manifests():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        value = str((data or {}).get("short_description") or "")
        rel = str(path.relative_to(ROOT))
        if len(value) > MAX_LEN:
            too_long.append((rel, len(value)))
        elif len(value) > TARGET_LEN:
            over_target.append((rel, len(value)))
    assert too_long == []
    assert over_target == []

"""Guard: bundled manifests expose an agent-routing ``short_description`` (#355).

Brief lines are often the only skill-specific context a multi-skill host sees at
tool-selection time (``SkillContext(mode="brief")``), so a missing or overlong
``short_description`` degrades routing. The 120-character target is a soft goal;
this guard enforces presence and the 160-character framework truncation cap.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_ROOT = REPO_ROOT / "skills"

# SkillContext._brief_line truncates here (see skillware/context.py).
BRIEF_LINE_CAP = 160


def bundled_manifests() -> list[Path]:
    return sorted(SKILLS_ROOT.rglob("manifest.yaml"))


def test_every_bundled_manifest_has_short_description():
    missing: list[str] = []
    for path in bundled_manifests():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        short = data.get("short_description")
        if not isinstance(short, str) or not short.strip():
            missing.append(path.parent.relative_to(SKILLS_ROOT).as_posix())
    assert not missing, (
        "Bundled skills missing a non-empty short_description "
        "(see CONTRIBUTING.md manifest guidance):\n"
        + "\n".join(f"  - {skill}" for skill in missing)
    )


def test_short_descriptions_fit_brief_line_cap():
    overlong: list[str] = []
    multiline: list[str] = []
    for path in bundled_manifests():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            continue
        short = data.get("short_description")
        if not isinstance(short, str):
            continue
        skill = path.parent.relative_to(SKILLS_ROOT).as_posix()
        if "\n" in short:
            multiline.append(skill)
        if len(short) > BRIEF_LINE_CAP:
            overlong.append(f"{skill} ({len(short)} > {BRIEF_LINE_CAP})")
    assert not multiline, "short_description must be a single line:\n" + "\n".join(
        f"  - {skill}" for skill in multiline
    )
    assert not overlong, (
        f"short_description exceeds the {BRIEF_LINE_CAP}-char brief-line cap:\n"
        + "\n".join(f"  - {item}" for item in overlong)
    )

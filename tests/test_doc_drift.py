"""Doc-drift guards for skill-history tables and the CHANGELOG (#477).

`CONTRIBUTING.md` already forbids template placeholders in the Skill history
tables and requires a well-formed `[Unreleased]` section, but both rules were
only enforced by memory during release cuts. These checks make the rules
machine-checked by CI.

Every rule lives in a pure function over text so the guard can be proven red
without editing repository files: the test functions at the bottom only supply
the real paths.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DOCS = REPO_ROOT / "docs" / "skills"
CHANGELOG = REPO_ROOT / "CHANGELOG.md"

HISTORY_BEGIN = "<!-- skill-history:begin -->"
HISTORY_END = "<!-- skill-history:end -->"
PLACEHOLDER = "TBD"

REQUIRED_UNRELEASED_SUBSECTIONS = ("### Added", "### Changed", "### Fixed")


def iter_catalog_pages() -> list[Path]:
    """Skill catalog pages only; skip the library index and category hubs."""
    return sorted(
        path for path in SKILLS_DOCS.rglob("*.md") if path.name != "README.md"
    )


def extract_history_block(page_text: str) -> str | None:
    """Return the text between the skill-history markers, or None if unmasked."""
    begin = page_text.find(HISTORY_BEGIN)
    if begin == -1:
        return None
    end = page_text.find(HISTORY_END, begin)
    if end == -1:
        return None
    return page_text[begin + len(HISTORY_BEGIN) : end]


def find_placeholder_rows(page_text: str) -> list[str]:
    """Return history rows whose commit cell is still a placeholder.

    Scoped to the `skill-history` block and to the first table cell: a page
    may legitimately mention `TBD` elsewhere, and the commit cell is the only
    place where the placeholder hides stale documentation.
    """
    block = extract_history_block(page_text)
    if block is None:
        return []

    stale: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        commit_cell = stripped.strip("|").split("|")[0].strip()
        if PLACEHOLDER in commit_cell.upper():
            stale.append(stripped)
    return stale


def changelog_problems(text: str) -> list[str]:
    """Return problems with the `[Unreleased]` section; empty means well formed."""
    lines = text.splitlines()
    heading_index = None
    for index, line in enumerate(lines):
        if line.strip() == "## [Unreleased]":
            heading_index = index
            break
    if heading_index is None:
        return ["missing `## [Unreleased]` section; it must precede released versions"]

    body: list[str] = []
    for line in lines[heading_index + 1 :]:
        if line.startswith("## "):
            break
        body.append(line)

    positions: dict[str, int] = {}
    for subsection in REQUIRED_UNRELEASED_SUBSECTIONS:
        hits = [index for index, line in enumerate(body) if line.strip() == subsection]
        if not hits:
            return [f"`## [Unreleased]` is missing the `{subsection}` subsection"]
        positions[subsection] = hits[0]

    order = [positions[name] for name in REQUIRED_UNRELEASED_SUBSECTIONS]
    if order != sorted(order):
        return [
            "`## [Unreleased]` subsections are out of order; expected "
            + ", ".join(REQUIRED_UNRELEASED_SUBSECTIONS)
        ]
    return []


def test_skill_history_has_no_placeholders() -> None:
    """Every catalog page records real commit hashes, not `TBD` (#477)."""
    failures = []

    for page in iter_catalog_pages():
        for row in find_placeholder_rows(page.read_text(encoding="utf-8")):
            rel = page.relative_to(REPO_ROOT).as_posix()
            failures.append(f"{rel}: {row}")

    assert not failures, (
        "Skill history rows still use the `TBD` placeholder. Replace the commit "
        "cell with the squash-merge SHA from `main` "
        "(`git log --oneline -- skills/<category>/<name>`):\n"
        + "\n".join(f"  - {item}" for item in failures)
    )


def test_changelog_unreleased_section_is_well_formed() -> None:
    """`CHANGELOG.md` keeps a valid Keep-a-Changelog `[Unreleased]` block (#477)."""
    problems = changelog_problems(CHANGELOG.read_text(encoding="utf-8"))

    assert not problems, "CHANGELOG.md `[Unreleased]` drift:\n" + "\n".join(
        f"  - {item}" for item in problems
    )


def test_placeholder_rows_are_detected() -> None:
    """The guard reports placeholder rows — without it a green run means nothing."""
    page = (
        f"{HISTORY_BEGIN}\n"
        "## Skill history\n\n"
        "| Commit | Description | Date |\n"
        "| :--- | :--- | :--- |\n"
        "| `TBD` | feat(demo): ship something (#1) | 1 Nov 2026 |\n"
        "| [`abc1234`](https://github.com/ARPAHLS/skillware/commit/abc1234) "
        "| feat(demo): follow-up (#2) | 2 Nov 2026 |\n"
        f"{HISTORY_END}\n"
    )

    assert find_placeholder_rows(page) == [
        "| `TBD` | feat(demo): ship something (#1) | 1 Nov 2026 |"
    ]


def test_placeholders_outside_the_history_block_are_ignored() -> None:
    """Only the skill-history table is guarded; other tables stay untouched."""
    page = (
        "| `TBD` | unrelated notes table |\n"
        f"{HISTORY_BEGIN}\n"
        "| Commit | Description |\n"
        "| [`abc1234`](https://github.com/ARPAHLS/skillware/commit/abc1234) | ok |\n"
        f"{HISTORY_END}\n"
    )

    assert find_placeholder_rows(page) == []


def test_placeholder_in_description_cell_is_ignored() -> None:
    """A description that mentions `TBD` is prose, not stale documentation."""
    page = (
        f"{HISTORY_BEGIN}\n"
        "| Commit | Description |\n"
        "| [`abc1234`](https://github.com/ARPAHLS/skillware/commit/abc1234) "
        "| docs: explain the TBD wording |\n"
        f"{HISTORY_END}\n"
    )

    assert find_placeholder_rows(page) == []


def test_changelog_accepts_a_well_formed_section() -> None:
    """The canonical layout from CONTRIBUTING.md passes the check."""
    text = (
        "# Changelog\n\n"
        "## [Unreleased]\n\n"
        "### Added\n\n- something\n\n"
        "### Changed\n\n### Fixed\n\n"
        "## [0.6.2] - 2026-11-18\n\n### Added\n\n- released\n"
    )

    assert changelog_problems(text) == []


def test_changelog_flags_a_missing_subsection() -> None:
    """A dropped `### Fixed` heading is drift, even when the section exists."""
    text = "## [Unreleased]\n\n### Added\n\n### Changed\n\n## [0.6.2] - 2026-11-18\n"

    assert changelog_problems(text) == [
        "`## [Unreleased]` is missing the `### Fixed` subsection"
    ]


def test_changelog_flags_misordered_subsections() -> None:
    """Keep-a-Changelog order matters: reviewers read top-down."""
    text = "## [Unreleased]\n\n### Fixed\n\n### Added\n\n### Changed\n"

    assert changelog_problems(text) == [
        "`## [Unreleased]` subsections are out of order; expected "
        + ", ".join(REQUIRED_UNRELEASED_SUBSECTIONS)
    ]


def test_changelog_flags_a_missing_unreleased_section() -> None:
    """Releasing must not delete the `[Unreleased]` slot for the next change."""
    text = "# Changelog\n\n## [0.6.2] - 2026-11-18\n\n### Added\n\n- released\n"

    assert changelog_problems(text) == [
        "missing `## [Unreleased]` section; it must precede released versions"
    ]

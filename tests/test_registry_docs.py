"""Repository documentation consistency tests."""

from difflib import SequenceMatcher
from pathlib import Path
import re
import subprocess

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

SKILL_PATTERN = re.compile(r"`([\w-]+/[\w-]+)`")
EXAMPLE_PATTERN = re.compile(r"^\|[^|]*`([\w-]+\.py)`", re.MULTILINE)


def get_manifested_skills(skills_root: Path) -> set[str]:
    """Return all skill IDs containing a manifest.yaml."""
    return {
        path.parent.relative_to(skills_root).as_posix()
        for path in skills_root.rglob("manifest.yaml")
    }


def get_cataloged_skills(readme: Path) -> set[str]:
    """Return all skill IDs listed in docs/skills/README.md."""
    return set(SKILL_PATTERN.findall(readme.read_text(encoding="utf-8")))


def catalog_page_for(skill_id: str) -> Path:
    """Catalog page lives at docs/skills/<category>/<skill_name>.md (#370)."""
    category, name = skill_id.split("/", 1)
    return REPO_ROOT / "docs" / "skills" / category / f"{name}.md"


def iter_catalog_pages() -> list[Path]:
    """Skill pages only — skip the library index and category hub READMEs."""
    docs_root = REPO_ROOT / "docs" / "skills"
    return sorted(path for path in docs_root.rglob("*.md") if path.name != "README.md")


def get_base_branch_skills(repo_root: Path) -> set[str]:
    """Return skill IDs with manifests on origin/main."""
    result = subprocess.run(
        ["git", "ls-tree", "-r", "--name-only", "origin/main", "--", "skills"],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    skill_ids = {
        path.removeprefix("skills/").removesuffix("/manifest.yaml")
        for path in result.stdout.splitlines()
        if path.startswith("skills/") and path.endswith("/manifest.yaml")
    }
    if not skill_ids:
        raise RuntimeError("No skill manifests found on origin/main")
    return skill_ids


def find_skill_history_rows(content: str) -> list[tuple[int, str]]:
    """Return table rows and line numbers within the marked skill history."""
    history = re.search(
        r"<!-- skill-history:begin -->(.*?)<!-- skill-history:end -->",
        content,
        re.DOTALL,
    )
    if history is None:
        return []

    start_line = content.count("\n", 0, history.start(1)) + 1
    return [
        (start_line + index, line)
        for index, line in enumerate(history.group(1).splitlines())
        if re.match(r"^[ \t]*\|", line)
    ]


def find_skill_history_placeholders(content: str) -> list[int]:
    """Return line numbers of TBD commit rows within the marked skill history."""
    return [
        line_number
        for line_number, row in find_skill_history_rows(content)
        if re.match(r"^[ \t]*\|[ \t]*`?TBD`?[ \t]*\|", row)
    ]


def find_stale_skill_history_entries(
    pages: list[Path], base_skill_ids: set[str]
) -> list[str]:
    """Find baseline TBD rows that remain in current skill histories."""
    failures = []
    for page in pages:
        skill_id = f"{page.parent.name}/{page.stem}"
        if skill_id not in base_skill_ids:
            continue
        base_result = subprocess.run(
            ["git", "show", f"origin/main:docs/skills/{skill_id}.md"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        base_content = base_result.stdout
        current_content = page.read_text(encoding="utf-8")
        base_rows = find_skill_history_rows(base_content)
        current_rows = find_skill_history_rows(current_content)
        base_placeholders = set(find_skill_history_placeholders(base_content))
        current_placeholders = set(find_skill_history_placeholders(current_content))
        matcher = SequenceMatcher(
            None,
            [row for _, row in base_rows],
            [row for _, row in current_rows],
            autojunk=False,
        )

        for tag, base_start, base_end, current_start, current_end in matcher.get_opcodes():
            if tag not in {"equal", "replace"}:
                continue
            for base_index, current_index in zip(
                range(base_start, base_end), range(current_start, current_end)
            ):
                base_line_number = base_rows[base_index][0]
                current_line_number = current_rows[current_index][0]
                if (
                    base_line_number in base_placeholders
                    and current_line_number in current_placeholders
                ):
                    failures.append(
                        f"docs/skills/{skill_id}.md:{current_line_number}: "
                        "placeholder commit hash `TBD`"
                    )
    return failures


def find_unreleased_changelog_issues(content: str) -> list[str]:
    """Validate required subsections inside CHANGELOG.md's Unreleased section."""
    match = re.search(r"^## \[Unreleased\][ \t]*$", content, re.MULTILINE)
    if match is None:
        return ["missing `## [Unreleased]` section"]

    section = content[match.end() :]
    next_section = re.search(r"^## ", section, re.MULTILINE)
    if next_section is not None:
        section = section[: next_section.start()]

    present = set(
        re.findall(r"^### (Added|Changed|Fixed)[ \t]*$", section, re.MULTILINE)
    )
    return [
        f"missing `### {heading}` in `## [Unreleased]`"
        for heading in (
            "Added",
            "Changed",
            "Fixed",
        )
        if heading not in present
    ]


def iter_category_hubs() -> list[Path]:
    return sorted((REPO_ROOT / "docs" / "skills").glob("*/README.md"))


@pytest.fixture(scope="session")
def manifested_skills() -> set[str]:
    return get_manifested_skills(REPO_ROOT / "skills")


@pytest.fixture(scope="session")
def cataloged_skills() -> set[str]:
    return get_cataloged_skills(REPO_ROOT / "docs" / "skills" / "README.md")


@pytest.fixture(scope="session")
def example_scripts() -> set[str]:
    examples_dir = REPO_ROOT / "examples"
    return {
        path.name
        for path in examples_dir.glob("*.py")
        if not path.name.endswith("_common.py")
    }


@pytest.fixture(scope="session")
def indexed_example_scripts() -> set[str]:
    readme = (REPO_ROOT / "examples" / "README.md").read_text(encoding="utf-8")
    return set(EXAMPLE_PATTERN.findall(readme))


@pytest.fixture(scope="session")
def agent_loops_text() -> str:
    return (
        (REPO_ROOT / "docs" / "usage" / "agent_loops.md")
        .read_text(encoding="utf-8")
        .lower()
    )


def test_readme_matches_manifests(
    cataloged_skills: set[str],
    manifested_skills: set[str],
):
    """README skill index matches manifested skills."""

    missing = manifested_skills - cataloged_skills
    extra = cataloged_skills - manifested_skills

    assert (
        not missing
    ), "Skills with manifest but missing from docs/skills/README.md:\n" + "\n".join(
        f"  - {skill}" for skill in sorted(missing)
    )

    assert (
        not extra
    ), "Skills listed in docs/skills/README.md without a manifest.yaml:\n" + "\n".join(
        f"  - {skill}" for skill in sorted(extra)
    )


def test_manifested_skills_have_catalog_pages(
    manifested_skills: set[str],
):
    """Every manifested skill has a catalog page under its category hub."""

    missing = [
        skill
        for skill in sorted(manifested_skills)
        if not catalog_page_for(skill).exists()
    ]

    assert not missing, "Missing catalog pages:\n" + "\n".join(
        f"  - docs/skills/{skill}.md" for skill in missing
    )


def test_catalog_pages_are_not_flat():
    """Skill pages must live in docs/skills/<category>/, not docs/skills/*.md (#370)."""
    docs_root = REPO_ROOT / "docs" / "skills"
    flat = sorted(
        path.name for path in docs_root.glob("*.md") if path.name != "README.md"
    )
    assert not flat, "Flat catalog pages must move under category hubs:\n" + "\n".join(
        f"  - docs/skills/{name}" for name in flat
    )


def test_catalog_pages_have_manifests(
    manifested_skills: set[str],
):
    """Every catalog page corresponds to a manifested skill."""

    expected = {Path(skill).name for skill in manifested_skills}
    actual = {page.stem for page in iter_catalog_pages()}
    orphaned = actual - expected

    assert not orphaned, "Catalog pages without a matching manifest:\n" + "\n".join(
        f"  - {page}" for page in sorted(orphaned)
    )


def test_examples_readme_matches_files(
    example_scripts: set[str],
    indexed_example_scripts: set[str],
):
    """Examples README matches runnable scripts."""

    missing = example_scripts - indexed_example_scripts
    orphaned = indexed_example_scripts - example_scripts

    assert (
        not missing
    ), "Example scripts missing from examples/README.md:\n" + "\n".join(
        f"  - {script}" for script in sorted(missing)
    )

    assert (
        not orphaned
    ), "README references non-existent example scripts:\n" + "\n".join(
        f"  - {script}" for script in sorted(orphaned)
    )


def test_agent_loops_reference_all_skills(
    manifested_skills: set[str],
    agent_loops_text: str,
):
    """Every manifested skill is referenced in agent_loops.md."""

    missing = []

    for skill in sorted(manifested_skills):
        skill_name = Path(skill).name

        if (
            skill.lower() not in agent_loops_text
            and skill_name.lower() not in agent_loops_text
        ):
            missing.append(skill)

    assert not missing, "Skills missing from docs/usage/agent_loops.md:\n" + "\n".join(
        f"  - {skill}" for skill in missing
    )


def test_skill_docs_gemini_anti_patterns():
    """Verify Gemini snippets in skill catalog pages do not use anti-patterns."""
    anti_patterns = [
        (r'tool_decl\["name"\]\s*=', 'tool_decl["name"] mutation'),
        (r'gemini_decl\["name"\]\s*=', 'gemini_decl["name"] mutation'),
        (
            r"types\.Tool\s*\(\s*function_declarations\s*=\s*\[",
            "types.Tool(function_declarations=[ manual wrap",
        ),
        (
            r'function_call\.name\s*==\s*(?:bundle|skill)\["manifest"\]\["name"\]',
            'function_call.name == bundle["manifest"]["name"] without sanitize',
        ),
    ]

    failures = []

    for md_file in iter_catalog_pages():
        content = md_file.read_text(encoding="utf-8")

        for pattern, name in anti_patterns:
            if re.search(pattern, content):
                failures.append(f"{md_file.name}: {name}")

    assert not failures, "Gemini anti-patterns found in skill docs:\n" + "\n".join(
        f"  - {f}" for f in failures
    )


def test_catalog_pages_have_skill_specific_recommended_install(
    manifested_skills: set[str],
):
    """Every catalog page recommends the per-skill pip extra."""
    from skillware.core.extras import registry_id_to_extra

    missing = []

    for skill_id in sorted(manifested_skills):
        page = catalog_page_for(skill_id)
        content = page.read_text(encoding="utf-8")
        extra = registry_id_to_extra(skill_id)
        needle = f"skillware[{extra}]"
        if needle not in content:
            rel = page.relative_to(REPO_ROOT).as_posix()
            missing.append(f"{rel}: expected Recommended install with {needle!r}")

    assert not missing, "Missing skill-specific recommended install:\n" + "\n".join(
        f"  - {item}" for item in missing
    )


def test_catalog_pages_have_version_and_history_blocks(
    manifested_skills: set[str],
):
    """Every catalog page exposes synced version metadata and skill history."""
    missing = []

    for skill_id in sorted(manifested_skills):
        page = catalog_page_for(skill_id)
        content = page.read_text(encoding="utf-8")
        rel = page.relative_to(REPO_ROOT).as_posix()
        checks = [
            ("<!-- skill-doc-meta:begin -->", "version metadata begin marker"),
            ("**Version**:", "version header"),
            ("**Tier**:", "tier header"),
            ("**Shape**:", "shape header"),
            ("**Target**:", "target header"),
            ("**Tags**:", "tags header"),
            ("<!-- skill-doc-meta:end -->", "version metadata end marker"),
            ("<!-- skill-intent:begin -->", "intent begin marker"),
            ("**Solves:**", "intent problem line"),
            ("**Works with:**", "intent host-agent line"),
            ("**Runtime:**", "intent runtime line"),
            ("<!-- skill-intent:end -->", "intent end marker"),
            ("<!-- skill-history:begin -->", "skill history begin marker"),
            ("## Skill history", "skill history heading"),
            ("<!-- skill-history:end -->", "skill history end marker"),
        ]
        for needle, label in checks:
            if needle not in content:
                missing.append(f"{rel}: missing {label}")

    assert not missing, "Missing skill version/history blocks:\n" + "\n".join(
        f"  - {item}" for item in missing
    )


def test_existing_skill_history_has_no_placeholder_commit_hashes():
    """Existing skills must not retain TBD hashes in their history table."""
    pages = sorted((REPO_ROOT / "docs" / "skills").glob("*/*.md"))
    failures = find_stale_skill_history_entries(
        [page for page in pages if page.name != "README.md"],
        get_base_branch_skills(REPO_ROOT),
    )
    assert not failures, "Placeholder skill history commit hashes:\n" + "\n".join(
        f"  - {failure}" for failure in failures
    )


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        (
            "## [Unreleased]\n\n### Added\n\n### Changed\n\n### Fixed\n",
            [],
        ),
        (
            "## [0.1.0]\n\n### Added\n### Changed\n### Fixed\n",
            ["missing `## [Unreleased]` section"],
        ),
        (
            "## [Unreleased]\n\n### Added\n\n## [0.1.0]\n\n### Changed\n### Fixed\n",
            [
                "missing `### Changed` in `## [Unreleased]`",
                "missing `### Fixed` in `## [Unreleased]`",
            ],
        ),
        (
            "## [Unreleased]\n\n### Changed\n\n### Fixed\n",
            ["missing `### Added` in `## [Unreleased]`"],
        ),
    ],
)
def test_unreleased_changelog_has_required_subsections(
    content: str, expected: list[str]
):
    """Only subsections within Unreleased satisfy the changelog guard."""
    assert find_unreleased_changelog_issues(content) == expected


def test_changelog_has_valid_unreleased_section():
    """The repository changelog keeps the standard Unreleased subsections."""
    content = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert find_unreleased_changelog_issues(content) == []


def test_new_skill_history_placeholders_are_allowed(tmp_path: Path):
    """New skill placeholders are allowed until their skill lands on main."""
    new_page = tmp_path / "finance" / "new_skill.md"
    history = (
        "<!-- skill-history:begin -->\n"
        "## Skill history\n"
        "| `TBD` | pending commit | date | version | author |\n"
        "<!-- skill-history:end -->\n"
    )
    new_page.parent.mkdir()
    new_page.write_text(history, encoding="utf-8")

    assert find_stale_skill_history_entries([new_page], set()) == []


def test_existing_skill_can_add_new_history_placeholder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """TBD rows added in the PR are allowed when the baseline has none."""
    page = tmp_path / "finance" / "existing_skill.md"
    page.parent.mkdir()
    page.write_text(
        "<!-- skill-history:begin -->\n"
        "## Skill history\n"
        "| `TBD` | newly added | date | version | author |\n"
        "<!-- skill-history:end -->\n",
        encoding="utf-8",
    )
    base_content = (
        "<!-- skill-history:begin -->\n"
        "## Skill history\n"
        "| [`abc1234`](https://example.com/commit/abc1234) | valid | date | version | author |\n"
        "<!-- skill-history:end -->\n"
    )

    def show_base_page(command: list[str], **kwargs) -> subprocess.CompletedProcess:
        assert command == [
            "git",
            "show",
            "origin/main:docs/skills/finance/existing_skill.md",
        ]
        return subprocess.CompletedProcess(command, 0, base_content, "")

    monkeypatch.setattr(subprocess, "run", show_base_page)

    assert find_stale_skill_history_entries([page], {"finance/existing_skill"}) == []


def test_existing_skill_retaining_base_placeholder_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """A retained baseline TBD fails, but a newly added row is not reported."""
    page = tmp_path / "finance" / "existing_skill.md"
    page.parent.mkdir()
    page.write_text(
        "<!-- skill-history:begin -->\n"
        "## Skill history\n"
        "| `TBD` | edited existing entry | updated date | updated version | author |\n"
        "| `TBD` | newly added | date | version | author |\n"
        "<!-- skill-history:end -->\n",
        encoding="utf-8",
    )
    base_content = (
        "<!-- skill-history:begin -->\n"
        "## Skill history\n"
        "| `TBD` | existing | date | version | author |\n"
        "<!-- skill-history:end -->\n"
    )

    def show_base_page(command: list[str], **kwargs) -> subprocess.CompletedProcess:
        assert command == [
            "git",
            "show",
            "origin/main:docs/skills/finance/existing_skill.md",
        ]
        return subprocess.CompletedProcess(command, 0, base_content, "")

    monkeypatch.setattr(subprocess, "run", show_base_page)

    assert find_stale_skill_history_entries([page], {"finance/existing_skill"}) == [
        "docs/skills/finance/existing_skill.md:3: placeholder commit hash `TBD`"
    ]


def test_existing_skill_duplicate_base_placeholders_match_one_to_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Duplicate baseline rows are matched to distinct current rows."""
    page = tmp_path / "finance" / "existing_skill.md"
    page.parent.mkdir()
    row = "| `TBD` | existing | date | version | author |"
    page.write_text(
        "<!-- skill-history:begin -->\n"
        "## Skill history\n"
        f"{row}\n"
        "<!-- skill-history:end -->\n",
        encoding="utf-8",
    )
    base_content = (
        "<!-- skill-history:begin -->\n"
        "## Skill history\n"
        f"{row}\n"
        f"{row}\n"
        "<!-- skill-history:end -->\n"
    )

    def show_base_page(command: list[str], **kwargs) -> subprocess.CompletedProcess:
        assert command == [
            "git",
            "show",
            "origin/main:docs/skills/finance/existing_skill.md",
        ]
        return subprocess.CompletedProcess(command, 0, base_content, "")

    monkeypatch.setattr(subprocess, "run", show_base_page)

    assert find_stale_skill_history_entries([page], {"finance/existing_skill"}) == [
        "docs/skills/finance/existing_skill.md:3: placeholder commit hash `TBD`"
    ]


@pytest.mark.parametrize(
    "current_row",
    [
        "| [`abc1234`](https://example.com/commit/abc1234) | existing | date | version | author |",
        None,
    ],
)
def test_existing_skill_correcting_or_removing_base_placeholder_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    current_row: str | None,
):
    """A baseline TBD no longer fails after it is corrected or removed."""
    page = tmp_path / "finance" / "existing_skill.md"
    page.parent.mkdir()
    current_content = (
        "<!-- skill-history:begin -->\n"
        "## Skill history\n"
        + (f"{current_row}\n" if current_row is not None else "")
        + "<!-- skill-history:end -->\n"
    )
    page.write_text(current_content, encoding="utf-8")
    base_content = (
        "<!-- skill-history:begin -->\n"
        "## Skill history\n"
        "| `TBD` | existing | date | version | author |\n"
        "<!-- skill-history:end -->\n"
    )

    def show_base_page(command: list[str], **kwargs) -> subprocess.CompletedProcess:
        assert command == [
            "git",
            "show",
            "origin/main:docs/skills/finance/existing_skill.md",
        ]
        return subprocess.CompletedProcess(command, 0, base_content, "")

    monkeypatch.setattr(subprocess, "run", show_base_page)

    assert find_stale_skill_history_entries([page], {"finance/existing_skill"}) == []


def test_skill_history_parser_ignores_non_placeholder_rows_and_other_sections():
    """Only TBD commit cells inside the marked history block are stale."""
    content = (
        "A mention of `TBD` outside the history table.\n"
        "<!-- skill-history:begin -->\n"
        "## Skill history\n"
        "| [`abc1234`](https://example.com/commit/abc1234) | valid | date | version | author |\n"
        "<!-- skill-history:end -->\n"
    )

    assert find_skill_history_placeholders(content) == []


def test_catalog_pages_taxonomy_matches_manifests(
    manifested_skills: set[str],
):
    """Catalog page taxonomy metadata matches manifest.yaml values."""
    missing = []
    for skill_id in sorted(manifested_skills):
        page = catalog_page_for(skill_id)
        content = page.read_text(encoding="utf-8")
        manifest_path = REPO_ROOT / "skills" / skill_id / "manifest.yaml"
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
        rel = page.relative_to(REPO_ROOT).as_posix()

        tier_needle = f"**Tier**: `{manifest['tier']}`"
        shape_needle = f"**Shape**: `{manifest['shape']}`"
        if tier_needle not in content:
            missing.append(f"{rel}: missing {tier_needle}")
        if shape_needle not in content:
            missing.append(f"{rel}: missing {shape_needle}")

    assert not missing, "Taxonomy mismatch between docs and manifests:\n" + "\n".join(
        f"  - {item}" for item in missing
    )


def test_skill_library_index_has_version_and_shape_columns():
    """Skill library tables include Shape and Version columns with manifest values."""
    readme = (REPO_ROOT / "docs" / "skills" / "README.md").read_text(encoding="utf-8")
    assert "| Skill | ID | Shape | Version | Issuer | Description |" in readme
    assert "| :--- | :--- | :--- | :--- | :--- | :--- |" in readme

    missing = []
    for manifest_path in (REPO_ROOT / "skills").rglob("manifest.yaml"):
        with open(manifest_path, encoding="utf-8") as f:
            manifest = yaml.safe_load(f)
        if isinstance(manifest, dict):
            skill_id = manifest_path.parent.relative_to(REPO_ROOT / "skills").as_posix()
            if "version" in manifest:
                expected_ver = f"`{manifest['version']}`"
                if expected_ver not in readme:
                    missing.append(f"{skill_id}: missing version {expected_ver}")
            if "shape" in manifest:
                expected_shape = f"`{manifest['shape']}`"
                if expected_shape not in readme:
                    missing.append(f"{skill_id}: missing shape {expected_shape}")

    assert (
        not missing
    ), "Missing manifest versions or shapes in docs/skills/README.md:\n" + "\n".join(
        f"  - {item}" for item in missing
    )


def test_category_hubs_match_manifests(manifested_skills: set[str]):
    """Each registry category has a docs hub that lists its skills (#370)."""
    categories = {skill.split("/", 1)[0] for skill in manifested_skills}
    hubs = {path.parent.name for path in iter_category_hubs()}
    missing_hubs = categories - hubs
    extra_hubs = hubs - categories
    assert not missing_hubs, "Missing category hubs:\n" + "\n".join(
        f"  - docs/skills/{cat}/README.md" for cat in sorted(missing_hubs)
    )
    assert not extra_hubs, "Category hubs without registry skills:\n" + "\n".join(
        f"  - docs/skills/{cat}/README.md" for cat in sorted(extra_hubs)
    )

    missing_rows = []
    for skill in sorted(manifested_skills):
        category, name = skill.split("/", 1)
        hub = (REPO_ROOT / "docs" / "skills" / category / "README.md").read_text(
            encoding="utf-8"
        )
        if "| Skill | ID | Version | Issuer | Description |" not in hub:
            missing_rows.append(f"{category}: missing catalog table header")
        if f"`{skill}`" not in hub:
            missing_rows.append(f"{category}: missing `{skill}`")
        if f"]({name}.md)" not in hub:
            missing_rows.append(f"{category}: missing link to {name}.md")
    assert not missing_rows, "Category hubs missing skill rows:\n" + "\n".join(
        f"  - {item}" for item in missing_rows
    )


def test_library_index_links_category_hubs(manifested_skills: set[str]):
    """Skill library points at each category hub (#370)."""
    readme = (REPO_ROOT / "docs" / "skills" / "README.md").read_text(encoding="utf-8")
    missing = []
    for category in sorted({skill.split("/", 1)[0] for skill in manifested_skills}):
        if f"]({category}/README.md)" not in readme:
            missing.append(category)
    assert not missing, "docs/skills/README.md missing hub links:\n" + "\n".join(
        f"  - {cat}/README.md" for cat in missing
    )


def test_sitemap_lists_hubs_and_catalog_pages(manifested_skills: set[str]):
    """docs/sitemap.md links the library, every hub, and every catalog page (#370)."""
    sitemap = (REPO_ROOT / "docs" / "sitemap.md").read_text(encoding="utf-8")
    missing = []
    if "skills/README.md" not in sitemap:
        missing.append("docs/skills/README.md")
    for skill in sorted(manifested_skills):
        category, name = skill.split("/", 1)
        if f"skills/{category}/README.md" not in sitemap:
            missing.append(f"docs/skills/{category}/README.md")
        if f"skills/{category}/{name}.md" not in sitemap:
            missing.append(f"docs/skills/{category}/{name}.md")
    assert not missing, "Sitemap missing links:\n" + "\n".join(
        f"  - {item}" for item in missing
    )


def test_root_readme_has_category_index(manifested_skills: set[str]):
    """Root README uses one category table with hub links and skill counts (#370)."""
    text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "## Supported Agent Skill Categories" in text
    assert "| Category | Skills | Description |" in text
    expected: dict[str, int] = {}
    for skill in manifested_skills:
        category = skill.split("/", 1)[0]
        expected[category] = expected.get(category, 0) + 1
    found = {
        match.group(1): int(match.group(2))
        for match in re.finditer(
            r"\]\(docs/skills/([a-z_]+)/README\.md\) \| (\d+) \|",
            text,
        )
    }
    assert found == expected, (
        "Root README category table out of sync with manifests:\n"
        f"  expected={dict(sorted(expected.items()))}\n"
        f"  found={dict(sorted(found.items()))}"
    )


def test_glossary_exists_with_canonical_terms():
    """Glossary documents roles and anatomy used across the repo (#252)."""
    text = (REPO_ROOT / "docs" / "glossary.md").read_text(encoding="utf-8")
    for term in (
        "**Operator**",
        "**Contributor**",
        "**Host agent**",
        "**End user**",
        "**Skill bundle**",
        "**Directive**",
        "**Contract**",
    ):
        assert term in text, f"glossary missing {term}"


def test_hub_and_catalog_pages_link_glossary():
    """Hub pages and skill catalog pages must link docs/glossary.md (#363)."""
    hubs = [
        REPO_ROOT / "docs" / "vision.md",
        REPO_ROOT / "docs" / "sitemap.md",
        REPO_ROOT / "docs" / "usage" / "README.md",
        REPO_ROOT / "docs" / "usage" / "agent_loops.md",
        REPO_ROOT / "docs" / "usage" / "skill_chaining.md",
    ]
    missing = []
    for path in hubs:
        text = path.read_text(encoding="utf-8")
        if "glossary.md" not in text:
            missing.append(str(path.relative_to(REPO_ROOT)))
    catalog = REPO_ROOT / "docs" / "skills"
    for path in sorted(catalog.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        if "glossary.md" not in text:
            missing.append(str(path.relative_to(REPO_ROOT)))
    assert not missing, "Pages missing glossary.md link:\n" + "\n".join(
        f"  - {item}" for item in missing
    )


def test_core_docs_avoid_retired_anatomy_labels():
    """Mind/Body/Conscience are not used as skill roles in core docs (#252, #326)."""
    paths = [
        REPO_ROOT / "README.md",
        REPO_ROOT / "CONTRIBUTING.md",
        REPO_ROOT / "docs" / "introduction.md",
        REPO_ROOT / "docs" / "contributing" / "ai_native_workflow.md",
    ]
    forbidden = (
        "Mind / Body / Conscience",
        "Body/Mind/Conscience",
        "in your Mind",
    )
    hits = []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for phrase in forbidden:
            if phrase in text:
                hits.append(f"{path.relative_to(REPO_ROOT)}: {phrase}")
    assert not hits, "Retired anatomy labels in core docs:\n" + "\n".join(
        f"  - {item}" for item in hits
    )


def test_mica_examples_avoid_mind_metaphor():
    """MiCA example system prompts do not use retired Mind wording (#252)."""
    for name in (
        "mica_claude_flow.py",
        "mica_ollama_flow.py",
        "mica_rag_flow.py",
    ):
        text = (REPO_ROOT / "examples" / name).read_text(encoding="utf-8")
        assert "in your Mind" not in text, name


def test_export_site_catalog_check():
    """Verify that scripts/export_site_catalog.py runs with zero validation errors."""
    from scripts.export_site_catalog import export_catalog

    ret = export_catalog(check_only=True)
    assert ret == 0, "export_site_catalog --check failed"

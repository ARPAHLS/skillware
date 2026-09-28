"""Repository documentation consistency tests."""

from pathlib import Path
import re

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

SKILL_PATTERN = re.compile(r"`([\w-]+/[\w-]+)`")
EXAMPLE_PATTERN = re.compile(r"^\|[^|]*`([\w-]+\.py)`", re.MULTILINE)

# TODO: script examples/issue_resolver_github_context.py is a shared helper module and
#       should be renamed to examples/issue_resolver_common.py (see #183).
GRANDFATHERED_EXAMPLES: set[str] = {"issue_resolver_github_context.py"}


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
        and path.name not in GRANDFATHERED_EXAMPLES
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


def test_skill_library_index_has_version_column():
    """Skill library tables include a Version column with manifest values."""
    readme = (REPO_ROOT / "docs" / "skills" / "README.md").read_text(encoding="utf-8")
    assert "| Skill | ID | Version | Issuer | Description |" in readme
    assert "| :--- | :--- | :--- | :--- | :--- |" in readme

    missing = []
    for manifest_path in (REPO_ROOT / "skills").rglob("manifest.yaml"):
        with open(manifest_path, encoding="utf-8") as f:
            manifest = yaml.safe_load(f)
        if isinstance(manifest, dict) and "version" in manifest:
            skill_id = manifest_path.parent.relative_to(REPO_ROOT / "skills").as_posix()
            expected = f"`{manifest['version']}`"
            if expected not in readme:
                missing.append(f"{skill_id}: missing {expected}")

    assert (
        not missing
    ), "Missing manifest versions in docs/skills/README.md:\n" + "\n".join(
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

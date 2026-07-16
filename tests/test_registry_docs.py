"""Repository documentation consistency tests."""

from pathlib import Path
import re

import pytest

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
    """Every manifested skill has a catalog page."""

    docs_root = REPO_ROOT / "docs" / "skills"

    missing = [
        skill
        for skill in sorted(manifested_skills)
        if not (docs_root / f"{Path(skill).name}.md").exists()
    ]

    assert not missing, "Missing catalog pages:\n" + "\n".join(
        f"  - docs/skills/{Path(skill).name}.md ({skill})" for skill in missing
    )


def test_catalog_pages_have_manifests(
    manifested_skills: set[str],
):
    """Every catalog page corresponds to a manifested skill."""

    docs_root = REPO_ROOT / "docs" / "skills"

    expected = {Path(skill).name for skill in manifested_skills}

    actual = {page.stem for page in docs_root.glob("*.md") if page.name != "README.md"}

    orphaned = actual - expected

    assert not orphaned, "Catalog pages without a matching manifest:\n" + "\n".join(
        f"  - docs/skills/{page}.md" for page in sorted(orphaned)
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
    docs_root = REPO_ROOT / "docs" / "skills"

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

    for md_file in docs_root.glob("*.md"):
        if md_file.name == "README.md":
            continue

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

    docs_root = REPO_ROOT / "docs" / "skills"
    missing = []

    for skill_id in sorted(manifested_skills):
        page = docs_root / f"{Path(skill_id).name}.md"
        content = page.read_text(encoding="utf-8")
        extra = registry_id_to_extra(skill_id)
        needle = f"skillware[{extra}]"
        if needle not in content:
            missing.append(f"{page.name}: expected Recommended install with {needle!r}")

    assert not missing, "Missing skill-specific recommended install:\n" + "\n".join(
        f"  - {item}" for item in missing
    )

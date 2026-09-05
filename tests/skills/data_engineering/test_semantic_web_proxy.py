"""Maintainer-layer tests for data_engineering/semantic_web_proxy.

Drives the skill through SkillLoader against a corpus of fixture pages, so the
extraction quality claims on the catalog page stay honest.
"""

from pathlib import Path

import pytest

from skillware.core.loader import SkillLoader

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "semantic_web_proxy"

BOILERPLATE_MARKERS = (
    "ADVERTISEMENT",
    "All rights reserved",
    "Manage preferences",
    "Unsubscribe at any time",
    "Share on Pinterest",
)


@pytest.fixture(scope="module")
def skill():
    bundle = SkillLoader.load_skill("data_engineering/semantic_web_proxy")
    assert bundle["manifest"]["name"] == "data_engineering/semantic_web_proxy"
    return bundle["class"]()


def read_fixture(name: str) -> str:
    return (FIXTURES_DIR / name).read_text(encoding="utf-8")


@pytest.mark.parametrize(
    "fixture_file",
    sorted(FIXTURES_DIR.glob("*.html")),
    ids=lambda path: path.stem,
)
def test_every_fixture_returns_a_serializable_envelope(skill, fixture_file):
    import json

    result = skill.execute({"html_content": fixture_file.read_text(encoding="utf-8")})
    assert result["status"] in {"success", "warning", "error"}
    json.dumps(result)


def test_article_keeps_the_body_and_drops_the_chrome(skill):
    result = skill.execute({"html_content": read_fixture("article.html")})
    payload = result["semantic_payload"]

    assert result["status"] == "success"
    assert "ending a run of three consecutive increases" in payload
    assert "labour market report" in payload
    for marker in ("ADVERTISEMENT", "Subscribe", "Careers", "Cookie preferences"):
        assert marker not in payload


def test_article_metadata_is_recovered(skill):
    result = skill.execute({"html_content": read_fixture("article.html")})
    assert result["metadata"]["title"].startswith("Central bank holds rates steady")
    assert result["metadata"]["author"] == "Priya Raman"
    assert result["metadata"]["date"] == "2026-02-11"


def test_thread_comments_are_opt_in(skill):
    html = read_fixture("thread_with_comments.html")

    without = skill.execute({"html_content": html})["semantic_payload"]
    with_comments = skill.execute({"html_content": html, "include_comments": True})[
        "semantic_payload"
    ]

    assert "worst day of the cycle" in without
    assert "cherry-picking forward" not in without
    assert "cherry-picking forward" in with_comments
    assert len(with_comments) > len(without)


def test_boilerplate_heavy_page_reduces_by_at_least_seventy_percent(skill):
    result = skill.execute({"html_content": read_fixture("boilerplate_heavy.html")})
    payload = result["semantic_payload"]

    assert "chunky aroid mix" in payload
    for marker in BOILERPLATE_MARKERS:
        assert marker not in payload
    assert result["token_savings"]["reduction_pct"] >= 70.0


def test_javascript_shell_is_flagged_not_silently_empty(skill):
    result = skill.execute({"html_content": read_fixture("js_shell.html")})
    assert result["status"] in {"warning", "error"}
    assert "page_likely_requires_javascript" in result["warnings"]

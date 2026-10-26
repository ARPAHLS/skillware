# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Tests for semantic skill discovery, ranking, readiness, and inspect CLI commands."""

import io
import json
from pathlib import Path

import pytest
from rich.console import Console

from skillware.cli import cmd_find
from skillware import (
    SkillMatcher,
    find_skills,
    inspect_skill,
)


def _setup_mock_skills(root: Path) -> None:
    # 1. office/gmail_handler (workflow, core, email)
    s1 = root / "office" / "gmail_handler"
    s1.mkdir(parents=True)
    (s1 / "skill.py").write_text("class GmailSkill: pass\n", encoding="utf-8")
    (s1 / "manifest.yaml").write_text(
        """name: office/gmail_handler
version: 0.2.0
category: office
description: Send and manage emails with attachments via Gmail API.
shape: workflow
tier: core
target:
  - software
tags:
  - email
  - gmail
  - messaging
  - attachments
requirements:
  - google-api-python-client
parameters:
  action:
    type: string
    description: Mail operation to perform.
  attachments:
    type: array
    description: List of files to attach.
""",
        encoding="utf-8",
    )
    (s1 / "instructions.md").write_text(
        "# Gmail Handler Instructions", encoding="utf-8"
    )

    # 2. bio/sequence_ops (atomic, core, dna, rna)
    s2 = root / "bio" / "sequence_ops"
    s2.mkdir(parents=True)
    (s2 / "skill.py").write_text("class SequenceOpsSkill: pass\n", encoding="utf-8")
    (s2 / "manifest.yaml").write_text(
        """name: bio/sequence_ops
version: 0.1.0
category: bio
description: Deterministic sequence operations and alignments.
shape: atomic
tier: core
target:
  - software
tags:
  - bioinformatics
  - genomics
  - dna
  - rna
parameters:
  action:
    type: string
    description: Sequence operation to perform.
  sequence:
    type: string
    description: Input nucleotide or protein sequence.
""",
        encoding="utf-8",
    )


def test_find_skills_scoring_and_ranking(tmp_path):
    _setup_mock_skills(tmp_path)

    results = find_skills("send email with attachments", skills_root=tmp_path)
    assert len(results) > 0
    top = results[0]
    assert top.skill_id == "office/gmail_handler"
    assert top.category == "office"
    assert top.confidence_pct >= 80
    assert "email" in top.matched_terms
    assert "attachments" in top.matched_terms
    assert "messaging" in top.tags


def test_find_skills_category_and_bio_match(tmp_path):
    _setup_mock_skills(tmp_path)

    results = find_skills("align dna sequence genomics", skills_root=tmp_path)
    assert len(results) > 0
    top = results[0]
    assert top.skill_id == "bio/sequence_ops"
    assert top.category == "bio"
    assert top.confidence_pct >= 70
    assert "dna" in top.matched_terms or "genomics" in top.matched_terms


def test_find_skills_min_score_filter(tmp_path):
    _setup_mock_skills(tmp_path)

    results_high = find_skills(
        "unrelated query rocket science",
        skills_root=tmp_path,
        min_score=90,
    )
    assert len(results_high) == 0


def test_find_skills_limit(tmp_path):
    _setup_mock_skills(tmp_path)

    results = find_skills("software", skills_root=tmp_path, limit=1)
    assert len(results) <= 1


def test_find_skills_readiness_evaluation(tmp_path, monkeypatch):
    _setup_mock_skills(tmp_path)

    # Missing dep 'google-api-python-client'
    results = find_skills("email", skills_root=tmp_path)
    top = next(r for r in results if r.skill_id == "office/gmail_handler")
    # google-api-python-client is not in core dependencies
    # and env vars are not set
    assert isinstance(top.is_ready, bool)
    assert isinstance(top.missing_prerequisites, list)
    assert isinstance(top.agent_hint, str)
    assert "office/gmail_handler" in top.agent_hint


def test_inspect_skill_details(tmp_path):
    _setup_mock_skills(tmp_path)

    details = inspect_skill("office/gmail_handler", skills_root=tmp_path)
    assert details["skill_id"] == "office/gmail_handler"
    assert details["version"] == "0.2.0"
    assert details["shape"] == "workflow"
    assert details["tier"] == "core"
    assert "action" in details["parameters"]
    assert "attachments" in details["parameters"]


def test_inspect_skill_unknown_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        inspect_skill("missing/skill", skills_root=tmp_path, raise_if_not_found=True)


def test_cli_find_plain_table(tmp_path):
    _setup_mock_skills(tmp_path)

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    ret = cmd_find(
        "send email",
        skills_root_override=tmp_path,
        console=console,
    )
    assert ret == 0
    out = buf.getvalue()
    assert "office/gmail_handler" in out
    assert "MATCH" in out
    assert "STATUS" in out
    assert "Found 1 skill(s)" in out


def test_cli_find_json_output(tmp_path):
    _setup_mock_skills(tmp_path)

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    ret = cmd_find(
        "send email",
        skills_root_override=tmp_path,
        as_json=True,
        console=console,
    )
    assert ret == 0
    data = json.loads(buf.getvalue().strip())
    assert isinstance(data, list)
    assert len(data) >= 1
    item = data[0]
    assert item["skill_id"] == "office/gmail_handler"
    assert item["confidence_pct"] > 50
    assert "agent_hint" in item
    assert "shape" in item
    assert "tier" in item


def test_cli_find_inspect_flag(tmp_path):
    _setup_mock_skills(tmp_path)

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    ret = cmd_find(
        "send email",
        skills_root_override=tmp_path,
        inspect=True,
        console=console,
    )
    assert ret == 0
    out = buf.getvalue()
    assert "Skill Inspection: office/gmail_handler" in out
    assert "Taxonomy:" in out
    assert "Parameters:" in out


def test_cli_find_no_results(tmp_path):
    _setup_mock_skills(tmp_path)

    buf = io.StringIO()
    console = Console(file=buf, force_terminal=False, width=120)
    ret = cmd_find(
        "quantum entanglement superconductor",
        skills_root_override=tmp_path,
        min_score=95,
        console=console,
    )
    assert ret == 0
    out = buf.getvalue()
    assert "No skills found matching" in out


def test_find_skills_stopwords_and_empty_queries(tmp_path):
    _setup_mock_skills(tmp_path)
    matcher = SkillMatcher(roots=[tmp_path])

    # Empty string and whitespace
    assert matcher.search("") == []
    assert matcher.search("   \t\n  ") == []

    # Pure stopwords (no content tokens)
    assert matcher.search("what is the a of to and") == []
    assert matcher.search("in on by for with") == []

    # Punctuation / symbols only
    assert matcher.search("???---$$$///@#%^&*()") == []


def test_find_skills_fuzzy_typo_resilience(tmp_path):
    _setup_mock_skills(tmp_path)
    matcher = SkillMatcher(roots=[tmp_path])

    # Misspelled compound query
    res = matcher.search("emial attachmnt", limit=3)
    assert len(res) >= 1
    assert res[0].skill_id == "office/gmail_handler"
    assert res[0].confidence_pct >= 75

    # Misspelled genomics
    res_bio = matcher.search("genomcs dna", limit=3)
    assert len(res_bio) >= 1
    assert res_bio[0].skill_id == "bio/sequence_ops"
    assert res_bio[0].confidence_pct >= 65


def test_find_skills_nonsense_no_match(tmp_path):
    _setup_mock_skills(tmp_path)
    matcher = SkillMatcher(roots=[tmp_path])

    # Extremely long nonsense token should not trigger false positive substring matches
    assert matcher.search("supercalifragilisticexpialidocious") == []
    assert matcher.search("x" * 200) == []


def test_find_skills_taxonomy_filters(tmp_path):
    _setup_mock_skills(tmp_path)
    matcher = SkillMatcher(roots=[tmp_path])

    # Filter by shape (mock gmail_handler is workflow, mock sequence_ops is atomic)
    res_workflow = matcher.search("email", shape="workflow")
    assert any(r.skill_id == "office/gmail_handler" for r in res_workflow)
    res_wrong_shape = matcher.search("email", shape="composite")
    assert len(res_wrong_shape) == 0

    res_atomic = matcher.search("dna", shape="atomic")
    assert any(r.skill_id == "bio/sequence_ops" for r in res_atomic)

    # Filter by tier
    res_tier = matcher.search("email", tier="core")
    assert len(res_tier) >= 1
    res_wrong_tier = matcher.search("email", tier="contrib")
    assert len(res_wrong_tier) == 0

    # Filter by target
    res_target = matcher.search("email", target="software")
    assert len(res_target) >= 1
    res_wrong_target = matcher.search("email", target="robotics")
    assert len(res_wrong_target) == 0

    # Filter by tag
    res_tag = matcher.search("email", tag="gmail")
    assert len(res_tag) >= 1
    res_wrong_tag = matcher.search("email", tag="nonexistent_tag")
    assert len(res_wrong_tag) == 0

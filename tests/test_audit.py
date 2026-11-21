"""Tests for SkillContext dispatch audit hook, hash-chained JSONL, redaction, and concurrency."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from skillware import SkillContext, verify_audit_log
from skillware.audit import GENESIS_HASH, REDACTED


def test_zero_overhead_when_audit_disabled() -> None:
    ctx = SkillContext(skills=["optimization/prompt_rewriter"])
    assert ctx._audit is None
    res = ctx.execute(
        "optimization/prompt_rewriter",
        {"raw_text": "Summarize quarterly results", "compression_aggression": "low"},
    )
    assert isinstance(res, dict)


def test_on_dispatch_hook_success_and_error(tmp_path: Path) -> None:
    events: List[Dict[str, Any]] = []
    log_path = tmp_path / "audit" / "events.jsonl"

    ctx = SkillContext(
        skills=["optimization/prompt_rewriter"],
        on_dispatch=events.append,
        audit_log_path=log_path,
    )

    ctx.execute(
        "optimization/prompt_rewriter",
        {"raw_text": "Hello world", "compression_aggression": "low"},
        audit_meta={
            "trace_id": "trace-123",
            "model": "gpt-4o",
            "prompt_tokens": 1000,
            "completion_tokens": 500,
        },
    )

    with pytest.raises(FileNotFoundError):
        ctx.execute("nonexistent/skill", {"x": 1})

    assert len(events) == 2
    ok_ev, err_ev = events
    assert ok_ev["status"] == "ok"
    assert ok_ev["skill_id"] == "optimization/prompt_rewriter"
    assert ok_ev["trace_id"] == "trace-123"
    assert ok_ev["model"] == "gpt-4o"
    assert ok_ev["estimated_cost_usd"] == pytest.approx(0.0075)
    assert ok_ev["prev_hash"] == GENESIS_HASH
    assert len(ok_ev["event_hash"]) == 64

    assert err_ev["status"] == "error"
    assert err_ev["error_type"] == "FileNotFoundError"
    assert err_ev["prev_hash"] == ok_ev["event_hash"]
    assert verify_audit_log(log_path) is True


def test_verify_audit_log_detects_tampering(tmp_path: Path) -> None:
    log_path = tmp_path / "tamper.jsonl"
    ctx = SkillContext(
        skills=["optimization/prompt_rewriter"],
        audit_log_path=log_path,
    )
    for i in range(3):
        ctx.execute(
            "optimization/prompt_rewriter",
            {"raw_text": f"Prompt {i}", "compression_aggression": "low"},
        )
    assert verify_audit_log(log_path) is True

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3

    # Tamper with payload of line 1
    tampered = json.loads(lines[1])
    tampered["status"] = "error"
    tampered_path = tmp_path / "tampered_payload.jsonl"
    tampered_path.write_text(
        "\n".join([lines[0], json.dumps(tampered), lines[2]]) + "\n",
        encoding="utf-8",
    )
    assert verify_audit_log(tampered_path) is False

    # Delete middle line (breaks prev_hash chain)
    truncated_path = tmp_path / "truncated.jsonl"
    truncated_path.write_text("\n".join([lines[0], lines[2]]) + "\n", encoding="utf-8")
    assert verify_audit_log(truncated_path) is False


def test_append_continuity_across_context_restarts(tmp_path: Path) -> None:
    log_path = tmp_path / "restart.jsonl"
    ctx1 = SkillContext(
        skills=["optimization/prompt_rewriter"],
        audit_log_path=log_path,
    )
    ctx1.execute(
        "optimization/prompt_rewriter",
        {"raw_text": "First", "compression_aggression": "low"},
    )

    ctx2 = SkillContext(
        skills=["optimization/prompt_rewriter"],
        audit_log_path=log_path,
    )
    ctx2.execute(
        "optimization/prompt_rewriter",
        {"raw_text": "Second", "compression_aggression": "low"},
    )
    assert verify_audit_log(log_path) is True
    assert len(log_path.read_text(encoding="utf-8").splitlines()) == 2


def test_secret_and_pii_redaction(tmp_path: Path) -> None:
    events: List[Dict[str, Any]] = []
    ctx = SkillContext(
        skills=["optimization/prompt_rewriter"],
        on_dispatch=events.append,
        audit_log_path=tmp_path / "redact.jsonl",
    )
    ctx.execute(
        "optimization/prompt_rewriter",
        {
            "raw_text": "Use sk-proj-abcdefghijklmnopqrstuvwxyz123456 and Bearer my_secret_jwt_token",
            "compression_aggression": "low",
            "api_key": "super-secret-key",
            "nested": {"authorization": "Basic abc", "items": [{"token": "ghp_1234567890abcdef1234"}]},
        },
    )
    args = events[0]["args"]
    assert args["api_key"] == REDACTED
    assert args["nested"]["authorization"] == REDACTED
    assert args["nested"]["items"][0]["token"] == REDACTED
    assert "sk-proj-" not in args["raw_text"]
    assert "my_secret_jwt_token" not in args["raw_text"]


@pytest.mark.asyncio
async def test_concurrent_async_and_threaded_stress(tmp_path: Path) -> None:
    log_path = tmp_path / "stress.jsonl"
    ctx = SkillContext(
        skills=["optimization/prompt_rewriter"],
        audit_log_path=log_path,
    )

    async def _run_async(i: int) -> Any:
        return await ctx.aexecute(
            "optimization/prompt_rewriter",
            {"raw_text": f"Async {i}", "compression_aggression": "low"},
        )

    await asyncio.gather(*[_run_async(i) for i in range(30)])

    def _run_sync(i: int) -> Any:
        return ctx.execute(
            "optimization/prompt_rewriter",
            {"raw_text": f"Sync {i}", "compression_aggression": "low"},
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_run_sync, range(20)))

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 50
    assert verify_audit_log(log_path) is True

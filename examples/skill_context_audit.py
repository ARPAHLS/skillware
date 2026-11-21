"""Minimal example: SkillContext dispatch audit hook & hash-chained JSONL verification."""

from pathlib import Path
import tempfile

from skillware import SkillContext, verify_audit_log


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / "audit.jsonl"
        events = []

        ctx = SkillContext(
            skills=["optimization/prompt_rewriter"],
            on_dispatch=events.append,
            audit_log_path=log_path,
        )

        ctx.execute(
            "optimization/prompt_rewriter",
            {
                "raw_text": "Summarize Q3 revenue with Bearer secret_token_123",
                "compression_aggression": "low",
            },
            audit_meta={
                "trace_id": "demo-trace-001",
                "model": "gpt-4o",
                "prompt_tokens": 500,
                "completion_tokens": 120,
            },
        )

        print("Captured events:", len(events))
        print("Redacted args:", events[0]["args"])
        print("Estimated cost (USD):", events[0]["estimated_cost_usd"])
        print("Hash chain valid:", verify_audit_log(log_path))


if __name__ == "__main__":
    main()

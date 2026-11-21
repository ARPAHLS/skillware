# Dispatch Audit Trail & Telemetry (`SkillContext`)

`SkillContext` provides an optional, zero-lock-in **dispatch audit & telemetry hook** (`on_dispatch` and `audit_log_path`) that records every skill execution at the framework boundary—without relying on the LLM to call an audit skill.

When neither `on_dispatch` nor `audit_log_path` is set, `SkillContext.execute()` and `aexecute()` incur **zero extra I/O, hashing, or redaction overhead**.

---

## Quick Start

```python
from pathlib import Path
from skillware import SkillContext, verify_audit_log

events = []
ctx = SkillContext(
    skills=["optimization/prompt_rewriter"],
    on_dispatch=events.append,
    audit_log_path=Path("logs/skill_audit.jsonl"),
)

result = ctx.execute(
    "optimization/prompt_rewriter",
    {"raw_text": "Summarize quarterly results", "compression_aggression": "low"},
    audit_meta={
        "trace_id": "req-9f8e7d",
        "model": "gpt-4o",
        "prompt_tokens": 1200,
        "completion_tokens": 350,
    },
)

assert verify_audit_log("logs/skill_audit.jsonl") is True
```

See [examples/skill_context_audit.py](../../examples/skill_context_audit.py) for a complete runnable script.

---

## Configuration Options

| Parameter / Helper | Type | Purpose |
| :--- | :--- | :--- |
| `on_dispatch` | `Optional[Callable[[Dict[str, Any]], None]]` | Synchronous callback invoked with each redacted audit event dict. Ideal for OpenTelemetry, SIEMs, or [ARPAHLS Aura](https://github.com/ARPAHLS/aura). |
| `audit_log_path` | `Optional[Union[str, Path]]` | Appends tamper-evident, SHA-256 hash-chained JSONL records to disk (thread-safe; continues the chain across restarts). |
| `audit_meta` | `Optional[Mapping[str, Any]]` | Optional keyword argument on `execute()`, `call()`, `aexecute()`, and `acall()` for `trace_id`, `span_id`, `model`, `prompt_tokens`, and `completion_tokens`. |
| `verify_audit_log(path)` | `bool` | Offline verifier that validates `prev_hash` and `event_hash` across every line in a JSONL audit log. |

---

## What Each Event Captures

Every dispatched call emits a structured dictionary:

- `timestamp`: UTC ISO-8601 timestamp
- `trace_id` / `span_id`: OpenTelemetry-compatible correlation IDs (auto-generated if omitted from `audit_meta`)
- `skill_id`, `action`, `context_mode` (`brief` / `tools_only` / `directives`)
- `status`: `"ok"` or `"error"` (with `error_type` and redacted `error_message` on failure)
- `duration_ms`: High-resolution `time.perf_counter()` execution latency
- `args`: Recursively redacted copy of input parameters
- `model`, `prompt_tokens`, `completion_tokens`, `estimated_cost_usd` (when supplied via `audit_meta`)
- `prev_hash` & `event_hash` (when `audit_log_path` is enabled)

### Automatic Secret & PII Redaction

Before writing to disk or invoking `on_dispatch`, Skillware recursively redacts:
- Sensitive keys (`api_key`, `secret`, `token`, `password`, `private_key`, `authorization`, `bearer`, `credential`, etc.)
- Raw credential patterns (`sk-...`, `ghp_...`, `AIza...`, `AKIA...`, `Bearer ...`, PEM private keys) in both arguments and error messages.

---

## Pragmatic Use Cases

- **Finance & Compliance:** Write immutable, hash-chained JSONL logs (`audit_log_path`) for SOC 2 / KYB / audit-trail requirements and verify them offline with `verify_audit_log()`.
- **Token Economics & FinOps:** Pass `model`, `prompt_tokens`, and `completion_tokens` via `audit_meta` to track per-skill USD spend alongside latency.
- **OpenTelemetry / SIEMs / ARPAHLS Aura:** Pass `on_dispatch=otel_emitter` (or forward into `aura.core.spine.AuditSpine`) without coupling Skillware to any external SDK.


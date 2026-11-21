# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""
Zero-lock-in dispatch audit & telemetry primitives for SkillContext.

Provides:
- Recursive secret & PII redaction for tool arguments and error messages.
- Lightweight, extensible token-cost estimation.
- Thread-safe, tamper-evident SHA-256 hash-chained JSONL logging.
- Offline ``verify_audit_log(path)`` integrity verification.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Union

GENESIS_HASH = "0" * 64
REDACTED = "[REDACTED]"

_SENSITIVE_KEY_TOKENS = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "password",
    "passwd",
    "private_key",
    "authorization",
    "bearer",
    "credential",
    "client_secret",
    "access_key",
)

_SECRET_VALUE_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{12,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{16,}"),
    re.compile(r"AIza[0-9A-Za-z\-_]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9\-._~+/]+=*"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
)

# Approximate USD per 1M tokens: (input_per_1m, output_per_1m).
# Extensible by hosts; unknown models return None.
MODEL_PRICING_PER_1M: Dict[str, tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-7-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.15, 0.60),
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
}


def _is_sensitive_key(key: str) -> bool:
    lowered = key.strip().lower()
    return any(tok in lowered for tok in _SENSITIVE_KEY_TOKENS)


def redact_string(value: str) -> str:
    """Redact raw credential patterns from a string."""
    result = value
    for pattern in _SECRET_VALUE_PATTERNS:
        result = pattern.sub(REDACTED, result)
    return result


def redact_value(value: Any, *, _depth: int = 0) -> Any:
    """Recursively redact sensitive keys and raw credential patterns."""
    if _depth > 32:
        return REDACTED
    if isinstance(value, Mapping):
        out: Dict[str, Any] = {}
        for k, v in value.items():
            key_str = str(k)
            if _is_sensitive_key(key_str):
                out[key_str] = REDACTED
            else:
                out[key_str] = redact_value(v, _depth=_depth + 1)
        return out
    if isinstance(value, (list, tuple)):
        return [redact_value(item, _depth=_depth + 1) for item in value]
    if isinstance(value, str):
        return redact_string(value)
    if isinstance(value, (int, float, bool)) or value is None:
        return value
    return redact_string(str(value))


def estimate_cost_usd(
    model: Optional[str],
    prompt_tokens: Optional[int],
    completion_tokens: Optional[int],
    pricing: Optional[Mapping[str, tuple[float, float]]] = None,
) -> Optional[float]:
    """Estimate USD cost for a model call when token counts and pricing are known."""
    if not model or prompt_tokens is None or completion_tokens is None:
        return None
    table = pricing or MODEL_PRICING_PER_1M
    norm = model.strip().lower()
    rates = table.get(norm)
    if rates is None:
        for prefix, candidate in table.items():
            if norm.startswith(prefix):
                rates = candidate
                break
    if rates is None:
        return None
    in_rate, out_rate = rates
    cost = (prompt_tokens * in_rate + completion_tokens * out_rate) / 1_000_000.0
    return round(cost, 8)


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _compute_event_hash(record_without_hash: Mapping[str, Any]) -> str:
    canonical = _canonical_json(record_without_hash)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def verify_audit_log(path: Union[str, Path]) -> bool:
    """
    Verify the SHA-256 hash chain of a SkillContext audit JSONL file.

    Returns ``True`` if every record's ``prev_hash`` and ``event_hash`` are valid
    (including an empty file). Returns ``False`` if any line is malformed or tampered.
    Raises ``FileNotFoundError`` if ``path`` does not exist.
    """
    log_path = Path(path)
    if not log_path.exists():
        raise FileNotFoundError(f"Audit log not found: {log_path}")

    expected_prev = GENESIS_HASH
    with log_path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                return False
            if not isinstance(record, dict):
                return False
            prev_hash = record.get("prev_hash")
            event_hash = record.get("event_hash")
            if not isinstance(prev_hash, str) or not isinstance(event_hash, str):
                return False
            if not hmac.compare_digest(prev_hash, expected_prev):
                return False
            body = {k: v for k, v in record.items() if k != "event_hash"}
            computed = _compute_event_hash(body)
            if not hmac.compare_digest(event_hash, computed):
                return False
            expected_prev = event_hash
    return True


class AuditDispatcher:
    """Thread-safe audit event builder, optional hash-chained JSONL writer, and callback."""

    def __init__(
        self,
        *,
        on_dispatch: Optional[Callable[[Dict[str, Any]], None]] = None,
        audit_log_path: Optional[Union[str, Path]] = None,
    ) -> None:
        self._on_dispatch = on_dispatch
        self._log_path = Path(audit_log_path) if audit_log_path is not None else None
        self._lock = threading.Lock()
        self._prev_hash = self._load_tail_hash() if self._log_path is not None else GENESIS_HASH

    def _load_tail_hash(self) -> str:
        assert self._log_path is not None
        if not self._log_path.exists():
            return GENESIS_HASH
        last_hash = GENESIS_HASH
        with self._log_path.open("r", encoding="utf-8") as fh:
            for raw_line in fh:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    break
                if isinstance(record, dict) and isinstance(record.get("event_hash"), str):
                    last_hash = record["event_hash"]
        return last_hash

    def emit(
        self,
        *,
        skill_id: str,
        params: Mapping[str, Any],
        status: str,
        duration_ms: float,
        context_mode: str,
        error: Optional[BaseException] = None,
        audit_meta: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        meta = dict(audit_meta) if audit_meta else {}
        action = str(params.get("action") or meta.get("action") or "execute")
        event: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": str(meta.get("trace_id") or uuid.uuid4().hex),
            "span_id": str(meta.get("span_id") or uuid.uuid4().hex[:16]),
            "skill_id": skill_id,
            "action": action,
            "status": status,
            "duration_ms": round(duration_ms, 3),
            "context_mode": context_mode,
            "args": redact_value(dict(params)),
        }
        if error is not None:
            event["error_type"] = type(error).__name__
            event["error_message"] = redact_string(str(error))

        model = meta.get("model")
        prompt_tokens = meta.get("prompt_tokens")
        completion_tokens = meta.get("completion_tokens")
        if model is not None:
            event["model"] = str(model)
        if prompt_tokens is not None:
            event["prompt_tokens"] = int(prompt_tokens)
        if completion_tokens is not None:
            event["completion_tokens"] = int(completion_tokens)
        cost = estimate_cost_usd(
            str(model) if model is not None else None,
            int(prompt_tokens) if prompt_tokens is not None else None,
            int(completion_tokens) if completion_tokens is not None else None,
        )
        if cost is not None:
            event["estimated_cost_usd"] = cost

        with self._lock:
            if self._log_path is not None:
                self._log_path.parent.mkdir(parents=True, exist_ok=True)
                chained = dict(event)
                chained["prev_hash"] = self._prev_hash
                event_hash = _compute_event_hash(chained)
                chained["event_hash"] = event_hash
                with self._log_path.open("a", encoding="utf-8") as fh:
                    fh.write(_canonical_json(chained) + "\n")
                self._prev_hash = event_hash
                event_to_emit = chained
            else:
                event_to_emit = event

        if self._on_dispatch is not None:
            self._on_dispatch(dict(event_to_emit))
        return event_to_emit

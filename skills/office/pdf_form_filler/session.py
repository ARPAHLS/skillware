# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""File-backed conversational interview session state machine for office/pdf_form_filler."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

DEFAULT_SESSION_TTL_SECONDS = 48 * 3600  # 48 hours
_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{4,80}$")


def default_sessions_dir() -> Path:
    """Return OS-appropriate user session directory without reading os.environ directly."""
    if os.name == "nt":
        return Path.home() / "AppData" / "Roaming" / "skillware" / "pdf_sessions"
    return Path.home() / ".config" / "skillware" / "pdf_sessions"


def resolve_sessions_dir(
    *,
    session_dir: Optional[str] = None,
    env_sessions_dir: Optional[str] = None,
) -> Path:
    if session_dir and str(session_dir).strip():
        return Path(str(session_dir).strip()).expanduser()
    if env_sessions_dir and str(env_sessions_dir).strip():
        return Path(str(env_sessions_dir).strip()).expanduser()
    return default_sessions_dir()


def _validate_session_id(session_id: str) -> str:
    sid = str(session_id or "").strip()
    if not _SESSION_ID_RE.match(sid):
        raise ValueError(
            f"Invalid session_id '{session_id}'. Expected 4-80 alphanumeric, '_' or '-' characters."
        )
    return sid


def _atomic_write_json(target_path: Path, payload: Dict[str, Any]) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target_path.parent / f"{target_path.name}.{uuid4().hex[:8]}.tmp"
    try:
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp_path, target_path)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def cleanup_expired_sessions(sessions_dir: Path) -> int:
    """Remove expired session JSON files lazily; returns count removed."""
    if not sessions_dir.is_dir():
        return 0
    now = datetime.now(timezone.utc)
    removed = 0
    for path in sessions_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            exp_raw = data.get("expires_at")
            if exp_raw:
                exp_dt = datetime.fromisoformat(str(exp_raw).replace("Z", "+00:00"))
                if now > exp_dt:
                    path.unlink()
                    removed += 1
        except Exception:
            continue
    return removed


def build_session_fields_from_schema(schema: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten section-chunked schema fields into ordered session field descriptors."""
    out: List[Dict[str, Any]] = []
    for sec in schema.get("sections") or []:
        if not isinstance(sec, dict):
            continue
        sec_id = str(sec.get("id") or "")
        for f in sec.get("fields") or []:
            if not isinstance(f, dict):
                continue
            fid = str(f.get("id") or "")
            if not fid:
                continue
            out.append(
                {
                    "id": fid,
                    "pdf_field_name": str(f.get("pdf_field_name") or fid),
                    "section_id": sec_id,
                    "field_type": str(f.get("field_type") or "text"),
                    "label": str(f.get("label") or fid),
                    "required": bool(f.get("required", False)),
                    "sensitive": bool(f.get("sensitive", False)),
                    "signature_mode": f.get("signature_mode"),
                    "date_format": f.get("date_format"),
                    "options": f.get("options"),
                }
            )
    return out


def create_session_record(
    *,
    template_id: Optional[str],
    pdf_path: str,
    schema_path: Optional[str],
    fields_meta: List[Dict[str, Any]],
    sections_index: List[Dict[str, Any]],
    sessions_dir: Path,
    ttl_seconds: int = DEFAULT_SESSION_TTL_SECONDS,
) -> Dict[str, Any]:
    """Create and atomically persist a new interview session."""
    cleanup_expired_sessions(sessions_dir)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=max(60, int(ttl_seconds)))
    prefix = (
        re.sub(r"[^a-zA-Z0-9_]+", "_", (template_id or "custom"))
        .strip("_")
        .lower()[:24]
    )
    session_id = f"sess_{prefix}_{uuid4().hex[:8]}"

    field_states: Dict[str, Dict[str, Any]] = {
        f["id"]: {"status": "empty"} for f in fields_meta
    }

    record: Dict[str, Any] = {
        "session_id": session_id,
        "template_id": template_id,
        "pdf_path": pdf_path,
        "schema_path": schema_path,
        "created_at": now.isoformat().replace("+00:00", "Z"),
        "updated_at": now.isoformat().replace("+00:00", "Z"),
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
        "finalized": False,
        "output_path": None,
        "sections_index": sections_index,
        "fields_meta": fields_meta,
        "field_states": field_states,
    }
    _atomic_write_json(sessions_dir / f"{session_id}.json", record)
    return record


def load_session_record(
    session_id: str,
    sessions_dir: Path,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Load session record; returns (record, error_response)."""
    try:
        sid = _validate_session_id(session_id)
    except ValueError as exc:
        return None, {
            "status": "error",
            "error_code": "invalid_session_id",
            "message": str(exc),
        }

    path = sessions_dir / f"{sid}.json"
    if not path.is_file():
        return None, {
            "status": "error",
            "error_code": "session_not_found",
            "message": f"Session '{sid}' not found.",
        }

    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, {
            "status": "error",
            "error_code": "session_corrupted",
            "message": f"Failed to read session '{sid}': {exc}",
        }

    exp_raw = record.get("expires_at")
    if exp_raw:
        exp_dt = datetime.fromisoformat(str(exp_raw).replace("Z", "+00:00"))
        if datetime.now(timezone.utc) > exp_dt:
            return None, {
                "status": "error",
                "error_code": "session_expired",
                "message": f"Session '{sid}' has expired. Please start a new session with session_init.",
            }

    return record, None


def save_session_record(record: Dict[str, Any], sessions_dir: Path) -> None:
    record["updated_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    sid = _validate_session_id(str(record["session_id"]))
    _atomic_write_json(sessions_dir / f"{sid}.json", record)


def compute_session_progress(record: Dict[str, Any]) -> Dict[str, Any]:
    """Compute progress counts, pending_revisions, and next_recommended_fields."""
    meta_list = record.get("fields_meta") or []
    states = record.get("field_states") or {}

    filled_count = 0
    skipped_count = 0
    to_revise_count = 0
    empty_count = 0
    remaining_required_count = 0
    pending_revisions: List[Dict[str, Any]] = []
    empty_required: List[Dict[str, Any]] = []
    empty_optional: List[Dict[str, Any]] = []

    for f in meta_list:
        fid = f["id"]
        st = states.get(fid, {}).get("status", "empty")
        if st == "filled":
            filled_count += 1
        elif st == "skipped":
            skipped_count += 1
        elif st == "to_revise":
            to_revise_count += 1
            pending_revisions.append(
                {
                    "field_id": fid,
                    "label": f.get("label", fid),
                    "note": states.get(fid, {}).get("note"),
                }
            )
            if f.get("required"):
                remaining_required_count += 1
        else:
            empty_count += 1
            entry = {
                "field_id": fid,
                "label": f.get("label", fid),
                "required": bool(f.get("required", False)),
                "section_id": f.get("section_id"),
            }
            if f.get("required") and f.get("signature_mode") != "auto_date":
                remaining_required_count += 1
                empty_required.append(entry)
            else:
                empty_optional.append(entry)

    next_recommended = (empty_required + empty_optional)[:5]
    return {
        "progress": {
            "total_fields": len(meta_list),
            "filled_count": filled_count,
            "skipped_count": skipped_count,
            "to_revise_count": to_revise_count,
            "empty_count": empty_count,
            "remaining_required_count": remaining_required_count,
        },
        "pending_revisions": pending_revisions,
        "next_recommended_fields": next_recommended,
    }

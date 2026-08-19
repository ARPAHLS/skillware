"""MIME attachment helpers for IMAP read and SMTP send."""

from __future__ import annotations

import email
import mimetypes
from email.message import EmailMessage
from typing import Any, Dict, List, Sequence, Tuple

try:
    from file_ref import read_bytes_from_ref
except ImportError:
    from .file_ref import read_bytes_from_ref


def list_attachment_metadata(msg: email.message.Message) -> List[Dict[str, Any]]:
    """Return attachment metadata for one parsed RFC822 message."""
    items: List[Dict[str, Any]] = []
    for part_index, part in enumerate(msg.walk()):
        if part.get_content_maintype() == "multipart":
            continue
        disposition = (part.get("Content-Disposition") or "").lower()
        filename = part.get_filename()
        content_type = (part.get_content_type() or "application/octet-stream").lower()
        is_attachment = "attachment" in disposition
        is_inline_file = bool(filename) and content_type not in (
            "text/plain",
            "text/html",
        )
        if not is_attachment and not is_inline_file:
            continue
        payload = part.get_payload(decode=True)
        size_bytes = len(payload) if isinstance(payload, (bytes, bytearray)) else 0
        items.append(
            {
                "part_index": part_index,
                "filename": filename or f"attachment-{len(items) + 1}",
                "content_type": content_type,
                "size_bytes": size_bytes,
            }
        )
    return items


def extract_attachment_payload(
    msg: email.message.Message,
    part_index: int,
) -> Tuple[bytes, str, str]:
    """Return ``(payload, filename, content_type)`` for one MIME part index."""
    for idx, part in enumerate(msg.walk()):
        if idx != part_index:
            continue
        disposition = (part.get("Content-Disposition") or "").lower()
        filename = part.get_filename()
        content_type = (part.get_content_type() or "application/octet-stream").lower()
        is_attachment = "attachment" in disposition
        is_inline_file = bool(filename) and content_type not in (
            "text/plain",
            "text/html",
        )
        if not is_attachment and not is_inline_file:
            raise ValueError(f"Part {part_index} is not an attachment.")
        payload = part.get_payload(decode=True)
        if not isinstance(payload, (bytes, bytearray)):
            raise ValueError(f"Attachment part {part_index} has no decodable payload.")
        name = filename or f"attachment-{part_index}"
        return bytes(payload), name, content_type
    raise ValueError(f"Attachment part {part_index} not found.")


def normalize_attachment_specs(raw: Any) -> List[Dict[str, str]]:
    """Normalize ``attachments`` action parameter to a list of path specs."""
    if raw is None:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    if isinstance(raw, str):
        raw = [{"path": raw}]
    if not isinstance(raw, list):
        raise ValueError("attachments must be a list of path objects.")

    specs: List[Dict[str, str]] = []
    for item in raw:
        if isinstance(item, str):
            specs.append({"path": item.strip()})
            continue
        if not isinstance(item, dict):
            raise ValueError("Each attachment entry must be a string path or object.")
        path = (item.get("path") or item.get("file") or "").strip()
        if not path:
            raise ValueError("Each attachment requires a path.")
        spec: Dict[str, str] = {"path": path}
        if item.get("filename"):
            spec["filename"] = str(item["filename"]).strip()
        if item.get("content_type"):
            spec["content_type"] = str(item["content_type"]).strip()
        specs.append(spec)
    return specs


def load_outbound_attachments(
    specs: Sequence[Dict[str, str]],
    *,
    max_bytes: int,
    max_count: int,
) -> List[Dict[str, Any]]:
    """Read attachment bytes from flexible path refs."""
    if len(specs) > max_count:
        raise ValueError(f"Attachment count {len(specs)} exceeds max ({max_count}).")

    loaded: List[Dict[str, Any]] = []
    for spec in specs:
        data, default_name, default_type = read_bytes_from_ref(
            spec["path"],
            max_bytes=max_bytes,
        )
        filename = spec.get("filename") or default_name
        content_type = spec.get("content_type") or default_type
        if not content_type:
            guessed, _ = mimetypes.guess_type(filename)
            content_type = guessed or "application/octet-stream"
        loaded.append(
            {
                "path": spec["path"],
                "filename": filename,
                "content_type": content_type,
                "size_bytes": len(data),
                "data": data,
            }
        )
    return loaded


def attach_files_to_message(
    msg: EmailMessage,
    attachments: Sequence[Dict[str, Any]],
) -> None:
    """Add binary attachments to an ``EmailMessage`` (multipart/mixed when needed)."""
    for item in attachments:
        msg.add_attachment(
            item["data"],
            maintype=(
                item["content_type"].split("/", 1)[0]
                if "/" in item["content_type"]
                else "application"
            ),
            subtype=(
                item["content_type"].split("/", 1)[1]
                if "/" in item["content_type"]
                else "octet-stream"
            ),
            filename=item["filename"],
        )

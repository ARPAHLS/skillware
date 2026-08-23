"""Read/write file bytes from local paths, URIs, HTTP(S), and optional cloud schemes."""

from __future__ import annotations

import mimetypes
import os
import re
from pathlib import Path
from typing import Tuple
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

_PATH_TRAVERSAL_RE = re.compile(r"(^|[\\/])\.\.([\\/]|$)")
_CLOUD_SCHEMES = frozenset({"s3", "gs", "gcs", "az", "abfs"})


def _normalize_local_path(ref: str) -> Path:
    text = (ref or "").strip()
    if not text:
        raise ValueError("Empty file reference.")

    # Windows drive paths (C:\...) are not URIs — urlparse misreads them as scheme "c".
    if re.match(r"^[A-Za-z]:[\\/]", text) or text.startswith("\\\\"):
        path = Path(os.path.expanduser(text))
    else:
        parsed = urlparse(text)
        if parsed.scheme == "file":
            raw = unquote(parsed.path or "")
            if (
                os.name == "nt"
                and raw.startswith("/")
                and len(raw) > 2
                and raw[2] == ":"
            ):
                raw = raw[1:]
            path = Path(os.path.expanduser(raw))
        elif parsed.scheme and parsed.scheme.lower() in _CLOUD_SCHEMES:
            return Path(text)  # handled separately via fsspec
        elif parsed.scheme and parsed.scheme.lower() not in ("", "file"):
            raise ValueError(f"Unsupported URI scheme for local path: {parsed.scheme}")
        else:
            path = Path(os.path.expanduser(text))

    if _PATH_TRAVERSAL_RE.search(str(path)):
        raise ValueError("Path traversal segments are not allowed.")
    return path


def _guess_content_type(
    filename: str, fallback: str = "application/octet-stream"
) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or fallback


def _read_via_fsspec(ref: str, max_bytes: int) -> Tuple[bytes, str, str]:
    try:
        import fsspec  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ValueError(
            "Cloud bucket URLs (s3://, gs://, etc.) require optional fsspec. "
            "Install fsspec, use an HTTPS presigned URL, or a mounted local path."
        ) from exc

    parsed = urlparse(ref)
    filename = Path(unquote(parsed.path or "")).name or "attachment"
    with fsspec.open(ref, "rb") as handle:
        data = handle.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"File exceeds max size ({max_bytes} bytes): {ref!r}")
    return data, filename, _guess_content_type(filename)


def read_bytes_from_ref(ref: str, *, max_bytes: int) -> Tuple[bytes, str, str]:
    """
    Read bytes from a file reference.

    Supports local paths, ``file://``, ``http(s)://``, and cloud URIs when
    ``fsspec`` is installed (``s3://``, ``gs://``, ``gcs://``, ``abfs://``).

    Returns ``(data, filename, content_type)``.
    """
    text = (ref or "").strip()
    if not text:
        raise ValueError("Empty file reference.")

    if re.match(r"^[A-Za-z]:[\\/]", text) or text.startswith("\\\\"):
        path = _normalize_local_path(text)
        if not path.is_file():
            raise FileNotFoundError(f"File not found: {text}")
        size = path.stat().st_size
        if size > max_bytes:
            raise ValueError(f"File exceeds max size ({max_bytes} bytes): {text!r}")
        data = path.read_bytes()
        return data, path.name, _guess_content_type(path.name)

    parsed = urlparse(text)
    scheme = (parsed.scheme or "").lower()

    if scheme in ("http", "https"):
        request = Request(text, method="GET")
        with urlopen(request, timeout=120) as response:
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ValueError(f"File exceeds max size ({max_bytes} bytes): {text!r}")
            filename = Path(unquote(parsed.path or "")).name or "download"
            content_type = response.headers.get_content_type() or _guess_content_type(
                filename
            )
            return data, filename, content_type

    if scheme in _CLOUD_SCHEMES:
        return _read_via_fsspec(text, max_bytes)

    path = _normalize_local_path(text)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {text}")
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError(f"File exceeds max size ({max_bytes} bytes): {text!r}")
    data = path.read_bytes()
    return data, path.name, _guess_content_type(path.name)


def write_bytes_to_ref(ref: str, data: bytes, *, max_bytes: int) -> str:
    """
    Write bytes to a local path or ``file://`` URI.

    Cloud write URIs require optional ``fsspec``. Returns the resolved path string.
    """
    if len(data) > max_bytes:
        raise ValueError(f"Payload exceeds max size ({max_bytes} bytes).")

    text = (ref or "").strip()
    if not text:
        raise ValueError("Empty output path.")

    if re.match(r"^[A-Za-z]:[\\/]", text) or text.startswith("\\\\"):
        path = _normalize_local_path(text)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return str(path.resolve())

    parsed = urlparse(text)
    scheme = (parsed.scheme or "").lower()

    if scheme in _CLOUD_SCHEMES:
        try:
            import fsspec  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ValueError(
                "Cloud bucket write URLs require optional fsspec. "
                "Use a mounted local path or install fsspec."
            ) from exc
        with fsspec.open(text, "wb") as handle:
            handle.write(data)
        return text

    if scheme in ("http", "https"):
        raise ValueError("HTTP(S) URLs cannot be used as attachment download targets.")

    path = _normalize_local_path(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return str(path.resolve())

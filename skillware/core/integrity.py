# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Deterministic fingerprints for skill bundles and lockfile verification.

``skillware doctor --verify`` hashes a bundle's files and compares the result to a
committed lockfile, so a CI job can tell whether the checked-out skills are the ones
that were reviewed. Hashing is byte-based and path-independent: the same bundle
produces the same digest on any machine, in any directory.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

BUNDLE_CORE_FILES: Tuple[str, ...] = (
    "manifest.yaml",
    "skill.py",
    "instructions.md",
    "card.json",
)
LOCKFILE_SCHEMA = "skillware-lockfile/1"

STATUS_COMPUTED = "computed"
STATUS_MATCH = "match"
STATUS_DRIFT = "drift"
STATUS_NEW = "new"
STATUS_MISSING = "missing"

_IGNORED_DIR_NAMES = frozenset({"__pycache__"})
_IGNORED_FILE_NAMES = frozenset({".DS_Store"})
_IGNORED_FILE_SUFFIXES = (".pyc", ".pyo")

DIGEST_PREFIX = "sha256:"


@dataclass(frozen=True)
class BundleFingerprint:
    """Digest of one bundle, plus the per-file digests it was built from."""

    bundle_id: str
    digest: str
    files: Mapping[str, str]
    missing: Tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        """Return True when every core bundle file is present."""
        return not self.missing

    def lockfile_entry(self) -> Dict[str, Any]:
        """Return the lockfile representation of this bundle."""
        return {"digest": self.digest, "files": dict(self.files)}


@dataclass(frozen=True)
class BundleVerdict:
    """Comparison result for a single bundle."""

    bundle_id: str
    status: str
    digest: str
    lockfile_digest: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        """Return a JSON-ready representation of the verdict."""
        payload: Dict[str, Any] = {
            "id": self.bundle_id,
            "status": self.status,
            "digest": self.digest,
        }
        if self.lockfile_digest is not None:
            payload["lockfile_digest"] = self.lockfile_digest
        return payload


@dataclass(frozen=True)
class VerifyReport:
    """Aggregate of every bundle verdict produced by one ``doctor --verify`` run."""

    lockfile: Optional[str]
    written: bool
    verdicts: Tuple[BundleVerdict, ...]

    def count(self, status: str) -> int:
        """Return the number of bundles with the given status."""
        return sum(1 for verdict in self.verdicts if verdict.status == status)

    @property
    def matched(self) -> int:
        """Bundles whose digest equals the lockfile entry."""
        return self.count(STATUS_MATCH)

    @property
    def drifted(self) -> int:
        """Bundles whose digest differs from the lockfile entry."""
        return self.count(STATUS_DRIFT)

    @property
    def new(self) -> int:
        """Bundles missing from the lockfile entirely."""
        return self.count(STATUS_NEW)

    @property
    def missing(self) -> int:
        """Bundles with at least one missing core file."""
        return self.count(STATUS_MISSING)

    @property
    def ok(self) -> bool:
        """Return True when nothing drifted and nothing is missing."""
        return self.drifted == 0 and self.missing == 0 and self.new == 0

    def as_dict(self) -> Dict[str, Any]:
        """Return a JSON-ready representation of the whole report."""
        return {
            "enabled": True,
            "lockfile": self.lockfile,
            "written": self.written,
            "matched": self.matched,
            "drifted": self.drifted,
            "new": self.new,
            "missing": self.missing,
            "ok": self.ok,
            "bundles": [verdict.as_dict() for verdict in self.verdicts],
        }


def hash_file(path: Path) -> str:
    """Return the ``sha256:`` digest of a file's raw bytes."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"{DIGEST_PREFIX}{digest.hexdigest()}"


def _iter_bundle_files(bundle_dir: Path, all_files: bool) -> List[Path]:
    if not all_files:
        return [
            bundle_dir / name
            for name in BUNDLE_CORE_FILES
            if (bundle_dir / name).is_file()
        ]

    candidates: List[Path] = []
    for path in bundle_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(bundle_dir)
        if any(part in _IGNORED_DIR_NAMES for part in relative.parts[:-1]):
            continue
        if path.name in _IGNORED_FILE_NAMES or path.suffix in _IGNORED_FILE_SUFFIXES:
            continue
        candidates.append(path)
    return candidates


def bundle_relative_paths(bundle_dir: Path, all_files: bool = False) -> List[str]:
    """Return the bundle-relative POSIX paths that take part in the digest."""
    files = _iter_bundle_files(bundle_dir, all_files)
    return sorted(path.relative_to(bundle_dir).as_posix() for path in files)


def compute_bundle_fingerprint(
    bundle_id: str,
    bundle_dir: Path,
    all_files: bool = False,
) -> BundleFingerprint:
    """Hash one bundle.

    The bundle digest is the SHA-256 of ``"<relative path>\\0<file digest>\\n"`` for every
    participating file, in path order, so it does not depend on the absolute location of
    the bundle or its timestamps.
    """
    files: Dict[str, str] = {}
    for relative in bundle_relative_paths(bundle_dir, all_files=all_files):
        files[relative] = hash_file(bundle_dir / relative)

    digest = hashlib.sha256()
    for relative in files:
        digest.update(f"{relative}\0{files[relative]}\n".encode("utf-8"))

    missing = tuple(name for name in BUNDLE_CORE_FILES if name not in files)
    return BundleFingerprint(
        bundle_id=bundle_id,
        digest=f"{DIGEST_PREFIX}{digest.hexdigest()}",
        files=files,
        missing=missing,
    )


def compute_fingerprints(
    bundle_dirs: Mapping[str, Path],
    all_files: bool = False,
) -> Dict[str, BundleFingerprint]:
    """Hash every bundle in ``bundle_dirs`` (bundle id -> directory)."""
    return {
        bundle_id: compute_bundle_fingerprint(
            bundle_id, bundle_dir, all_files=all_files
        )
        for bundle_id, bundle_dir in bundle_dirs.items()
    }


def load_lockfile(path: Path) -> Optional[Dict[str, Any]]:
    """Read a lockfile, or return None when it does not exist yet."""
    if not path.is_file():
        return None
    with open(path, encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Lockfile {path} is not a JSON object")
    schema = payload.get("schema")
    if schema != LOCKFILE_SCHEMA:
        raise ValueError(
            f"Lockfile {path} has unsupported schema {schema!r}; expected {LOCKFILE_SCHEMA!r}"
        )
    bundles = payload.get("bundles")
    if not isinstance(bundles, dict):
        raise ValueError(f"Lockfile {path} is missing a 'bundles' object")
    return payload


def write_lockfile(
    path: Path,
    fingerprints: Mapping[str, BundleFingerprint],
    generated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Write a lockfile for ``fingerprints`` and return the payload that was written."""
    payload: Dict[str, Any] = {
        "schema": LOCKFILE_SCHEMA,
        "generated_at": generated_at
        or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "bundles": {
            bundle_id: fingerprint.lockfile_entry()
            for bundle_id, fingerprint in sorted(fingerprints.items())
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return payload


def compare_fingerprints(
    fingerprints: Mapping[str, BundleFingerprint],
    lockfile: Optional[Mapping[str, Any]],
) -> Tuple[BundleVerdict, ...]:
    """Compare computed fingerprints against a loaded lockfile."""
    locked: Mapping[str, Any] = {}
    if lockfile:
        locked = lockfile.get("bundles") or {}

    verdicts: List[BundleVerdict] = []
    for bundle_id, fingerprint in sorted(fingerprints.items()):
        entry = locked.get(bundle_id) if isinstance(locked, Mapping) else None
        locked_digest = entry.get("digest") if isinstance(entry, Mapping) else None

        if not fingerprint.complete:
            verdicts.append(
                BundleVerdict(
                    bundle_id=bundle_id,
                    status=STATUS_MISSING,
                    digest=fingerprint.digest,
                    lockfile_digest=locked_digest,
                )
            )
        elif lockfile is None:
            verdicts.append(
                BundleVerdict(
                    bundle_id=bundle_id,
                    status=STATUS_COMPUTED,
                    digest=fingerprint.digest,
                )
            )
        elif locked_digest is None:
            verdicts.append(
                BundleVerdict(
                    bundle_id=bundle_id, status=STATUS_NEW, digest=fingerprint.digest
                )
            )
        elif locked_digest == fingerprint.digest:
            verdicts.append(
                BundleVerdict(
                    bundle_id=bundle_id,
                    status=STATUS_MATCH,
                    digest=fingerprint.digest,
                    lockfile_digest=locked_digest,
                )
            )
        else:
            verdicts.append(
                BundleVerdict(
                    bundle_id=bundle_id,
                    status=STATUS_DRIFT,
                    digest=fingerprint.digest,
                    lockfile_digest=locked_digest,
                )
            )
    return tuple(verdicts)


def verify_bundle_fingerprints(
    bundle_dirs: Mapping[str, Path],
    lockfile_path: Optional[Path],
    all_files: bool = False,
    update: bool = False,
) -> VerifyReport:
    """Hash the bundles and compare them against ``lockfile_path``.

    Without a lockfile path this only reports digests. With one, a missing file or
    ``update=True`` writes the lockfile; otherwise the existing lockfile is compared
    and drift is reported.
    """
    fingerprints = compute_fingerprints(bundle_dirs, all_files=all_files)

    if lockfile_path is None:
        return VerifyReport(
            lockfile=None,
            written=False,
            verdicts=compare_fingerprints(fingerprints, None),
        )

    existing = load_lockfile(lockfile_path)
    if existing is None or update:
        write_lockfile(lockfile_path, fingerprints)
        return VerifyReport(
            lockfile=str(lockfile_path),
            written=True,
            verdicts=compare_fingerprints(fingerprints, None),
        )

    return VerifyReport(
        lockfile=str(lockfile_path),
        written=False,
        verdicts=compare_fingerprints(fingerprints, existing),
    )


def summarize_verdicts(verdicts: Sequence[BundleVerdict]) -> Dict[str, int]:
    """Return a status -> count mapping, for compact console summaries."""
    counts: Dict[str, int] = {}
    for verdict in verdicts:
        counts[verdict.status] = counts.get(verdict.status, 0) + 1
    return counts

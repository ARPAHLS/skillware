#!/usr/bin/env python3
"""Sync GitHub repository labels from .github/labels.json."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

LABELS_FILE = Path(__file__).resolve().parent.parent / "labels.json"
API_ROOT = "https://api.github.com"
GITHUB_LABEL_DESCRIPTION_MAX = 100
# Labels removed from labels.json — deleted on sync so GitHub UI does not keep stale pills.
DEPRECATED_LABELS = ["core-framework", "creative", "office"]


def _request(
    method: str,
    url: str,
    token: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    data = None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed ({exc.code}): {detail}") from exc


def _load_labels() -> list[dict[str, str]]:
    raw = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("labels.json must be a JSON array")
    labels: list[dict[str, str]] = []
    seen: set[str] = set()
    for entry in raw:
        name = entry.get("name", "").strip()
        color = entry.get("color", "").strip().lstrip("#").upper()
        description = entry.get("description", "").strip()
        if not name:
            raise ValueError("Each label entry requires a name")
        if len(description) > GITHUB_LABEL_DESCRIPTION_MAX:
            raise ValueError(
                f"Label {name!r} description is {len(description)} chars; "
                f"GitHub maximum is {GITHUB_LABEL_DESCRIPTION_MAX}"
            )
        if len(color) != 6 or any(c not in "0123456789ABCDEF" for c in color):
            raise ValueError(f"Label {name!r} has invalid color {color!r}")
        if name in seen:
            raise ValueError(f"Duplicate label name: {name!r}")
        seen.add(name)
        labels.append({"name": name, "color": color, "description": description})
    return labels


def sync_labels(dry_run: bool = False) -> int:
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    token = os.environ.get("GITHUB_TOKEN", "").strip()

    labels = _load_labels()
    if dry_run:
        for label in labels:
            print(f"[dry-run] UPSERT {label['name']} #{label['color']}")
        print(f"Label validation OK ({len(labels)} labels in labels.json).")
        return 0

    if not repo:
        print("GITHUB_REPOSITORY is not set", file=sys.stderr)
        return 1
    if not token:
        print("GITHUB_TOKEN is not set", file=sys.stderr)
        return 1

    created = updated = unchanged = 0

    for label in labels:
        name = label["name"]
        encoded = urllib.parse.quote(name, safe="")
        url = f"{API_ROOT}/repos/{repo}/labels/{encoded}"
        body = {"color": label["color"], "description": label["description"]}
        existing = _request("GET", url, token)

        if existing is None:
            create_url = f"{API_ROOT}/repos/{repo}/labels"
            create_body = {"name": name, **body}
            _request("POST", create_url, token, create_body)
            print(f"CREATE {name} #{label['color']}")
            created += 1
            continue

        needs_update = (
            existing.get("color", "").upper() != label["color"]
            or existing.get("description", "") != label["description"]
        )
        if needs_update:
            _request("PATCH", url, token, body)
            print(f"UPDATE {name} #{label['color']}")
            updated += 1
        else:
            unchanged += 1

    deleted = 0
    for name in DEPRECATED_LABELS:
        encoded = urllib.parse.quote(name, safe="")
        url = f"{API_ROOT}/repos/{repo}/labels/{encoded}"
        if _request("GET", url, token) is not None:
            _request("DELETE", url, token)
            print(f"DELETE {name} (deprecated)")
            deleted += 1

    print(
        f"Label sync complete: {created} created, {updated} updated, "
        f"{unchanged} unchanged, {deleted} deleted "
        f"({len(labels)} defined in labels.json)."
    )
    return 0


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    raise SystemExit(sync_labels(dry_run=dry))

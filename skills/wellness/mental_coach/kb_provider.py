"""Public corpus retrieval for wellness/mental_coach."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, List, Sequence

_CORPUS_PATH = os.path.join(os.path.dirname(__file__), "kb", "corpus.json")


@dataclass(frozen=True)
class KBChunk:
    chunk_id: str
    source_doc: str
    text: str
    section: str = ""
    jurisdiction: str = "GLOBAL"
    session_modes: tuple = ("coaching", "information")
    suppress_in_crisis: bool = True


@lru_cache(maxsize=1)
def _load_corpus_chunks() -> List[Dict[str, Any]]:
    with open(_CORPUS_PATH, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    chunks = payload.get("chunks", [])
    return [c for c in chunks if isinstance(c, dict)]


class DefaultCorpusProvider:
    """Keyword router over the bundled public corpus."""

    def __init__(self, corpus_path: str = _CORPUS_PATH) -> None:
        self.corpus_path = corpus_path

    def retrieve(
        self,
        query: str,
        *,
        jurisdiction: str = "GLOBAL",
        session_mode: str = "coaching",
        max_chunks: int = 8,
        suppress_in_crisis: bool = False,
    ) -> Sequence[KBChunk]:
        normalized = re.sub(r"\s+", " ", (query or "").lower()).strip()
        words = [w for w in re.split(r"[^a-z0-9]+", normalized) if len(w) > 3]
        jurisdiction = (jurisdiction or "GLOBAL").upper()
        scored: List[tuple] = []

        for raw in _load_corpus_chunks():
            if suppress_in_crisis and raw.get("safety", {}).get("suppress_in_crisis"):
                continue
            modes = raw.get("session_modes", ["coaching", "information"])
            if session_mode not in modes:
                continue
            chunk_jurisdiction = str(raw.get("jurisdiction", "GLOBAL")).upper()
            if chunk_jurisdiction not in (jurisdiction, "GLOBAL"):
                continue

            score = 0
            text_blob = " ".join(
                [
                    str(raw.get("text", "")),
                    " ".join(raw.get("tags", []) or []),
                    str(raw.get("framework", "")),
                ]
            ).lower()
            for word in words:
                if word in text_blob:
                    score += 10
            if score <= 0 and words:
                continue
            if score <= 0:
                score = 1  # allow generic chunks when query is short
            scored.append((score, raw))

        scored.sort(key=lambda item: item[0], reverse=True)
        selected = scored[: max(1, min(max_chunks, 15))]

        results: List[KBChunk] = []
        for _, raw in selected:
            safety = raw.get("safety", {})
            results.append(
                KBChunk(
                    chunk_id=str(raw.get("chunk_id", "")),
                    source_doc=str(raw.get("source_doc", "")),
                    text=str(raw.get("text", "")),
                    section=str(raw.get("section", "")),
                    jurisdiction=str(raw.get("jurisdiction", "GLOBAL")),
                    session_modes=tuple(raw.get("session_modes", ["coaching"])),
                    suppress_in_crisis=bool(safety.get("suppress_in_crisis", True)),
                )
            )
        return results

    def describe(self) -> Dict[str, str]:
        return {"provider": "default", "visibility": "public", "version": "0.1.0"}

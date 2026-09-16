"""Query-aware extractive context selection via local embeddings."""

from __future__ import annotations

import math
import os
import re
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Tuple

import numpy as np
import yaml
from fastembed import TextEmbedding

from skillware.core.base_skill import BaseSkill

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_MIN_SCORE = 0.35
_DEFAULT_MAX_TOKENS = 2000
_DEFAULT_CHUNK_CHARS = 1800
_PREVIEW_CHARS = 120


class TextChunk(NamedTuple):
    index: int
    start_offset: int
    end_offset: int
    text: str

    @property
    def char_count(self) -> int:
        return len(self.text)


class ContextOptimizerSkill(BaseSkill):
    """Extractive mini-RAG: score document chunks against agent_goal with local embeddings."""

    _model: Optional[TextEmbedding] = None

    @classmethod
    def _get_model(cls) -> TextEmbedding:
        if cls._model is None:
            cls._model = TextEmbedding()
        return cls._model

    @property
    def manifest(self) -> Dict[str, Any]:
        path = os.path.join(_SKILL_DIR, "manifest.yaml")
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        return max(0, len(text) // 4)

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        norm_a = float(np.linalg.norm(a))
        norm_b = float(np.linalg.norm(b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _chunk_document(
        self,
        text: str,
        strategy: str,
        chunk_size_chars: int,
        chunk_overlap_chars: int,
    ) -> List[TextChunk]:
        strategy = (strategy or "paragraph").strip().lower()
        if strategy == "sentence":
            return self._chunk_by_sentence(text)
        if strategy == "fixed_chars":
            return self._chunk_fixed_chars(text, chunk_size_chars, chunk_overlap_chars)
        return self._chunk_by_paragraph(text)

    @staticmethod
    def _chunk_by_paragraph(text: str) -> List[TextChunk]:
        chunks: List[TextChunk] = []
        cursor = 0
        for block in re.split(r"\n\s*\n", text):
            stripped = block.strip()
            if not stripped:
                cursor += len(block)
                continue
            start = text.find(stripped, cursor)
            if start < 0:
                start = cursor
            end = start + len(stripped)
            chunks.append(
                TextChunk(
                    index=len(chunks), start_offset=start, end_offset=end, text=stripped
                )
            )
            cursor = end
        if not chunks and text.strip():
            stripped = text.strip()
            chunks.append(
                TextChunk(
                    index=0, start_offset=0, end_offset=len(stripped), text=stripped
                )
            )
        return chunks

    @staticmethod
    def _chunk_by_sentence(text: str) -> List[TextChunk]:
        chunks: List[TextChunk] = []
        cursor = 0
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            stripped = sentence.strip()
            if not stripped:
                continue
            start = text.find(stripped, cursor)
            if start < 0:
                start = cursor
            end = start + len(stripped)
            chunks.append(
                TextChunk(
                    index=len(chunks), start_offset=start, end_offset=end, text=stripped
                )
            )
            cursor = end
        if not chunks and text.strip():
            stripped = text.strip()
            chunks.append(
                TextChunk(
                    index=0, start_offset=0, end_offset=len(stripped), text=stripped
                )
            )
        return chunks

    @staticmethod
    def _chunk_fixed_chars(
        text: str,
        chunk_size: int,
        overlap: int,
    ) -> List[TextChunk]:
        size = max(200, int(chunk_size))
        overlap = max(0, min(int(overlap), size // 2))
        step = max(1, size - overlap)
        stripped = text.strip()
        if not stripped:
            return []
        chunks: List[TextChunk] = []
        pos = 0
        while pos < len(stripped):
            end = min(len(stripped), pos + size)
            piece = stripped[pos:end].strip()
            if piece:
                chunks.append(
                    TextChunk(
                        index=len(chunks),
                        start_offset=pos,
                        end_offset=pos + len(piece),
                        text=piece,
                    )
                )
            if end >= len(stripped):
                break
            pos += step
        return chunks

    def _select_chunks(
        self,
        chunks: Sequence[TextChunk],
        scores: Sequence[float],
        *,
        min_score: float,
        max_tokens: int,
    ) -> Tuple[List[TextChunk], List[float]]:
        ranked = sorted(
            zip(chunks, scores),
            key=lambda item: item[1],
            reverse=True,
        )
        selected: List[TextChunk] = []
        selected_scores: List[float] = []
        budget = max(1, int(max_tokens))
        used_tokens = 0

        for chunk, score in ranked:
            if score < min_score:
                continue
            est = self._estimate_tokens(chunk.text)
            if selected and used_tokens + est > budget:
                continue
            if not selected and est > budget:
                # Single oversized chunk: hard truncate extractively at char boundary.
                max_chars = budget * 4
                truncated = chunk.text[:max_chars]
                selected.append(
                    TextChunk(
                        index=chunk.index,
                        start_offset=chunk.start_offset,
                        end_offset=chunk.start_offset + len(truncated),
                        text=truncated,
                    )
                )
                selected_scores.append(score)
                used_tokens = self._estimate_tokens(truncated)
                break
            selected.append(chunk)
            selected_scores.append(score)
            used_tokens += est
            if used_tokens >= budget:
                break

        ordered = sorted(
            zip(selected, selected_scores), key=lambda item: item[0].start_offset
        )
        return [item[0] for item in ordered], [item[1] for item in ordered]

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        document_text = str(params.get("document_text") or "")
        agent_goal = str(params.get("agent_goal") or "").strip()
        max_tokens_return = int(params.get("max_tokens_return") or _DEFAULT_MAX_TOKENS)
        min_score = float(
            params.get("min_score")
            if params.get("min_score") is not None
            else _DEFAULT_MIN_SCORE
        )
        chunk_strategy = str(params.get("chunk_strategy") or "paragraph")
        chunk_size_chars = int(params.get("chunk_size_chars") or _DEFAULT_CHUNK_CHARS)
        chunk_overlap_chars = int(params.get("chunk_overlap_chars") or 200)

        if not document_text.strip():
            return self._error(
                "missing_document",
                "document_text is required and must be non-empty.",
                agent_hint="Pass the full source document as document_text.",
            )
        if not agent_goal:
            return self._error(
                "missing_goal",
                "agent_goal is required — describe what the host agent needs from the document.",
            )
        if max_tokens_return < 1:
            return self._error("invalid_budget", "max_tokens_return must be >= 1.")
        if not 0.0 <= min_score <= 1.0:
            return self._error(
                "invalid_min_score", "min_score must be between 0.0 and 1.0."
            )

        input_tokens = self._estimate_tokens(document_text)
        if input_tokens <= max_tokens_return:
            return {
                "status": "ready",
                "optimized_context": document_text.strip(),
                "reduction_percentage": "0%",
                "estimated_input_tokens": input_tokens,
                "estimated_output_tokens": input_tokens,
                "chunks_total": 1,
                "chunks_selected_count": 1,
                "chunks_selected": [
                    {
                        "index": 0,
                        "score": 1.0,
                        "start_offset": 0,
                        "end_offset": len(document_text.strip()),
                        "char_count": len(document_text.strip()),
                        "preview": document_text.strip()[:_PREVIEW_CHARS],
                    }
                ],
                "agent_hint": "Document already fits the token budget; returned verbatim.",
            }

        chunks = self._chunk_document(
            document_text,
            chunk_strategy,
            chunk_size_chars,
            chunk_overlap_chars,
        )
        if not chunks:
            return self._error("chunk_failed", "Unable to chunk document_text.")

        model = self._get_model()
        texts_to_embed = [agent_goal] + [chunk.text for chunk in chunks]
        vectors = list(model.embed(texts_to_embed))
        goal_vector = vectors[0]
        chunk_vectors = vectors[1:]
        scores = [self._cosine_similarity(goal_vector, vec) for vec in chunk_vectors]

        selected, selected_scores = self._select_chunks(
            chunks,
            scores,
            min_score=min_score,
            max_tokens=max_tokens_return,
        )

        if not selected:
            best = max(scores) if scores else 0.0
            return {
                "status": "empty_result",
                "optimized_context": "",
                "reduction_percentage": "100%",
                "estimated_input_tokens": input_tokens,
                "estimated_output_tokens": 0,
                "chunks_total": len(chunks),
                "chunks_selected_count": 0,
                "chunks_selected": [],
                "best_score": round(best, 4),
                "min_score": min_score,
                "agent_hint": (
                    "No chunk scored above min_score. Lower min_score, broaden agent_goal, "
                    "or try chunk_strategy='fixed_chars'."
                ),
            }

        optimized_context = "\n\n".join(chunk.text for chunk in selected)
        output_tokens = self._estimate_tokens(optimized_context)
        reduction = 0.0
        if input_tokens > 0:
            reduction = max(0.0, (1.0 - (output_tokens / input_tokens)) * 100.0)

        chunk_rows: List[Dict[str, Any]] = []
        for chunk, score in zip(selected, selected_scores):
            chunk_rows.append(
                {
                    "index": chunk.index,
                    "score": round(float(score), 4),
                    "start_offset": chunk.start_offset,
                    "end_offset": chunk.end_offset,
                    "char_count": chunk.char_count,
                    "preview": chunk.text[:_PREVIEW_CHARS],
                }
            )

        return {
            "status": "ready",
            "optimized_context": optimized_context,
            "reduction_percentage": f"{math.floor(reduction)}%",
            "estimated_input_tokens": input_tokens,
            "estimated_output_tokens": output_tokens,
            "chunks_total": len(chunks),
            "chunks_selected_count": len(selected),
            "chunks_selected": chunk_rows,
            "min_score": min_score,
            "chunk_strategy": chunk_strategy,
            "agent_hint": (
                "Pass optimized_context to the main model. Chain with "
                "security/prompt_injection_firewall when document_text is untrusted."
            ),
        }

    @staticmethod
    def _error(
        code: str, message: str, agent_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "status": "error",
            "error": code,
            "message": message,
            "optimized_context": "",
            "reduction_percentage": "0%",
            "chunks_selected": [],
        }
        if agent_hint:
            payload["agent_hint"] = agent_hint
        return payload

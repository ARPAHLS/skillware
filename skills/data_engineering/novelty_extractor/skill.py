from typing import Any, Dict, List
import numpy as np
from fastembed import TextEmbedding
from skillware.core.base_skill import BaseSkill


class NoveltyExtractor(BaseSkill):
    """Filters a text dataset by semantic novelty using local embeddings."""

    _model = None

    @classmethod
    def _get_model(cls) -> TextEmbedding:
        """Load the embedding model once and reuse it across calls."""
        if cls._model is None:
            cls._model = TextEmbedding()
        return cls._model

    @property
    def manifest(self) -> Dict[str, Any]:
        return {
            "name": "data_engineering/novelty_extractor",
            "version": "0.1.0",
            "description": (
                "Filters a text dataset by semantic novelty, retaining only "
                "chunks that carry new information above a configurable threshold."
            ),
        }

    def _chunk_text(self, text: str, strategy: str) -> List[str]:
        """Split text into chunks using the given strategy."""
        strategies = {
            "paragraph": self._chunk_by_paragraph,
            "sentence": self._chunk_by_sentence,
        }
        chunk_fn = strategies.get(strategy, self._chunk_by_paragraph)
        return chunk_fn(text)

    def _chunk_by_paragraph(self, text: str) -> List[str]:
        """Split text by double newline (paragraph boundaries)."""
        return [c.strip() for c in text.split("\n\n") if c.strip()]

    def _chunk_by_sentence(self, text: str) -> List[str]:
        """Split text by period followed by whitespace."""
        import re

        return [c.strip() for c in re.split(r"(?<=[.!?])\s+", text) if c.strip()]

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Filter dataset_chunk by semantic novelty."""
        try:
            dataset_chunk = params.get("dataset_chunk", "")
            novelty_threshold = float(params.get("novelty_threshold", 0.85))
            baseline_text = params.get("baseline_chunks", "")
            chunk_strategy = params.get("chunk_strategy", "paragraph")

            if not dataset_chunk.strip():
                return {
                    "distilled_content": "",
                    "compression_ratio": "0%",
                    "redundant_chunks_dropped": 0,
                }

            model = self._get_model()
            chunks = self._chunk_text(dataset_chunk, chunk_strategy)

            # Embed baseline chunks if provided
            seen_vectors = []
            if baseline_text.strip():
                baseline_chunks = self._chunk_text(baseline_text, chunk_strategy)
                seen_vectors = list(model.embed(baseline_chunks))

            # Embed all chunks at once
            chunk_vectors = list(model.embed(chunks))

            novel_chunks = []
            redundant_count = 0

            for chunk, chunk_vector in zip(chunks, chunk_vectors):
                if not seen_vectors:
                    novel_chunks.append(chunk)
                    seen_vectors.append(chunk_vector)
                    continue

                similarities = [float(np.dot(chunk_vector, sv)) for sv in seen_vectors]
                max_similarity = max(similarities)

                if max_similarity < novelty_threshold:
                    novel_chunks.append(chunk)
                    seen_vectors.append(chunk_vector)
                else:
                    redundant_count += 1

            total = len(chunks)
            compression = (
                round((redundant_count / total) * 100, 1) if total > 0 else 0.0
            )

            return {
                "distilled_content": "\n\n".join(novel_chunks),
                "compression_ratio": f"{compression}%",
                "redundant_chunks_dropped": redundant_count,
            }

        except Exception as e:
            return {
                "error": str(e),
                "distilled_content": "",
                "compression_ratio": "0%",
                "redundant_chunks_dropped": 0,
            }

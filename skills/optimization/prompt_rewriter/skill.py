import os
import re
from typing import Any, Dict
from skillware.core.base_skill import BaseSkill


class PromptRewriter(BaseSkill):
    """
    A skill that heuristically compresses a prompt by removing unnecessary whitespace,
    low-value words, and optionally trimming grammar.
    """

    @property
    def manifest(self) -> Dict[str, Any]:
        return self.load_manifest_from_dir(os.path.dirname(__file__))

    def _estimate_tokens(self, text: str) -> int:
        """Naive estimation since we want to avoid strict pip dependencies inside the skill."""
        return max(1, len(text) // 4)

    def execute(self, params: Dict[str, Any]) -> Any:
        raw_text = params.get("raw_text", "")
        aggression = params.get("compression_aggression", "medium").lower()

        if not raw_text:
            return {"error": "raw_text cannot be empty."}

        original_tokens = self._estimate_tokens(raw_text)

        # Level 1: Standardize Whitespace (Low Aggression)
        compressed = re.sub(r"\s+", " ", raw_text).strip()

        # Level 2: Remove Filler Words (Medium Aggression)
        if aggression in ["medium", "high"]:
            fillers = [
                "please",
                "could you",
                "would you",
                "kindly",
                "make sure to",
                "ensure that",
                "I want you to",
                "can you",
            ]
            for filler in fillers:
                compressed = re.compile(re.escape(filler), re.IGNORECASE).sub(
                    "", compressed
                )
            compressed = re.sub(r"\s+", " ", compressed).strip()

        # Level 3: Intense Vowel/Punctuation Dropping (High Aggression)
        if aggression == "high":
            # Remove non-essential punctuation
            compressed = re.sub(r"[^\w\s\.\-]", "", compressed)
            # Remove common extremely high frequency stop words naively
            stop_words = [
                " a ",
                " an ",
                " the ",
                " is ",
                " that ",
                " this ",
                " and ",
                " to ",
            ]
            for word in stop_words:
                compressed = re.compile(word, re.IGNORECASE).sub(" ", compressed)
            compressed = re.sub(r"\s+", " ", compressed).strip()

        new_tokens = self._estimate_tokens(compressed)

        return {
            "compressed_text": compressed,
            "original_tokens": original_tokens,
            "new_tokens": new_tokens,
            "tokens_saved": original_tokens - new_tokens,
        }

import os
import re
import requests
from typing import Any, Dict, List, Tuple
from skillware.core.base_skill import BaseSkill


class PIIMaskerSkill(BaseSkill):
    """
    Skill to mask/redact PII from text using the arpacorp/micro-f1-mask model via Ollama.
    """

    @property
    def manifest(self) -> Dict[str, Any]:
        return self.load_manifest_from_dir(os.path.dirname(__file__))

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        text = params.get("text", "")
        mode = params.get("mode", "mask")
        ollama_url = params.get("ollama_url", "http://localhost:11434")

        sanitized_text, detected_entities = self._call_ollama(text, ollama_url)
        sanitized_text = self._apply_mode(sanitized_text, mode)

        # Build unique entity types list
        entities = list(set([re.sub(r"_[0-9]+$", "", e) for e in detected_entities]))

        return {
            "sanitized_text": sanitized_text,
            "metadata": {
                "detected_entities": entities,
                "entity_count": len(detected_entities),
                "security_level": "local-only",
                "model": "arpacorp/micro-f1-mask",
            },
        }

    def _call_ollama(self, text: str, endpoint: str) -> Tuple[str, List[str]]:
        try:
            response = requests.post(
                f"{endpoint}/api/generate",
                json={
                    "model": "arpacorp/micro-f1-mask",
                    "prompt": text,
                    "stream": False,
                },
                timeout=30,
            )
            if response.status_code == 200:
                result_text = response.json().get("response", text)
            else:
                # If Ollama is down or model missing, return original text as a fallback
                # or we could throw an exception. We'll return the raw text if it fails
                result_text = text
        except requests.exceptions.RequestException:
            # Fall back to returning the text unmasked if Ollama is unreachable.
            # In a strict environment, you might want to block here.
            result_text = text

        # Detect entities in the response
        detected = re.findall(r"\[([A-Z_]+(?:_[0-9]+)?)\]", result_text)
        return result_text, detected

    def _apply_mode(self, text: str, mode: str) -> str:
        if mode == "mask":
            return text

        # Pattern to catch [DOCUMENT], [PERSON_1], etc.
        pattern = r"\[[A-Z_]+(?:_[0-9]+)?\]"
        if mode == "redact":
            return re.sub(pattern, "XXXX", text)
        elif mode == "remove":
            # Replace token and any immediate preceding/following spaces safely
            # A simple sub is sufficient. Cleaning up double spaces.
            text = re.sub(pattern, "", text)
            text = re.sub(r"\s+", " ", text).strip()
            return text

        return text

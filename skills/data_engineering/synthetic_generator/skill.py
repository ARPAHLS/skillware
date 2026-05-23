import os
import zlib
import json

from typing import Dict, Any

from skillware.core.base_skill import BaseSkill


class SyntheticGeneratorSkill(BaseSkill):
    """
    A skill that generates high-entropy synthetic data using internal LLMs,
    and validates the generated text with zlib-based entropy scoring.
    """

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            import yaml
            with open(manifest_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def _calculate_entropy_score(self, text: str) -> float:
        """
        Calculates a heuristic entropy score using zlib compression ratio.
        Higher score = less compressible = higher entropy.
        """
        if not text:
            return 0.0
        encoded = text.encode("utf-8")
        compressed = zlib.compress(encoded)
        ratio = len(compressed) / len(encoded)
        # Scaled for readability
        return round(min(ratio * 1.5, 1.0), 3)

    def _call_gemini(
        self, prompt: str, temperature: float, model_name: str
    ) -> str:
        import google.genai as genai
        from google.genai import types

        api_key = (
            self.config.get("GOOGLE_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
        )
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=temperature),
        )
        return response.text

    def _call_anthropic(
        self, prompt: str, temperature: float, model_name: str
    ) -> str:
        import anthropic
        api_key = (
            self.config.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_API_KEY")
        )
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=model_name,
            max_tokens=4096,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def _call_ollama(
        self, prompt: str, temperature: float, model_name: str
    ) -> str:
        import ollama
        response = ollama.chat(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": temperature}
        )
        return response.get("message", {}).get("content", "")

    def execute(self, params: Dict[str, Any]) -> Any:
        domain = params.get("domain")
        num_samples = params.get("num_samples")
        temperature = float(params.get("entropy_temperature", 0.8))
        diversity_prompt = params.get("diversity_prompt")

        provider = params.get("model_provider", "ollama").lower()
        model_name = params.get("model_name")

        if not model_name:
            if provider == "ollama":
                model_name = "llama3"
            elif provider == "gemini":
                model_name = "gemini-1.5-flash"
            elif provider == "anthropic":
                model_name = "claude-3-haiku-20240307"

        system_prompt = (
            f"You are a generator for domain: '{domain}'.\n"
            f"Output exactly {num_samples} samples in a JSON array.\n"
            f"Constraint: {diversity_prompt}\n"
            "Return valid JSON array. Keys: instruction, input, output."
        )

        try:
            if provider == "gemini":
                raw_text = self._call_gemini(
                    system_prompt, temperature, model_name
                )
            elif provider == "anthropic":
                raw_text = self._call_anthropic(
                    system_prompt, temperature, model_name
                )
            else:
                raw_text = self._call_ollama(
                    system_prompt, temperature, model_name
                )
        except Exception as e:
            return {
                "status": "error",
                "message": f"LLM Call Failed via {provider}: {str(e)}"
            }

        samples = []
        try:
            cleaned = raw_text.strip()
            if "```json" in cleaned:
                cleaned = cleaned.split("```json")[-1].split("```")[0].strip()
            elif "```" in cleaned:
                cleaned = cleaned.split("```")[-1].split("```")[0].strip()

            parsed = json.loads(cleaned)
            if isinstance(parsed, list):
                samples = parsed
            else:
                samples = [parsed]
        except Exception as e:
            return {
                "status": "error",
                "message": f"Parsing failed: {e}",
                "raw_output": raw_text
            }

        all_text = " ".join([str(s) for s in samples])
        score = self._calculate_entropy_score(all_text)

        return {
            "samples": samples,
            "entropy_score": score,
            "status": "success",
            "provider_used": provider,
            "samples_generated": len(samples)
        }

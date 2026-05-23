import json
import os
from typing import Any, Dict, List

from skillware.core.base_skill import BaseSkill


class MiCAModuleSkill(BaseSkill):
    """
    Acts as a highly specialized, localized RAG and policy enforcement engine for MiCA.
    """

    @property
    def manifest(self) -> Dict[str, Any]:
        return {"name": "compliance/mica_module", "version": "0.1.0"}

    _corpus_cache: List[Dict[str, Any]] = None

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self._ensure_corpus_loaded()

    def _ensure_corpus_loaded(self):
        """Lazy loader for the MiCA JSON corpus."""
        if MiCAModuleSkill._corpus_cache is not None:
            return

        corpus_path = os.path.join(os.path.dirname(__file__), "mica_corpus.json")
        try:
            with open(corpus_path, "r", encoding="utf-8") as f:
                MiCAModuleSkill._corpus_cache = json.load(f)
        except Exception as e:
            print(f"Error loading MiCA corpus: {e}")
            MiCAModuleSkill._corpus_cache = []

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        user_prompt = params.get("user_prompt", "")
        run_evaluator = params.get("run_evaluator", False)
        evaluator_model = params.get("evaluator_model", "gemini-2.5-flash-lite")

        # Use the cached corpus
        mica_data = MiCAModuleSkill._corpus_cache

        # 2. Extract Intent and Route to matched sections
        relevant_chunks = self._route_and_fetch(user_prompt, mica_data)

        # Format the retrieved sections list
        retrieved_sections = []
        context_text = ""
        for chunk in relevant_chunks:
            title_info = chunk.get("title_num", "")
            if chunk.get("title_name"):
                title_info += f": {chunk.get('title_name')}"

            art_info = chunk.get("article_num", "")
            if chunk.get("article_title"):
                art_info += f": {chunk.get('article_title')}"

            sec_name = f"{title_info} | {art_info}"
            retrieved_sections.append(sec_name)
            context_text += f"\n--- {sec_name} ---\n{chunk.get('content', '')}\n"

        # 3. Default Policy Status if no evaluator runs
        policy_status = "CAUTION"
        gemini_feedback = {
            "grade": "N/A",
            "holes_found": (
                "Evaluator disabled. Review MiCA context manually for regulatory holes."
            ),
            "suggestion": "Follow the integrated MiCA chunks exactly.",
        }

        if not retrieved_sections:
            final_context = "No specific MiCA articles matched the user query."
        else:
            final_context = (
                "Output your final answer seamlessly integrating and adhering to "
                f"these MiCA rules:\n{context_text}"
            )

        # 4. Optional Evaluator Node execution
        if run_evaluator and relevant_chunks:
            eval_result = self._run_evaluator(
                user_prompt, context_text, evaluator_model
            )
            policy_status = eval_result.get("policy_status", policy_status)
            gemini_feedback = eval_result.get(
                "gemini_evaluator_feedback", gemini_feedback
            )
            final_context = eval_result.get("final_context_for_agent", final_context)

        return {
            "retrieved_sections": list(set(retrieved_sections)),
            "policy_status": policy_status,
            "gemini_evaluator_feedback": gemini_feedback,
            "final_context_for_agent": final_context,
        }

    def _route_and_fetch(
        self, prompt: str, corpus: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        # Lightweight keyword overlap router to prevent huge context bloat.
        prompt_lower = prompt.lower()

        # Normalize common spelling variations (US to UK for the European regulation)
        replacements = {
            "authorization": "authorisation",
            "authorize": "authorise",
            "organization": "organisation",
            "crypto asset": "crypto-asset",
            "stablecoin": "asset-referenced token",  # High-level intent mapping
        }
        normalized_prompt = prompt_lower
        for us, uk in replacements.items():
            normalized_prompt = normalized_prompt.replace(us, uk)

        # We look for significant words to increase collision hits
        prompt_words = [
            w.lower()
            for w in normalized_prompt.replace("?", "")
            .replace(".", "")
            .replace(",", "")
            .split()
            if len(w) > 3
        ]

        scored_matches = []
        # We look for significant words to increase collision hits
        prompt_words = [
            w.lower()
            for w in normalized_prompt.replace("?", "")
            .replace(".", "")
            .replace(",", "")
            .split()
            if len(w) > 3
        ]

        for article in corpus:
            score = 0
            keywords = [k.lower() for k in article.get("keywords", [])]
            art_num = article.get("article_num", "").lower()
            art_title = article.get("article_title", "").lower()

            # Match 1: Specific article mention (Highest Priority)
            if art_num and f"article {art_num}" in normalized_prompt:
                score += 100

            # Match 2: Exact keyword match in prompt
            for k in keywords:
                if k in normalized_prompt:
                    score += 20

            # Match 3: Article title collision
            if any(w in art_title for w in prompt_words):
                score += 10

            # Match 4: Significant word collision with keywords (Normalized by length)
            collision_count = 0
            for w in prompt_words:
                for k in keywords:
                    if w in k:
                        # Favor specificity: longer word matches are more significant
                        collision_count += len(w) / max(len(k), 1)
            score += collision_count * 5

            if score > 0:
                scored_matches.append((score, article))

        # Sort by score descending
        scored_matches.sort(key=lambda x: x[0], reverse=True)

        # Deduplicate and limit
        unique_matches = []
        seen = set()
        for score, m in scored_matches:
            a_id = f"{m.get('title_num', '')}_{m.get('article_num', '')}"
            if a_id not in seen:
                unique_matches.append(m)
                seen.add(a_id)

        # Return top 10 most relevant hits to maximize production depth
        return unique_matches[:10]

    def _run_evaluator(
        self, prompt: str, context: str, model_name: str
    ) -> Dict[str, Any]:
        prompt_payload = f"""
        You are a MiCA Regulation Evaluator.
        User Query: {prompt}
        MiCA Rule Context from RAG: {context}

        Draft a response silently to see what an AI would say based on the user query.
        Then, evaluate that draft against the MiCA rules to see if it violates
        anything or misses vital compliance disclosures (like publishing a
        White Paper, authorization required, etc).
        Return exactly a JSON summarizing the grade and issues found.
        Schema:
        {{
            "policy_status": "APPROVED|CAUTION|HIGH_RISK_DETECTED",
            "gemini_evaluator_feedback": {{
                "grade": "<Letter Grade (A to F)>",
                "holes_found": "<Issues the drafted response missed>",
                "suggestion": "<How the agent should fix the holes in its final answer>"
            }},
            "final_context_for_agent": "Output instructions for the agent embedding your suggestion and the context."
        }}
        """

        try:
            import google.genai as genai
            from google.genai import types
        except ImportError:
            return {
                "policy_status": "CAUTION",
                "gemini_evaluator_feedback": {
                    "grade": "N/A",
                    "holes_found": "google-genai is not installed.",
                    "suggestion": "Proceed manually integrating the extracted logic.",
                },
                "final_context_for_agent": (
                    f"Output your final answer seamlessly integrating and adhering to these MiCA rules:\n{context}"
                ),
            }

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return {
                "policy_status": "CAUTION",
                "gemini_evaluator_feedback": {
                    "grade": "N/A",
                    "holes_found": "GOOGLE_API_KEY is not configured.",
                    "suggestion": "Proceed manually integrating the extracted logic.",
                },
                "final_context_for_agent": (
                    f"Output your final answer seamlessly integrating and adhering to these MiCA rules:\n{context}"
                ),
            }

        try:
            client = genai.Client(api_key=api_key)
            resp = client.models.generate_content(
                model=model_name,
                contents=prompt_payload,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.0,
                ),
            )
            return json.loads(resp.text)
        except Exception as e:
            return {
                "policy_status": "CAUTION",
                "gemini_evaluator_feedback": {
                    "grade": "N/A",
                    "holes_found": f"Evaluator API failed or rate-limited: {str(e)}",
                    "suggestion": "Proceed manually integrating the extracted logic.",
                },
                "final_context_for_agent": (
                    f"Output your final answer seamlessly integrating and adhering to these MiCA rules:\n{context}"
                ),
            }

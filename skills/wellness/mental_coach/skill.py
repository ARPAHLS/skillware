"""wellness/mental_coach — deterministic coaching firewall skill."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional

import yaml

from skillware.core.base_skill import BaseSkill

_SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
if _SKILL_DIR not in sys.path:
    sys.path.insert(0, _SKILL_DIR)

from constraints import (  # noqa: E402
    detect_clinical_violation,
    detect_injection_attempt,
    get_disclaimers,
    get_playbook_entry,
)
from crisis_gate import assess_language, evaluate_crisis_gate  # noqa: E402
from kb_provider import DefaultCorpusProvider, KBChunk  # noqa: E402
from resources import format_crisis_resources, normalize_jurisdiction  # noqa: E402


class MentalCoachSkill(BaseSkill):
    """Grounded wellness coaching guardrail with crisis triage."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        self._provider = DefaultCorpusProvider()

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
        return {}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        user_prompt = (params.get("user_prompt") or "").strip()
        if not user_prompt:
            return self._error("user_prompt is required.")

        jurisdiction = normalize_jurisdiction(params.get("user_jurisdiction", "GLOBAL"))
        session_mode = (params.get("session_mode") or "coaching").strip().lower()
        if session_mode not in ("coaching", "information", "crisis_check"):
            session_mode = "coaching"

        run_evaluator = bool(params.get("run_evaluator", False))
        evaluator_model = params.get("evaluator_model") or "gemini-2.5-flash-lite"
        try:
            max_chunks = int(params.get("max_chunks", 8))
        except (TypeError, ValueError):
            max_chunks = 8
        max_chunks = max(1, min(max_chunks, 15))

        hard_applied: List[str] = []
        if detect_injection_attempt(user_prompt):
            hard_applied.append("prompt_injection_resistant")

        language = assess_language(user_prompt)
        gate = evaluate_crisis_gate(user_prompt)

        policy_status = gate.policy_status
        if language.non_english and policy_status == "OK":
            policy_status = "CAUTION"

        if policy_status == "ESCALATE":
            return self._escalate_response(
                user_prompt=user_prompt,
                jurisdiction=jurisdiction,
                gate=gate,
                hard_applied=hard_applied + ["crisis_escalation_mandatory"],
                language=language,
            )

        clinical = detect_clinical_violation(user_prompt)
        if clinical:
            return self._blocked_response(
                constraint_id=clinical,
                hard_applied=hard_applied + [clinical],
                jurisdiction=jurisdiction,
            )

        disclaimers = get_disclaimers("default")
        suppress_coaching = policy_status == "ESCALATE" or language.non_english

        chunks: List[KBChunk] = []
        if not suppress_coaching:
            chunks = list(
                self._provider.retrieve(
                    user_prompt,
                    jurisdiction=jurisdiction,
                    session_mode=session_mode,
                    max_chunks=max_chunks,
                    suppress_in_crisis=False,
                )
            )

        citations, retrieved_sections, context_text = self._format_chunks(chunks)
        playbook = get_playbook_entry(policy_status)

        final_context = self._build_coaching_context(
            context_text=context_text,
            playbook=playbook,
            language=language,
            jurisdiction=jurisdiction,
            policy_status=policy_status,
        )

        evaluator_feedback = {
            "grade": "N/A",
            "holes_found": "Evaluator disabled.",
            "suggestion": "Follow retrieved chunks and required disclaimers exactly.",
        }

        if run_evaluator and context_text:
            eval_result = self._run_evaluator(
                user_prompt, context_text, evaluator_model
            )
            policy_status = eval_result.get("policy_status", policy_status)
            evaluator_feedback = eval_result.get(
                "evaluator_feedback", evaluator_feedback
            )
            final_context = eval_result.get("final_context_for_agent", final_context)

        if language.non_english:
            resource_block = format_crisis_resources(jurisdiction)
            final_context = (
                "Input appears to be outside the v0.1 English-first scope. "
                "Do not provide detailed coaching. Offer calm support, default "
                "disclaimers, and crisis/help resources.\n\n"
                f"{resource_block}\n\n"
                f"{final_context}"
            )

        return {
            "policy_status": policy_status,
            "scope": "coaching",
            "retrieved_sections": retrieved_sections,
            "citations": citations,
            "hard_constraints_applied": hard_applied,
            "disclaimers_required": disclaimers,
            "evaluator_feedback": evaluator_feedback,
            "final_context_for_agent": final_context,
            "privacy_metadata": {
                "jurisdiction": jurisdiction,
                "session_mode": session_mode,
                "kb_chunks_retrieved": len(chunks),
                "language_assessment": language.reason or "english",
            },
        }

    def _escalate_response(
        self,
        *,
        user_prompt: str,
        jurisdiction: str,
        gate,
        hard_applied: List[str],
        language,
    ) -> Dict[str, Any]:
        del user_prompt
        resources = format_crisis_resources(jurisdiction)
        playbook = get_playbook_entry("ESCALATE")
        instruction = playbook.get(
            "host_instruction",
            playbook.get(
                "ao_instruction",
                "Surface resources prominently. Do not provide coaching or clinical advice.",
            ),
        )
        final_context = (
            f"{instruction.strip()}\n\n"
            "Crisis signals detected. Stop coaching. Share escalation steps and "
            "resources below. Keep tone calm, brief, and non-judgmental.\n\n"
            f"{resources}"
        )
        if language.non_english:
            final_context = (
                "Non-English input detected (v0.1 EN-first). Prioritize resources "
                "and emergency guidance.\n\n" + final_context
            )
        return {
            "policy_status": "ESCALATE",
            "scope": "crisis_referral",
            "crisis_categories": gate.crisis_categories,
            "retrieved_sections": [],
            "citations": [],
            "hard_constraints_applied": hard_applied,
            "disclaimers_required": get_disclaimers("crisis"),
            "evaluator_feedback": {
                "grade": "N/A",
                "holes_found": "Evaluator skipped during crisis escalation.",
                "suggestion": "Follow escalation playbook and resources only.",
            },
            "final_context_for_agent": final_context,
            "privacy_metadata": {
                "jurisdiction": jurisdiction,
                "session_mode": "crisis_check",
                "kb_chunks_retrieved": 0,
                "language_assessment": language.reason or "english",
            },
        }

    def _blocked_response(
        self,
        *,
        constraint_id: str,
        hard_applied: List[str],
        jurisdiction: str,
    ) -> Dict[str, Any]:
        return {
            "policy_status": "BLOCKED",
            "scope": "blocked",
            "retrieved_sections": [],
            "citations": [],
            "hard_constraints_applied": hard_applied,
            "disclaimers_required": get_disclaimers("default"),
            "evaluator_feedback": {
                "grade": "N/A",
                "holes_found": "Clinical request blocked before retrieval.",
                "suggestion": "Decline the clinical request and offer non-clinical alternatives.",
            },
            "final_context_for_agent": (
                "Decline the clinical request (diagnosis, medication, or clinical "
                "interpretation). Offer supportive, non-clinical information only. "
                "Encourage speaking with a qualified professional when appropriate."
            ),
            "privacy_metadata": {
                "jurisdiction": jurisdiction,
                "session_mode": "coaching",
                "kb_chunks_retrieved": 0,
                "blocked_constraint": constraint_id,
            },
        }

    @staticmethod
    def _format_chunks(chunks: List[KBChunk]) -> tuple:
        citations: List[Dict[str, str]] = []
        retrieved_sections: List[str] = []
        context_parts: List[str] = []
        for chunk in chunks:
            label = f"{chunk.source_doc} | {chunk.section} [{chunk.chunk_id}]"
            retrieved_sections.append(label)
            citations.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "source_doc": chunk.source_doc,
                    "section": chunk.section,
                    "jurisdiction": chunk.jurisdiction,
                }
            )
            context_parts.append(f"--- {label} ---\n{chunk.text}\n")
        return citations, retrieved_sections, "\n".join(context_parts)

    @staticmethod
    def _build_coaching_context(
        *,
        context_text: str,
        playbook: Dict[str, Any],
        language,
        jurisdiction: str,
        policy_status: str,
    ) -> str:
        instruction = playbook.get(
            "host_instruction",
            playbook.get(
                "ao_instruction",
                "Provide supportive coaching grounded only in retrieved guidance.",
            ),
        )
        if not context_text:
            base = (
                "No specific KB sections matched the query. Provide cautious, "
                "supportive coaching within scope and include required disclaimers."
            )
        else:
            base = (
                "Provide supportive coaching using ONLY the retrieved guidance below. "
                "Do not diagnose, prescribe, or claim clinical authority.\n\n"
                f"{context_text}"
            )
        if policy_status == "CAUTION":
            resources = format_crisis_resources(jurisdiction)
            base = (
                f"{instruction.strip()}\n\n"
                "Proceed gently with validation and lower intensity. Include resources "
                "when appropriate.\n\n"
                f"{resources}\n\n"
                f"{base}"
            )
        else:
            base = f"{instruction.strip()}\n\n{base}"
        if language.non_english:
            return base
        return base

    def _run_evaluator(
        self, user_prompt: str, context: str, model_name: str
    ) -> Dict[str, Any]:
        prompt_payload = f"""
You are a wellness coaching scope evaluator.
User query: {user_prompt}
Retrieved coaching context: {context}

Draft a response silently, then evaluate whether it stays within supportive
coaching (no diagnosis, no medication advice, no emergency counseling).
Return JSON only:
{{
  "policy_status": "OK|CAUTION|BLOCKED",
  "evaluator_feedback": {{
    "grade": "A-F or N/A",
    "holes_found": "issues found",
    "suggestion": "how the agent should adjust"
  }},
  "final_context_for_agent": "instructions for the host agent"
}}
"""
        try:
            import google.genai as genai
            from google.genai import types
        except ImportError:
            return {
                "policy_status": "CAUTION",
                "evaluator_feedback": {
                    "grade": "N/A",
                    "holes_found": "google-genai is not installed.",
                    "suggestion": "Follow retrieved chunks manually.",
                },
                "final_context_for_agent": context,
            }

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            return {
                "policy_status": "CAUTION",
                "evaluator_feedback": {
                    "grade": "N/A",
                    "holes_found": "GOOGLE_API_KEY is not configured.",
                    "suggestion": "Follow retrieved chunks manually.",
                },
                "final_context_for_agent": context,
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
            parsed = json.loads(resp.text)
            if (
                "evaluator_feedback" not in parsed
                and "gemini_evaluator_feedback" in parsed
            ):
                parsed["evaluator_feedback"] = parsed.pop("gemini_evaluator_feedback")
            return parsed
        except Exception as exc:
            return {
                "policy_status": "CAUTION",
                "evaluator_feedback": {
                    "grade": "N/A",
                    "holes_found": f"Evaluator failed: {exc}",
                    "suggestion": "Follow retrieved chunks manually.",
                },
                "final_context_for_agent": context,
            }

    @staticmethod
    def _error(message: str) -> Dict[str, Any]:
        return {
            "error": message,
            "policy_status": "BLOCKED",
            "scope": "blocked",
            "retrieved_sections": [],
            "citations": [],
            "hard_constraints_applied": [],
            "disclaimers_required": get_disclaimers("default"),
            "evaluator_feedback": {
                "grade": "N/A",
                "holes_found": message,
                "suggestion": "Provide a valid user_prompt.",
            },
            "final_context_for_agent": message,
            "privacy_metadata": {},
        }

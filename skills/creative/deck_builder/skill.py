"""Deck Builder Skill: Deterministic assembly of editable .pptx presentations."""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, Optional

import yaml
from skillware.core.base_skill import BaseSkill

try:
    from .builder import inspect_deck, list_templates, render_deck, validate_spec
    from .lint import lint_deck
    from .archetypes import suggest_outline
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from builder import inspect_deck, list_templates, render_deck, validate_spec
    from lint import lint_deck
    from archetypes import suggest_outline


class DeckBuilderSkill(BaseSkill):
    """Deterministic presentation builder from structured JSON deck specifications."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(config)

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute requested presentation operation.

        Supported actions:
        - validate_spec (default): Validate deck_spec against schema and soft limits.
        - render: Assemble .pptx to output_path.
        - inspect: Inspect existing .pptx file at input_path.
        - list_templates: List bundled templates and layout types.
        """
        if not isinstance(params, dict):
            return {
                "success": False,
                "action": "unknown",
                "valid": False,
                "error_code": "INVALID_PARAMS",
                "errors": [
                    {
                        "code": "INVALID_PARAMS",
                        "slide_index": -1,
                        "message": "Parameters must be provided as a JSON dictionary.",
                    }
                ],
            }

        action = params.get("action", "validate_spec")

        if action == "validate_spec":
            return validate_spec(
                deck_spec=params.get("deck_spec"),
                strict=bool(params.get("strict", False)),
            )

        if action == "render":
            output_path = params.get("output_path")
            if not output_path:
                return {
                    "success": False,
                    "action": "render",
                    "valid": False,
                    "slide_count": 0,
                    "file_size_bytes": 0,
                    "slides": [],
                    "warnings": [],
                    "errors": [
                        {
                            "code": "OUTPUT_PATH_MISSING",
                            "slide_index": -1,
                            "message": "output_path is required for render action.",
                        }
                    ],
                    "error_code": "OUTPUT_PATH_MISSING",
                }

            return render_deck(
                deck_spec=params.get("deck_spec") or {},
                output_path=str(output_path),
                template_id=params.get("template_id"),
                theme=params.get("theme"),
                strict=bool(params.get("strict", False)),
            )

        if action == "inspect":
            input_path = params.get("input_path")
            if not input_path:
                return {
                    "success": False,
                    "action": "inspect",
                    "slide_count": 0,
                    "slides": [],
                    "errors": [
                        {
                            "code": "INPUT_PATH_MISSING",
                            "slide_index": -1,
                            "message": "input_path is required for inspect action.",
                        }
                    ],
                    "error_code": "INPUT_PATH_MISSING",
                }
            return inspect_deck(str(input_path))

        if action == "list_templates":
            return list_templates()

        if action == "lint_deck":
            deck_spec = params.get("deck_spec")
            if not deck_spec:
                return {
                    "success": False,
                    "action": "lint_deck",
                    "score": 0,
                    "passed": False,
                    "error_code": "DECK_SPEC_MISSING",
                    "message": "deck_spec is required for lint_deck action.",
                    "findings": [],
                }
            options = {
                "min_score": params.get("min_score", 70),
                "strict_a11y": params.get("strict_a11y", False),
            }
            return lint_deck(deck_spec, options)

        if action == "suggest_outline":
            archetype = params.get("archetype", "investor_pitch")
            topic = params.get("topic", "")
            constraints = params.get("constraints", [])
            return suggest_outline(archetype, topic, constraints)

        return {
            "success": False,
            "action": str(action),
            "valid": False,
            "error_code": "UNKNOWN_ACTION",
            "errors": [
                {
                    "code": "UNKNOWN_ACTION",
                    "slide_index": -1,
                    "message": (
                        f"Action '{action}' is not supported. "
                        "Use validate_spec, render, inspect, list_templates, lint_deck, or suggest_outline."
                    ),
                }
            ],
        }

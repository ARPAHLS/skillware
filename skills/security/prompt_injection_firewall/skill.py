import os
import sys
from typing import Any, Dict

import yaml

from skillware.core.base_skill import BaseSkill

try:
    from .firewall import SensitivityLevel, scan_source_text
except ImportError:
    # SkillLoader exec's skill.py as a flat module (no package parent).
    sys.path.insert(0, os.path.dirname(__file__))
    from firewall import SensitivityLevel, scan_source_text


class PromptInjectionFirewallSkill(BaseSkill):
    """
    Offline, deterministic pre-flight scanner for hostile instructions in untrusted text.
    """

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as handle:
                return yaml.safe_load(handle)
        return {"name": "security/prompt_injection_firewall", "version": "0.1.0"}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source_text = params.get("source_text", "")
        if source_text is None:
            source_text = ""

        sensitivity = self._normalize_sensitivity(params.get("sensitivity", "balanced"))
        input_mode = self._normalize_input_mode(params.get("input_mode", "auto"))

        result = scan_source_text(
            str(source_text),
            sensitivity=sensitivity,
            input_mode=input_mode,
        )

        return {
            "is_safe": result.is_safe,
            "risk_level": result.risk_level,
            "detected_threat": result.detected_threat,
            "findings": result.findings,
            "sanitized_text": result.sanitized_text,
            "offline": result.offline,
            "sensitivity": result.sensitivity,
        }

    def _normalize_sensitivity(self, value: Any) -> SensitivityLevel:
        normalized = str(value or "balanced").strip().lower()
        if normalized in {"strict", "balanced", "lenient"}:
            return normalized  # type: ignore[return-value]
        return "balanced"

    def _normalize_input_mode(self, value: Any) -> str:
        normalized = str(value or "auto").strip().lower()
        if normalized in {"plain", "html", "markdown", "auto"}:
            return normalized
        return "auto"

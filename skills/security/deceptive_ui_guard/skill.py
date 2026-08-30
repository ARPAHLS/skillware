import os
import sys
from typing import Any, Dict

import yaml

from skillware.core.base_skill import BaseSkill

try:
    from .guard import SensitivityLevel, scan_surface
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from guard import SensitivityLevel, scan_surface


class DeceptiveUiGuardSkill(BaseSkill):
    """Offline deterministic scanner for deceptive UI and anti-agent surface tricks."""

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as handle:
                return yaml.safe_load(handle)
        return {"name": "security/deceptive_ui_guard", "version": "0.1.0"}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        html_content = params.get("html_content") or ""
        url = params.get("url") or ""
        sensitivity = self._normalize_sensitivity(params.get("sensitivity", "balanced"))
        intended_action = str(params.get("intended_action") or "")

        result = scan_surface(
            html_content=str(html_content),
            url=str(url),
            sensitivity=sensitivity,
            intended_action=intended_action,
        )

        return {
            "status": result.status,
            "trust_score": result.trust_score,
            "surface_integrity": result.surface_integrity,
            "is_safe": result.is_safe,
            "risk_level": result.risk_level,
            "detected_threat": result.detected_threat,
            "findings": result.findings,
            "agent_guidance": result.agent_guidance,
            "sanitized_excerpt": result.sanitized_excerpt,
            "fetch_status": result.fetch_status,
            "offline": result.offline,
            "sensitivity": result.sensitivity,
        }

    def _normalize_sensitivity(self, value: Any) -> SensitivityLevel:
        normalized = str(value or "balanced").strip().lower()
        if normalized in {"strict", "balanced", "lenient"}:
            return normalized  # type: ignore[return-value]
        return "balanced"

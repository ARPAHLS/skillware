import os
import sys
from typing import Any, Dict

import yaml

from skillware.core.base_skill import BaseSkill

try:
    from .guard import RenderMode, SensitivityLevel, SurfaceProfile, scan_surface
except ImportError:
    sys.path.insert(0, os.path.dirname(__file__))
    from guard import RenderMode, SensitivityLevel, SurfaceProfile, scan_surface


class DeceptiveUiGuardSkill(BaseSkill):
    """Offline deterministic scanner for deceptive UI and anti-agent surface tricks."""

    @property
    def manifest(self) -> Dict[str, Any]:
        manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r", encoding="utf-8") as handle:
                return yaml.safe_load(handle)
        return {"name": "security/deceptive_ui_guard", "version": "0.2.0"}

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        html_content = params.get("html_content") or ""
        url = params.get("url") or ""
        sensitivity = self._normalize_sensitivity(params.get("sensitivity", "balanced"))
        intended_action = str(params.get("intended_action") or "")
        render_mode = self._normalize_render_mode(params.get("render_mode", "off"))
        surface_profile = self._normalize_surface_profile(params.get("surface_profile", "desktop"))
        session_fingerprint = str(params.get("session_fingerprint") or "")

        result = scan_surface(
            html_content=str(html_content),
            url=str(url),
            sensitivity=sensitivity,
            intended_action=intended_action,
            render_mode=render_mode,
            surface_profile=surface_profile,
            session_fingerprint=session_fingerprint,
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
            "zone_summary": result.zone_summary,
            "session_recommendation": result.session_recommendation,
        }

    def _normalize_sensitivity(self, value: Any) -> SensitivityLevel:
        normalized = str(value or "balanced").strip().lower()
        if normalized in {"strict", "balanced", "lenient"}:
            return normalized  # type: ignore[return-value]
        return "balanced"

    def _normalize_render_mode(self, value: Any) -> RenderMode:
        normalized = str(value or "off").strip().lower()
        if normalized in {"off", "auto", "force"}:
            return normalized  # type: ignore[return-value]
        return "off"

    def _normalize_surface_profile(self, value: Any) -> SurfaceProfile:
        normalized = str(value or "desktop").strip().lower()
        if normalized in {"desktop", "mobile", "auto"}:
            return normalized  # type: ignore[return-value]
        return "desktop"


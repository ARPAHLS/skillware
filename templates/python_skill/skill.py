from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Optional
import yaml

from skillware.core.base_skill import BaseSkill


class MyAwesomeSkill(BaseSkill):
    """Template skill demonstrating deterministic Effect execution.

    Implements a pure, deterministic capability for host LLMs.
    Never embeds open-ended LLM calls or writes to stdout/stderr.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the skill instance.

        Pass host-injected configuration (e.g. API credentials, custom settings)
        to the BaseSkill superclass so `self.credential()` resolves config before
        falling back to environment variables.
        """
        super().__init__(config=config)
        # For credentials declared in manifest.yaml env_vars, use self.credential("KEY_NAME")
        # api_key = self.credential("MY_SERVICE_API_KEY")

    @property
    def manifest(self) -> Dict[str, Any]:
        """Loads metadata dynamically from co-located manifest.yaml."""
        manifest_path = Path(__file__).resolve().parent / "manifest.yaml"
        if manifest_path.is_file():
            with open(manifest_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {
            "name": "category/my_awesome_skill",
            "version": "0.1.0",
            "description": "A short description of what this skill does.",
        }

    def execute(
        self,
        params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """The main execution entry point for the skill.

        Validates input arguments against the JSON Schema defined in manifest.yaml,
        executes deterministic logic, and returns a JSON-serializable dictionary.
        Catches internal errors and returns a structured error response rather than
        crashing the host agent.
        """
        payload = dict(params or {})
        payload.update(kwargs)

        # Validate arguments against manifest parameter schema
        self.validate_params(payload)

        param1 = payload.get("param1", "default")

        try:
            # Implement your deterministic logic here (never embed open-ended LLM calls)
            result_data = f"Executed with {param1}"

            return {
                "status": "success",
                "result": result_data,
            }
        except Exception as exc:
            # Return structured error details; never crash the host agent
            return {
                "status": "error",
                "error": str(exc),
                "result": None,
            }

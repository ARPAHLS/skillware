from __future__ import annotations

import os
from typing import Any, Dict, Optional
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
        """Load manifest.yaml from the skill bundle directory."""
        return self.load_manifest_from_dir(os.path.dirname(__file__))

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

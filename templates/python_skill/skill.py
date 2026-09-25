import os
from typing import Any, Dict
from skillware.core.base_skill import BaseSkill


class MyAwesomeSkill(BaseSkill):
    @property
    def manifest(self) -> Dict[str, Any]:
        """Load manifest.yaml from the skill bundle directory."""
        return self.load_manifest_from_dir(os.path.dirname(__file__))

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        The main execution logic for the skill.
        Expects 'param1' in params as defined in manifest.yaml.
        For API keys declared in manifest env_vars, use self.credential("KEY_NAME").
        """
        param1 = params.get("param1", "default")

        # Implement your logic here

        return {"result": f"Executed with {param1}"}

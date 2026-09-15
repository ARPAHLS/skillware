from typing import Any, Dict
from skillware.core.base_skill import BaseSkill


class MyAwesomeSkill(BaseSkill):
    @property
    def manifest(self) -> Dict[str, Any]:
        """
        Returns the skill's manifest. In a production skill,
        you can load this from manifest.yaml using SkillLoader.
        """
        return {
            "name": "my-awesome-skill",
            "version": "0.1.0",
            "description": "A short description of what this skill does.",
        }

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        The main execution logic for the skill.
        Expects 'param1' in params as defined in manifest.yaml.
        For API keys declared in manifest env_vars, use self.credential("KEY_NAME").
        """
        param1 = params.get("param1", "default")

        # Implement your logic here

        return {"result": f"Executed with {param1}"}

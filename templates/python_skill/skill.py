from typing import Any, Dict
from skillware.core.base_skill import BaseSkill

class MyAwesomeSkill(BaseSkill):
    @property
    def manifest(self) -> Dict[str, Any]:
        # You can load this from manifest.yaml or define it here
        return {
            "name": "my-awesome-skill",
            "version": "0.1.0"
        }

    def execute(self, params: Dict[str, Any]) -> Any:
        # Your skill logic goes here
        param1 = params.get("param1")
        return {"result": f"Executed with {param1}"}

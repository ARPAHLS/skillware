from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

class BaseSkill(ABC):
    """
    The foundational class for all Skillware skills.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}

    @property
    @abstractmethod
    def manifest(self) -> Dict[str, Any]:
        """
        Returns the metadata for this skill, including name, version,
        description, inputs, and outputs.
        """
        pass

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Any:
        """
        The main entry point for the skill.
        """
        pass

    def validate_params(self, params: Dict[str, Any]) -> bool:
        """
        Validates input parameters against the manifest schema.
        """
        # TODO: Implement schema validation (e.g. using Pydantic or jsonschema)
        return True

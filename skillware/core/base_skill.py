from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import jsonschema
from jsonschema import ValidationError


class SkillwareParamValidationError(ValueError):
    """Raised when tool arguments fail manifest ``parameters`` JSON Schema validation."""


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
        Validates input parameters against the manifest ``parameters`` schema.

        Returns ``True`` when validation passes. Raises ``SkillwareParamValidationError``
        when ``params`` is not a mapping or does not satisfy the schema.
        """
        schema = self.manifest.get("parameters")
        if not schema or not isinstance(schema, dict):
            return True

        skill_name = self.manifest.get("name", "unknown_skill")
        if not isinstance(params, dict):
            raise SkillwareParamValidationError(
                f"Skill '{skill_name}' expects parameter arguments as a JSON object (dict), "
                f"got {type(params).__name__}."
            )

        try:
            jsonschema.validate(instance=params, schema=schema)
        except ValidationError as exc:
            path = ".".join(str(part) for part in exc.absolute_path) or "(root)"
            raise SkillwareParamValidationError(
                f"Skill '{skill_name}' parameter validation failed at '{path}': {exc.message}"
            ) from exc

        return True

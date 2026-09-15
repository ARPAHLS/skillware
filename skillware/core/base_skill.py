import os
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

    def credential(self, key: str) -> Optional[str]:
        """
        Resolve a manifest ``env_vars`` name.

        Host-injected ``config`` wins over ``os.environ`` so multi-tenant and
        KMS-backed providers do not rely on process-global state. Local dev
        still works via ``.env`` / exports when the host omits ``config``.
        """
        cfg_val = self.config.get(key)
        if cfg_val is not None:
            text = str(cfg_val).strip()
            if text:
                return text
        env_val = os.environ.get(key)
        if env_val is None:
            return None
        text = str(env_val).strip()
        return text or None

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

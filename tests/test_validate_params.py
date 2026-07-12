"""Tests for BaseSkill.validate_params() against manifest parameters schema."""

from typing import Any, Dict

import pytest

from skillware.core.base_skill import BaseSkill, SkillwareParamValidationError
from skillware.core.loader import SkillLoader


class _SchemaSkill(BaseSkill):
    """Minimal skill with a fixed manifest schema for unit tests."""

    @property
    def manifest(self) -> Dict[str, Any]:
        return {
            "name": "test/schema_skill",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
        }

    def execute(self, params: Dict[str, Any]) -> Any:
        return {"ok": True}


def test_validate_params_accepts_valid_arguments():
    skill = _SchemaSkill()
    assert skill.validate_params({"query": "hello", "limit": 3}) is True


def test_validate_params_rejects_missing_required_field():
    skill = _SchemaSkill()
    with pytest.raises(
        SkillwareParamValidationError, match="'query' is a required property"
    ):
        skill.validate_params({})


def test_validate_params_rejects_wrong_type():
    skill = _SchemaSkill()
    with pytest.raises(SkillwareParamValidationError, match="limit"):
        skill.validate_params({"query": "hello", "limit": "three"})


def test_validate_params_rejects_non_object_arguments():
    skill = _SchemaSkill()
    with pytest.raises(SkillwareParamValidationError, match="JSON object"):
        skill.validate_params([])  # type: ignore[arg-type]


def test_validate_params_no_schema_is_noop():
    class _NoSchemaSkill(BaseSkill):
        @property
        def manifest(self) -> Dict[str, Any]:
            return {"name": "test/no_schema"}

        def execute(self, params: Dict[str, Any]) -> Any:
            return {}

    assert _NoSchemaSkill().validate_params({}) is True


def test_registry_mental_coach_validates_required_user_prompt():
    bundle = SkillLoader.load_skill("wellness/mental_coach")
    skill = bundle["class"]()
    assert skill.validate_params({"user_prompt": "I need a breathing exercise"}) is True


def test_registry_mental_coach_rejects_missing_user_prompt():
    bundle = SkillLoader.load_skill("wellness/mental_coach")
    skill = bundle["class"]()
    with pytest.raises(SkillwareParamValidationError, match="user_prompt"):
        skill.validate_params({})

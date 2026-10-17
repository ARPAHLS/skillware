"""Tests for the Agent Protocol Bridge skill."""

import os

import pytest
import yaml

from .skill import AgentProtocolBridgeSkill
from .translators.base import ProtocolTranslator


@pytest.fixture
def skill():
    return AgentProtocolBridgeSkill()


@pytest.fixture
def manifest():
    manifest_path = os.path.join(os.path.dirname(__file__), "manifest.yaml")
    with open(manifest_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Manifest integrity
# ---------------------------------------------------------------------------


def test_manifest_name(skill, manifest):
    assert skill.manifest["name"] == manifest["name"]
    assert manifest["name"] == "dev_tools/agent_protocol_bridge"


def test_manifest_version_is_new(skill, manifest):
    assert manifest["version"] == "0.1.0"


def test_manifest_declares_all_actions(manifest):
    action_enum = set(manifest["parameters"]["properties"]["action"]["enum"])
    assert action_enum == {
        "translate_schema",
        "translate_call",
        "translate_result",
        "translate_messages",
        "format_handshake",
        "service_health",
    }


def test_manifest_declares_all_protocols(manifest):
    protocols = set(manifest["parameters"]["properties"]["source_protocol"]["enum"])
    assert protocols == {
        "mcp",
        "openai",
        "langchain",
        "anthropic",
        "autogpt",
        "skillware",
    }


# ---------------------------------------------------------------------------
# Skill dispatch
# ---------------------------------------------------------------------------


def test_execute_rejects_unknown_action(skill):
    result = skill.execute({"action": "nope"})
    assert result["status"] == "error"
    assert "Unknown action" in result["message"]


def test_execute_stubs_every_declared_action(skill):
    """Every declared action must return a well-shaped envelope, even now."""
    for action in [
        "translate_schema",
        "translate_call",
        "translate_result",
        "translate_messages",
        "format_handshake",
        "service_health",
    ]:
        result = skill.execute({"action": action})
        assert result["status"] in {"ready", "error"}
        assert result.get("action") == action


# ---------------------------------------------------------------------------
# ProtocolTranslator ABC contract
# ---------------------------------------------------------------------------


def test_protocol_translator_cannot_be_instantiated():
    with pytest.raises(TypeError):
        ProtocolTranslator()  # type: ignore[abstract]


def test_protocol_translator_subclass_must_implement_all_methods():
    class Incomplete(ProtocolTranslator):
        @property
        def protocol_id(self):
            return "incomplete"

    with pytest.raises(TypeError):
        Incomplete()  # type: ignore[abstract]


def test_protocol_translator_minimal_subclass_works():
    class Echo(ProtocolTranslator):
        @property
        def protocol_id(self):
            return "echo"

        def to_canonical(self, data):
            return data

        def from_canonical(self, canonical):
            return canonical

    translator = Echo()
    assert translator.protocol_id == "echo"
    assert translator.to_canonical({"x": 1}) == {"x": 1}
    assert translator.from_canonical({"y": 2}) == {"y": 2}
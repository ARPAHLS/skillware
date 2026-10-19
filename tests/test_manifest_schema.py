# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""Tests for Manifest v2 core schema, validation, and normalization."""

from skillware.core.base_skill import BaseSkill
from skillware.core.manifest_schema import (
    DEFAULT_SHAPE,
    DEFAULT_TAGS,
    DEFAULT_TARGET,
    DEFAULT_TIER,
    VALID_SHAPES,
    VALID_TARGETS,
    VALID_TIERS,
    normalize_manifest_v2,
    validate_manifest_schema,
)


def test_taxonomy_constants():
    assert VALID_SHAPES == ("atomic", "workflow", "middleware", "stream")
    assert VALID_TIERS == ("core", "cloud", "enterprise")
    assert VALID_TARGETS == ("software", "hardware", "bioware")
    assert DEFAULT_SHAPE == "atomic"
    assert DEFAULT_TIER == "core"
    assert DEFAULT_TARGET == ["software"]
    assert DEFAULT_TAGS == []


def test_validate_manifest_schema_valid_minimal():
    data = {
        "name": "category/test_skill",
        "version": "1.0.0",
        "description": "A test skill.",
    }
    errors = validate_manifest_schema(data, skill_id="category/test_skill")
    assert errors == []


def test_validate_manifest_schema_valid_full_v2():
    data = {
        "name": "robotics/ur5_arm",
        "version": "0.1.0",
        "shape": "workflow",
        "tier": "enterprise",
        "target": ["software", "hardware"],
        "tags": ["robotics", "kinematics", "ros2"],
        "description": "Trajectory planning.",
        "short_description": "Robotic arm controller.",
        "issuer": {
            "name": "Robotics Lab",
            "email": "dev@example.com",
            "github": "robotics-dev",
            "org": "ARPAHLS",
        },
        "requirements": ["pybullet"],
        "parameters": {"type": "object"},
        "outputs": {"type": "object"},
        "constitution": "Safety limits strictly enforced.",
        "presentation": {"icon": "cpu", "color": "#2ECC71"},
    }
    errors = validate_manifest_schema(data, skill_id="robotics/ur5_arm")
    assert errors == []


def test_validate_manifest_schema_invalid_shape():
    data = {
        "name": "category/test_skill",
        "version": "1.0.0",
        "shape": "continuous",  # invalid shape
        "description": "Test.",
    }
    errors = validate_manifest_schema(data)
    assert any("Invalid shape" in err or "shape" in err for err in errors)


def test_validate_manifest_schema_invalid_tier():
    data = {
        "name": "category/test_skill",
        "version": "1.0.0",
        "tier": "ultimate",  # invalid tier
        "description": "Test.",
    }
    errors = validate_manifest_schema(data)
    assert any("Invalid tier" in err or "tier" in err for err in errors)


def test_validate_manifest_schema_invalid_target():
    # Target not a list
    data1 = {
        "name": "category/test_skill",
        "version": "1.0.0",
        "target": "software",
        "description": "Test.",
    }
    errors1 = validate_manifest_schema(data1)
    assert len(errors1) > 0

    # Target containing invalid substrate
    data2 = {
        "name": "category/test_skill",
        "version": "1.0.0",
        "target": ["software", "quantum"],
        "description": "Test.",
    }
    errors2 = validate_manifest_schema(data2)
    assert any("Invalid target substrate" in err or "target" in err for err in errors2)

    # Empty target list
    data3 = {
        "name": "category/test_skill",
        "version": "1.0.0",
        "target": [],
        "description": "Test.",
    }
    errors3 = validate_manifest_schema(data3)
    assert len(errors3) > 0


def test_validate_manifest_schema_invalid_tags():
    # Uppercase tag
    data1 = {
        "name": "category/test_skill",
        "version": "1.0.0",
        "tags": ["AML"],
        "description": "Test.",
    }
    errors1 = validate_manifest_schema(data1)
    assert any("Invalid tag" in err or "tags" in err for err in errors1)

    # Tag with spaces or special characters
    data2 = {
        "name": "category/test_skill",
        "version": "1.0.0",
        "tags": ["web scraping!"],
        "description": "Test.",
    }
    errors2 = validate_manifest_schema(data2)
    assert any("Invalid tag" in err or "tags" in err for err in errors2)

    # Tags not a list
    data3 = {
        "name": "category/test_skill",
        "version": "1.0.0",
        "tags": "not_a_list",
        "description": "Test.",
    }
    errors3 = validate_manifest_schema(data3)
    assert any("Tags must be a list" in err or "tags" in err for err in errors3)


def test_validate_manifest_schema_missing_required_fields():
    data = {"version": "1.0.0"}
    errors = validate_manifest_schema(data)
    assert any("name" in err for err in errors)
    assert any("description" in err for err in errors)


def test_validate_manifest_schema_non_mapping():
    errors = validate_manifest_schema(["not", "a", "dict"])
    assert any("must be a mapping" in err for err in errors)


def test_normalize_manifest_v2_legacy_fallback():
    legacy_manifest = {
        "name": "compliance/legacy_check",
        "version": "0.1.0",
        "description": "Legacy skill without v2 keys.",
    }
    normalized = normalize_manifest_v2(legacy_manifest)

    # Original fields preserved
    assert normalized["name"] == "compliance/legacy_check"
    assert normalized["version"] == "0.1.0"
    assert normalized["description"] == "Legacy skill without v2 keys."

    # v2 defaults populated
    assert normalized["shape"] == DEFAULT_SHAPE
    assert normalized["tier"] == DEFAULT_TIER
    assert normalized["target"] == DEFAULT_TARGET
    assert normalized["tags"] == DEFAULT_TAGS


def test_normalize_manifest_v2_preserves_explicit_values():
    explicit = {
        "name": "security/guard",
        "version": "1.0.0",
        "shape": "middleware",
        "tier": "enterprise",
        "target": ["hardware", "software"],
        "tags": ["security", "guard", "firewall"],
        "description": "Guard skill.",
    }
    normalized = normalize_manifest_v2(explicit)
    assert normalized["shape"] == "middleware"
    assert normalized["tier"] == "enterprise"
    assert normalized["target"] == ["hardware", "software"]
    assert normalized["tags"] == ["security", "guard", "firewall"]


def test_normalize_manifest_v2_cleans_dirty_input():
    dirty = {
        "name": "bci/filter",
        "version": "0.1.0",
        "shape": "  STREAM  ",
        "tier": " CORE ",
        "target": ["BIOWARE", "software", "INVALID_SUBSTRATE", "bioware"],
        "tags": ["EEG", "Signal_Processing", ""],
    }
    normalized = normalize_manifest_v2(dirty)
    assert normalized["shape"] == "stream"
    assert normalized["tier"] == "core"
    assert normalized["target"] == ["bioware", "software"]
    assert normalized["tags"] == ["eeg", "signal_processing"]


def test_normalize_manifest_v2_empty_dict():
    normalized = normalize_manifest_v2({})
    assert normalized["shape"] == DEFAULT_SHAPE
    assert normalized["tier"] == DEFAULT_TIER
    assert normalized["target"] == DEFAULT_TARGET
    assert normalized["tags"] == DEFAULT_TAGS


def test_base_skill_v2_properties():
    class DummySkill(BaseSkill):
        @property
        def manifest(self):
            return {
                "name": "test/dummy",
                "version": "1.0.0",
                "shape": "middleware",
                "tier": "cloud",
                "target": ["software", "hardware"],
                "tags": ["test", "demo"],
            }

        def execute(self, params):
            return {"status": "ok"}

    skill = DummySkill()
    assert skill.shape == "middleware"
    assert skill.tier == "cloud"
    assert skill.target == ["software", "hardware"]
    assert skill.tags == ["test", "demo"]


def test_base_skill_v2_defaults_on_legacy_manifest():
    class LegacySkill(BaseSkill):
        @property
        def manifest(self):
            return {
                "name": "test/legacy",
                "version": "1.0.0",
                # shape, tier, target, tags omitted
            }

        def execute(self, params):
            return {"status": "ok"}

    skill = LegacySkill()
    assert skill.shape == "atomic"
    assert skill.tier == "core"
    assert skill.target == ["software"]
    assert skill.tags == []

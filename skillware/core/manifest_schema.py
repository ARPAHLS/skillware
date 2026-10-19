# Copyright (c) 2026 ARPA Hellenic Logical Systems
# SPDX-License-Identifier: MIT

"""
Manifest v2 core schema definitions, validation helpers, and default normalizers.

Defines the four orthogonal taxonomy primitives for Skillware packages:
1. shape: ("atomic", "workflow", "middleware", "stream")
2. tier: ("core", "cloud", "enterprise")
3. target: subset of ("software", "hardware", "bioware")
4. tags: list of lowercase alphanumeric semantic keywords ([a-z0-9_-]+)
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional

from jsonschema import Draft7Validator

# -----------------------------------------------------------------------------
# Universal Taxonomy Primitives
# -----------------------------------------------------------------------------

VALID_SHAPES = ("atomic", "workflow", "middleware", "stream")
VALID_TIERS = ("core", "cloud", "enterprise")
VALID_TARGETS = ("software", "hardware", "bioware")

DEFAULT_SHAPE = "atomic"
DEFAULT_TIER = "core"
DEFAULT_TARGET = ["software"]
DEFAULT_TAGS: List[str] = []

TAG_PATTERN = r"^[a-z0-9_-]+$"
TAG_REGEX = re.compile(TAG_PATTERN)

# -----------------------------------------------------------------------------
# JSON Schema Definition for Manifest v2
# -----------------------------------------------------------------------------

MANIFEST_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "version": {"type": "string"},
        "shape": {"type": "string", "enum": list(VALID_SHAPES)},
        "tier": {"type": "string", "enum": list(VALID_TIERS)},
        "target": {
            "type": "array",
            "items": {"type": "string", "enum": list(VALID_TARGETS)},
            "minItems": 1,
            "uniqueItems": True,
        },
        "tags": {
            "type": "array",
            "items": {"type": "string", "pattern": TAG_PATTERN},
            "uniqueItems": True,
        },
        "description": {"type": "string"},
        "short_description": {"type": "string"},
        "issuer": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "email": {"type": "string"},
                "github": {"type": "string"},
                "org": {"type": "string"},
            },
        },
        "parameters": {"type": "object"},
        "outputs": {"type": "object"},
        "category": {"type": "string"},
        "constitution": {"type": ["string", "object"]},
        "env_vars": {"type": "object"},
        "presentation": {
            "type": "object",
            "properties": {
                "icon": {"type": "string"},
                "color": {"type": "string"},
            },
        },
        "requirements": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["name", "version", "description"],
}

_MANIFEST_VALIDATOR = Draft7Validator(MANIFEST_SCHEMA)


def validate_manifest_schema(
    data: Mapping[str, Any],
    skill_id: Optional[str] = None,
) -> List[str]:
    """
    Validate a manifest dictionary against the Manifest v2 JSON Schema and
    domain-specific rules.

    Returns a list of human-readable error strings. Returns an empty list if
    the manifest is fully compliant.
    """
    if not isinstance(data, Mapping):
        prefix = f"Skill '{skill_id}': " if skill_id else ""
        return [f"{prefix}Manifest must be a mapping/dict, got {type(data).__name__}."]

    errors: List[str] = []
    prefix = f"Skill '{skill_id}': " if skill_id else ""

    # 1. Structural validation via jsonschema
    for err in sorted(_MANIFEST_VALIDATOR.iter_errors(data), key=lambda e: str(e.path)):
        path = ".".join(str(p) for p in err.absolute_path) or "(root)"
        errors.append(f"{prefix}Schema error at '{path}': {err.message}")

    # 2. Targeted validation for shape, tier, target, tags if present
    shape = data.get("shape")
    if shape is not None:
        normalized_shape = str(shape).strip().lower()
        if normalized_shape not in VALID_SHAPES:
            errors.append(
                f"{prefix}Invalid shape '{shape}'. Must be one of: {', '.join(VALID_SHAPES)}."
            )

    tier = data.get("tier")
    if tier is not None:
        normalized_tier = str(tier).strip().lower()
        if normalized_tier not in VALID_TIERS:
            errors.append(
                f"{prefix}Invalid tier '{tier}'. Must be one of: {', '.join(VALID_TIERS)}."
            )

    target = data.get("target")
    if target is not None:
        if not isinstance(target, list) or not target:
            errors.append(
                f"{prefix}Target must be a non-empty list of substrates: {', '.join(VALID_TARGETS)}."
            )
        else:
            for item in target:
                if str(item).strip().lower() not in VALID_TARGETS:
                    errors.append(
                        f"{prefix}Invalid target substrate '{item}'. Must be one of: {', '.join(VALID_TARGETS)}."
                    )

    tags = data.get("tags")
    if tags is not None:
        if not isinstance(tags, list):
            errors.append(f"{prefix}Tags must be a list of lowercase string keywords.")
        else:
            for tag in tags:
                if not isinstance(tag, str) or not TAG_REGEX.match(tag.strip()):
                    errors.append(
                        f"{prefix}Invalid tag '{tag}'. Tags must be lowercase alphanumeric, "
                        f"hyphens, or underscores matching '{TAG_PATTERN}'."
                    )

    return sorted(list(set(errors)))


def normalize_manifest_v2(data: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Return a normalized copy of the manifest with v2 defaults applied for any
    omitted taxonomy fields.

    Ensures backward compatibility for legacy v1 manifests:
    - shape: defaults to "atomic"
    - tier: defaults to "core"
    - target: defaults to ["software"]
    - tags: defaults to []
    """
    normalized = dict(data) if data else {}

    # 1. Normalize shape
    raw_shape = normalized.get("shape")
    if raw_shape is not None and str(raw_shape).strip().lower() in VALID_SHAPES:
        normalized["shape"] = str(raw_shape).strip().lower()
    else:
        normalized["shape"] = DEFAULT_SHAPE

    # 2. Normalize tier
    raw_tier = normalized.get("tier")
    if raw_tier is not None and str(raw_tier).strip().lower() in VALID_TIERS:
        normalized["tier"] = str(raw_tier).strip().lower()
    else:
        normalized["tier"] = DEFAULT_TIER

    # 3. Normalize target
    raw_target = normalized.get("target")
    if isinstance(raw_target, list) and raw_target:
        cleaned_targets = [
            str(item).strip().lower()
            for item in raw_target
            if str(item).strip().lower() in VALID_TARGETS
        ]
        # remove duplicates while preserving order
        deduped_targets: List[str] = []
        for t in cleaned_targets:
            if t not in deduped_targets:
                deduped_targets.append(t)
        normalized["target"] = deduped_targets or list(DEFAULT_TARGET)
    else:
        normalized["target"] = list(DEFAULT_TARGET)

    # 4. Normalize tags
    raw_tags = normalized.get("tags")
    if isinstance(raw_tags, list):
        cleaned_tags = [str(item).strip().lower() for item in raw_tags if item]
        deduped_tags: List[str] = []
        for t in cleaned_tags:
            if t not in deduped_tags:
                deduped_tags.append(t)
        normalized["tags"] = deduped_tags
    else:
        normalized["tags"] = list(DEFAULT_TAGS)

    return normalized

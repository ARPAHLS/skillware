"""Helpers for validating card.json ui_schema field keys against skill output."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Sequence, Union

JsonObject = Dict[str, Any]


def resolve_dot_path(data: Mapping[str, Any], path: str) -> Any:
    """Resolve a dot-separated path against a nested mapping.

    Raises:
        KeyError: if any segment is missing.
        TypeError: if a segment is not a mapping when further segments remain.
    """
    if not path or not path.strip():
        raise KeyError("empty path")

    current: Any = data
    for segment in path.split("."):
        if not isinstance(current, Mapping):
            raise KeyError(path)
        if segment not in current:
            raise KeyError(path)
        current = current[segment]
    return current


def path_exists(data: Mapping[str, Any], path: str) -> bool:
    """Return True when ``path`` resolves in ``data``."""
    try:
        resolve_dot_path(data, path)
    except (KeyError, TypeError):
        return False
    return True


def is_output_card_ui_schema(ui_schema: Any) -> bool:
    """True when ui_schema declares output card fields (type=card + fields list)."""
    if not isinstance(ui_schema, Mapping):
        return False
    if ui_schema.get("type") != "card":
        return False
    fields = ui_schema.get("fields")
    return isinstance(fields, list) and bool(fields)


def extract_card_field_keys(ui_schema: Mapping[str, Any]) -> List[str]:
    """Return ui_schema.fields[].key values for output card schemas."""
    if not is_output_card_ui_schema(ui_schema):
        return []

    keys: List[str] = []
    for field in ui_schema.get("fields", []):
        if not isinstance(field, Mapping):
            continue
        key = field.get("key")
        if isinstance(key, str) and key.strip():
            keys.append(key.strip())
    return keys


def missing_keys_for_samples(
    samples: Sequence[Mapping[str, Any]], keys: Iterable[str]
) -> List[str]:
    """Return field keys that do not resolve in any sample output."""
    key_list = list(keys)
    missing: List[str] = []
    for key in key_list:
        if not any(path_exists(sample, key) for sample in samples):
            missing.append(key)
    return missing


def normalize_fixture_samples(
    payload: Union[JsonObject, Sequence[JsonObject]],
) -> List[JsonObject]:
    """Accept a single output object or {"samples": [...]} fixture payload."""
    if isinstance(payload, Mapping) and "samples" in payload:
        raw_samples = payload.get("samples")
        if not isinstance(raw_samples, list) or not raw_samples:
            raise ValueError("fixture samples must be a non-empty list")
        return [sample for sample in raw_samples if isinstance(sample, Mapping)]

    if isinstance(payload, Mapping):
        return [payload]

    raise ValueError("fixture must be an object or a samples list wrapper")


def validate_card_ui_schema(
    ui_schema: Mapping[str, Any], samples: Sequence[Mapping[str, Any]]
) -> List[str]:
    """Validate output card field keys against one or more execute() samples."""
    keys = extract_card_field_keys(ui_schema)
    if not keys:
        return []
    return missing_keys_for_samples(samples, keys)

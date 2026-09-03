"""Parse and merge skill chain definitions from Skillware YAML config."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class StepWhen:
    """Conditional skip: run step only when prior output field equals value."""

    prior_step: str
    field: str
    equals: Any

    @classmethod
    def from_dict(cls, raw: Any) -> Optional[StepWhen]:
        if not isinstance(raw, dict):
            return None
        prior = raw.get("prior_step")
        fld = raw.get("field")
        if prior is None or fld is None or "equals" not in raw:
            return None
        return cls(
            prior_step=str(prior).strip(),
            field=str(fld).strip(),
            equals=raw.get("equals"),
        )


@dataclass(frozen=True)
class ChainStep:
    skill: str
    step_id: Optional[str] = None
    params: Dict[str, Any] = field(default_factory=dict)
    input_from: Dict[str, str] = field(default_factory=dict)
    map_out: Dict[str, str] = field(default_factory=dict)
    when: Optional[StepWhen] = None

    @classmethod
    def from_dict(cls, raw: Any) -> Optional[ChainStep]:
        if not isinstance(raw, dict):
            return None
        skill = raw.get("skill")
        if not skill or not str(skill).strip():
            return None
        params = raw.get("params")
        input_from = raw.get("input_from")
        map_out = raw.get("map_out")
        step_id = raw.get("id")
        return cls(
            skill=str(skill).strip(),
            step_id=str(step_id).strip() if step_id is not None else None,
            params=dict(params) if isinstance(params, dict) else {},
            input_from=dict(input_from) if isinstance(input_from, dict) else {},
            map_out=dict(map_out) if isinstance(map_out, dict) else {},
            when=StepWhen.from_dict(raw.get("when")),
        )


@dataclass(frozen=True)
class ChainDefinition:
    name: str
    description: str = ""
    when: str = ""
    stop_on_error: bool = True
    steps: Tuple[ChainStep, ...] = ()

    @classmethod
    def from_dict(cls, name: str, raw: Mapping[str, Any]) -> Optional[ChainDefinition]:
        if not isinstance(raw, Mapping) or "steps" not in raw:
            return None
        steps_raw = raw.get("steps")
        if not isinstance(steps_raw, list) or not steps_raw:
            return None
        steps: List[ChainStep] = []
        for entry in steps_raw:
            step = ChainStep.from_dict(entry)
            if step is None:
                return None
            steps.append(step)
        stop_raw = raw.get("stop_on_error", True)
        return cls(
            name=name,
            description=str(raw.get("description") or "").strip(),
            when=str(raw.get("when") or "").strip(),
            stop_on_error=bool(stop_raw) if stop_raw is not None else True,
            steps=tuple(steps),
        )


def parse_chains_block(
    raw: Any,
) -> Tuple[Dict[str, ChainDefinition], Dict[str, Any]]:
    """
    Parse a YAML ``chains:`` block.

    Returns ``(definitions, legacy_entries)`` where legacy entries lack a valid
    ``steps`` list (e.g. ``default: []`` placeholders).
    """
    if not isinstance(raw, dict):
        return {}, {}

    definitions: Dict[str, ChainDefinition] = {}
    legacy: Dict[str, Any] = {}

    for name, entry in raw.items():
        key = str(name).strip()
        if not key:
            continue
        if not isinstance(entry, dict) or "steps" not in entry:
            legacy[key] = entry
            continue
        definition = ChainDefinition.from_dict(key, entry)
        if definition is None:
            legacy[key] = entry
            continue
        definitions[key] = definition

    return definitions, legacy


def merge_chain_layers(
    layers: Sequence[Mapping[str, Any]],
) -> Tuple[Dict[str, ChainDefinition], Dict[str, Any]]:
    """Merge chain definitions; later layers override names. Collect legacy fragments."""
    merged: Dict[str, ChainDefinition] = {}
    legacy: Dict[str, Any] = {}

    for layer_data in layers:
        raw = layer_data.get("chains")
        if raw is None:
            continue
        parsed, legacy_part = parse_chains_block(raw)
        merged.update(parsed)
        if legacy_part:
            legacy.update(legacy_part)

    return merged, legacy

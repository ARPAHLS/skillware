"""Deterministic skill chain execution and validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union
from skillware.core.chains_config import ChainDefinition, ChainStep, StepWhen
from skillware.core.config import load_merged_config
from skillware.core.loader import SkillLoader


def _dot_get(obj: Any, path: str) -> Any:
    if not path:
        return obj
    current = obj
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


_MISSING = object()


def _resolve_binding(
    binding: str,
    *,
    host_input: Mapping[str, Any],
    next_params: Mapping[str, Any],
    prev_output: Optional[Mapping[str, Any]],
) -> Any:
    text = str(binding).strip()
    if not text or "." not in text:
        return _MISSING

    prefix, remainder = text.split(".", 1)
    if prefix == "host":
        return _dot_get(dict(host_input), remainder)
    if prefix == "next":
        return _dot_get(dict(next_params), remainder)
    if prefix == "prev":
        if prev_output is None:
            return _MISSING
        return _dot_get(dict(prev_output), remainder)
    return _MISSING


def _apply_map_out(
    output: Mapping[str, Any],
    map_out: Mapping[str, str],
    *,
    host_input: Dict[str, Any],
    next_params: Dict[str, Any],
) -> None:
    for source_key, target in map_out.items():
        value = (
            _dot_get(output, source_key)
            if "." in source_key
            else output.get(source_key)
        )
        if value is _MISSING:
            continue
        target = str(target).strip()
        if target.startswith("next."):
            next_params[target.split(".", 1)[1]] = value
        elif target.startswith("host."):
            host_input[target.split(".", 1)[1]] = value


def _step_index_for_ref(
    ref: str,
    steps: Sequence[ChainStep],
    current_index: int,
    step_outputs: Sequence[Optional[Mapping[str, Any]]],
    step_ids: Sequence[Optional[str]],
) -> Optional[int]:
    ref = ref.strip()
    if ref.isdigit():
        idx = int(ref)
        return idx if 0 <= idx < current_index else None
    for idx in range(current_index):
        if step_ids[idx] == ref or steps[idx].skill == ref:
            return idx
    return None


def _evaluate_when(
    when: StepWhen,
    *,
    steps: Sequence[ChainStep],
    step_index: int,
    step_outputs: Sequence[Optional[Mapping[str, Any]]],
    step_ids: Sequence[Optional[str]],
) -> bool:
    prior_idx = _step_index_for_ref(
        when.prior_step, steps, step_index, step_outputs, step_ids
    )
    if prior_idx is None:
        return False
    prior_out = step_outputs[prior_idx]
    if prior_out is None:
        return False
    value = _dot_get(dict(prior_out), when.field)
    if value is _MISSING:
        return False
    return value == when.equals


def _build_step_params(
    step: ChainStep,
    *,
    host_input: Mapping[str, Any],
    next_params: Mapping[str, Any],
    prev_output: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    params = dict(step.params)
    for param_name, binding in step.input_from.items():
        resolved = _resolve_binding(
            binding,
            host_input=host_input,
            next_params=next_params,
            prev_output=prev_output,
        )
        if resolved is not _MISSING:
            params[param_name] = resolved
    for key, value in next_params.items():
        params.setdefault(key, value)
    return params


def _is_error_output(output: Any) -> bool:
    if not isinstance(output, dict):
        return False
    status = output.get("status")
    if isinstance(status, str) and status.lower() in {"error", "failed", "failure"}:
        return True
    if output.get("error"):
        return True
    return False


@dataclass(frozen=True)
class ChainStepResult:
    index: int
    skill_id: str
    status: str
    output: Optional[Dict[str, Any]] = None
    skip_reason: Optional[str] = None


@dataclass(frozen=True)
class ChainResult:
    chain_name: str
    status: str
    steps: Tuple[ChainStepResult, ...]
    final: Optional[Dict[str, Any]] = None
    errors: Tuple[str, ...] = ()


class ChainValidationError(ValueError):
    """Raised when a chain definition or runtime validation fails."""


def list_chains(*, refresh: bool = False) -> Dict[str, ChainDefinition]:
    return dict(load_merged_config(refresh=refresh).chains)


def load_chain(name: str, *, refresh: bool = False) -> ChainDefinition:
    chains = list_chains(refresh=refresh)
    if name not in chains:
        raise ChainValidationError(f"Unknown chain: {name!r}")
    return chains[name]


def _collect_host_keys(steps: Sequence[ChainStep]) -> List[str]:
    keys: List[str] = []
    seen: set[str] = set()
    for step in steps:
        for binding in step.input_from.values():
            text = str(binding).strip()
            if text.startswith("host."):
                key = text.split(".", 1)[1]
                if key not in seen:
                    seen.add(key)
                    keys.append(key)
    return keys


def validate_chain(
    name_or_definition: Union[str, ChainDefinition],
    *,
    strict: bool = False,
    refresh: bool = False,
) -> List[str]:
    """
    Validate chain structure and skill resolution.

    Returns warnings. Raises ``ChainValidationError`` when ``strict`` and errors exist.
    """
    if isinstance(name_or_definition, str):
        definition = load_chain(name_or_definition, refresh=refresh)
    else:
        definition = name_or_definition
    return _validate_definition(definition, strict=strict)


def _validate_definition(definition: ChainDefinition, *, strict: bool) -> List[str]:
    errors: List[str] = []
    warnings_out: List[str] = []

    step_ids: List[Optional[str]] = []
    for idx, step in enumerate(definition.steps):
        sid = step.step_id or step.skill
        if sid in step_ids:
            errors.append(f"Duplicate step id/reference {sid!r} at index {idx}")

        if step.when is not None:
            prior_idx = _step_index_for_ref(
                step.when.prior_step,
                definition.steps,
                idx,
                [None] * idx,
                step_ids,
            )
            if prior_idx is None:
                errors.append(
                    f"Step {idx} when.prior_step {step.when.prior_step!r} "
                    "must reference an earlier step"
                )

        try:
            SkillLoader.load_skill(step.skill, execute_module=False)
        except FileNotFoundError:
            msg = f"Step {idx}: skill not found: {step.skill!r}"
            if strict:
                errors.append(msg)
            else:
                warnings_out.append(msg)
        except Exception as exc:  # pragma: no cover
            warnings_out.append(f"Step {idx}: {step.skill!r}: {exc}")

        step_ids.append(step.step_id)

    if errors:
        raise ChainValidationError("; ".join(errors))
    return warnings_out


def run_chain(
    name_or_definition: Union[str, ChainDefinition],
    *,
    host_input: Optional[Mapping[str, Any]] = None,
    stop_on_error: Optional[bool] = None,
    validate_params: bool = True,
    check_requirements: bool = True,
    dry_run: bool = False,
) -> ChainResult:
    if isinstance(name_or_definition, str):
        definition = load_chain(name_or_definition)
        chain_name = name_or_definition
    else:
        definition = name_or_definition
        chain_name = definition.name

    host: Dict[str, Any] = dict(host_input or {})
    stop = definition.stop_on_error if stop_on_error is None else stop_on_error

    step_results: List[ChainStepResult] = []
    step_outputs: List[Optional[Dict[str, Any]]] = []
    step_ids: List[Optional[str]] = []
    next_params: Dict[str, Any] = {}
    prev_executed_output: Optional[Dict[str, Any]] = None
    errors: List[str] = []
    final: Optional[Dict[str, Any]] = None

    for index, step in enumerate(definition.steps):
        if step.when is not None and not _evaluate_when(
            step.when,
            steps=definition.steps,
            step_index=index,
            step_outputs=step_outputs,
            step_ids=step_ids,
        ):
            step_results.append(
                ChainStepResult(
                    index=index,
                    skill_id=step.skill,
                    status="skipped",
                    skip_reason="when condition not met",
                )
            )
            step_outputs.append(None)
            step_ids.append(step.step_id)
            continue

        params = _build_step_params(
            step,
            host_input=host,
            next_params=next_params,
            prev_output=prev_executed_output,
        )
        next_params = {}

        if dry_run:
            step_results.append(
                ChainStepResult(
                    index=index,
                    skill_id=step.skill,
                    status="ok",
                    output=params,
                )
            )
            step_outputs.append(params)
            prev_executed_output = params
            final = params
            step_ids.append(step.step_id)
            continue

        try:
            bundle = SkillLoader.load_skill(
                step.skill,
                check_requirements=check_requirements,
                execute_module=True,
            )
            skill_cls = SkillLoader.get_skill_class(bundle)
            skill = skill_cls()
            if validate_params:
                skill.validate_params(params)
            raw_output = skill.execute(params)
            output = (
                dict(raw_output)
                if isinstance(raw_output, dict)
                else {"result": raw_output}
            )
        except Exception as exc:
            step_results.append(
                ChainStepResult(
                    index=index,
                    skill_id=step.skill,
                    status="failed",
                    output={"error": str(exc)},
                )
            )
            step_outputs.append(None)
            step_ids.append(step.step_id)
            errors.append(f"Step {index} ({step.skill}): {exc}")
            if stop:
                return ChainResult(
                    chain_name=chain_name,
                    status="failed",
                    steps=tuple(step_results),
                    final=final,
                    errors=tuple(errors),
                )
            continue

        if _is_error_output(output):
            step_results.append(
                ChainStepResult(
                    index=index,
                    skill_id=step.skill,
                    status="failed",
                    output=output,
                )
            )
            step_outputs.append(None)
            step_ids.append(step.step_id)
            errors.append(f"Step {index} ({step.skill}): error-shaped output")
            if stop:
                return ChainResult(
                    chain_name=chain_name,
                    status="failed",
                    steps=tuple(step_results),
                    final=final,
                    errors=tuple(errors),
                )
            continue

        _apply_map_out(output, step.map_out, host_input=host, next_params=next_params)
        step_results.append(
            ChainStepResult(
                index=index,
                skill_id=step.skill,
                status="ok",
                output=output,
            )
        )
        step_outputs.append(output)
        prev_executed_output = output
        final = output
        step_ids.append(step.step_id)

    statuses = {s.status for s in step_results}
    if "failed" in statuses:
        overall = "failed"
    elif "skipped" in statuses:
        overall = "partial"
    else:
        overall = "ok"

    return ChainResult(
        chain_name=chain_name,
        status=overall,
        steps=tuple(step_results),
        final=final,
        errors=tuple(errors),
    )


def required_host_input_keys(definition: ChainDefinition) -> List[str]:
    return _collect_host_keys(definition.steps)

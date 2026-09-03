"""Registry host context for multi-skill agent sessions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from skillware.core.discovery import (
    SkillRoot,
    find_shadow_conflicts,
    get_skill_roots,
    list_registry_skill_ids,
)
from skillware.core.loader import SkillLoader

ContextMode = str  # brief | tools_only | directives


@dataclass(frozen=True)
class PreparedSkill:
    skill_id: str
    directive: str
    manifest: Mapping[str, Any]
    bundle: Mapping[str, Any]


def _normalize_categories(raw: Optional[Sequence[str]]) -> Optional[frozenset]:
    if raw is None:
        return None
    values = {str(item).strip() for item in raw if str(item).strip()}
    return frozenset(values) if values else None


def _root_matches_filter(
    root: SkillRoot,
    *,
    roots: Optional[Union[str, Path, Sequence[Union[str, Path]]]],
    exclude_roots: Optional[Sequence[str]],
) -> bool:
    if exclude_roots:
        excluded = {str(item).strip().lower() for item in exclude_roots}
        if root.tier.value in excluded:
            return False

    if roots is None:
        return True

    if isinstance(roots, (str, Path)):
        roots_arg: Sequence[Union[str, Path]] = [roots]
    else:
        roots_arg = roots

    for entry in roots_arg:
        text = str(entry).strip().lower()
        if text in {"bundled", "project", "external", "override"}:
            if root.tier.value == text:
                return True
            continue
        path = Path(entry).expanduser().resolve()
        if root.path.resolve() == path:
            return True
    return False


def _discover_skill_ids(
    *,
    skill: Optional[str],
    skills: Optional[Sequence[str]],
    categories: Optional[Sequence[str]],
    roots: Optional[Union[str, Path, Sequence[Union[str, Path]]]],
    exclude_roots: Optional[Sequence[str]],
    max_skills: Optional[int],
) -> Tuple[List[str], List[str], Dict[str, str]]:
    """Return (skill_ids, warnings, trust_tier_by_id)."""
    warnings: List[str] = []
    tier_by_id: Dict[str, str] = {}
    winner_root: Dict[str, SkillRoot] = {}

    if skill is not None:
        sid = str(skill).strip()
        if not sid:
            return [], ["Empty skill filter"], {}
        return [sid], warnings, {sid: "unknown"}

    if skills is not None:
        ids = [str(s).strip() for s in skills if str(s).strip()]
        return ids, warnings, {sid: "unknown" for sid in ids}

    category_set = _normalize_categories(categories)
    roots_list = get_skill_roots()

    for conflict in find_shadow_conflicts(roots_list):
        warnings.append(
            f"Shadowed {conflict.skill_id!r} in {conflict.shadowed.path} "
            f"(winner: {conflict.winner.path})"
        )

    for root in roots_list:
        if not root.exists:
            continue
        if not _root_matches_filter(root, roots=roots, exclude_roots=exclude_roots):
            continue
        for skill_id in list_registry_skill_ids(root.path):
            if skill_id in winner_root:
                continue
            if category_set is not None:
                category = skill_id.split("/", 1)[0]
                if category not in category_set:
                    continue
            winner_root[skill_id] = root
            tier_by_id[skill_id] = root.tier.value

    ids = sorted(winner_root.keys())
    if max_skills is not None and len(ids) > max_skills:
        omitted = ids[max_skills:]
        ids = ids[:max_skills]
        warnings.append(f"max_skills={max_skills} cap omitted: {', '.join(omitted)}")

    return ids, warnings, tier_by_id


def _brief_line(skill_id: str, bundle: Mapping[str, Any], tier: str) -> str:
    manifest = bundle.get("manifest") or {}
    name = manifest.get("name", skill_id)
    short = manifest.get("short_description") or manifest.get("description") or ""
    short = str(short).strip().replace("\n", " ")
    if len(short) > 160:
        short = short[:157] + "..."
    reqs = manifest.get("requirements") or []
    req_hint = ""
    if isinstance(reqs, list) and reqs:
        req_hint = f" deps={','.join(str(r) for r in reqs[:3])}"
    return f"- **{name}** [{tier}]{req_hint}: {short}"


class SkillContext:
    """
    Discovery-aware registry context for multi-skill hosts.

    Uses ``SkillLoader.load_skill(..., execute_module=False)`` for brief assembly;
    full module load on ``prepare()`` / ``execute()``.
    """

    def __init__(
        self,
        *,
        skill: Optional[str] = None,
        skills: Optional[Sequence[str]] = None,
        categories: Optional[Sequence[str]] = None,
        roots: Optional[Union[str, Path, Sequence[Union[str, Path]]]] = None,
        exclude_roots: Optional[Sequence[str]] = None,
        max_skills: Optional[int] = None,
        mode: ContextMode = "brief",
        check_requirements: bool = True,
    ) -> None:
        self.mode = mode if mode in {"brief", "tools_only", "directives"} else "brief"
        self._check_requirements = check_requirements
        self.skill_ids, self.warnings, self._tier_by_id = _discover_skill_ids(
            skill=skill,
            skills=skills,
            categories=categories,
            roots=roots,
            exclude_roots=exclude_roots,
            max_skills=max_skills,
        )
        self._bundles: Dict[str, Dict[str, Any]] = {}
        self._instances: Dict[str, Any] = {}
        self._load_bundles()

    def _load_bundles(self) -> None:
        execute = self.mode == "directives"
        for skill_id in self.skill_ids:
            try:
                self._bundles[skill_id] = SkillLoader.load_skill(
                    skill_id,
                    check_requirements=self._check_requirements,
                    execute_module=execute,
                )
            except Exception as exc:
                self.warnings.append(f"Skipped {skill_id!r}: {exc}")

        self.skill_ids = [sid for sid in self.skill_ids if sid in self._bundles]

    def brief(self, skill_id: str) -> str:
        bundle = self._bundles.get(skill_id)
        if bundle is None:
            bundle = SkillLoader.load_skill(
                skill_id,
                check_requirements=self._check_requirements,
                execute_module=False,
            )
        tier = self._tier_by_id.get(skill_id, "unknown")
        return _brief_line(skill_id, bundle, tier)

    def _system_append(self) -> str:
        if self.mode == "tools_only":
            return ""
        if self.mode == "directives":
            parts: List[str] = []
            for skill_id in self.skill_ids:
                instructions = str(
                    self._bundles[skill_id].get("instructions") or ""
                ).strip()
                if instructions:
                    parts.append(f"## {skill_id}\n{instructions}")
            return ("\n\n".join(parts) + "\n") if parts else ""
        lines = ["## Skill registry (brief)"]
        for skill_id in self.skill_ids:
            lines.append(self.brief(skill_id))
        return "\n".join(lines) + "\n"

    def merge_system(self, system: str) -> str:
        append = self._system_append()
        if not append.strip():
            return system
        if not system:
            return append.strip()
        return system.rstrip() + "\n\n" + append

    def tools(self, provider: str) -> List[Any]:
        provider_key = provider.strip().lower()
        tools: List[Any] = []
        for skill_id in self.skill_ids:
            bundle = self._bundles[skill_id]
            if provider_key == "gemini":
                tools.append(SkillLoader.to_gemini_tool(bundle))
            elif provider_key == "claude":
                tools.append(SkillLoader.to_claude_tool(bundle))
            elif provider_key == "openai":
                tools.append(SkillLoader.to_openai_tool(bundle))
            elif provider_key == "deepseek":
                tools.append(SkillLoader.to_deepseek_tool(bundle))
            else:
                raise ValueError(
                    f"Unknown provider {provider!r}; "
                    "choose gemini, claude, openai, or deepseek"
                )
        return tools

    @property
    def ollama_prompt(self) -> str:
        parts = [
            SkillLoader.to_ollama_prompt(self._bundles[sid]) for sid in self.skill_ids
        ]
        if self.mode == "tools_only":
            return "\n".join(parts)
        return self._system_append() + "\n" + "\n".join(parts)

    def prepare(self, skill_id: str) -> PreparedSkill:
        if (
            skill_id not in self._bundles
            or self._bundles[skill_id].get("class") is None
        ):
            bundle = SkillLoader.load_skill(
                skill_id,
                check_requirements=self._check_requirements,
                execute_module=True,
            )
            self._bundles[skill_id] = bundle
            if skill_id not in self.skill_ids:
                self.skill_ids.append(skill_id)
        bundle = self._bundles[skill_id]
        return PreparedSkill(
            skill_id=skill_id,
            directive=str(bundle.get("instructions") or ""),
            manifest=bundle.get("manifest") or {},
            bundle=bundle,
        )

    def execute(self, skill_id: str, params: Mapping[str, Any]) -> Any:
        prep = self.prepare(skill_id)
        skill_cls = SkillLoader.get_skill_class(dict(prep.bundle))
        if skill_id not in self._instances:
            self._instances[skill_id] = skill_cls()
        instance = self._instances[skill_id]
        instance.validate_params(dict(params))
        return instance.execute(dict(params))

    def call(self, skill_id: str, params: Mapping[str, Any]) -> Any:
        return self.execute(skill_id, params)

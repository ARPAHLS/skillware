"""Persistent Skillware user and project configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import yaml

from skillware.core.chains_config import ChainDefinition, merge_chain_layers
from skillware.core.mail_config import (
    MailSettings,
    merge_mail_settings,
    parse_mail_block,
)

GLOBAL_CONFIG_DIR_ENV = "SKILLWARE_CONFIG_DIR"
PROJECT_CONFIG_FILENAME = ".skillware.yaml"
GLOBAL_CONFIG_FILENAME = "config.yaml"
DEFAULT_PRESENTATION_THEME = "pastel"
SUPPORTED_PRESENTATION_THEMES: Tuple[str, ...] = ("pastel", "ocean", "mono")
_MAX_PARENT_WALK = 6

_DEFAULT_RESOLUTION_ORDER: Tuple[str, ...] = ("project", "external", "bundled")
_VALID_ORDER_TIERS = frozenset({"project", "external", "bundled"})
_PATH_TOP_LEVEL_KEYS = frozenset({"paths", "resolution", "legacy"})
_KNOWN_TOP_LEVEL_KEYS = _PATH_TOP_LEVEL_KEYS | {"mail", "presentation", "chains"}


@dataclass(frozen=True)
class ConfigLayer:
    """One YAML config file that contributed to the merged result."""

    path: Path
    data: Mapping[str, Any]


@dataclass
class PathsSettings:
    """Skill root paths and discovery order (``paths`` + related keys in YAML)."""

    project: Optional[str] = None
    external: List[str] = field(default_factory=list)
    resolution_order: Tuple[str, ...] = _DEFAULT_RESOLUTION_ORDER
    honor_skillware_skill_path: bool = True

    def project_is_auto(self) -> bool:
        return self.project is None or str(self.project).strip().lower() == "auto"


@dataclass
class PresentationSettings:
    """CLI presentation settings from merged configuration."""

    theme: str = DEFAULT_PRESENTATION_THEME


@dataclass
class SkillwareConfig:
    """
    Merged Skillware configuration.

    ``paths``, ``mail``, ``presentation``, and ``chains`` are active settings.
    Additional top-level YAML sections are preserved in ``extra`` for forward
    compatibility and shown by ``skillware config show``.
    """

    paths: PathsSettings = field(default_factory=PathsSettings)
    mail: MailSettings = field(default_factory=MailSettings)
    presentation: PresentationSettings = field(default_factory=PresentationSettings)
    chains: Dict[str, ChainDefinition] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)
    layers: Tuple[ConfigLayer, ...] = ()

    @property
    def has_config_files(self) -> bool:
        return bool(self.layers)


_merged_config_cache: Optional[SkillwareConfig] = None


def clear_config_cache() -> None:
    """Reset cached config (tests only)."""
    global _merged_config_cache
    _merged_config_cache = None


def global_config_dir() -> Path:
    """Return the directory for the global Skillware config file."""
    override = os.environ.get(GLOBAL_CONFIG_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser()

    xdg = os.environ.get("XDG_CONFIG_HOME", "").strip()
    if xdg:
        return Path(xdg).expanduser() / "skillware"

    if os.name == "nt":
        appdata = os.environ.get("APPDATA", "").strip()
        if appdata:
            return Path(appdata) / "skillware"
        return Path.home() / "skillware"

    return Path.home() / ".config" / "skillware"


def global_config_path() -> Path:
    return global_config_dir() / GLOBAL_CONFIG_FILENAME


def find_project_config_file(start: Optional[Path] = None) -> Optional[Path]:
    """Walk up from ``start`` (default cwd) for ``.skillware.yaml``."""
    current = (start or Path.cwd()).resolve()
    for _ in range(_MAX_PARENT_WALK):
        candidate = current / PROJECT_CONFIG_FILENAME
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _read_yaml(path: Path) -> Mapping[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _parse_resolution_order(raw: Any) -> Tuple[str, ...]:
    if not isinstance(raw, list) or not raw:
        return _DEFAULT_RESOLUTION_ORDER

    tiers: List[str] = []
    seen: set[str] = set()
    for item in raw:
        key = str(item).strip().lower()
        if key not in _VALID_ORDER_TIERS or key in seen:
            continue
        seen.add(key)
        tiers.append(key)

    if "bundled" not in seen:
        tiers.append("bundled")

    return tuple(tiers) if tiers else _DEFAULT_RESOLUTION_ORDER


def normalize_presentation_theme(raw: Any) -> str:
    """Return a supported theme name, falling back safely to pastel."""
    if not isinstance(raw, str):
        return DEFAULT_PRESENTATION_THEME
    theme = raw.strip().lower()
    if theme not in SUPPORTED_PRESENTATION_THEMES:
        return DEFAULT_PRESENTATION_THEME
    return theme


def _layer_from_file(path: Path) -> ConfigLayer:
    return ConfigLayer(path=path.resolve(), data=_read_yaml(path))


def _merge_extra_section(
    existing: Dict[str, Any], layer_data: Mapping[str, Any]
) -> Dict[str, Any]:
    merged = dict(existing)
    for key, value in layer_data.items():
        if key in _KNOWN_TOP_LEVEL_KEYS:
            continue
        merged[key] = value
    return merged


def _merge_layers(layers: Sequence[ConfigLayer]) -> SkillwareConfig:
    paths = PathsSettings()
    presentation = PresentationSettings()
    mail_layers: List[MailSettings] = []
    extra: Dict[str, Any] = {}

    for layer in layers:
        extra = _merge_extra_section(extra, layer.data)

        mail_raw = layer.data.get("mail")
        if mail_raw is not None:
            mail_layers.append(parse_mail_block(mail_raw))

        paths_block = layer.data.get("paths")
        if isinstance(paths_block, dict):
            if "project" in paths_block:
                project_value = paths_block.get("project")
                if project_value is None:
                    paths.project = "auto"
                else:
                    paths.project = str(project_value).strip() or "auto"

            raw_external = paths_block.get("external")
            if isinstance(raw_external, list):
                for entry in raw_external:
                    text = str(entry).strip()
                    if text and text not in paths.external:
                        paths.external.append(text)

        resolution_block = layer.data.get("resolution")
        if isinstance(resolution_block, dict) and "order" in resolution_block:
            paths.resolution_order = _parse_resolution_order(
                resolution_block.get("order")
            )

        legacy_block = layer.data.get("legacy")
        if (
            isinstance(legacy_block, dict)
            and "honor_skillware_skill_path" in legacy_block
        ):
            paths.honor_skillware_skill_path = bool(
                legacy_block.get("honor_skillware_skill_path")
            )

        if "presentation" in layer.data:
            presentation_block = layer.data.get("presentation")
            if isinstance(presentation_block, dict) and "theme" in presentation_block:
                presentation.theme = normalize_presentation_theme(
                    presentation_block.get("theme")
                )
            elif not isinstance(presentation_block, dict):
                presentation.theme = DEFAULT_PRESENTATION_THEME

    mail = merge_mail_settings(mail_layers)
    chains, chains_legacy = merge_chain_layers(layer.data for layer in layers)
    if chains_legacy:
        extra = {**extra, "chains": chains_legacy}

    return SkillwareConfig(
        paths=paths,
        mail=mail,
        presentation=presentation,
        chains=chains,
        extra=extra,
        layers=tuple(layers),
    )


def load_merged_config(*, refresh: bool = False) -> SkillwareConfig:
    """
    Load global then project config (walk-up). Later layers override earlier
    fields. Returns a config with ``has_config_files=False`` when no YAML exists.
    """
    global _merged_config_cache
    if not refresh and _merged_config_cache is not None:
        return _merged_config_cache

    layers: List[ConfigLayer] = []
    global_path = global_config_path()
    if global_path.is_file():
        layers.append(_layer_from_file(global_path))

    project_path = find_project_config_file()
    if project_path is not None and (
        not layers or project_path.resolve() != layers[0].path.resolve()
    ):
        layers.append(_layer_from_file(project_path))

    if not layers:
        _merged_config_cache = SkillwareConfig()
        return _merged_config_cache

    _merged_config_cache = _merge_layers(layers)
    return _merged_config_cache


def format_config_sources(config: SkillwareConfig) -> List[str]:
    """Human-readable list of config files that were loaded."""
    if not config.layers:
        return ["(none — implicit env/cwd/bundled resolution)"]
    return [str(layer.path) for layer in config.layers]


def project_config_write_path(start: Optional[Path] = None) -> Path:
    """Path where project path settings should be written."""
    existing = find_project_config_file(start)
    if existing is not None:
        return existing
    return (start or Path.cwd()).resolve() / PROJECT_CONFIG_FILENAME


def load_project_paths_settings(*, start: Optional[Path] = None) -> PathsSettings:
    """Load ``paths`` settings from the project config file only (not global merge)."""
    path = find_project_config_file(start)
    if path is None:
        return PathsSettings()
    return _merge_layers([_layer_from_file(path)]).paths


def paths_settings_to_document(paths: PathsSettings) -> Dict[str, Any]:
    """Serialize path-related settings for YAML persistence."""
    document: Dict[str, Any] = {
        "paths": {
            "project": paths.project if paths.project is not None else "auto",
            "external": list(paths.external),
        },
        "resolution": {"order": list(paths.resolution_order)},
        "legacy": {
            "honor_skillware_skill_path": paths.honor_skillware_skill_path,
        },
    }
    return document


def save_project_config(
    paths: PathsSettings,
    *,
    start: Optional[Path] = None,
    preserve_extra: bool = True,
) -> Path:
    """
    Write project ``paths`` settings to ``.skillware.yaml``.

    Preserves unknown top-level keys from an existing project file when
    ``preserve_extra`` is True. Clears the merged config cache.
    """
    target = project_config_write_path(start)
    target.parent.mkdir(parents=True, exist_ok=True)

    document = paths_settings_to_document(paths)
    if preserve_extra and target.is_file():
        existing = _read_yaml(target)
        for key, value in existing.items():
            if key not in _PATH_TOP_LEVEL_KEYS:
                document[key] = value

    target.write_text(
        yaml.safe_dump(document, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    clear_config_cache()
    return target.resolve()


def save_global_presentation_theme(theme: str) -> Path:
    """Persist a supported presentation theme without replacing other settings."""
    normalized = str(theme).strip().lower()
    if normalized not in SUPPORTED_PRESENTATION_THEMES:
        supported = ", ".join(SUPPORTED_PRESENTATION_THEMES)
        raise ValueError(f"Unknown presentation theme '{theme}'. Choose: {supported}.")

    target = global_config_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    document = dict(_read_yaml(target)) if target.is_file() else {}

    raw_presentation = document.get("presentation")
    presentation = dict(raw_presentation) if isinstance(raw_presentation, dict) else {}
    presentation["theme"] = normalized
    document["presentation"] = presentation

    target.write_text(
        yaml.safe_dump(document, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    clear_config_cache()
    return target.resolve()

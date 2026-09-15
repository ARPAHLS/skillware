"""Pluggable secret resolution for skill runtime credentials."""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Mapping, Optional, Protocol, runtime_checkable


@runtime_checkable
class SecretProvider(Protocol):
    """
    Resolve a credential by manifest ``env_vars`` name.

    Implementations may return static strings (Vault, K8s secrets) or fetch
    ephemeral values on each call (AWS STS via workload identity, Azure
    managed identity, GCP metadata, HashiCorp Vault lease renewal). Callers
    invoke ``get()`` at resolution time — keep fetches out of skill ``execute()``.
    """

    def get(self, key: str) -> Optional[str]:
        """Return the secret value, or ``None`` when unset or empty."""


class EnvSecretProvider:
    """
    Read secrets from ``os.environ``.

    This is the only framework class that should read process-global
    environment variables for skill credentials. Solo-dev and 12-factor hosts
    use this path; production multi-tenant hosts should prefer injected
    providers instead of mutating ``os.environ``.
    """

    def get(self, key: str) -> Optional[str]:
        value = os.environ.get(key)
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class MappingSecretProvider:
    """Inject secrets from an in-memory mapping (host fetched at init)."""

    def __init__(self, secrets: Mapping[str, str]) -> None:
        self._secrets = {str(k): str(v) for k, v in secrets.items() if v is not None}

    def get(self, key: str) -> Optional[str]:
        value = self._secrets.get(key)
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class CallableSecretProvider:
    """Wrap a host callback (Vault, STS, KMS) as a ``SecretProvider``."""

    def __init__(self, fetcher: Callable[[str], Optional[str]]) -> None:
        self._fetcher = fetcher

    def get(self, key: str) -> Optional[str]:
        value = self._fetcher(key)
        if value is None:
            return None
        text = str(value).strip()
        return text or None


def resolve_manifest_env_vars(
    manifest: Mapping[str, Any],
    provider: SecretProvider,
) -> Dict[str, str]:
    """
    Resolve manifest ``env_vars`` keys through ``provider``.

    Calls ``provider.get(key)`` once per declared key. Returns only keys with
    non-empty values for injection into ``BaseSkill(config=...)``.
    """
    env_vars = manifest.get("env_vars")
    if not isinstance(env_vars, dict):
        return {}

    resolved: Dict[str, str] = {}
    for key in env_vars:
        if not isinstance(key, str) or not key.strip():
            continue
        value = provider.get(key)
        if value is not None:
            resolved[key] = value
    return resolved


def audit_manifest_env_vars(
    manifest: Mapping[str, Any],
    provider: Optional[SecretProvider] = None,
) -> tuple[str, str]:
    """
    Check manifest ``env_vars`` against a provider (default ``EnvSecretProvider``).

    Returns ``(status, detail)`` where status is ``ok``, ``fail``, or ``—`` (none declared).
    """
    env_vars = manifest.get("env_vars")
    if not isinstance(env_vars, dict) or not env_vars:
        return "—", ""

    active = provider if provider is not None else EnvSecretProvider()
    resolved = resolve_manifest_env_vars(manifest, active)
    missing_required: list[str] = []
    for key, meta in env_vars.items():
        if not isinstance(key, str) or not key.strip():
            continue
        required = True
        if isinstance(meta, dict):
            required = bool(meta.get("required", False))
        if required and key not in resolved:
            missing_required.append(key)

    if missing_required:
        return "fail", "missing: " + ", ".join(sorted(missing_required))
    return "ok", ""


def coerce_secret_provider(
    provider: Optional[SecretProvider | Mapping[str, str]],
) -> Optional[SecretProvider]:
    if provider is None:
        return None
    if isinstance(provider, Mapping):
        return MappingSecretProvider(provider)
    return provider

"""Pluggable secret resolution for skill runtime credentials."""

from __future__ import annotations

import os
from typing import Any, Dict, Mapping, Optional, Protocol, runtime_checkable


@runtime_checkable
class SecretProvider(Protocol):
    """Resolve a credential by manifest ``env_vars`` name."""

    def get(self, key: str) -> Optional[str]:
        """Return the secret value, or ``None`` when unset or empty."""


class EnvSecretProvider:
    """Read secrets from ``os.environ`` (default local / 12-factor path)."""

    def get(self, key: str) -> Optional[str]:
        value = os.environ.get(key)
        if value is None:
            return None
        text = str(value).strip()
        return text or None


class MappingSecretProvider:
    """Inject secrets from an in-memory mapping (Vault/KMS fetch at host init)."""

    def __init__(self, secrets: Mapping[str, str]) -> None:
        self._secrets = {str(k): str(v) for k, v in secrets.items() if v is not None}

    def get(self, key: str) -> Optional[str]:
        value = self._secrets.get(key)
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

    Returns only keys with non-empty values. Skills may still fall back to
    ``os.environ`` when a key is omitted and the host did not inject config.
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


def coerce_secret_provider(
    provider: Optional[SecretProvider | Mapping[str, str]],
) -> Optional[SecretProvider]:
    if provider is None:
        return None
    if isinstance(provider, Mapping):
        return MappingSecretProvider(provider)
    return provider

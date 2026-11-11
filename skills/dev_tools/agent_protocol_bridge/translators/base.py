"""Abstract interface for protocol translators.

Every protocol translator — MCP, OpenAI, LangChain, Anthropic, AutoGPT,
Skillware — converts its own wire format to and from a shared canonical
form. Cross-protocol translation is then a two-step compose:
``source.to_canonical()`` followed by ``target.from_canonical()``.

The canonical form is intentionally minimal and protocol-agnostic. It is
not part of any public wire format; it exists only inside this skill so
that N protocols need N translators instead of N * (N - 1) pairings.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class ProtocolTranslator(ABC):
    """Contract every protocol translator implements."""

    @property
    @abstractmethod
    def protocol_id(self) -> str:
        """The protocol's short identifier, matching the manifest enum."""
        raise NotImplementedError

    @abstractmethod
    def to_canonical(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a native payload into the canonical form.

        Args:
            data: The protocol-specific input.

        Returns:
            A dict in the shared canonical shape.
        """
        raise NotImplementedError

    @abstractmethod
    def from_canonical(self, canonical: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a canonical payload back into this protocol's shape.

        Args:
            canonical: A dict in the shared canonical shape.

        Returns:
            A dict matching this protocol's wire format.
        """
        raise NotImplementedError
"""Central exception hierarchy for NEXUS."""
from __future__ import annotations

from typing import Any, Mapping


class NexusError(Exception):
    def __init__(self, message: str, *, details: Mapping[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = dict(details) if details else {}

    def __str__(self) -> str:
        if self.details:
            return f"{self.message} details={self.details!r}"
        return self.message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r}, details={self.details!r})"


class ConfigurationError(NexusError):
    pass


class ProviderNotRegisteredError(NexusError):
    pass


class GuardrailViolation(NexusError):
    pass


class ActionExecutionError(NexusError):
    pass


class MemoryError(NexusError):
    pass


class VoicePipelineError(NexusError):
    pass


class AgentError(NexusError):
    pass


class PermissionDeniedError(NexusError):
    pass
"""Provider protocols and shared value objects."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass(frozen=True, slots=True)
class Message:
    role: Role
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class LLMResponse:
    content: str
    model_name: str
    input_tokens: int
    output_tokens: int
    raw: Any = None


@dataclass(frozen=True, slots=True)
class ActionPlan:
    action_type: str
    target: str | None = None
    params: dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    requested_by_agent: str = ""


class GuardrailDecision(str, Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    REQUIRES_CONFIRMATION = "requires_confirmation"


@dataclass(frozen=True, slots=True)
class GuardrailResult:
    decision: GuardrailDecision
    reason: str
    plan: ActionPlan
    confirmation_id: str | None = None


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    success: bool
    output: str
    plan: ActionPlan
    error: str | None = None


@dataclass(frozen=True, slots=True)
class MemoryRecord:
    id: str
    content: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None


# Provider interfaces


@runtime_checkable
class LLMProvider(Protocol):
    async def complete(
        self,
        messages: list[Message],
        *,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.4,
    ) -> LLMResponse:
        ...

    async def stream(
        self,
        messages: list[Message],
        *,
        system_prompt: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.4,
    ):
        ...


@runtime_checkable
class SpeechToTextProvider(Protocol):
    async def transcribe(self, audio_bytes: bytes, *, language: str | None = None) -> str:
        ...

    async def transcribe_stream(self, audio_chunks):
        ...


@runtime_checkable
class TextToSpeechProvider(Protocol):
    async def synthesize(self, text: str, *, voice_id: str, language: str = "en") -> bytes:
        ...

    async def synthesize_stream(self, text: str, *, voice_id: str, language: str = "en"):
        ...


@runtime_checkable
class MemoryStore(Protocol):
    async def add(self, record: MemoryRecord) -> None:
        ...

    async def search(self, query: str, *, top_k: int = 5, filters: dict[str, Any] | None = None) -> list[MemoryRecord]:
        ...

    async def delete(self, record_id: str) -> None:
        ...


@runtime_checkable
class ActionExecutor(Protocol):
    async def execute(self, plan: ActionPlan) -> ExecutionResult:
        ...

    def supports(self, action_type: str) -> bool:
        ...


@runtime_checkable
class GuardrailEngine(Protocol):
    def evaluate(self, plan: ActionPlan) -> GuardrailResult:
        ...


@runtime_checkable
class Agent(Protocol):
    name: str

    async def run(self, state: dict[str, Any]) -> dict[str, Any]:
        ...
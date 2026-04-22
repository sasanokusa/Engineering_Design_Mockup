from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str


@dataclass(frozen=True)
class LLMChatMessage:
    role: str
    content: str


class LLMAdapter(Protocol):
    provider_name: str
    model_name: str

    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Generate text through a local or local-network LLM runtime."""

    def generate_chat(self, *, messages: list[LLMChatMessage]) -> LLMResponse:
        """Generate a response from a chat history."""

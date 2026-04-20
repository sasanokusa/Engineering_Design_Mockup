from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMResponse:
    text: str
    provider: str
    model: str


class LLMAdapter(Protocol):
    provider_name: str
    model_name: str

    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMResponse:
        """Generate text through a local or local-network LLM runtime."""


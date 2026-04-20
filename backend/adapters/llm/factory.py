from __future__ import annotations

from backend.adapters.llm.base import LLMAdapter
from backend.adapters.llm.mock import MockLLMAdapter
from backend.adapters.llm.openai_compatible import OpenAICompatibleLLMAdapter
from backend.config import Settings, get_settings


def create_llm_adapter(settings: Settings | None = None) -> LLMAdapter:
    settings = settings or get_settings()
    provider = settings.llm_provider.lower()
    if provider == "mock":
        return MockLLMAdapter()
    if provider in {"openai_compatible", "openai-compatible", "openai"}:
        return OpenAICompatibleLLMAdapter(settings)
    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.llm_provider}")


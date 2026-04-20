from __future__ import annotations

from backend.adapters.asr.base import ASRAdapter
from backend.adapters.asr.faster_whisper import FasterWhisperASRAdapter
from backend.adapters.asr.mock import MockASRAdapter
from backend.adapters.asr.whisper_cpp import WhisperCppASRAdapter
from backend.config import Settings, get_settings


def create_asr_adapter(settings: Settings | None = None) -> ASRAdapter:
    settings = settings or get_settings()
    provider = settings.asr_provider.lower()
    if provider == "mock":
        return MockASRAdapter()
    if provider in {"whisper_cpp", "whisper.cpp", "whisper-cpp"}:
        return WhisperCppASRAdapter(settings)
    if provider in {"faster_whisper", "faster-whisper"}:
        return FasterWhisperASRAdapter(settings)
    raise ValueError(f"Unsupported ASR_PROVIDER: {settings.asr_provider}")


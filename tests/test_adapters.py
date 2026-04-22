from pathlib import Path

from backend.adapters.asr.factory import create_asr_adapter
from backend.adapters.asr.mock import MockASRAdapter
from backend.adapters.llm.base import LLMChatMessage
from backend.adapters.llm.factory import create_llm_adapter
from backend.adapters.llm.mock import MockLLMAdapter
from backend.config import get_settings


def test_mock_asr_adapter_returns_transcript(tmp_path):
    audio_path = tmp_path / "sample.wav"
    audio_path.write_bytes(b"demo")

    result = MockASRAdapter().transcribe(audio_path)

    assert result.provider == "mock"
    assert "mock文字起こし" in result.text
    assert result.segments


def test_mock_llm_adapter_can_generate_minutes():
    adapter = MockLLMAdapter()

    result = adapter.generate(
        system_prompt="議事録を作成してください。",
        user_prompt="面談名: テスト面談\n実施日: 2026-04-20\n参加者: 担任、保護者\n",
    )

    assert result.provider == "mock"
    assert "テスト面談" in result.text
    assert "決定事項" in result.text


def test_mock_llm_adapter_can_generate_chat_response():
    adapter = MockLLMAdapter()

    result = adapter.generate_chat(
        messages=[
            LLMChatMessage(role="system", content="共通チャット担当です。"),
            LLMChatMessage(role="user", content="校則について確認したいです。"),
        ]
    )

    assert result.provider == "mock"
    assert "受け取った内容" in result.text
    assert "校則" in result.text


def test_adapter_factories_switch_by_environment(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("ASR_PROVIDER", "mock")
    get_settings.cache_clear()

    assert create_llm_adapter().provider_name == "mock"
    assert create_asr_adapter().provider_name == "mock"

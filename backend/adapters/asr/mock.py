from __future__ import annotations

from pathlib import Path

from backend.adapters.asr.base import ASRResult


class MockASRAdapter:
    provider_name = "mock"
    model_name = "mock-whisper"

    def transcribe(self, audio_path: Path) -> ASRResult:
        text = (
            f"これは {audio_path.name} から生成したmock文字起こしです。"
            "保護者面談で、学習状況、今後の対応、次回確認事項について話しました。"
            "聞き取れない箇所は不明として扱ってください。"
        )
        return ASRResult(
            text=text,
            segments=[{"start": 0.0, "end": 5.0, "text": text}],
            provider=self.provider_name,
            model=self.model_name,
        )


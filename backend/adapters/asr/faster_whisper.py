from __future__ import annotations

from pathlib import Path

from backend.adapters.asr.base import ASRResult
from backend.config import Settings


class FasterWhisperASRAdapter:
    provider_name = "faster_whisper"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_name = settings.asr_model_size

    def transcribe(self, audio_path: Path) -> ASRResult:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed. Install the optional extra "
                "or use ASR_PROVIDER=whisper_cpp/mock."
            ) from exc

        model = WhisperModel(self.settings.asr_model_size, device=self.settings.asr_device)
        segments_iter, _info = model.transcribe(str(audio_path), language=self.settings.asr_language)
        segments = [
            {"start": segment.start, "end": segment.end, "text": segment.text}
            for segment in segments_iter
        ]
        text = "\n".join(segment["text"].strip() for segment in segments if segment["text"].strip())
        if not text:
            raise RuntimeError("faster-whisper finished but returned an empty transcript")
        return ASRResult(text=text, segments=segments, provider=self.provider_name, model=self.model_name)


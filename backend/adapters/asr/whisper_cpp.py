from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from backend.adapters.asr.base import ASRResult
from backend.config import Settings


class WhisperCppASRAdapter:
    provider_name = "whisper_cpp"

    def __init__(self, settings: Settings):
        self.settings = settings
        self.model_name = settings.asr_model_size

    def transcribe(self, audio_path: Path) -> ASRResult:
        model_path = self.settings.resolved_asr_model_path
        if not model_path.exists():
            raise RuntimeError(
                f"Whisper model file not found: {model_path}. "
                "Set ASR_MODEL_PATH or choose another ASR_MODEL_SIZE."
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            output_prefix = Path(temp_dir) / "transcript"
            command = [
                self.settings.asr_whisper_cpp_binary,
                "-m",
                str(model_path),
                "-f",
                str(audio_path),
                "-l",
                self.settings.asr_language,
                "-otxt",
                "-of",
                str(output_prefix),
            ]
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or "whisper.cpp transcription failed")

            transcript_file = output_prefix.with_suffix(".txt")
            text = transcript_file.read_text(encoding="utf-8").strip() if transcript_file.exists() else ""
            if not text:
                text = completed.stdout.strip()
            if not text:
                raise RuntimeError("whisper.cpp finished but returned an empty transcript")

        return ASRResult(
            text=text,
            segments=[],
            provider=self.provider_name,
            model=self.model_name,
        )


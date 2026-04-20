from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from backend.adapters.asr.base import ASRAdapter
from backend.models.db import Transcript
from backend.repositories.minutes_repository import MinutesRepository


class TranscriptionService:
    def __init__(self, db: Session, asr_adapter: ASRAdapter):
        self.db = db
        self.repository = MinutesRepository(db)
        self.asr_adapter = asr_adapter

    def transcribe_audio(self, *, audio_file_id: int) -> Transcript:
        audio_file = self.repository.get_audio_file(audio_file_id)
        if audio_file is None:
            raise ValueError(f"Audio file not found: {audio_file_id}")

        audio_path = Path(audio_file.file_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Uploaded audio file is missing: {audio_path}")

        result = self.asr_adapter.transcribe(audio_path)
        return self.repository.create_transcript(
            meeting_session_id=audio_file.meeting_session_id,
            audio_file_id=audio_file.id,
            text=result.text,
            segments=result.segments,
            asr_provider=result.provider,
            asr_model=result.model,
        )


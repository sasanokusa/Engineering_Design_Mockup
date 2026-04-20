from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from backend.models.db import AudioFile, CleanedTranscript, MeetingSession, MinutesDocument, Transcript


class MinutesRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_meeting_session(
        self,
        *,
        meeting_name: str,
        meeting_date: date | None,
        meeting_type: str | None,
        participants: str | None,
        notes: str | None,
    ) -> MeetingSession:
        session = MeetingSession(
            meeting_name=meeting_name,
            meeting_date=meeting_date,
            meeting_type=meeting_type,
            participants=participants,
            notes=notes,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def create_audio_file(
        self,
        *,
        meeting_session_id: int,
        original_filename: str,
        stored_filename: str,
        file_path: Path,
        content_type: str | None,
        size_bytes: int,
    ) -> AudioFile:
        audio_file = AudioFile(
            meeting_session_id=meeting_session_id,
            original_filename=original_filename,
            stored_filename=stored_filename,
            file_path=str(file_path),
            content_type=content_type,
            size_bytes=size_bytes,
        )
        self.db.add(audio_file)
        self.db.commit()
        self.db.refresh(audio_file)
        return audio_file

    def get_audio_file(self, audio_file_id: int) -> AudioFile | None:
        return self.db.get(AudioFile, audio_file_id)

    def get_transcript(self, transcript_id: int) -> Transcript | None:
        return self.db.get(Transcript, transcript_id)

    def get_cleaned_transcript(self, cleaned_transcript_id: int) -> CleanedTranscript | None:
        return self.db.get(CleanedTranscript, cleaned_transcript_id)

    def get_minutes_document(self, minutes_id: int) -> MinutesDocument | None:
        return self.db.get(MinutesDocument, minutes_id)

    def create_transcript(
        self,
        *,
        meeting_session_id: int,
        audio_file_id: int,
        text: str,
        segments: list | None,
        asr_provider: str,
        asr_model: str,
    ) -> Transcript:
        transcript = Transcript(
            meeting_session_id=meeting_session_id,
            audio_file_id=audio_file_id,
            text=text,
            segments=segments,
            asr_provider=asr_provider,
            asr_model=asr_model,
        )
        self.db.add(transcript)
        self.db.commit()
        self.db.refresh(transcript)
        return transcript

    def create_cleaned_transcript(
        self,
        *,
        meeting_session_id: int,
        transcript_id: int,
        text: str,
        llm_provider: str,
        llm_model: str,
    ) -> CleanedTranscript:
        cleaned = CleanedTranscript(
            meeting_session_id=meeting_session_id,
            transcript_id=transcript_id,
            text=text,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )
        self.db.add(cleaned)
        self.db.commit()
        self.db.refresh(cleaned)
        return cleaned

    def update_cleaned_transcript_text(self, cleaned: CleanedTranscript, *, text: str) -> CleanedTranscript:
        cleaned.text = text
        self.db.commit()
        self.db.refresh(cleaned)
        return cleaned

    def create_minutes_document(
        self,
        *,
        meeting_session_id: int,
        cleaned_transcript_id: int,
        content: str,
        llm_provider: str,
        llm_model: str,
    ) -> MinutesDocument:
        minutes = MinutesDocument(
            meeting_session_id=meeting_session_id,
            cleaned_transcript_id=cleaned_transcript_id,
            content=content,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )
        self.db.add(minutes)
        self.db.commit()
        self.db.refresh(minutes)
        return minutes

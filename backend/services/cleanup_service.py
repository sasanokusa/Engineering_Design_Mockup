from __future__ import annotations

from sqlalchemy.orm import Session

from backend.adapters.llm.base import LLMAdapter
from backend.models.db import CleanedTranscript
from backend.repositories.minutes_repository import MinutesRepository
from backend.services.prompt_loader import load_prompt


class CleanupService:
    def __init__(self, db: Session, llm_adapter: LLMAdapter):
        self.db = db
        self.repository = MinutesRepository(db)
        self.llm_adapter = llm_adapter

    def cleanup_transcript(self, *, transcript_id: int) -> CleanedTranscript:
        transcript = self.repository.get_transcript(transcript_id)
        if transcript is None:
            raise ValueError(f"Transcript not found: {transcript_id}")

        meeting = transcript.meeting_session
        user_prompt = "\n".join(
            [
                f"面談名: {meeting.meeting_name}",
                f"実施日: {meeting.meeting_date or '不明'}",
                f"参加者: {meeting.participants or '不明'}",
                f"備考: {meeting.notes or 'なし'}",
                "",
                "文字起こし:",
                transcript.text,
            ]
        )
        response = self.llm_adapter.generate(
            system_prompt=load_prompt("cleanup_prompt.md"),
            user_prompt=user_prompt,
        )
        return self.repository.create_cleaned_transcript(
            meeting_session_id=transcript.meeting_session_id,
            transcript_id=transcript.id,
            text=response.text,
            llm_provider=response.provider,
            llm_model=response.model,
        )


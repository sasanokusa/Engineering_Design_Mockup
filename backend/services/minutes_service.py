from __future__ import annotations

from sqlalchemy.orm import Session

from backend.adapters.llm.base import LLMAdapter
from backend.models.db import MinutesDocument
from backend.repositories.minutes_repository import MinutesRepository
from backend.services.prompt_loader import load_prompt


class MinutesService:
    def __init__(self, db: Session, llm_adapter: LLMAdapter):
        self.db = db
        self.repository = MinutesRepository(db)
        self.llm_adapter = llm_adapter

    def generate_minutes(self, *, cleaned_transcript_id: int) -> MinutesDocument:
        cleaned = self.repository.get_cleaned_transcript(cleaned_transcript_id)
        if cleaned is None:
            raise ValueError(f"Cleaned transcript not found: {cleaned_transcript_id}")

        meeting = cleaned.meeting_session
        user_prompt = "\n".join(
            [
                f"面談名: {meeting.meeting_name}",
                f"実施日: {meeting.meeting_date or '不明'}",
                f"面談種別: {meeting.meeting_type or '不明'}",
                f"参加者: {meeting.participants or '不明'}",
                f"備考: {meeting.notes or 'なし'}",
                "",
                "整形済みテキスト:",
                cleaned.text,
            ]
        )
        response = self.llm_adapter.generate(
            system_prompt=load_prompt("minutes_prompt.md"),
            user_prompt=user_prompt,
        )
        return self.repository.create_minutes_document(
            meeting_session_id=cleaned.meeting_session_id,
            cleaned_transcript_id=cleaned.id,
            content=response.text,
            llm_provider=response.provider,
            llm_model=response.model,
        )


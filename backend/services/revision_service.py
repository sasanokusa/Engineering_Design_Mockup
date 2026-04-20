from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.adapters.llm.base import LLMAdapter
from backend.models.db import CleanedTranscript
from backend.repositories.minutes_repository import MinutesRepository
from backend.services.prompt_loader import load_prompt


REVIEW_FLAG_WORDS = ("要確認", "不明", "聞き取れない", "確認が必要")


@dataclass(frozen=True)
class RevisionSuggestions:
    cleaned_transcript_id: int
    has_review_flags: bool
    suggestions: str
    llm_provider: str | None
    llm_model: str | None


class RevisionService:
    def __init__(self, db: Session, llm_adapter: LLMAdapter | None = None):
        self.db = db
        self.repository = MinutesRepository(db)
        self.llm_adapter = llm_adapter

    def update_cleaned_text(self, *, cleaned_transcript_id: int, text: str) -> CleanedTranscript:
        cleaned = self.repository.get_cleaned_transcript(cleaned_transcript_id)
        if cleaned is None:
            raise ValueError(f"Cleaned transcript not found: {cleaned_transcript_id}")
        return self.repository.update_cleaned_transcript_text(cleaned, text=text)

    def suggest_revisions(self, *, cleaned_transcript_id: int) -> RevisionSuggestions:
        cleaned = self.repository.get_cleaned_transcript(cleaned_transcript_id)
        if cleaned is None:
            raise ValueError(f"Cleaned transcript not found: {cleaned_transcript_id}")

        has_flags = _has_review_flags(cleaned.text)
        if not has_flags:
            return RevisionSuggestions(
                cleaned_transcript_id=cleaned.id,
                has_review_flags=False,
                suggestions="要確認箇所は見つかりませんでした。",
                llm_provider=None,
                llm_model=None,
            )

        if self.llm_adapter is None:
            raise RuntimeError("LLM adapter is required to suggest revisions")

        response = self.llm_adapter.generate(
            system_prompt=load_prompt("revision_suggestions_prompt.md"),
            user_prompt="\n".join(
                [
                    "raw transcript:",
                    cleaned.transcript.text,
                    "",
                    "整形済みテキスト:",
                    cleaned.text,
                ]
            ),
        )
        return RevisionSuggestions(
            cleaned_transcript_id=cleaned.id,
            has_review_flags=True,
            suggestions=response.text,
            llm_provider=response.provider,
            llm_model=response.model,
        )


def _has_review_flags(text: str) -> bool:
    return any(word in text for word in REVIEW_FLAG_WORDS)

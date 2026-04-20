from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


JobStatus = Literal["queued", "running", "completed", "failed"]


class MeetingSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_name: str
    meeting_date: date | None
    meeting_type: str | None
    participants: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime


class AudioFileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_session_id: int
    original_filename: str
    content_type: str | None
    size_bytes: int
    created_at: datetime


class AudioUploadResponse(BaseModel):
    meeting_session: MeetingSessionOut
    audio_file: AudioFileOut


class TranscriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_session_id: int
    audio_file_id: int
    text: str
    segments: list[Any] | None = None
    asr_provider: str
    asr_model: str
    created_at: datetime


class CleanedTranscriptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_session_id: int
    transcript_id: int
    text: str
    llm_provider: str
    llm_model: str
    created_at: datetime


class MinutesDocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    meeting_session_id: int
    cleaned_transcript_id: int
    content: str
    llm_provider: str
    llm_model: str
    created_at: datetime


class CreateTranscriptionJobRequest(BaseModel):
    audio_file_id: int = Field(gt=0)


class CreateCleanupJobRequest(BaseModel):
    transcript_id: int = Field(gt=0)


class CreateMinutesJobRequest(BaseModel):
    cleaned_transcript_id: int = Field(gt=0)


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    job_type: str
    status: JobStatus
    input_payload: dict[str, Any] | None
    result_type: str | None
    result_id: int | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class ErrorResponse(BaseModel):
    detail: str


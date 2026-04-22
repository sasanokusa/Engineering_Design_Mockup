from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class MeetingSession(Base, TimestampMixin):
    __tablename__ = "meeting_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    meeting_name: Mapped[str] = mapped_column(String(255))
    meeting_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    meeting_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    participants: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    audio_files: Mapped[list["AudioFile"]] = relationship(back_populates="meeting_session")
    transcripts: Mapped[list["Transcript"]] = relationship(back_populates="meeting_session")
    cleaned_transcripts: Mapped[list["CleanedTranscript"]] = relationship(back_populates="meeting_session")
    minutes_documents: Mapped[list["MinutesDocument"]] = relationship(back_populates="meeting_session")


class AudioFile(Base, TimestampMixin):
    __tablename__ = "audio_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    meeting_session_id: Mapped[int] = mapped_column(ForeignKey("meeting_sessions.id"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255))
    file_path: Mapped[str] = mapped_column(Text)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)

    meeting_session: Mapped[MeetingSession] = relationship(back_populates="audio_files")
    transcripts: Mapped[list["Transcript"]] = relationship(back_populates="audio_file")


class Transcript(Base, TimestampMixin):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    meeting_session_id: Mapped[int] = mapped_column(ForeignKey("meeting_sessions.id"), index=True)
    audio_file_id: Mapped[int] = mapped_column(ForeignKey("audio_files.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    segments: Mapped[list | None] = mapped_column(JSON, nullable=True)
    asr_provider: Mapped[str] = mapped_column(String(100))
    asr_model: Mapped[str] = mapped_column(String(100))

    meeting_session: Mapped[MeetingSession] = relationship(back_populates="transcripts")
    audio_file: Mapped[AudioFile] = relationship(back_populates="transcripts")
    cleaned_transcripts: Mapped[list["CleanedTranscript"]] = relationship(back_populates="transcript")


class CleanedTranscript(Base, TimestampMixin):
    __tablename__ = "cleaned_transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    meeting_session_id: Mapped[int] = mapped_column(ForeignKey("meeting_sessions.id"), index=True)
    transcript_id: Mapped[int] = mapped_column(ForeignKey("transcripts.id"), index=True)
    text: Mapped[str] = mapped_column(Text)
    llm_provider: Mapped[str] = mapped_column(String(100))
    llm_model: Mapped[str] = mapped_column(String(255))

    meeting_session: Mapped[MeetingSession] = relationship(back_populates="cleaned_transcripts")
    transcript: Mapped[Transcript] = relationship(back_populates="cleaned_transcripts")
    minutes_documents: Mapped[list["MinutesDocument"]] = relationship(back_populates="cleaned_transcript")


class MinutesDocument(Base, TimestampMixin):
    __tablename__ = "minutes_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    meeting_session_id: Mapped[int] = mapped_column(ForeignKey("meeting_sessions.id"), index=True)
    cleaned_transcript_id: Mapped[int] = mapped_column(ForeignKey("cleaned_transcripts.id"), index=True)
    content: Mapped[str] = mapped_column(Text)
    llm_provider: Mapped[str] = mapped_column(String(100))
    llm_model: Mapped[str] = mapped_column(String(255))

    meeting_session: Mapped[MeetingSession] = relationship(back_populates="minutes_documents")
    cleaned_transcript: Mapped[CleanedTranscript] = relationship(back_populates="minutes_documents")


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    job_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    input_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    result_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    result_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChatSession(Base, TimestampMixin):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), default="新規チャット")
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.id",
    )


class ChatMessage(Base, TimestampMixin):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"), index=True)
    role: Mapped[str] = mapped_column(String(30), index=True)
    content: Mapped[str] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tool_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    llm_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    llm_model: Mapped[str | None] = mapped_column(String(255), nullable=True)

    session: Mapped[ChatSession] = relationship(back_populates="messages")


class DocumentCollection(Base, TimestampMixin):
    __tablename__ = "document_collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    documents: Mapped[list["DocumentRecord"]] = relationship(
        back_populates="collection",
        cascade="all, delete-orphan",
        order_by="DocumentRecord.id",
    )


class DocumentRecord(Base, TimestampMixin):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("document_collections.id"), index=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    external_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    scope: Mapped[str] = mapped_column(String(30), default="persistent", index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_filename: Mapped[str] = mapped_column(String(255), default="")
    file_path: Mapped[str] = mapped_column(Text, default="")
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="uploaded", index=True)
    normalization_backend: Mapped[str | None] = mapped_column(String(100), nullable=True)
    normalized_json_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    normalized_markdown_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    chunks_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    collection: Mapped[DocumentCollection] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )


class DocumentChunk(Base, TimestampMixin):
    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_document_chunks_document_index"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"), index=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("document_collections.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    heading: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_locator: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    document: Mapped[DocumentRecord] = relationship(back_populates="chunks")
    collection: Mapped[DocumentCollection] = relationship()


class DocumentComparison(Base, TimestampMixin):
    __tablename__ = "document_comparisons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_ids: Mapped[list[int]] = mapped_column(JSON)
    min_similarity: Mapped[float] = mapped_column(Float, default=0.35)
    granularity: Mapped[str] = mapped_column(String(30), default="chunk")
    result_json: Mapped[dict] = mapped_column(JSON)

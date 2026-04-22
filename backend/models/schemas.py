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


class UpdateCleanedTranscriptRequest(BaseModel):
    text: str = Field(min_length=1)


class CleanedRevisionSuggestionsOut(BaseModel):
    cleaned_transcript_id: int
    has_review_flags: bool
    suggestions: str
    llm_provider: str | None
    llm_model: str | None


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


class ChatToolInfoOut(BaseModel):
    name: str
    display_name: str
    description: str
    status: str


class ChatSessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    system_prompt: str | None = None


class ChatSessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    system_prompt: str | None
    metadata_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: int
    role: str
    content: str
    tool_name: str | None
    tool_payload: dict[str, Any] | None
    llm_provider: str | None
    llm_model: str | None
    created_at: datetime


class ChatSessionDetailOut(BaseModel):
    session: ChatSessionOut
    messages: list[ChatMessageOut]
    available_tools: list[ChatToolInfoOut]


class ChatMessageCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    use_tools: bool = True


class ChatMessageDirectCreateRequest(ChatMessageCreateRequest):
    session_id: int = Field(gt=0)


class ChatMessageSendResponse(BaseModel):
    session: ChatSessionOut
    user_message: ChatMessageOut
    assistant_message: ChatMessageOut
    tool_suggestions: list[ChatToolInfoOut]


class DocumentCollectionCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class DocumentCollectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    metadata_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    collection_id: int
    session_id: int | None
    external_session_id: str | None
    scope: str
    original_filename: str
    stored_filename: str
    file_path: str
    content_type: str | None
    size_bytes: int
    sha256: str | None
    status: str
    normalization_backend: str | None
    normalized_json_path: str | None
    normalized_markdown_path: str | None
    chunks_path: str | None
    error_message: str | None
    metadata_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class DocumentChunkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    document_id: int
    collection_id: int
    chunk_index: int
    text: str
    heading: str | None
    source_locator: str | None
    metadata_json: dict[str, Any] | None
    created_at: datetime


class DocumentDetailOut(BaseModel):
    document: DocumentOut
    collection: DocumentCollectionOut
    chunks: list[DocumentChunkOut] = []


class DocumentIngestFailureOut(BaseModel):
    filename: str
    document_id: int | None = None
    error_message: str


class DocumentIngestResponse(BaseModel):
    collection: DocumentCollectionOut
    documents: list[DocumentOut]
    failures: list[DocumentIngestFailureOut]


class DocumentIngestPathRequest(BaseModel):
    path: str = Field(min_length=1)
    collection: str = Field(min_length=1)
    scope: Literal["persistent", "temporary"] = "persistent"
    session_id: int | None = Field(default=None, gt=0)
    external_session_id: str | None = Field(default=None, max_length=255)
    process: bool = True


class DocumentProcessResponse(BaseModel):
    document: DocumentOut
    chunks: list[DocumentChunkOut]


class DocumentSearchRequest(BaseModel):
    query: str = Field(min_length=1)
    collection: str | None = None
    scope: Literal["persistent", "temporary"] | None = None
    session_id: int | None = Field(default=None, gt=0)
    external_session_id: str | None = Field(default=None, max_length=255)
    limit: int = Field(default=10, ge=1, le=50)


class DocumentSearchResultOut(BaseModel):
    document_id: int
    collection_id: int
    collection_name: str
    original_filename: str
    chunk_id: int
    chunk_index: int
    text: str
    heading: str | None
    source_locator: str | None
    score: float | None = None


class DocumentSearchResponse(BaseModel):
    query: str
    results: list[DocumentSearchResultOut]


class DocumentCompareJobCreateRequest(BaseModel):
    document_ids: list[int] = Field(min_length=2, max_length=10)
    min_similarity: float = Field(default=0.35, ge=0.0, le=1.0)
    limit: int = Field(default=20, ge=1, le=100)
    granularity: Literal["chunk", "paragraph", "section", "full"] = "chunk"


class DocumentCompareChunkRefOut(BaseModel):
    document_id: int
    original_filename: str
    chunk_id: int
    chunk_index: int
    heading: str | None
    text: str
    unit_type: str = "chunk"
    unit_label: str | None = None


class DocumentSimilarChunkOut(BaseModel):
    left: DocumentCompareChunkRefOut
    right: DocumentCompareChunkRefOut
    similarity: float
    method: str


class DocumentDiffBlockOut(BaseModel):
    operation: str
    left_start_line: int
    right_start_line: int
    left_text: str
    right_text: str


class DocumentComparePairOut(BaseModel):
    left_document_id: int
    right_document_id: int
    left_filename: str
    right_filename: str
    overall_similarity: float
    left_chunk_count: int
    right_chunk_count: int
    matched_chunk_count: int
    diff_summary: dict[str, int]
    diff_excerpt: list[DocumentDiffBlockOut]


class DocumentCompareResultOut(BaseModel):
    comparison_id: int
    document_ids: list[int]
    min_similarity: float
    granularity: str = "chunk"
    pairs: list[DocumentComparePairOut]
    similar_chunks: list[DocumentSimilarChunkOut]
    created_at: datetime


class DocumentCompareJobOut(BaseModel):
    job: JobOut
    result: DocumentCompareResultOut | None = None


class OpenWebUIManifestOut(BaseModel):
    name: str
    role: str
    backend_base_path: str
    openwebui_base_url: str
    llm_runtime: dict[str, str]
    tool_launcher_paths: dict[str, str]
    data_policy: list[str]


class OpenWebUIToolEndpointOut(BaseModel):
    name: str
    display_name: str
    description: str
    method: str
    path: str
    scope: str
    input_schema: dict[str, Any]


class OpenWebUIDocumentSearchToolRequest(BaseModel):
    query: str = Field(min_length=1)
    collection: str | None = None
    scope: Literal["persistent", "temporary"] | None = None
    session_id: int | None = Field(default=None, gt=0)
    external_session_id: str | None = Field(default=None, max_length=255)
    limit: int = Field(default=5, ge=1, le=20)


class OpenWebUIDocumentSearchToolResponse(BaseModel):
    query: str
    results: list[DocumentSearchResultOut]
    context_markdown: str


class OpenWebUIMinutesLaunchRequest(BaseModel):
    external_session_id: str | None = Field(default=None, max_length=255)


class OpenWebUIMinutesLaunchResponse(BaseModel):
    launch_url: str
    description: str
    return_to_chat_supported: bool = False


class OpenWebUIHealthOut(BaseModel):
    status: str
    service: str

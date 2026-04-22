from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.orm import Session

from backend.adapters.llm.base import LLMAdapter
from backend.adapters.llm.factory import create_llm_adapter
from backend.models.db import ChatMessage, ChatSession
from backend.orchestrator.chat_orchestrator import ChatOrchestrator
from backend.repositories.chat_repository import ChatRepository
from backend.services.document_service import DocumentService
from backend.tooling.base import ToolInfo
from backend.tooling.registry import create_default_tool_registry


MAX_ATTACHMENT_DOCUMENTS = 5
MAX_ATTACHMENT_CONTEXT_CHARS = 18000
MAX_ATTACHMENT_CHUNK_CHARS = 1800


class ChatService:
    def __init__(
        self,
        db: Session,
        llm_adapter: LLMAdapter | None = None,
        *,
        llm_adapter_factory: Callable[[], LLMAdapter] | None = None,
    ):
        self.db = db
        self.repository = ChatRepository(db)
        self.documents = DocumentService(db)
        self.tool_registry = create_default_tool_registry()
        self._llm_adapter = llm_adapter
        self._llm_adapter_factory = llm_adapter_factory or create_llm_adapter
        self._orchestrator: ChatOrchestrator | None = None

    def create_session(self, *, title: str | None, system_prompt: str | None) -> ChatSession:
        return self.repository.create_session(title=title, system_prompt=system_prompt)

    def list_sessions(self) -> list[ChatSession]:
        return self.repository.list_sessions()

    def delete_session(self, *, session_id: int) -> None:
        session = self.repository.get_session(session_id)
        if session is None:
            raise ValueError(f"Chat session not found: {session_id}")
        self.documents.delete_temporary_documents_for_session(session_id=session_id)
        self.repository.delete_session(session)

    def get_session(self, *, session_id: int) -> ChatSession:
        session = self.repository.get_session_with_messages(session_id)
        if session is None:
            raise ValueError(f"Chat session not found: {session_id}")
        return session

    def list_messages(self, *, session_id: int) -> list[ChatMessage]:
        if self.repository.get_session(session_id) is None:
            raise ValueError(f"Chat session not found: {session_id}")
        return self.repository.list_messages(session_id)

    def send_message(
        self,
        *,
        session_id: int,
        content: str,
        use_tools: bool,
    ) -> tuple[ChatSession, ChatMessage, ChatMessage, list[ToolInfo]]:
        session = self.repository.get_session(session_id)
        if session is None:
            raise ValueError(f"Chat session not found: {session_id}")

        user_message = self.repository.create_message(
            session_id=session_id,
            role="user",
            content=content,
        )
        history = self.repository.list_messages(session_id)
        attachment_context, attachment_payload = self._build_attachment_context(session_id=session_id)
        response, tool_suggestions = self.orchestrator.generate_response(
            session=session,
            messages=history,
            latest_user_content=content,
            attachment_context=attachment_context,
            use_tools=use_tools,
        )
        assistant_message = self.repository.create_message(
            session_id=session_id,
            role="assistant",
            content=response.text,
            tool_payload={
                "suggested_tools": [tool.__dict__ for tool in tool_suggestions],
                "attached_documents": attachment_payload,
            },
            llm_provider=response.provider,
            llm_model=response.model,
        )
        refreshed_session = self.repository.get_session(session_id) or session
        return refreshed_session, user_message, assistant_message, tool_suggestions

    def list_available_tools(self) -> list[ToolInfo]:
        return self.tool_registry.list_tools()

    @property
    def orchestrator(self) -> ChatOrchestrator:
        if self._orchestrator is None:
            if self._llm_adapter is None:
                self._llm_adapter = self._llm_adapter_factory()
            self._orchestrator = ChatOrchestrator(self._llm_adapter, self.tool_registry)
        return self._orchestrator

    def _build_attachment_context(self, *, session_id: int) -> tuple[str | None, list[dict]]:
        documents = self.documents.list_documents(scope="temporary", session_id=session_id)
        if not documents:
            return None, []

        payload: list[dict] = []
        context_parts: list[str] = []
        remaining_chars = MAX_ATTACHMENT_CONTEXT_CHARS

        for document in documents[:MAX_ATTACHMENT_DOCUMENTS]:
            detail = self.documents.get_document_detail(document_id=document.id)
            chunks = list(getattr(detail, "chunks", []) or [])
            payload.append(
                {
                    "document_id": detail.id,
                    "filename": detail.original_filename,
                    "status": detail.status,
                    "chunk_count": len(chunks),
                }
            )

            header = (
                f"[document_id={detail.id} filename={detail.original_filename} "
                f"status={detail.status} chunks={len(chunks)}]"
            )
            if remaining_chars <= 0:
                break
            context_parts.append(header)
            remaining_chars -= len(header)

            if detail.status != "processed":
                note = "この文書は添付済みですが、まだ処理済みではありません。"
                context_parts.append(note)
                remaining_chars -= len(note)
                continue

            if not chunks:
                note = "この文書は処理済みですが、参照できるchunkがありません。"
                context_parts.append(note)
                remaining_chars -= len(note)
                continue

            for chunk in chunks:
                if remaining_chars <= 0:
                    break
                text = _clip_for_context(chunk.text, max_chars=min(MAX_ATTACHMENT_CHUNK_CHARS, remaining_chars))
                chunk_header = f"- chunk {chunk.chunk_index}"
                if chunk.heading:
                    chunk_header += f" / {chunk.heading}"
                chunk_text = f"{chunk_header}\n{text}"
                context_parts.append(chunk_text)
                remaining_chars -= len(chunk_text)

        if len(documents) > MAX_ATTACHMENT_DOCUMENTS:
            context_parts.append(f"ほかに {len(documents) - MAX_ATTACHMENT_DOCUMENTS} 件の添付文書があります。")
        if remaining_chars <= 0:
            context_parts.append("添付文書コンテキストは長いため一部のみ含めています。")

        return "\n\n".join(context_parts), payload


def _clip_for_context(text: str, *, max_chars: int) -> str:
    clean_text = " ".join(text.split())
    if len(clean_text) <= max_chars:
        return clean_text
    if max_chars <= 20:
        return clean_text[:max_chars]
    return f"{clean_text[: max_chars - 3].rstrip()}..."

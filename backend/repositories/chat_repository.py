from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models.db import ChatMessage, ChatSession


class ChatRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_session(self, *, title: str | None, system_prompt: str | None) -> ChatSession:
        session = ChatSession(
            title=(title or "新規チャット").strip() or "新規チャット",
            system_prompt=system_prompt,
            metadata_json={},
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def list_sessions(self) -> list[ChatSession]:
        statement = select(ChatSession).order_by(ChatSession.updated_at.desc(), ChatSession.id.desc())
        return list(self.db.scalars(statement).all())

    def get_session(self, session_id: int) -> ChatSession | None:
        return self.db.get(ChatSession, session_id)

    def delete_session(self, session: ChatSession) -> None:
        self.db.delete(session)
        self.db.commit()

    def get_session_with_messages(self, session_id: int) -> ChatSession | None:
        statement = (
            select(ChatSession)
            .where(ChatSession.id == session_id)
            .options(selectinload(ChatSession.messages))
        )
        return self.db.scalars(statement).first()

    def list_messages(self, session_id: int) -> list[ChatMessage]:
        statement = (
            select(ChatMessage)
            .where(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.id.asc())
        )
        return list(self.db.scalars(statement).all())

    def create_message(
        self,
        *,
        session_id: int,
        role: str,
        content: str,
        tool_name: str | None = None,
        tool_payload: dict | None = None,
        llm_provider: str | None = None,
        llm_model: str | None = None,
    ) -> ChatMessage:
        message = ChatMessage(
            session_id=session_id,
            role=role,
            content=content,
            tool_name=tool_name,
            tool_payload=tool_payload,
            llm_provider=llm_provider,
            llm_model=llm_model,
        )
        self.db.add(message)
        session = self.get_session(session_id)
        if session is not None:
            session.title = _derive_title(session.title, role=role, content=content)
        self.db.commit()
        self.db.refresh(message)
        return message


def _derive_title(current_title: str, *, role: str, content: str) -> str:
    if role != "user" or current_title != "新規チャット":
        return current_title
    collapsed = " ".join(content.split())
    if not collapsed:
        return current_title
    return collapsed[:40]

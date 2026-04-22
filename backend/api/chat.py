from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.models.schemas import (
    ChatMessageCreateRequest,
    ChatMessageDirectCreateRequest,
    ChatMessageOut,
    ChatMessageSendResponse,
    ChatSessionCreateRequest,
    ChatSessionDetailOut,
    ChatSessionOut,
    ChatToolInfoOut,
)
from backend.repositories.database import get_db
from backend.services.chat_service import ChatService
from backend.tooling.base import ToolInfo

router = APIRouter()


@router.post("/chat/sessions", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
def create_chat_session(request: ChatSessionCreateRequest, db: Session = Depends(get_db)):
    return ChatService(db).create_session(
        title=request.title,
        system_prompt=request.system_prompt,
    )


@router.get("/chat/sessions", response_model=list[ChatSessionOut])
def list_chat_sessions(db: Session = Depends(get_db)):
    return ChatService(db).list_sessions()


@router.get("/chat/sessions/{session_id}", response_model=ChatSessionDetailOut)
def get_chat_session(session_id: int, db: Session = Depends(get_db)):
    service = ChatService(db)
    try:
        session = service.get_session(session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="チャットセッションが見つかりません。") from exc
    return ChatSessionDetailOut(
        session=session,
        messages=session.messages,
        available_tools=_tool_infos_to_schema(service.list_available_tools()),
    )


@router.delete("/chat/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chat_session(session_id: int, db: Session = Depends(get_db)):
    try:
        ChatService(db).delete_session(session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="チャットセッションが見つかりません。") from exc
    return None


@router.get("/chat/sessions/{session_id}/messages", response_model=list[ChatMessageOut])
def list_chat_messages(session_id: int, db: Session = Depends(get_db)):
    try:
        return ChatService(db).list_messages(session_id=session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="チャットセッションが見つかりません。") from exc


@router.post("/chat/sessions/{session_id}/messages", response_model=ChatMessageSendResponse)
def send_chat_message(
    session_id: int,
    request: ChatMessageCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        return _send_chat_message_response(
            db=db,
            session_id=session_id,
            content=request.content,
            use_tools=request.use_tools,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="チャットセッションが見つかりません。") from exc


@router.post("/chat/messages", response_model=ChatMessageSendResponse)
def send_chat_message_direct(
    request: ChatMessageDirectCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        return _send_chat_message_response(
            db=db,
            session_id=request.session_id,
            content=request.content,
            use_tools=request.use_tools,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="チャットセッションが見つかりません。") from exc


@router.get("/chat/tools", response_model=list[ChatToolInfoOut])
def list_chat_tools(db: Session = Depends(get_db)):
    return _tool_infos_to_schema(ChatService(db).list_available_tools())


def _send_chat_message_response(
    *,
    db: Session,
    session_id: int,
    content: str,
    use_tools: bool,
) -> ChatMessageSendResponse:
    session, user_message, assistant_message, tool_suggestions = ChatService(db).send_message(
        session_id=session_id,
        content=content,
        use_tools=use_tools,
    )
    return ChatMessageSendResponse(
        session=session,
        user_message=user_message,
        assistant_message=assistant_message,
        tool_suggestions=_tool_infos_to_schema(tool_suggestions),
    )


def _tool_infos_to_schema(tools: list[ToolInfo]) -> list[ChatToolInfoOut]:
    return [
        ChatToolInfoOut(
            name=tool.name,
            display_name=tool.display_name,
            description=tool.description,
            status=tool.status,
        )
        for tool in tools
    ]

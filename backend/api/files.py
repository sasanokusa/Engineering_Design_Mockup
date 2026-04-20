from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.schemas import AudioUploadResponse
from backend.repositories.database import get_db
from backend.repositories.minutes_repository import MinutesRepository
from backend.repositories.storage import save_audio_upload

router = APIRouter()


@router.post("/files/audio", response_model=AudioUploadResponse)
def upload_audio_file(
    file: UploadFile = File(...),
    meeting_name: str = Form(...),
    meeting_date: date | None = Form(default=None),
    meeting_type: str | None = Form(default=None),
    participants: str | None = Form(default=None),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="音声ファイルが選択されていません。")

    settings = get_settings()
    repository = MinutesRepository(db)
    meeting_session = repository.create_meeting_session(
        meeting_name=meeting_name,
        meeting_date=meeting_date,
        meeting_type=meeting_type,
        participants=participants,
        notes=notes,
    )

    try:
        file_path, stored_filename, size_bytes = save_audio_upload(file, settings)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"音声ファイルの保存に失敗しました: {exc}") from exc

    if size_bytes == 0:
        raise HTTPException(status_code=400, detail="アップロードされた音声ファイルが空です。")

    audio_file = repository.create_audio_file(
        meeting_session_id=meeting_session.id,
        original_filename=file.filename,
        stored_filename=stored_filename,
        file_path=file_path,
        content_type=file.content_type,
        size_bytes=size_bytes,
    )
    return AudioUploadResponse(meeting_session=meeting_session, audio_file=audio_file)


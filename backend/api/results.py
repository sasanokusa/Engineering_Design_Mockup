from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.models.schemas import CleanedTranscriptOut, MinutesDocumentOut, TranscriptOut
from backend.repositories.database import get_db
from backend.repositories.minutes_repository import MinutesRepository

router = APIRouter()


@router.get("/transcripts/{transcript_id}", response_model=TranscriptOut)
def get_transcript(transcript_id: int, db: Session = Depends(get_db)):
    transcript = MinutesRepository(db).get_transcript(transcript_id)
    if transcript is None:
        raise HTTPException(status_code=404, detail="文字起こし結果が見つかりません。")
    return transcript


@router.get("/cleaned/{cleaned_id}", response_model=CleanedTranscriptOut)
def get_cleaned_transcript(cleaned_id: int, db: Session = Depends(get_db)):
    cleaned = MinutesRepository(db).get_cleaned_transcript(cleaned_id)
    if cleaned is None:
        raise HTTPException(status_code=404, detail="整形済みテキストが見つかりません。")
    return cleaned


@router.get("/minutes/{minutes_id}", response_model=MinutesDocumentOut)
def get_minutes(minutes_id: int, db: Session = Depends(get_db)):
    minutes = MinutesRepository(db).get_minutes_document(minutes_id)
    if minutes is None:
        raise HTTPException(status_code=404, detail="議事録が見つかりません。")
    return minutes


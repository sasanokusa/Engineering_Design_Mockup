from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.models.schemas import (
    CreateCleanupJobRequest,
    CreateMinutesJobRequest,
    CreateTranscriptionJobRequest,
    JobOut,
)
from backend.repositories.database import get_db
from backend.repositories.job_repository import JobRepository
from backend.repositories.minutes_repository import MinutesRepository
from backend.workers.job_worker import run_job

router = APIRouter()


@router.post("/jobs/transcription", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def create_transcription_job(
    request: CreateTranscriptionJobRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if MinutesRepository(db).get_audio_file(request.audio_file_id) is None:
        raise HTTPException(status_code=404, detail="音声ファイルが見つかりません。")
    job = JobRepository(db).create_job(
        job_type="transcription",
        input_payload={"audio_file_id": request.audio_file_id},
    )
    background_tasks.add_task(run_job, job.id)
    return job


@router.post("/jobs/cleanup", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def create_cleanup_job(
    request: CreateCleanupJobRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if MinutesRepository(db).get_transcript(request.transcript_id) is None:
        raise HTTPException(status_code=404, detail="文字起こし結果が見つかりません。")
    job = JobRepository(db).create_job(
        job_type="cleanup",
        input_payload={"transcript_id": request.transcript_id},
    )
    background_tasks.add_task(run_job, job.id)
    return job


@router.post("/jobs/minutes", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def create_minutes_job(
    request: CreateMinutesJobRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    if MinutesRepository(db).get_cleaned_transcript(request.cleaned_transcript_id) is None:
        raise HTTPException(status_code=404, detail="整形済みテキストが見つかりません。")
    job = JobRepository(db).create_job(
        job_type="minutes",
        input_payload={"cleaned_transcript_id": request.cleaned_transcript_id},
    )
    background_tasks.add_task(run_job, job.id)
    return job


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, db: Session = Depends(get_db)):
    job = JobRepository(db).get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="ジョブが見つかりません。")
    return job


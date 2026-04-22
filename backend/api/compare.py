from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.models.schemas import (
    DocumentCompareJobCreateRequest,
    DocumentCompareJobOut,
    DocumentCompareResultOut,
    JobOut,
)
from backend.repositories.database import get_db
from backend.repositories.job_repository import JobRepository
from backend.services.document_compare_service import DocumentCompareService
from backend.workers.job_worker import run_job

router = APIRouter()


@router.post("/compare/jobs", response_model=JobOut, status_code=status.HTTP_202_ACCEPTED)
def create_compare_job(
    request: DocumentCompareJobCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    service = DocumentCompareService(db)
    try:
        service.validate_documents(document_ids=request.document_ids)
    except ValueError as exc:
        raise HTTPException(status_code=_status_for_compare_error(str(exc)), detail=str(exc)) from exc

    job = JobRepository(db).create_job(
        job_type="document_compare",
        input_payload={
            "document_ids": request.document_ids,
            "min_similarity": request.min_similarity,
            "limit": request.limit,
            "granularity": request.granularity,
        },
    )
    background_tasks.add_task(run_job, job.id)
    return job


@router.get("/compare/jobs/{job_id}", response_model=DocumentCompareJobOut)
def get_compare_job(job_id: int, db: Session = Depends(get_db)):
    job = JobRepository(db).get_job(job_id)
    if job is None or job.job_type != "document_compare":
        raise HTTPException(status_code=404, detail="比較ジョブが見つかりません。")

    result = None
    if job.status == "completed" and job.result_id is not None:
        payload = DocumentCompareService(db).get_result_payload(comparison_id=job.result_id)
        if payload is not None:
            result = DocumentCompareResultOut(**payload)

    return DocumentCompareJobOut(job=job, result=result)


def _status_for_compare_error(message: str) -> int:
    if "見つかりません" in message:
        return 404
    return 400

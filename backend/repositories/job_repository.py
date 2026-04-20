from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.models.db import Job


class JobRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_job(self, *, job_type: str, input_payload: dict[str, Any]) -> Job:
        job = Job(job_type=job_type, status="queued", input_payload=input_payload)
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)
        return job

    def get_job(self, job_id: int) -> Job | None:
        return self.db.get(Job, job_id)

    def mark_running(self, job: Job) -> Job:
        job.status = "running"
        job.error_message = None
        job.started_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_completed(self, job: Job, *, result_type: str, result_id: int) -> Job:
        job.status = "completed"
        job.result_type = result_type
        job.result_id = result_id
        job.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(job)
        return job

    def mark_failed(self, job: Job, *, error_message: str) -> Job:
        job.status = "failed"
        job.error_message = error_message
        job.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(job)
        return job


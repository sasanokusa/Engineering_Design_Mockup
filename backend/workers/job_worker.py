from __future__ import annotations

import traceback

from backend.adapters.asr.factory import create_asr_adapter
from backend.adapters.llm.factory import create_llm_adapter
from backend.repositories.database import session_scope
from backend.repositories.job_repository import JobRepository
from backend.services.cleanup_service import CleanupService
from backend.services.document_compare_service import DocumentCompareService
from backend.services.minutes_service import MinutesService
from backend.services.transcription_service import TranscriptionService


def run_job(job_id: int) -> None:
    db = session_scope()
    try:
        jobs = JobRepository(db)
        job = jobs.get_job(job_id)
        if job is None:
            return

        jobs.mark_running(job)
        payload = job.input_payload or {}

        if job.job_type == "transcription":
            transcript = TranscriptionService(db, create_asr_adapter()).transcribe_audio(
                audio_file_id=int(payload["audio_file_id"])
            )
            jobs.mark_completed(job, result_type="transcript", result_id=transcript.id)
            return

        if job.job_type == "cleanup":
            cleaned = CleanupService(db, create_llm_adapter()).cleanup_transcript(
                transcript_id=int(payload["transcript_id"])
            )
            jobs.mark_completed(job, result_type="cleaned_transcript", result_id=cleaned.id)
            return

        if job.job_type == "minutes":
            minutes = MinutesService(db, create_llm_adapter()).generate_minutes(
                cleaned_transcript_id=int(payload["cleaned_transcript_id"])
            )
            jobs.mark_completed(job, result_type="minutes_document", result_id=minutes.id)
            return

        if job.job_type == "document_compare":
            comparison = DocumentCompareService(db).compare_documents(
                document_ids=[int(document_id) for document_id in payload["document_ids"]],
                min_similarity=float(payload.get("min_similarity", 0.35)),
                limit=int(payload.get("limit", 20)),
                granularity=str(payload.get("granularity", "chunk")),
            )
            jobs.mark_completed(job, result_type="document_comparison", result_id=comparison.id)
            return

        raise ValueError(f"Unsupported job type: {job.job_type}")
    except Exception as exc:
        message = f"{exc}"
        if not message:
            message = traceback.format_exc(limit=1).strip()
        try:
            job = JobRepository(db).get_job(job_id)
            if job is not None:
                JobRepository(db).mark_failed(job, error_message=message)
        finally:
            return
    finally:
        db.close()

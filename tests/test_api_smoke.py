import importlib

from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.repositories.database import reset_database_caches


def make_test_client(tmp_path, monkeypatch) -> TestClient:
    data_dir = tmp_path / "data"
    monkeypatch.setenv("LOCAL_SCHOOL_AI_DATA_DIR", str(data_dir))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{data_dir / 'test.db'}")
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("ASR_PROVIDER", "mock")
    get_settings.cache_clear()
    reset_database_caches()
    main = importlib.import_module("backend.main")
    main = importlib.reload(main)
    return TestClient(main.create_app())


def test_minutes_flow_smoke(tmp_path, monkeypatch):
    with make_test_client(tmp_path, monkeypatch) as client:
        upload_response = client.post(
            "/api/files/audio",
            data={
                "meeting_name": "APIスモーク面談",
                "meeting_date": "2026-04-20",
                "meeting_type": "保護者面談",
                "participants": "担任、保護者",
            },
            files={"file": ("sample.wav", b"RIFF demo audio", "audio/wav")},
        )
        assert upload_response.status_code == 200, upload_response.text
        audio_file_id = upload_response.json()["audio_file"]["id"]

        transcription_job = client.post("/api/jobs/transcription", json={"audio_file_id": audio_file_id})
        assert transcription_job.status_code == 202, transcription_job.text
        transcription_job_id = transcription_job.json()["id"]
        transcription_status = client.get(f"/api/jobs/{transcription_job_id}").json()
        assert transcription_status["status"] == "completed"
        transcript_id = transcription_status["result_id"]

        transcript = client.get(f"/api/transcripts/{transcript_id}")
        assert transcript.status_code == 200
        assert "mock文字起こし" in transcript.json()["text"]

        cleanup_job = client.post("/api/jobs/cleanup", json={"transcript_id": transcript_id})
        assert cleanup_job.status_code == 202, cleanup_job.text
        cleanup_status = client.get(f"/api/jobs/{cleanup_job.json()['id']}").json()
        assert cleanup_status["status"] == "completed"
        cleaned_id = cleanup_status["result_id"]

        cleaned = client.get(f"/api/cleaned/{cleaned_id}")
        assert cleaned.status_code == 200
        assert "整形済み文字起こし" in cleaned.json()["text"]

        minutes_job = client.post("/api/jobs/minutes", json={"cleaned_transcript_id": cleaned_id})
        assert minutes_job.status_code == 202, minutes_job.text
        minutes_status = client.get(f"/api/jobs/{minutes_job.json()['id']}").json()
        assert minutes_status["status"] == "completed"
        minutes_id = minutes_status["result_id"]

        minutes = client.get(f"/api/minutes/{minutes_id}")
        assert minutes.status_code == 200
        assert "議事録案" in minutes.json()["content"]


def test_missing_job_returns_404(tmp_path, monkeypatch):
    with make_test_client(tmp_path, monkeypatch) as client:
        response = client.get("/api/jobs/999")
        assert response.status_code == 404


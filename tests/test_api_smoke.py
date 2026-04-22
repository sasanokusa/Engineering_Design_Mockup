import importlib
import json
from pathlib import Path

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

        updated_cleaned = client.patch(
            f"/api/cleaned/{cleaned_id}",
            json={"text": cleaned.json()["text"] + "\n要確認: 参加者名が不明です。"},
        )
        assert updated_cleaned.status_code == 200
        assert "要確認" in updated_cleaned.json()["text"]

        suggestions = client.post(f"/api/cleaned/{cleaned_id}/revision-suggestions", json={})
        assert suggestions.status_code == 200
        assert suggestions.json()["has_review_flags"] is True
        assert "修正候補" in suggestions.json()["suggestions"]

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


def test_chat_session_message_flow_smoke(tmp_path, monkeypatch):
    with make_test_client(tmp_path, monkeypatch) as client:
        create_response = client.post("/api/chat/sessions", json={"title": "資料確認"})
        assert create_response.status_code == 201, create_response.text
        session_id = create_response.json()["id"]

        sessions = client.get("/api/chat/sessions")
        assert sessions.status_code == 200
        assert sessions.json()[0]["id"] == session_id

        send_response = client.post(
            f"/api/chat/sessions/{session_id}/messages",
            json={"content": "議事録作成ツールを使いたいです。", "use_tools": True},
        )
        assert send_response.status_code == 200, send_response.text
        body = send_response.json()
        assert body["user_message"]["role"] == "user"
        assert body["assistant_message"]["role"] == "assistant"
        assert "受け取った内容" in body["assistant_message"]["content"]
        assert body["tool_suggestions"][0]["name"] == "minutes_tool"

        messages = client.get(f"/api/chat/sessions/{session_id}/messages")
        assert messages.status_code == 200
        assert [message["role"] for message in messages.json()] == ["user", "assistant"]

        detail = client.get(f"/api/chat/sessions/{session_id}")
        assert detail.status_code == 200
        assert len(detail.json()["available_tools"]) >= 4

        delete_response = client.delete(f"/api/chat/sessions/{session_id}")
        assert delete_response.status_code == 204

        missing = client.get(f"/api/chat/sessions/{session_id}")
        assert missing.status_code == 404


def test_document_upload_process_and_search_flow(tmp_path, monkeypatch):
    with make_test_client(tmp_path, monkeypatch) as client:
        collection_response = client.post(
            "/api/document-collections",
            json={"name": "handbooks", "description": "学内ハンドブック"},
        )
        assert collection_response.status_code == 201, collection_response.text
        assert collection_response.json()["name"] == "handbooks"

        collections = client.get("/api/document-collections")
        assert collections.status_code == 200
        assert [collection["name"] for collection in collections.json()] == ["handbooks"]

        upload_response = client.post(
            "/api/documents/upload",
            data={"collection": "handbooks"},
            files=[
                (
                    "files",
                    (
                        "school-handbook.md",
                        "# School Handbook\n\nAttendance policy handbook searchable text.\n\nShared academic honesty paragraph.",
                        "text/markdown",
                    ),
                ),
                (
                    "files",
                    (
                        "clubs.txt",
                        "Club activity guidance and local school rules.\n\nShared academic honesty paragraph.",
                        "text/plain",
                    ),
                ),
            ],
        )
        assert upload_response.status_code == 200, upload_response.text
        body = upload_response.json()
        assert body["failures"] == []
        assert len(body["documents"]) == 2
        assert {document["status"] for document in body["documents"]} == {"processed"}

        document = body["documents"][0]
        assert Path(document["file_path"]).exists()
        assert Path(document["normalized_json_path"]).exists()
        assert Path(document["normalized_markdown_path"]).exists()
        assert Path(document["chunks_path"]).exists()

        detail = client.get(f"/api/documents/{document['id']}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["collection"]["name"] == "handbooks"
        assert detail.json()["chunks"]

        search = client.post(
            "/api/documents/search",
            json={"query": "handbook", "collection": "handbooks", "limit": 5},
        )
        assert search.status_code == 200, search.text
        assert search.json()["results"]
        assert search.json()["results"][0]["collection_name"] == "handbooks"

        documents = client.get("/api/documents?status=processed")
        assert documents.status_code == 200, documents.text
        document_ids = [record["id"] for record in documents.json()]
        assert len(document_ids) == 2

        compare_job = client.post(
            "/api/compare/jobs",
            json={"document_ids": document_ids, "min_similarity": 0.2, "limit": 5, "granularity": "paragraph"},
        )
        assert compare_job.status_code == 202, compare_job.text
        compare_status = client.get(f"/api/compare/jobs/{compare_job.json()['id']}")
        assert compare_status.status_code == 200, compare_status.text
        compare_body = compare_status.json()
        assert compare_body["job"]["status"] == "completed"
        assert compare_body["result"]["granularity"] == "paragraph"
        assert compare_body["result"]["pairs"][0]["matched_chunk_count"] >= 1
        assert compare_body["result"]["similar_chunks"]

        reprocess = client.post(f"/api/documents/{document['id']}/process")
        assert reprocess.status_code == 200, reprocess.text
        assert reprocess.json()["document"]["status"] == "processed"
        assert reprocess.json()["chunks"]

        chat_session = client.post("/api/chat/sessions", json={"title": "添付確認"})
        assert chat_session.status_code == 201, chat_session.text
        session_id = chat_session.json()["id"]

        temporary_upload = client.post(
            "/api/documents/upload",
            data={"collection": "chat-session-docs", "scope": "temporary", "session_id": str(session_id)},
            files=[
                (
                    "files",
                    (
                        "attached.md",
                        "# Attached\n\nTemporary session document searchable text.",
                        "text/markdown",
                    ),
                )
            ],
        )
        assert temporary_upload.status_code == 200, temporary_upload.text
        temporary_document = temporary_upload.json()["documents"][0]
        assert temporary_document["scope"] == "temporary"
        assert temporary_document["session_id"] == session_id
        assert f"temporary/{session_id}/{temporary_document['id']}" in temporary_document["file_path"]

        session_documents = client.get(f"/api/documents?scope=temporary&session_id={session_id}")
        assert session_documents.status_code == 200, session_documents.text
        assert [record["id"] for record in session_documents.json()] == [temporary_document["id"]]

        temporary_search = client.post(
            "/api/documents/search",
            json={
                "query": "Temporary session",
                "scope": "temporary",
                "session_id": session_id,
                "limit": 5,
            },
        )
        assert temporary_search.status_code == 200, temporary_search.text
        assert temporary_search.json()["results"][0]["document_id"] == temporary_document["id"]

        direct_message = client.post(
            "/api/chat/messages",
            json={"session_id": session_id, "content": "この文書をまとめてください。", "use_tools": False},
        )
        assert direct_message.status_code == 200, direct_message.text
        direct_body = direct_message.json()
        assert direct_body["session"]["id"] == session_id
        assert "attached.md" in direct_body["assistant_message"]["content"]
        assert "Temporary session document searchable text" in direct_body["assistant_message"]["content"]
        assert direct_body["assistant_message"]["tool_payload"]["attached_documents"][0]["document_id"] == temporary_document["id"]

        detach_response = client.delete(f"/api/documents/{temporary_document['id']}?session_id={session_id}")
        assert detach_response.status_code == 204, detach_response.text
        detached_documents = client.get(f"/api/documents?scope=temporary&session_id={session_id}")
        assert detached_documents.status_code == 200, detached_documents.text
        assert detached_documents.json() == []

        missing_detached_document = client.get(f"/api/documents/{temporary_document['id']}")
        assert missing_detached_document.status_code == 404

        persistent_delete = client.delete(f"/api/documents/{document['id']}")
        assert persistent_delete.status_code == 400

        source_file = tmp_path / "api-ingest.md"
        source_file.write_text("# API Ingest\n\nPath ingest endpoint text.", encoding="utf-8")
        ingest_response = client.post(
            "/api/documents/ingest",
            json={"path": str(source_file), "collection": "api-ingest", "process": True},
        )
        assert ingest_response.status_code == 200, ingest_response.text
        assert ingest_response.json()["documents"][0]["status"] == "processed"


def test_openwebui_bridge_keeps_chat_ui_and_backend_data_separated(tmp_path, monkeypatch):
    with make_test_client(tmp_path, monkeypatch) as client:
        health = client.get("/api/openwebui/health")
        assert health.status_code == 200
        assert health.json()["status"] == "ok"

        manifest = client.get("/api/openwebui/manifest")
        assert manifest.status_code == 200
        assert manifest.json()["role"] == "Open WebUI tool bridge and school-owned data backend"
        assert manifest.json()["llm_runtime"]["connection_owner"] == "Open WebUI"

        tools = client.get("/api/openwebui/tools")
        assert tools.status_code == 200
        assert {tool["name"] for tool in tools.json()} >= {
            "document_search",
            "session_document_upload",
            "document_compare",
            "minutes_launch",
        }

        session_upload = client.post(
            "/api/openwebui/tools/session-documents/upload",
            data={"external_session_id": "owui-chat-1", "process": "true"},
            files=[
                (
                    "files",
                    (
                        "owui-note.md",
                        "# Open WebUI Note\n\nOpen WebUI temporary session document searchable text.",
                        "text/markdown",
                    ),
                )
            ],
        )
        assert session_upload.status_code == 200, session_upload.text
        session_document = session_upload.json()["documents"][0]
        assert session_document["scope"] == "temporary"
        assert session_document["session_id"] is None
        assert session_document["external_session_id"] == "owui-chat-1"
        assert "temporary/owui-chat-1" in session_document["file_path"]

        session_documents = client.get(
            "/api/openwebui/tools/session-documents",
            params={"external_session_id": "owui-chat-1"},
        )
        assert session_documents.status_code == 200, session_documents.text
        assert [document["id"] for document in session_documents.json()] == [session_document["id"]]

        search = client.post(
            "/api/openwebui/tools/document-search",
            json={
                "query": "Open WebUI temporary",
                "scope": "temporary",
                "external_session_id": "owui-chat-1",
                "limit": 5,
            },
        )
        assert search.status_code == 200, search.text
        assert search.json()["results"][0]["document_id"] == session_document["id"]
        assert "文書検索結果" in search.json()["context_markdown"]

        detail = client.get(f"/api/openwebui/tools/documents/{session_document['id']}")
        assert detail.status_code == 200, detail.text
        assert detail.json()["document"]["external_session_id"] == "owui-chat-1"
        assert detail.json()["chunks"]

        upload_response = client.post(
            "/api/documents/upload",
            data={"collection": "bridge-compare"},
            files=[
                (
                    "files",
                    ("left.md", "Shared bridge comparison paragraph.\n\nLeft only detail.", "text/markdown"),
                ),
                (
                    "files",
                    ("right.md", "Shared bridge comparison paragraph.\n\nRight only detail.", "text/markdown"),
                ),
            ],
        )
        assert upload_response.status_code == 200, upload_response.text
        document_ids = [document["id"] for document in upload_response.json()["documents"]]

        compare = client.post(
            "/api/openwebui/tools/document-compare",
            json={"document_ids": document_ids, "min_similarity": 0.2, "limit": 5, "granularity": "paragraph"},
        )
        assert compare.status_code == 200, compare.text
        assert compare.json()["granularity"] == "paragraph"
        assert compare.json()["similar_chunks"]

        launch = client.post("/api/openwebui/tools/minutes-launch", json={"external_session_id": "owui-chat-1"})
        assert launch.status_code == 200, launch.text
        assert launch.json()["return_to_chat_supported"] is False
        assert launch.json()["launch_url"].endswith("/")

        delete_response = client.delete(
            f"/api/openwebui/tools/session-documents/{session_document['id']}",
            params={"external_session_id": "owui-chat-1"},
        )
        assert delete_response.status_code == 204, delete_response.text
        assert (
            client.get(
                "/api/openwebui/tools/session-documents",
                params={"external_session_id": "owui-chat-1"},
            ).json()
            == []
        )
        assert (tmp_path / "data" / "audit" / "openwebui_bridge.jsonl").exists()


def test_cli_ingest_uses_document_pipeline(tmp_path, monkeypatch, capsys):
    data_dir = tmp_path / "data"
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "rules.md").write_text("# Rules\n\nCLI searchable handbook content.", encoding="utf-8")

    monkeypatch.setenv("LOCAL_SCHOOL_AI_DATA_DIR", str(data_dir))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{data_dir / 'test.db'}")
    get_settings.cache_clear()
    reset_database_caches()

    from backend.cli import main as cli_main

    exit_code = cli_main(["ingest", str(source_dir), "--collection", "cli-handbooks", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["collection"]["name"] == "cli-handbooks"
    assert payload["failures"] == []
    assert payload["documents"][0]["status"] == "processed"
    assert Path(payload["documents"][0]["normalized_markdown_path"]).exists()
    assert Path(payload["documents"][0]["chunks_path"]).exists()

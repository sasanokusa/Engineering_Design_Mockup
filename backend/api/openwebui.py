from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile, status
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.models.schemas import (
    DocumentCompareJobCreateRequest,
    DocumentCompareResultOut,
    DocumentDetailOut,
    DocumentIngestFailureOut,
    DocumentIngestResponse,
    DocumentOut,
    DocumentSearchResultOut,
    OpenWebUIDocumentSearchToolRequest,
    OpenWebUIDocumentSearchToolResponse,
    OpenWebUIHealthOut,
    OpenWebUIManifestOut,
    OpenWebUIMinutesLaunchRequest,
    OpenWebUIMinutesLaunchResponse,
    OpenWebUIToolEndpointOut,
)
from backend.repositories.database import get_db
from backend.services.audit_service import AuditService
from backend.services.document_compare_service import DocumentCompareService, comparison_to_payload
from backend.services.document_service import DocumentIngestResult, DocumentService

router = APIRouter()


@router.get("/openwebui/health", response_model=OpenWebUIHealthOut)
def openwebui_health():
    return OpenWebUIHealthOut(status="ok", service="local-school-ai-openwebui-bridge")


@router.get("/openwebui/manifest", response_model=OpenWebUIManifestOut)
def get_openwebui_manifest():
    settings = get_settings()
    return OpenWebUIManifestOut(
        name="Local School AI Backend",
        role="Open WebUI tool bridge and school-owned data backend",
        backend_base_path="/api/openwebui",
        openwebui_base_url=settings.openwebui_base_url,
        llm_runtime={
            "connection_owner": "Open WebUI",
            "base_url": settings.llm_base_url,
            "model": settings.llm_model,
        },
        tool_launcher_paths={
            "minutes": "/",
            "documents": "/documents/",
            "compare": "/compare/",
        },
        data_policy=[
            "Open WebUI は通常チャットUIとツール起動導線を担当する",
            "原本、正規化文書、chunk、比較結果、議事録中間生成物は自前バックエンドで保持する",
            "Open WebUI の内部DBを学校向け業務データの主保存先にしない",
        ],
    )


@router.get("/openwebui/tools", response_model=list[OpenWebUIToolEndpointOut])
def list_openwebui_tools():
    return [
        OpenWebUIToolEndpointOut(
            name="document_search",
            display_name="資料検索",
            description="永続資料またはOpen WebUIセッションに紐づく一時文書から関連chunkを検索します。",
            method="POST",
            path="/api/openwebui/tools/document-search",
            scope="persistent_and_temporary_documents",
            input_schema={
                "query": "string",
                "collection": "string | null",
                "scope": "persistent | temporary | null",
                "external_session_id": "string | null",
                "limit": "1..20",
            },
        ),
        OpenWebUIToolEndpointOut(
            name="session_document_upload",
            display_name="一時文書アップロード",
            description="Open WebUIの会話IDに一時文書を紐づけ、正規化、chunk化、FTS5索引化します。",
            method="POST",
            path="/api/openwebui/tools/session-documents/upload",
            scope="temporary_documents",
            input_schema={
                "files": "multipart files[]",
                "external_session_id": "string",
                "collection": "string | null",
                "process": "boolean",
            },
        ),
        OpenWebUIToolEndpointOut(
            name="document_read",
            display_name="文書読解",
            description="登録済み文書の正規化済みchunkを読み出します。",
            method="GET",
            path="/api/openwebui/tools/documents/{document_id}",
            scope="persistent_and_temporary_documents",
            input_schema={"document_id": "integer"},
        ),
        OpenWebUIToolEndpointOut(
            name="document_compare",
            display_name="文書比較",
            description="処理済み文書を同期実行で比較し、差分サマリと類似箇所を返します。",
            method="POST",
            path="/api/openwebui/tools/document-compare",
            scope="processed_documents",
            input_schema={
                "document_ids": "integer[]",
                "min_similarity": "0.0..1.0",
                "limit": "1..100",
                "granularity": "chunk | paragraph | section | full",
            },
        ),
        OpenWebUIToolEndpointOut(
            name="minutes_launch",
            display_name="議事録作成",
            description="音声起点の議事録専用UIへの導線を返します。処理本体は独立サービスで実行します。",
            method="POST",
            path="/api/openwebui/tools/minutes-launch",
            scope="minutes_tool_service",
            input_schema={"external_session_id": "string | null"},
        ),
    ]


@router.post("/openwebui/tools/document-search", response_model=OpenWebUIDocumentSearchToolResponse)
def run_document_search_tool(
    request: OpenWebUIDocumentSearchToolRequest,
    db: Session = Depends(get_db),
):
    try:
        raw_results = DocumentService(db).search(
            query=request.query,
            collection_name=request.collection,
            scope=request.scope,
            session_id=request.session_id,
            external_session_id=request.external_session_id,
            limit=request.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    results = [DocumentSearchResultOut(**result.__dict__) for result in raw_results]
    AuditService().log_event(
        action="document_search",
        resource_type="document_chunks",
        metadata={
            "query": request.query,
            "collection": request.collection,
            "scope": request.scope,
            "session_id": request.session_id,
            "external_session_id": request.external_session_id,
            "result_count": len(results),
        },
    )
    return OpenWebUIDocumentSearchToolResponse(
        query=request.query,
        results=results,
        context_markdown=_search_results_to_context_markdown(results),
    )


@router.post("/openwebui/tools/session-documents/upload", response_model=DocumentIngestResponse)
def upload_openwebui_session_documents(
    files: list[UploadFile] = File(...),
    external_session_id: str = Form(...),
    collection: str | None = Form(default=None),
    process: bool = Form(default=True),
    db: Session = Depends(get_db),
):
    clean_external_session_id = " ".join(external_session_id.split())
    if not clean_external_session_id:
        raise HTTPException(status_code=400, detail="external_session_id が必要です。")
    if not files:
        raise HTTPException(status_code=400, detail="アップロードするファイルがありません。")

    collection_name = collection or f"openwebui-session-{_safe_label(clean_external_session_id)}"
    try:
        result = DocumentService(db).ingest_uploads(
            files,
            collection_name=collection_name,
            scope="temporary",
            external_session_id=clean_external_session_id,
            process=process,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    AuditService().log_event(
        action="session_document_upload",
        resource_type="document",
        metadata={
            "external_session_id": clean_external_session_id,
            "collection": collection_name,
            "document_ids": [document.id for document in result.documents],
            "failure_count": len(result.failures),
        },
    )
    return _ingest_result_to_response(result)


@router.get("/openwebui/tools/session-documents", response_model=list[DocumentOut])
def list_openwebui_session_documents(
    external_session_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    return DocumentService(db).list_documents(
        scope="temporary",
        external_session_id=external_session_id,
    )


@router.delete("/openwebui/tools/session-documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_openwebui_session_document(
    document_id: int,
    external_session_id: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
):
    try:
        DocumentService(db).delete_temporary_document(
            document_id=document_id,
            external_session_id=external_session_id,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message:
            raise HTTPException(status_code=404, detail="文書が見つかりません。") from exc
        raise HTTPException(status_code=400, detail=message) from exc

    AuditService().log_event(
        action="session_document_delete",
        resource_type="document",
        resource_id=document_id,
        metadata={"external_session_id": external_session_id},
    )
    return None


@router.get("/openwebui/tools/documents/{document_id}", response_model=DocumentDetailOut)
def read_document_tool(document_id: int, db: Session = Depends(get_db)):
    try:
        document = DocumentService(db).get_document_detail(document_id=document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="文書が見つかりません。") from exc

    AuditService().log_event(
        action="document_read",
        resource_type="document",
        resource_id=document_id,
        metadata={"chunk_count": len(document.chunks)},
    )
    return DocumentDetailOut(document=document, collection=document.collection, chunks=document.chunks)


@router.post("/openwebui/tools/document-compare", response_model=DocumentCompareResultOut)
def run_document_compare_tool(
    request: DocumentCompareJobCreateRequest,
    db: Session = Depends(get_db),
):
    service = DocumentCompareService(db)
    try:
        comparison = service.compare_documents(
            document_ids=request.document_ids,
            min_similarity=request.min_similarity,
            limit=request.limit,
            granularity=request.granularity,
        )
    except ValueError as exc:
        raise HTTPException(status_code=_status_for_compare_error(str(exc)), detail=str(exc)) from exc

    AuditService().log_event(
        action="document_compare",
        resource_type="document_comparison",
        resource_id=comparison.id,
        metadata={
            "document_ids": comparison.document_ids,
            "granularity": comparison.granularity,
            "min_similarity": comparison.min_similarity,
        },
    )
    return DocumentCompareResultOut(**comparison_to_payload(comparison))


@router.post("/openwebui/tools/minutes-launch", response_model=OpenWebUIMinutesLaunchResponse)
def launch_minutes_tool(
    request: Request,
    payload: OpenWebUIMinutesLaunchRequest | None = None,
):
    launch_url = str(request.base_url).rstrip("/") + "/"
    external_session_id = payload.external_session_id if payload else None
    AuditService().log_event(
        action="minutes_launch",
        resource_type="minutes_tool",
        metadata={"external_session_id": external_session_id, "launch_url": launch_url},
    )
    return OpenWebUIMinutesLaunchResponse(
        launch_url=launch_url,
        description="議事録作成は通常チャットではなく、音声入力から始まる専用UIで実行します。",
        return_to_chat_supported=False,
    )


def _ingest_result_to_response(result: DocumentIngestResult) -> DocumentIngestResponse:
    return DocumentIngestResponse(
        collection=result.collection,
        documents=[DocumentOut.model_validate(document) for document in result.documents],
        failures=[
            DocumentIngestFailureOut(
                filename=failure.filename,
                document_id=failure.document_id,
                error_message=failure.error_message,
            )
            for failure in result.failures
        ],
    )


def _search_results_to_context_markdown(results: list[DocumentSearchResultOut]) -> str:
    if not results:
        return "該当する文書chunkは見つかりませんでした。"

    lines = ["# 文書検索結果", ""]
    for index, result in enumerate(results, start=1):
        lines.extend(
            [
                f"## {index}. {result.original_filename} / chunk {result.chunk_index}",
                f"- document_id: {result.document_id}",
                f"- collection: {result.collection_name}",
                f"- source: {result.source_locator or '-'}",
                "",
                _clip_text(result.text),
                "",
            ]
        )
    return "\n".join(lines).strip()


def _clip_text(text: str, *, max_chars: int = 1200) -> str:
    clean = " ".join(text.split())
    if len(clean) <= max_chars:
        return clean
    return f"{clean[: max_chars - 3].rstrip()}..."


def _safe_label(value: str) -> str:
    clean = "".join(character if character.isalnum() or character in "-_." else "-" for character in value.strip())
    return clean[:80] or "session"


def _status_for_compare_error(message: str) -> int:
    if "見つかりません" in message:
        return 404
    return 400

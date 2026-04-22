from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from backend.models.schemas import (
    DocumentCollectionCreateRequest,
    DocumentCollectionOut,
    DocumentDetailOut,
    DocumentIngestFailureOut,
    DocumentIngestPathRequest,
    DocumentIngestResponse,
    DocumentOut,
    DocumentProcessResponse,
    DocumentSearchRequest,
    DocumentSearchResponse,
    DocumentSearchResultOut,
)
from backend.repositories.database import get_db
from backend.services.document_service import DocumentService

router = APIRouter()


@router.post(
    "/document-collections",
    response_model=DocumentCollectionOut,
    status_code=status.HTTP_201_CREATED,
)
def create_document_collection(
    request: DocumentCollectionCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        return DocumentService(db).create_collection(name=request.name, description=request.description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/document-collections", response_model=list[DocumentCollectionOut])
def list_document_collections(db: Session = Depends(get_db)):
    return DocumentService(db).list_collections()


@router.get("/documents", response_model=list[DocumentOut])
def list_documents(
    collection: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    scope: str | None = Query(default=None),
    session_id: int | None = Query(default=None),
    external_session_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        return DocumentService(db).list_documents(
            collection_name=collection,
            status=status_filter,
            scope=scope,
            session_id=session_id,
            external_session_id=external_session_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/documents/upload", response_model=DocumentIngestResponse)
def upload_documents(
    files: list[UploadFile] = File(...),
    collection: str | None = Form(default=None),
    scope: str = Form(default="persistent"),
    session_id: int | None = Form(default=None),
    external_session_id: str | None = Form(default=None),
    process: bool = Form(default=True),
    db: Session = Depends(get_db),
):
    if not files:
        raise HTTPException(status_code=400, detail="アップロードするファイルがありません。")
    try:
        collection_name = _resolve_collection_name(
            collection=collection,
            scope=scope,
            session_id=session_id,
            external_session_id=external_session_id,
        )
        result = DocumentService(db).ingest_uploads(
            files,
            collection_name=collection_name,
            scope=scope,
            session_id=session_id,
            external_session_id=external_session_id,
            process=process,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ingest_result_to_response(result)


@router.post("/documents/ingest", response_model=DocumentIngestResponse)
def ingest_documents(request: DocumentIngestPathRequest, db: Session = Depends(get_db)):
    try:
        result = DocumentService(db).ingest_path(
            Path(request.path),
            collection_name=request.collection,
            scope=request.scope,
            session_id=request.session_id,
            external_session_id=request.external_session_id,
            process=request.process,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _ingest_result_to_response(result)


@router.post("/documents/search", response_model=DocumentSearchResponse)
def search_documents(request: DocumentSearchRequest, db: Session = Depends(get_db)):
    try:
        results = DocumentService(db).search(
            query=request.query,
            collection_name=request.collection,
            scope=request.scope,
            session_id=request.session_id,
            external_session_id=request.external_session_id,
            limit=request.limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return DocumentSearchResponse(
        query=request.query,
        results=[DocumentSearchResultOut(**result.__dict__) for result in results],
    )


@router.get("/documents/{document_id}", response_model=DocumentDetailOut)
def get_document(document_id: int, db: Session = Depends(get_db)):
    try:
        document = DocumentService(db).get_document_detail(document_id=document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="文書が見つかりません。") from exc
    return DocumentDetailOut(document=document, collection=document.collection, chunks=document.chunks)


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_temporary_document(
    document_id: int,
    session_id: int | None = Query(default=None),
    external_session_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    try:
        DocumentService(db).delete_temporary_document(
            document_id=document_id,
            session_id=session_id,
            external_session_id=external_session_id,
        )
    except ValueError as exc:
        message = str(exc)
        if "not found" in message:
            raise HTTPException(status_code=404, detail="文書が見つかりません。") from exc
        raise HTTPException(status_code=400, detail=message) from exc
    return None


@router.post("/documents/{document_id}/process", response_model=DocumentProcessResponse)
def process_document(document_id: int, db: Session = Depends(get_db)):
    service = DocumentService(db)
    try:
        service.get_document_detail(document_id=document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="文書が見つかりません。") from exc
    try:
        document, chunks = service.process_document(document_id=document_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"文書処理に失敗しました: {exc}") from exc
    return DocumentProcessResponse(document=document, chunks=chunks)


def _ingest_result_to_response(result) -> DocumentIngestResponse:
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


def _resolve_collection_name(
    *,
    collection: str | None,
    scope: str,
    session_id: int | None,
    external_session_id: str | None,
) -> str:
    if collection and collection.strip():
        return collection
    if scope.strip().lower() == "temporary":
        if session_id is not None:
            return f"temporary-session-{session_id}"
        if external_session_id and external_session_id.strip():
            return f"openwebui-session-{_safe_label(external_session_id)}"
        return "temporary"
    raise ValueError("永続資料にはコレクション名が必要です。")


def _safe_label(value: str) -> str:
    return "".join(character if character.isalnum() or character in "-_." else "-" for character in value.strip())[:80]

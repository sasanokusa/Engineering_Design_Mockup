from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.models.db import DocumentChunk, DocumentCollection, DocumentRecord


class DocumentRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_collection(
        self,
        *,
        name: str,
        description: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> DocumentCollection:
        collection = DocumentCollection(
            name=name.strip(),
            description=description,
            metadata_json=metadata_json or {},
        )
        self.db.add(collection)
        self.db.commit()
        self.db.refresh(collection)
        return collection

    def get_collection_by_name(self, name: str) -> DocumentCollection | None:
        statement = select(DocumentCollection).where(DocumentCollection.name == name.strip())
        return self.db.scalars(statement).first()

    def get_or_create_collection(
        self,
        *,
        name: str,
        description: str | None = None,
    ) -> DocumentCollection:
        existing = self.get_collection_by_name(name)
        if existing is not None:
            return existing
        return self.create_collection(name=name, description=description)

    def list_collections(self) -> list[DocumentCollection]:
        statement = select(DocumentCollection).order_by(DocumentCollection.name.asc())
        return list(self.db.scalars(statement).all())

    def list_documents(
        self,
        *,
        collection_name: str | None = None,
        status: str | None = None,
        scope: str | None = None,
        session_id: int | None = None,
        external_session_id: str | None = None,
    ) -> list[DocumentRecord]:
        statement = select(DocumentRecord).options(selectinload(DocumentRecord.collection))
        if collection_name:
            statement = statement.join(DocumentRecord.collection).where(DocumentCollection.name == collection_name)
        if status:
            statement = statement.where(DocumentRecord.status == status)
        if scope:
            statement = statement.where(DocumentRecord.scope == scope)
        if session_id is not None:
            statement = statement.where(DocumentRecord.session_id == session_id)
        if external_session_id:
            statement = statement.where(DocumentRecord.external_session_id == external_session_id)
        statement = statement.order_by(DocumentRecord.created_at.desc(), DocumentRecord.id.desc())
        return list(self.db.scalars(statement).all())

    def get_document(self, document_id: int) -> DocumentRecord | None:
        return self.db.get(DocumentRecord, document_id)

    def get_document_detail(self, document_id: int) -> DocumentRecord | None:
        statement = (
            select(DocumentRecord)
            .where(DocumentRecord.id == document_id)
            .options(selectinload(DocumentRecord.collection), selectinload(DocumentRecord.chunks))
        )
        return self.db.scalars(statement).first()

    def create_document(
        self,
        *,
        collection_id: int,
        original_filename: str,
        content_type: str | None,
        size_bytes: int,
        scope: str = "persistent",
        session_id: int | None = None,
        external_session_id: str | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> DocumentRecord:
        document = DocumentRecord(
            collection_id=collection_id,
            session_id=session_id,
            external_session_id=external_session_id,
            scope=scope,
            original_filename=original_filename,
            content_type=content_type,
            size_bytes=size_bytes,
            status="uploaded",
            metadata_json=metadata_json or {},
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def update_original_storage(
        self,
        document: DocumentRecord,
        *,
        stored_filename: str,
        file_path: Path,
        size_bytes: int,
        sha256: str,
    ) -> DocumentRecord:
        document.stored_filename = stored_filename
        document.file_path = str(file_path)
        document.size_bytes = size_bytes
        document.sha256 = sha256
        document.status = "stored"
        document.error_message = None
        self.db.commit()
        self.db.refresh(document)
        return document

    def mark_processing(self, document: DocumentRecord) -> DocumentRecord:
        document.status = "processing"
        document.error_message = None
        self.db.commit()
        self.db.refresh(document)
        return document

    def mark_failed(self, document: DocumentRecord, *, error_message: str) -> DocumentRecord:
        document.status = "failed"
        document.error_message = error_message
        self.db.commit()
        self.db.refresh(document)
        return document

    def mark_processed(
        self,
        document: DocumentRecord,
        *,
        normalization_backend: str,
        normalized_json_path: Path,
        normalized_markdown_path: Path,
        chunks_path: Path,
    ) -> DocumentRecord:
        document.status = "processed"
        document.normalization_backend = normalization_backend
        document.normalized_json_path = str(normalized_json_path)
        document.normalized_markdown_path = str(normalized_markdown_path)
        document.chunks_path = str(chunks_path)
        document.error_message = None
        self.db.commit()
        self.db.refresh(document)
        return document

    def delete_chunks_for_document(self, document_id: int) -> None:
        statement = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        for chunk in self.db.scalars(statement).all():
            self.db.delete(chunk)
        self.db.commit()

    def delete_document(self, document: DocumentRecord) -> None:
        self.db.delete(document)
        self.db.commit()

    def replace_chunks(
        self,
        *,
        document_id: int,
        collection_id: int,
        chunks: list[dict[str, Any]],
    ) -> list[DocumentChunk]:
        self.delete_chunks_for_document(document_id)
        records: list[DocumentChunk] = []
        for chunk in chunks:
            record = DocumentChunk(
                document_id=document_id,
                collection_id=collection_id,
                chunk_index=int(chunk["chunk_index"]),
                text=str(chunk["text"]),
                heading=chunk.get("heading"),
                source_locator=chunk.get("source_locator"),
                metadata_json=chunk.get("metadata_json") or {},
            )
            self.db.add(record)
            records.append(record)
        self.db.commit()
        for record in records:
            self.db.refresh(record)
        return records

    def list_chunks(self, document_id: int) -> list[DocumentChunk]:
        statement = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        return list(self.db.scalars(statement).all())

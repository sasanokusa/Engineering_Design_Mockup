from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.config import Settings, get_settings
from backend.models.db import DocumentChunk, DocumentCollection, DocumentRecord
from backend.repositories.document_repository import DocumentRepository
from backend.services.document_chunker import DocumentChunker
from backend.services.document_indexer import DocumentIndex, SQLiteFTSIndex
from backend.services.document_normalizer import DocumentNormalizer


@dataclass(frozen=True)
class DocumentIngestFailure:
    filename: str
    document_id: int | None
    error_message: str


@dataclass(frozen=True)
class DocumentIngestResult:
    collection: DocumentCollection
    documents: list[DocumentRecord]
    failures: list[DocumentIngestFailure]


class DocumentService:
    def __init__(
        self,
        db: Session,
        *,
        settings: Settings | None = None,
        normalizer: DocumentNormalizer | None = None,
        chunker: DocumentChunker | None = None,
        index: DocumentIndex | None = None,
    ):
        self.db = db
        self.settings = settings or get_settings()
        self.settings.ensure_storage_directories()
        self.repository = DocumentRepository(db)
        self.normalizer = normalizer or DocumentNormalizer()
        self.chunker = chunker or DocumentChunker()
        self.index = index or SQLiteFTSIndex(db)

    def create_collection(self, *, name: str, description: str | None = None) -> DocumentCollection:
        clean_name = _clean_collection_name(name)
        return self.repository.get_or_create_collection(name=clean_name, description=description)

    def list_collections(self) -> list[DocumentCollection]:
        return self.repository.list_collections()

    def list_documents(
        self,
        *,
        collection_name: str | None = None,
        status: str | None = None,
        scope: str | None = None,
        session_id: int | None = None,
        external_session_id: str | None = None,
    ) -> list[DocumentRecord]:
        return self.repository.list_documents(
            collection_name=collection_name,
            status=status,
            scope=_clean_scope(scope) if scope else None,
            session_id=session_id,
            external_session_id=_clean_optional_external_session_id(external_session_id),
        )

    def get_document_detail(self, *, document_id: int) -> DocumentRecord:
        document = self.repository.get_document_detail(document_id)
        if document is None:
            raise ValueError(f"Document not found: {document_id}")
        return document

    def ingest_path(
        self,
        source_path: Path,
        *,
        collection_name: str,
        scope: str = "persistent",
        session_id: int | None = None,
        external_session_id: str | None = None,
        process: bool = True,
    ) -> DocumentIngestResult:
        clean_scope = _clean_scope(scope)
        clean_external_session_id = _clean_optional_external_session_id(external_session_id)
        collection = self.create_collection(name=collection_name)
        documents: list[DocumentRecord] = []
        failures: list[DocumentIngestFailure] = []

        for file_path in _iter_ingest_files(source_path):
            document = self._create_document_record(
                collection=collection,
                scope=clean_scope,
                session_id=session_id,
                external_session_id=clean_external_session_id,
                original_filename=file_path.name,
                content_type=mimetypes.guess_type(file_path.name)[0],
                size_bytes=file_path.stat().st_size,
            )
            try:
                self._store_original_from_path(document=document, source_path=file_path)
                if process:
                    document, _chunks = self.process_document(document_id=document.id)
                else:
                    document = self.repository.get_document(document.id) or document
            except Exception as exc:
                document = self.repository.mark_failed(document, error_message=str(exc))
            documents.append(document)
            if document.status == "failed":
                failures.append(
                    DocumentIngestFailure(
                        filename=file_path.name,
                        document_id=document.id,
                        error_message=document.error_message or "unknown error",
                    )
                )

        return DocumentIngestResult(collection=collection, documents=documents, failures=failures)

    def ingest_uploads(
        self,
        uploads: list[UploadFile],
        *,
        collection_name: str,
        scope: str = "persistent",
        session_id: int | None = None,
        external_session_id: str | None = None,
        process: bool = True,
    ) -> DocumentIngestResult:
        clean_scope = _clean_scope(scope)
        clean_external_session_id = _clean_optional_external_session_id(external_session_id)
        collection = self.create_collection(name=collection_name)
        documents: list[DocumentRecord] = []
        failures: list[DocumentIngestFailure] = []

        for upload in uploads:
            filename = Path(upload.filename or "document").name
            if not upload.filename:
                failures.append(
                    DocumentIngestFailure(
                        filename=filename,
                        document_id=None,
                        error_message="ファイル名がありません。",
                    )
                )
                continue

            document = self._create_document_record(
                collection=collection,
                scope=clean_scope,
                session_id=session_id,
                external_session_id=clean_external_session_id,
                original_filename=filename,
                content_type=upload.content_type,
                size_bytes=0,
            )
            try:
                self._store_original_from_upload(document=document, upload=upload)
                if process:
                    document, _chunks = self.process_document(document_id=document.id)
                else:
                    document = self.repository.get_document(document.id) or document
            except Exception as exc:
                document = self.repository.mark_failed(document, error_message=str(exc))
            documents.append(document)
            if document.status == "failed":
                failures.append(
                    DocumentIngestFailure(
                        filename=filename,
                        document_id=document.id,
                        error_message=document.error_message or "unknown error",
                    )
                )

        return DocumentIngestResult(collection=collection, documents=documents, failures=failures)

    def process_document(self, *, document_id: int) -> tuple[DocumentRecord, list[DocumentChunk]]:
        document = self.repository.get_document(document_id)
        if document is None:
            raise ValueError(f"Document not found: {document_id}")
        if not document.file_path:
            document = self.repository.mark_failed(document, error_message="原本ファイルが保存されていません。")
            raise ValueError(document.error_message)

        document = self.repository.mark_processing(document)
        self.index.delete_document(document.id)
        self.repository.delete_chunks_for_document(document.id)

        try:
            source_path = Path(document.file_path)
            normalized = self.normalizer.normalize(source_path, original_filename=document.original_filename)
            normalized_json_path, normalized_markdown_path = self._write_normalized_files(
                document=document,
                data=normalized.data,
                markdown=normalized.markdown,
            )
            chunk_payloads = self.chunker.chunk(
                normalized.markdown,
                document_id=document.id,
                source_filename=document.original_filename,
            )
            chunks_path = self._write_chunk_file(document=document, chunks=chunk_payloads)
            chunk_records = self.repository.replace_chunks(
                document_id=document.id,
                collection_id=document.collection_id,
                chunks=chunk_payloads,
            )
            self.index.index_chunks(chunk_records)
            document = self.repository.mark_processed(
                document,
                normalization_backend=normalized.backend,
                normalized_json_path=normalized_json_path,
                normalized_markdown_path=normalized_markdown_path,
                chunks_path=chunks_path,
            )
            return document, chunk_records
        except Exception as exc:
            document = self.repository.mark_failed(document, error_message=str(exc))
            raise

    def search(
        self,
        *,
        query: str,
        collection_name: str | None = None,
        scope: str | None = None,
        session_id: int | None = None,
        external_session_id: str | None = None,
        limit: int = 10,
    ):
        return self.index.search(
            query=query,
            collection_name=collection_name,
            scope=_clean_scope(scope) if scope else None,
            session_id=session_id,
            external_session_id=_clean_optional_external_session_id(external_session_id),
            limit=limit,
        )

    def delete_temporary_document(
        self,
        *,
        document_id: int,
        session_id: int | None = None,
        external_session_id: str | None = None,
    ) -> None:
        document = self.repository.get_document_detail(document_id)
        if document is None:
            raise ValueError(f"Document not found: {document_id}")
        if document.scope != "temporary":
            raise ValueError("チャットから解除できるのは一時文書だけです。")
        if session_id is not None and document.session_id != session_id:
            raise ValueError("指定されたチャットセッションの添付文書ではありません。")
        clean_external_session_id = _clean_optional_external_session_id(external_session_id)
        if clean_external_session_id and document.external_session_id != clean_external_session_id:
            raise ValueError("指定されたOpen WebUIセッションの一時文書ではありません。")

        self.index.delete_document(document.id)
        self.repository.delete_chunks_for_document(document.id)
        artifact_dirs = [
            self._document_artifact_dir(document=document, root=self.settings.resolved_originals_dir),
            self._document_artifact_dir(document=document, root=self.settings.resolved_normalized_dir),
            self._document_artifact_dir(document=document, root=self.settings.resolved_chunks_dir),
        ]
        self.repository.delete_document(document)
        for directory in artifact_dirs:
            _remove_tree_if_safe(directory, root=self.settings.resolved_data_dir)

    def _create_document_record(
        self,
        *,
        collection: DocumentCollection,
        scope: str,
        session_id: int | None,
        external_session_id: str | None,
        original_filename: str,
        content_type: str | None,
        size_bytes: int,
    ) -> DocumentRecord:
        metadata: dict[str, str | int | None] = {}
        if session_id is not None:
            metadata["session_id"] = session_id
        if external_session_id is not None:
            metadata["external_session_id"] = external_session_id
        return self.repository.create_document(
            collection_id=collection.id,
            session_id=session_id,
            external_session_id=external_session_id,
            original_filename=Path(original_filename).name,
            content_type=content_type,
            size_bytes=size_bytes,
            scope=scope,
            metadata_json=metadata,
        )

    def _store_original_from_path(self, *, document: DocumentRecord, source_path: Path) -> DocumentRecord:
        destination = self._original_path(document=document)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if source_path.resolve() != destination.resolve():
            shutil.copy2(source_path, destination)
        size_bytes = destination.stat().st_size
        sha256 = _sha256_path(destination)
        return self.repository.update_original_storage(
            document,
            stored_filename=destination.name,
            file_path=destination,
            size_bytes=size_bytes,
            sha256=sha256,
        )

    def _store_original_from_upload(self, *, document: DocumentRecord, upload: UploadFile) -> DocumentRecord:
        destination = self._original_path(document=document)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as buffer:
            _copy_upload(upload.file, buffer)
        size_bytes = destination.stat().st_size
        sha256 = _sha256_path(destination)
        return self.repository.update_original_storage(
            document,
            stored_filename=destination.name,
            file_path=destination,
            size_bytes=size_bytes,
            sha256=sha256,
        )

    def _original_path(self, *, document: DocumentRecord) -> Path:
        return self._document_artifact_dir(document=document, root=self.settings.resolved_originals_dir) / _source_filename(
            document.original_filename
        )

    def _normalized_dir(self, *, document: DocumentRecord) -> Path:
        return self._document_artifact_dir(document=document, root=self.settings.resolved_normalized_dir)

    def _chunk_path(self, *, document: DocumentRecord) -> Path:
        return self._document_artifact_dir(document=document, root=self.settings.resolved_chunks_dir) / f"{document.id}.jsonl"

    def _document_artifact_dir(self, *, document: DocumentRecord, root: Path) -> Path:
        if document.scope == "temporary":
            session_part = _temporary_session_part(document)
            return root / "temporary" / session_part / str(document.id)
        return root / "persistent" / str(document.collection_id) / str(document.id)

    def _write_normalized_files(
        self,
        *,
        document: DocumentRecord,
        data: dict,
        markdown: str,
    ) -> tuple[Path, Path]:
        directory = self._normalized_dir(document=document)
        directory.mkdir(parents=True, exist_ok=True)
        json_path = directory / "document.json"
        markdown_path = directory / "document.md"
        json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        return json_path, markdown_path

    def _write_chunk_file(self, *, document: DocumentRecord, chunks: list[dict]) -> Path:
        chunks_path = self._chunk_path(document=document)
        chunks_path.parent.mkdir(parents=True, exist_ok=True)
        with chunks_path.open("w", encoding="utf-8") as handle:
            for chunk in chunks:
                handle.write(json.dumps(chunk, ensure_ascii=False) + "\n")
        return chunks_path


def _clean_collection_name(name: str) -> str:
    clean_name = " ".join(name.split())
    if not clean_name:
        raise ValueError("コレクション名が空です。")
    return clean_name


def _clean_scope(scope: str | None) -> str:
    clean_scope = (scope or "persistent").strip().lower()
    if clean_scope not in {"persistent", "temporary"}:
        raise ValueError("scope は persistent または temporary を指定してください。")
    return clean_scope


def _clean_optional_external_session_id(external_session_id: str | None) -> str | None:
    if external_session_id is None:
        return None
    clean = " ".join(external_session_id.split())
    return clean or None


def _temporary_session_part(document: DocumentRecord) -> str:
    if document.session_id is not None:
        return str(document.session_id)
    if document.external_session_id:
        return _safe_path_token(document.external_session_id, default="openwebui-session")
    return "unscoped"


def _safe_path_token(value: str, *, default: str) -> str:
    clean = re.sub(r"[^A-Za-z0-9_.=-]+", "_", value).strip("._")
    return clean[:120] or default


def _iter_ingest_files(source_path: Path) -> list[Path]:
    path = source_path.expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"取り込み対象が見つかりません: {path}")
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise ValueError(f"取り込み対象はファイルまたはディレクトリである必要があります: {path}")
    return sorted(
        candidate
        for candidate in path.rglob("*")
        if candidate.is_file() and not any(part.startswith(".") for part in candidate.relative_to(path).parts)
    )


def _source_filename(original_filename: str) -> str:
    suffix = Path(original_filename).suffix
    if suffix and suffix.isascii() and len(suffix) <= 20:
        return f"source{suffix.lower()}"
    return "source"


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _copy_upload(source: BinaryIO, destination: BinaryIO) -> None:
    source.seek(0)
    shutil.copyfileobj(source, destination)


def _remove_tree_if_safe(path: Path, *, root: Path) -> None:
    target = path.expanduser().resolve()
    safe_root = root.expanduser().resolve()
    if target == safe_root or safe_root not in target.parents:
        return
    shutil.rmtree(target, ignore_errors=True)

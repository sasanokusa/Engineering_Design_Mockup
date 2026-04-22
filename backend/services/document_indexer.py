from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.models.db import DocumentChunk


@dataclass(frozen=True)
class DocumentSearchResult:
    document_id: int
    collection_id: int
    collection_name: str
    original_filename: str
    chunk_id: int
    chunk_index: int
    text: str
    heading: str | None
    source_locator: str | None
    score: float | None


class DocumentIndex:
    def delete_document(self, document_id: int) -> None:
        raise NotImplementedError

    def index_chunks(self, chunks: list[DocumentChunk]) -> None:
        raise NotImplementedError

    def search(
        self,
        *,
        query: str,
        collection_name: str | None = None,
        scope: str | None = None,
        session_id: int | None = None,
        external_session_id: str | None = None,
        limit: int = 10,
    ) -> list[DocumentSearchResult]:
        raise NotImplementedError


class SQLiteFTSIndex(DocumentIndex):
    def __init__(self, db: Session):
        self.db = db

    def delete_document(self, document_id: int) -> None:
        self.db.execute(
            text("DELETE FROM document_chunks_fts WHERE document_id = :document_id"),
            {"document_id": document_id},
        )
        self.db.commit()

    def index_chunks(self, chunks: list[DocumentChunk]) -> None:
        if not chunks:
            return
        document_id = chunks[0].document_id
        self.delete_document(document_id)
        for chunk in chunks:
            self.db.execute(
                text(
                    """
                    INSERT INTO document_chunks_fts(rowid, chunk_id, document_id, collection_id, text)
                    VALUES (:rowid, :chunk_id, :document_id, :collection_id, :text)
                    """
                ),
                {
                    "rowid": chunk.id,
                    "chunk_id": chunk.id,
                    "document_id": chunk.document_id,
                    "collection_id": chunk.collection_id,
                    "text": chunk.text,
                },
            )
        self.db.commit()

    def search(
        self,
        *,
        query: str,
        collection_name: str | None = None,
        scope: str | None = None,
        session_id: int | None = None,
        external_session_id: str | None = None,
        limit: int = 10,
    ) -> list[DocumentSearchResult]:
        normalized_query = query.strip()
        if not normalized_query:
            return []

        results = self._search_fts(
            query=normalized_query,
            collection_name=collection_name,
            scope=scope,
            session_id=session_id,
            external_session_id=external_session_id,
            limit=limit,
        )
        if results:
            return results
        return self._search_like(
            query=normalized_query,
            collection_name=collection_name,
            scope=scope,
            session_id=session_id,
            external_session_id=external_session_id,
            limit=limit,
        )

    def _search_fts(
        self,
        *,
        query: str,
        collection_name: str | None,
        scope: str | None,
        session_id: int | None,
        external_session_id: str | None,
        limit: int,
    ) -> list[DocumentSearchResult]:
        match_query = _to_fts_phrase(query)
        collection_filter = "AND c.name = :collection_name" if collection_name else ""
        scope_filter = "AND d.scope = :scope" if scope else ""
        session_filter = "AND d.session_id = :session_id" if session_id is not None else ""
        external_session_filter = "AND d.external_session_id = :external_session_id" if external_session_id else ""
        statement = text(
            f"""
            SELECT
                dc.document_id AS document_id,
                dc.collection_id AS collection_id,
                c.name AS collection_name,
                d.original_filename AS original_filename,
                dc.id AS chunk_id,
                dc.chunk_index AS chunk_index,
                dc.text AS text,
                dc.heading AS heading,
                dc.source_locator AS source_locator,
                bm25(document_chunks_fts) AS score
            FROM document_chunks_fts
            JOIN document_chunks dc ON dc.id = document_chunks_fts.rowid
            JOIN documents d ON d.id = dc.document_id
            JOIN document_collections c ON c.id = dc.collection_id
            WHERE document_chunks_fts MATCH :match_query
            {collection_filter}
            {scope_filter}
            {session_filter}
            {external_session_filter}
            ORDER BY score ASC
            LIMIT :limit
            """
        )
        params = {"match_query": match_query, "limit": limit}
        if collection_name:
            params["collection_name"] = collection_name
        if scope:
            params["scope"] = scope
        if session_id is not None:
            params["session_id"] = session_id
        if external_session_id:
            params["external_session_id"] = external_session_id
        return [_row_to_result(row) for row in self.db.execute(statement, params).mappings().all()]

    def _search_like(
        self,
        *,
        query: str,
        collection_name: str | None,
        scope: str | None,
        session_id: int | None,
        external_session_id: str | None,
        limit: int,
    ) -> list[DocumentSearchResult]:
        collection_filter = "AND c.name = :collection_name" if collection_name else ""
        scope_filter = "AND d.scope = :scope" if scope else ""
        session_filter = "AND d.session_id = :session_id" if session_id is not None else ""
        external_session_filter = "AND d.external_session_id = :external_session_id" if external_session_id else ""
        statement = text(
            f"""
            SELECT
                dc.document_id AS document_id,
                dc.collection_id AS collection_id,
                c.name AS collection_name,
                d.original_filename AS original_filename,
                dc.id AS chunk_id,
                dc.chunk_index AS chunk_index,
                dc.text AS text,
                dc.heading AS heading,
                dc.source_locator AS source_locator,
                NULL AS score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            JOIN document_collections c ON c.id = dc.collection_id
            WHERE dc.text LIKE :like_query
            {collection_filter}
            {scope_filter}
            {session_filter}
            {external_session_filter}
            ORDER BY dc.document_id ASC, dc.chunk_index ASC
            LIMIT :limit
            """
        )
        params = {"like_query": f"%{query}%", "limit": limit}
        if collection_name:
            params["collection_name"] = collection_name
        if scope:
            params["scope"] = scope
        if session_id is not None:
            params["session_id"] = session_id
        if external_session_id:
            params["external_session_id"] = external_session_id
        return [_row_to_result(row) for row in self.db.execute(statement, params).mappings().all()]


def _to_fts_phrase(query: str) -> str:
    return f'"{query.replace(chr(34), chr(34) + chr(34))}"'


def _row_to_result(row) -> DocumentSearchResult:
    return DocumentSearchResult(
        document_id=int(row["document_id"]),
        collection_id=int(row["collection_id"]),
        collection_name=str(row["collection_name"]),
        original_filename=str(row["original_filename"]),
        chunk_id=int(row["chunk_id"]),
        chunk_index=int(row["chunk_index"]),
        text=str(row["text"]),
        heading=row["heading"],
        source_locator=row["source_locator"],
        score=float(row["score"]) if row["score"] is not None else None,
    )

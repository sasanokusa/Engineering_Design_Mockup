from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from itertools import combinations

from sqlalchemy.orm import Session

from backend.models.db import DocumentChunk, DocumentComparison, DocumentRecord
from backend.repositories.comparison_repository import ComparisonRepository
from backend.repositories.document_repository import DocumentRepository


@dataclass(frozen=True)
class SimilarityScore:
    value: float
    method: str


@dataclass(frozen=True)
class CompareUnit:
    document_id: int
    original_filename: str
    chunk_id: int
    chunk_index: int
    heading: str | None
    text: str
    unit_type: str
    unit_label: str | None


class DocumentCompareService:
    def __init__(self, db: Session):
        self.db = db
        self.documents = DocumentRepository(db)
        self.comparisons = ComparisonRepository(db)

    def list_documents(
        self,
        *,
        collection_name: str | None = None,
        status: str | None = None,
    ) -> list[DocumentRecord]:
        return self.documents.list_documents(collection_name=collection_name, status=status)

    def validate_documents(self, *, document_ids: list[int]) -> list[DocumentRecord]:
        clean_ids = _dedupe_ids(document_ids)
        if len(clean_ids) < 2:
            raise ValueError("比較には2件以上の文書が必要です。")

        records: list[DocumentRecord] = []
        for document_id in clean_ids:
            document = self.documents.get_document_detail(document_id)
            if document is None:
                raise ValueError(f"文書が見つかりません: {document_id}")
            if document.status != "processed":
                raise ValueError(f"文書 #{document_id} は処理済みではありません。先に文書処理を実行してください。")
            if not document.chunks:
                raise ValueError(f"文書 #{document_id} には比較できるチャンクがありません。")
            records.append(document)
        return records

    def compare_documents(
        self,
        *,
        document_ids: list[int],
        min_similarity: float = 0.35,
        limit: int = 20,
        granularity: str = "chunk",
    ) -> DocumentComparison:
        records = self.validate_documents(document_ids=document_ids)
        clean_ids = [document.id for document in records]
        threshold = max(0.0, min(1.0, float(min_similarity)))
        clean_granularity = _clean_granularity(granularity)
        result_json = self._build_result(
            records,
            min_similarity=threshold,
            limit=limit,
            granularity=clean_granularity,
        )
        return self.comparisons.create_comparison(
            document_ids=clean_ids,
            min_similarity=threshold,
            granularity=clean_granularity,
            result_json=result_json,
        )

    def get_result_payload(self, *, comparison_id: int) -> dict | None:
        comparison = self.comparisons.get_comparison(comparison_id)
        if comparison is None:
            return None
        return comparison_to_payload(comparison)

    def _build_result(
        self,
        documents: list[DocumentRecord],
        *,
        min_similarity: float,
        limit: int,
        granularity: str,
    ) -> dict:
        pairs: list[dict] = []
        similar_chunks: list[dict] = []

        for left, right in combinations(documents, 2):
            left_text = _document_text(left)
            right_text = _document_text(right)
            overall = _similarity_score(left_text, right_text)
            diff_summary, diff_excerpt = _diff_documents(left_text, right_text)
            matches = _compare_units(
                left_units=_units_for_document(left, granularity=granularity),
                right_units=_units_for_document(right, granularity=granularity),
                min_similarity=min_similarity,
                limit=limit,
            )
            pairs.append(
                {
                    "left_document_id": left.id,
                    "right_document_id": right.id,
                    "left_filename": left.original_filename,
                    "right_filename": right.original_filename,
                    "overall_similarity": round(overall.value, 4),
                    "left_chunk_count": len(left.chunks),
                    "right_chunk_count": len(right.chunks),
                    "matched_chunk_count": len(matches),
                    "diff_summary": diff_summary,
                    "diff_excerpt": diff_excerpt,
                }
            )
            similar_chunks.extend(matches)

        similar_chunks.sort(key=lambda item: item["similarity"], reverse=True)
        return {
            "granularity": granularity,
            "pairs": pairs,
            "similar_chunks": similar_chunks[:limit],
        }


def comparison_to_payload(comparison: DocumentComparison) -> dict:
    return {
        "comparison_id": comparison.id,
        "document_ids": comparison.document_ids,
        "min_similarity": comparison.min_similarity,
        "granularity": comparison.granularity or comparison.result_json.get("granularity", "chunk"),
        "pairs": comparison.result_json.get("pairs", []),
        "similar_chunks": comparison.result_json.get("similar_chunks", []),
        "created_at": comparison.created_at,
    }


def _dedupe_ids(document_ids: list[int]) -> list[int]:
    clean_ids: list[int] = []
    seen: set[int] = set()
    for raw_id in document_ids:
        document_id = int(raw_id)
        if document_id in seen:
            continue
        seen.add(document_id)
        clean_ids.append(document_id)
    return clean_ids


def _document_text(document: DocumentRecord) -> str:
    return "\n\n".join(chunk.text for chunk in document.chunks)


def _compare_units(
    *,
    left_units: list[CompareUnit],
    right_units: list[CompareUnit],
    min_similarity: float,
    limit: int,
) -> list[dict]:
    matches: list[dict] = []
    for left in left_units:
        for right in right_units:
            score = _similarity_score(left.text, right.text)
            if score.value < min_similarity:
                continue
            matches.append(
                {
                    "left": _unit_ref(left),
                    "right": _unit_ref(right),
                    "similarity": round(score.value, 4),
                    "method": score.method,
                }
            )

    matches.sort(key=lambda item: item["similarity"], reverse=True)
    return matches[:limit]


def _units_for_document(document: DocumentRecord, *, granularity: str) -> list[CompareUnit]:
    if granularity == "full":
        return [
            CompareUnit(
                document_id=document.id,
                original_filename=document.original_filename,
                chunk_id=0,
                chunk_index=0,
                heading=None,
                text=_document_text(document),
                unit_type="full",
                unit_label="全文",
            )
        ]

    if granularity == "section":
        grouped: list[tuple[str | None, list[DocumentChunk]]] = []
        for chunk in document.chunks:
            heading = chunk.heading or "本文"
            if grouped and grouped[-1][0] == heading:
                grouped[-1][1].append(chunk)
            else:
                grouped.append((heading, [chunk]))
        return [
            CompareUnit(
                document_id=document.id,
                original_filename=document.original_filename,
                chunk_id=chunks[0].id,
                chunk_index=index,
                heading=heading,
                text="\n\n".join(chunk.text for chunk in chunks),
                unit_type="section",
                unit_label=heading or f"section {index}",
            )
            for index, (heading, chunks) in enumerate(grouped)
        ]

    if granularity == "paragraph":
        units: list[CompareUnit] = []
        for chunk in document.chunks:
            paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", chunk.text) if paragraph.strip()]
            for paragraph_index, paragraph in enumerate(paragraphs or [chunk.text]):
                units.append(
                    CompareUnit(
                        document_id=document.id,
                        original_filename=document.original_filename,
                        chunk_id=chunk.id,
                        chunk_index=(chunk.chunk_index * 1000) + paragraph_index,
                        heading=chunk.heading,
                        text=paragraph,
                        unit_type="paragraph",
                        unit_label=f"chunk {chunk.chunk_index} paragraph {paragraph_index + 1}",
                    )
                )
        return units

    return [
        CompareUnit(
            document_id=document.id,
            original_filename=document.original_filename,
            chunk_id=chunk.id,
            chunk_index=chunk.chunk_index,
            heading=chunk.heading,
            text=chunk.text,
            unit_type="chunk",
            unit_label=f"chunk {chunk.chunk_index}",
        )
        for chunk in document.chunks
    ]


def _unit_ref(unit: CompareUnit) -> dict:
    return {
        "document_id": unit.document_id,
        "original_filename": unit.original_filename,
        "chunk_id": unit.chunk_id,
        "chunk_index": unit.chunk_index,
        "heading": unit.heading,
        "text": unit.text,
        "unit_type": unit.unit_type,
        "unit_label": unit.unit_label,
    }


def _clean_granularity(granularity: str) -> str:
    clean = (granularity or "chunk").strip().lower()
    if clean not in {"chunk", "paragraph", "section", "full"}:
        raise ValueError("granularity は chunk, paragraph, section, full のいずれかを指定してください。")
    return clean


def _similarity_score(left: str, right: str) -> SimilarityScore:
    left_normalized = _normalize_for_similarity(left)
    right_normalized = _normalize_for_similarity(right)
    if not left_normalized or not right_normalized:
        return SimilarityScore(value=0.0, method="empty")
    if left_normalized == right_normalized:
        return SimilarityScore(value=1.0, method="exact")

    sequence_ratio = SequenceMatcher(
        None,
        _trim_for_sequence(left_normalized),
        _trim_for_sequence(right_normalized),
        autojunk=False,
    ).ratio()
    left_ngrams = _char_ngrams(left_normalized)
    right_ngrams = _char_ngrams(right_normalized)
    jaccard = _jaccard(left_ngrams, right_ngrams)
    containment = _containment(left_ngrams, right_ngrams)

    candidates = {
        "sequence": sequence_ratio,
        "ngram_jaccard": jaccard,
        "ngram_containment": min(containment * 0.92, 1.0),
    }
    method, value = max(candidates.items(), key=lambda item: item[1])
    return SimilarityScore(value=value, method=method)


def _normalize_for_similarity(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"https?://\S+", " ", lowered)
    lowered = re.sub(r"[\s\u3000]+", " ", lowered)
    return lowered.strip()


def _trim_for_sequence(text: str, *, max_chars: int = 30000) -> str:
    if len(text) <= max_chars:
        return text
    head = text[: max_chars // 2]
    tail = text[-max_chars // 2 :]
    return f"{head}\n{tail}"


def _char_ngrams(text: str, *, size: int = 3) -> set[str]:
    compact = re.sub(r"[\s\u3000]+", "", text)
    if not compact:
        return set()
    if len(compact) <= size:
        return {compact}
    return {compact[index : index + size] for index in range(len(compact) - size + 1)}


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def _containment(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / min(len(left), len(right))


def _diff_documents(left_text: str, right_text: str) -> tuple[dict[str, int], list[dict]]:
    left_lines = _content_lines(left_text)
    right_lines = _content_lines(right_text)
    summary = {
        "equal_lines": 0,
        "inserted_lines": 0,
        "deleted_lines": 0,
        "replaced_left_lines": 0,
        "replaced_right_lines": 0,
    }
    excerpts: list[dict] = []

    matcher = SequenceMatcher(None, left_lines, right_lines, autojunk=False)
    for operation, left_start, left_end, right_start, right_end in matcher.get_opcodes():
        left_count = left_end - left_start
        right_count = right_end - right_start
        if operation == "equal":
            summary["equal_lines"] += left_count
            continue
        if operation == "insert":
            summary["inserted_lines"] += right_count
        elif operation == "delete":
            summary["deleted_lines"] += left_count
        elif operation == "replace":
            summary["replaced_left_lines"] += left_count
            summary["replaced_right_lines"] += right_count

        if len(excerpts) < 8:
            excerpts.append(
                {
                    "operation": operation,
                    "left_start_line": left_start + 1,
                    "right_start_line": right_start + 1,
                    "left_text": _clip_text("\n".join(left_lines[left_start:left_end])),
                    "right_text": _clip_text("\n".join(right_lines[right_start:right_end])),
                }
            )

    return summary, excerpts


def _content_lines(text: str) -> list[str]:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return [line for line in lines if line]


def _clip_text(text: str, *, max_chars: int = 700) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars].rstrip()}..."

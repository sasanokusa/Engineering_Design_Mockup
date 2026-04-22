from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models.db import DocumentComparison


class ComparisonRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_comparison(
        self,
        *,
        document_ids: list[int],
        min_similarity: float,
        granularity: str,
        result_json: dict,
    ) -> DocumentComparison:
        comparison = DocumentComparison(
            document_ids=document_ids,
            min_similarity=min_similarity,
            granularity=granularity,
            result_json=result_json,
        )
        self.db.add(comparison)
        self.db.commit()
        self.db.refresh(comparison)
        return comparison

    def get_comparison(self, comparison_id: int) -> DocumentComparison | None:
        return self.db.get(DocumentComparison, comparison_id)

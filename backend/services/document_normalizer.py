from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class NormalizedDocument:
    backend: str
    markdown: str
    data: dict[str, Any]


class DocumentNormalizer:
    def normalize(self, source_path: Path, *, original_filename: str) -> NormalizedDocument:
        docling_result = self._try_docling(source_path, original_filename=original_filename)
        if docling_result is not None:
            return docling_result
        return self._fallback_text_normalize(source_path, original_filename=original_filename)

    def _try_docling(self, source_path: Path, *, original_filename: str) -> NormalizedDocument | None:
        try:
            from docling.document_converter import DocumentConverter
        except ImportError:
            return None

        converter = DocumentConverter()
        result = converter.convert(source_path)
        document = result.document
        markdown = _call_first(document, ("export_to_markdown", "to_markdown")) or ""
        data = _call_first(document, ("export_to_dict", "model_dump", "dict")) or {}
        if not isinstance(data, dict):
            data = {"docling_repr": str(data)}
        return NormalizedDocument(
            backend="docling",
            markdown=markdown.strip(),
            data={
                "schema_version": 1,
                "backend": "docling",
                "source": {
                    "filename": original_filename,
                    "path": str(source_path),
                },
                "document": data,
                "markdown": markdown,
            },
        )

    def _fallback_text_normalize(self, source_path: Path, *, original_filename: str) -> NormalizedDocument:
        suffix = source_path.suffix.lower()
        raw = source_path.read_bytes()
        if not raw:
            raise ValueError("ファイルが空です。")

        text_like_suffixes = {
            ".txt",
            ".md",
            ".markdown",
            ".csv",
            ".tsv",
            ".json",
            ".html",
            ".htm",
            ".xml",
            ".log",
        }
        if suffix not in text_like_suffixes and b"\x00" in raw[:4096]:
            raise ValueError("Docling が未導入のため、この形式はフォールバック正規化できません。")

        text = _decode_text(raw)
        if not text.strip():
            raise ValueError("テキストを抽出できませんでした。")

        markdown = text.strip()
        if suffix == ".txt":
            markdown = f"# {Path(original_filename).stem}\n\n{markdown}"

        return NormalizedDocument(
            backend="text_fallback",
            markdown=markdown,
            data={
                "schema_version": 1,
                "backend": "text_fallback",
                "source": {
                    "filename": original_filename,
                    "path": str(source_path),
                },
                "content": {
                    "text": text,
                },
                "markdown": markdown,
            },
        )


def _call_first(target: Any, names: tuple[str, ...]) -> Any | None:
    for name in names:
        method = getattr(target, name, None)
        if callable(method):
            return method()
    return None


def _decode_text(raw: bytes) -> str:
    for encoding in ("utf-8", "utf-8-sig", "cp932"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")

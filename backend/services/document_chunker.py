from __future__ import annotations

import re
from dataclasses import dataclass


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass(frozen=True)
class ChunkingOptions:
    max_chars: int = 1200
    overlap_chars: int = 120


class DocumentChunker:
    def __init__(self, options: ChunkingOptions | None = None):
        self.options = options or ChunkingOptions()

    def chunk(self, markdown: str, *, document_id: int, source_filename: str) -> list[dict]:
        text = _normalize_newlines(markdown).strip()
        if not text:
            raise ValueError("チャンク化するテキストが空です。")

        sections = _split_sections(text)
        chunks: list[dict] = []
        for heading, section_text in sections:
            for piece in self._split_text(section_text):
                clean_piece = piece.strip()
                if not clean_piece:
                    continue
                chunks.append(
                    {
                        "chunk_index": len(chunks),
                        "text": clean_piece,
                        "heading": heading,
                        "source_locator": source_filename,
                        "metadata_json": {
                            "document_id": document_id,
                            "source_filename": source_filename,
                            "heading": heading,
                        },
                    }
                )
        if not chunks:
            raise ValueError("チャンクを生成できませんでした。")
        return chunks

    def _split_text(self, text: str) -> list[str]:
        max_chars = self.options.max_chars
        overlap = min(self.options.overlap_chars, max_chars // 3)
        paragraphs = [paragraph.strip() for paragraph in re.split(r"\n{2,}", text) if paragraph.strip()]
        pieces: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if len(paragraph) > max_chars:
                if current:
                    pieces.append(current)
                    current = ""
                pieces.extend(_window_text(paragraph, max_chars=max_chars, overlap_chars=overlap))
                continue
            proposed = f"{current}\n\n{paragraph}".strip() if current else paragraph
            if len(proposed) <= max_chars:
                current = proposed
            else:
                if current:
                    pieces.append(current)
                current = paragraph
        if current:
            pieces.append(current)
        return pieces


def _normalize_newlines(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _split_sections(text: str) -> list[tuple[str | None, str]]:
    sections: list[tuple[str | None, list[str]]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in text.split("\n"):
        match = HEADING_RE.match(line)
        if match:
            if current_lines:
                sections.append((current_heading, current_lines))
                current_lines = []
            current_heading = match.group(2).strip()
        current_lines.append(line)

    if current_lines:
        sections.append((current_heading, current_lines))

    return [(heading, "\n".join(lines).strip()) for heading, lines in sections if "\n".join(lines).strip()]


def _window_text(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = max(0, end - overlap_chars)
    return chunks

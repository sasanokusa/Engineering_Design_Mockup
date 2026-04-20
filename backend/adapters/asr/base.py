from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class ASRResult:
    text: str
    segments: list[dict[str, Any]]
    provider: str
    model: str


class ASRAdapter(Protocol):
    provider_name: str
    model_name: str

    def transcribe(self, audio_path: Path) -> ASRResult:
        """Transcribe audio through a local ASR runtime."""


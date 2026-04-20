from __future__ import annotations

import re
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from backend.config import Settings


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def safe_filename(filename: str) -> str:
    cleaned = _SAFE_NAME_RE.sub("_", Path(filename).name).strip("._")
    return cleaned or "audio"


def save_audio_upload(upload: UploadFile, settings: Settings) -> tuple[Path, str, int]:
    settings.resolved_upload_dir.mkdir(parents=True, exist_ok=True)
    original = safe_filename(upload.filename or "audio")
    stored_name = f"{uuid4().hex}_{original}"
    destination = settings.resolved_upload_dir / stored_name

    with destination.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)

    return destination, stored_name, destination.stat().st_size


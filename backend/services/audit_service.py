from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from backend.config import Settings, get_settings


class AuditService:
    """Append-only JSONL audit trail for bridge/tool actions."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.settings.ensure_storage_directories()

    def log_event(
        self,
        *,
        action: str,
        actor: str = "openwebui",
        resource_type: str | None = None,
        resource_id: str | int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "action": action,
            "resource_type": resource_type,
            "resource_id": str(resource_id) if resource_id is not None else None,
            "metadata": metadata or {},
        }
        path = self.settings.resolved_audit_dir / "openwebui_bridge.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ToolInfo:
    name: str
    display_name: str
    description: str
    status: str = "planned"


class ChatTool(Protocol):
    info: ToolInfo

    def matches(self, user_message: str) -> bool:
        """Return true when this tool may be relevant to a user message."""


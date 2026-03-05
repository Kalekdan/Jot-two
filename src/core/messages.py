from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Message:
    request_id: str
    source: str
    user_id: str
    reply_channel: str
    timestamp: int
    payload: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "source": self.source,
            "user_id": self.user_id,
            "reply_channel": self.reply_channel,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }

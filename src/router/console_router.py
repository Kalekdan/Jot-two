from __future__ import annotations

from src.core.messages import Message
from src.router.base import BaseOutputRouter


class ConsoleOutputRouter(BaseOutputRouter):
    """Routes output messages back to the console."""

    channel = "console"

    async def send(self, message: Message) -> None:
        output_text = message.payload.get("text", "")
        print(f"Jot-two: {output_text}")

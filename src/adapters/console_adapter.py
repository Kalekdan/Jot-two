from __future__ import annotations

import asyncio
from time import time
from uuid import uuid4

from src.adapters.base import BaseInputAdapter
from src.core.messages import Message


def from_console_text(text: str, user_id: str = "console_user") -> Message:
    return Message(
        request_id=str(uuid4()),
        source="console",
        user_id=user_id,
        reply_channel="console",
        timestamp=int(time()),
        payload={"text": text},
    )


class ConsoleInputAdapter(BaseInputAdapter):
    """Reads user input from stdin and pushes normalized messages to the input queue."""

    def __init__(
        self,
        input_queue: asyncio.Queue[Message],
        stop_event: asyncio.Event,
    ) -> None:
        self.input_queue = input_queue
        self.stop_event = stop_event

    async def run(self) -> None:
        print("Console adapter started. Type your message and press Enter.")
        print("Type 'exit' or 'quit' to stop.\n")

        while not self.stop_event.is_set():
            raw_text = await asyncio.to_thread(input, "> ")
            text = raw_text.strip()

            if not text:
                continue

            if text.lower() in {"exit", "quit"}:
                self.stop_event.set()
                break

            await self.input_queue.put(from_console_text(text=text))

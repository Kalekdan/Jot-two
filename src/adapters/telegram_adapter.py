from __future__ import annotations

import asyncio
import json
import os
from time import time
from typing import Any
from urllib import error, request
from uuid import uuid4

from src.adapters.base import BaseInputAdapter
from src.core.messages import Message
from src.streams.streams import MessageWriter


def _telegram_api_request(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=35) as response:
        return json.loads(response.read().decode("utf-8"))


class TelegramInputAdapter(BaseInputAdapter):
    """Polls Telegram updates and writes normalized messages to the input queue."""

    def __init__(
        self,
        input_queue: MessageWriter,
        stop_event: asyncio.Event,
    ) -> None:
        self.input_queue = input_queue
        self.stop_event = stop_event
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.poll_timeout_seconds = int(os.environ.get("TELEGRAM_POLL_TIMEOUT", "20"))
        self.retry_delay_seconds = float(os.environ.get("TELEGRAM_RETRY_DELAY", "2"))
        self._offset: int | None = None

    async def run(self) -> None:
        if not self.bot_token:
            print("Telegram input adapter disabled: TELEGRAM_BOT_TOKEN is not set.")
            await self.stop_event.wait()
            return

        print("Telegram input adapter started.")

        while not self.stop_event.is_set():
            try:
                payload: dict[str, Any] = {
                    "timeout": self.poll_timeout_seconds,
                    "allowed_updates": ["message"],
                }
                if self._offset is not None:
                    payload["offset"] = self._offset

                response = await asyncio.to_thread(
                    _telegram_api_request,
                    self.bot_token,
                    "getUpdates",
                    payload,
                )

                if not response.get("ok", False):
                    await asyncio.sleep(self.retry_delay_seconds)
                    continue

                updates: list[dict[str, Any]] = response.get("result", [])
                for update in updates:
                    update_id = update.get("update_id")
                    if isinstance(update_id, int):
                        self._offset = update_id + 1

                    message_data = update.get("message") or {}
                    text = message_data.get("text")
                    if not isinstance(text, str) or not text.strip():
                        continue

                    chat = message_data.get("chat") or {}
                    chat_id = chat.get("id")
                    if chat_id is None:
                        continue

                    message = Message(
                        request_id=str(uuid4()),
                        source="telegram",
                        user_id=str(chat_id),
                        reply_channel="telegram",
                        timestamp=int(time()),
                        payload={"text": text.strip()},
                    )
                    await self.input_queue.put(message)

            except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                print(f"Telegram input adapter request error: {exc}")
                await asyncio.sleep(self.retry_delay_seconds)

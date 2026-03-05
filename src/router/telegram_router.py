from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from urllib import error, request

from src.core.messages import Message
from src.router.base import BaseOutputRouter


def _telegram_api_request(token: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"https://api.telegram.org/bot{token}/{method}"
    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


class TelegramOutputRouter(BaseOutputRouter):
    """Routes outgoing messages to Telegram chats via the Bot API."""

    channel = "telegram"

    def __init__(self) -> None:
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not self.bot_token:
            # Keep a non-telegram channel key so dispatch can fall back if configured.
            self.channel = "_telegram_disabled"

    async def send(self, message: Message) -> None:
        if not self.bot_token:
            print("Telegram output router disabled: TELEGRAM_BOT_TOKEN is not set.")
            return

        chat_id = message.payload.get("chat_id", message.user_id)
        text = str(message.payload.get("text", ""))
        if not text.strip():
            return

        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }

        try:
            response = await asyncio.to_thread(
                _telegram_api_request,
                self.bot_token,
                "sendMessage",
                payload,
            )
            if not response.get("ok", False):
                print(f"Telegram output router error response: {response}")
        except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            print(f"Telegram output router request error: {exc}")

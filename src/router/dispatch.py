from __future__ import annotations

from src.core.messages import Message
from src.router.base import BaseOutputRouter
from src.router.loader import load_output_routers


class DispatchOutputRouter:
    """Dispatches output messages based on message.reply_channel."""

    def __init__(self) -> None:
        self.routers: dict[str, BaseOutputRouter] = load_output_routers()

    async def send(self, message: Message) -> None:
        router = self.routers.get(message.reply_channel)

        if router is None:
            fallback = self.routers.get("console")
            if fallback is not None:
                await fallback.send(message)
                return

            raise ValueError(f"No output router configured for channel '{message.reply_channel}'.")

        await router.send(message)

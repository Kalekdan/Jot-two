from __future__ import annotations

import asyncio

from src.core.messages import Message


class Agent:
    """Simple placeholder agent that returns a generic response."""

    async def process(self, message: Message) -> Message:
        text = message.payload.get("text", "")

        response = Message(
            request_id=message.request_id,
            source="agent",
            user_id=message.user_id,
            reply_channel=message.reply_channel,
            timestamp=message.timestamp,
            payload={
                "text": f"Received: '{text}'. This is a mock response from Jot-two.",
            },
        )

        await asyncio.sleep(0)
        return response

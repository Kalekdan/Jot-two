from __future__ import annotations

from abc import ABC, abstractmethod

from src.core.messages import Message


class BaseOutputRouter(ABC):
    """Contract for output routers keyed by reply channel."""

    channel: str

    @abstractmethod
    async def send(self, message: Message) -> None:
        raise NotImplementedError

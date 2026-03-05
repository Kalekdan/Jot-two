from __future__ import annotations

from abc import ABC, abstractmethod


class BaseInputAdapter(ABC):
    """Contract for any input adapter discovered from src/adapters."""

    @abstractmethod
    async def run(self) -> None:
        raise NotImplementedError

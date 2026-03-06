from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Base interface that all agent tools should implement."""

    name: str
    description: str
    parameters: dict[str, Any]

    @abstractmethod
    async def execute(self, **kwargs: Any) -> dict[str, Any]:
        """Run the tool with keyword arguments and return a JSON-serializable result."""

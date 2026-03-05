from __future__ import annotations

import importlib
import inspect
import pkgutil
import asyncio

import src.adapters as adapters_pkg
from src.adapters.base import BaseInputAdapter
from src.core.messages import Message


def load_input_adapters(
    input_queue: asyncio.Queue[Message],
    stop_event: asyncio.Event,
) -> list[BaseInputAdapter]:
    """Discover and instantiate adapter classes from src/adapters modules."""
    adapters: list[BaseInputAdapter] = []

    for module_info in pkgutil.iter_modules(adapters_pkg.__path__):
        module_name = module_info.name
        if module_name in {"__init__", "base", "loader"}:
            continue

        module = importlib.import_module(f"src.adapters.{module_name}")

        for _, candidate in inspect.getmembers(module, inspect.isclass):
            if not issubclass(candidate, BaseInputAdapter):
                continue
            if candidate is BaseInputAdapter:
                continue
            if candidate.__module__ != module.__name__:
                continue

            adapters.append(candidate(input_queue=input_queue, stop_event=stop_event))

    return adapters

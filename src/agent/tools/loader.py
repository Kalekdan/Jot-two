from __future__ import annotations

import importlib
import inspect
import pkgutil

import src.agent.tools as tools_pkg
from src.agent.tools.base import BaseTool


def load_tools() -> dict[str, BaseTool]:
    """Discover and instantiate tools from src/agent/tools modules."""
    tools: dict[str, BaseTool] = {}

    for module_info in pkgutil.iter_modules(tools_pkg.__path__):
        module_name = module_info.name
        if module_name in {"__init__", "base", "loader"}:
            continue

        module = importlib.import_module(f"src.agent.tools.{module_name}")

        for _, candidate in inspect.getmembers(module, inspect.isclass):
            if not issubclass(candidate, BaseTool):
                continue
            if candidate is BaseTool:
                continue
            if inspect.isabstract(candidate):
                continue
            if candidate.__module__ != module.__name__:
                continue

            instance = candidate()
            if instance.name in tools:
                raise ValueError(f"Duplicate tool name discovered: {instance.name}")
            tools[instance.name] = instance

    return tools

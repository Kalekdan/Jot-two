from __future__ import annotations

import importlib
import inspect
import pkgutil

import src.router as router_pkg
from src.router.base import BaseOutputRouter


def load_output_routers() -> dict[str, BaseOutputRouter]:
    """Discover and instantiate output routers from src/router modules."""
    routers: dict[str, BaseOutputRouter] = {}

    for module_info in pkgutil.iter_modules(router_pkg.__path__):
        module_name = module_info.name
        if module_name in {"__init__", "base", "loader", "dispatch"}:
            continue

        module = importlib.import_module(f"src.router.{module_name}")

        for _, candidate in inspect.getmembers(module, inspect.isclass):
            if not issubclass(candidate, BaseOutputRouter):
                continue
            if candidate is BaseOutputRouter:
                continue
            if candidate.__module__ != module.__name__:
                continue

            instance = candidate()
            routers[instance.channel] = instance

    return routers

from __future__ import annotations

"""Entrypoint for the jot-adapters container.

Discovers all input adapters and runs them.  Each adapter writes incoming
messages directly to the ``jot:input`` Redis stream.
"""

import asyncio
import signal

from src.adapters.loader import load_input_adapters
from src.streams.client import get_redis_client
from src.streams.streams import INPUT_STREAM, RedisStreamWriter


async def run() -> None:
    redis_client = await get_redis_client()
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    writer = RedisStreamWriter(redis_client, INPUT_STREAM)
    adapters = load_input_adapters(input_queue=writer, stop_event=stop_event)
    if not adapters:
        raise RuntimeError("No input adapters found in src/adapters.")

    adapter_tasks = [asyncio.create_task(adapter.run()) for adapter in adapters]
    await asyncio.gather(*adapter_tasks)

    await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(run())

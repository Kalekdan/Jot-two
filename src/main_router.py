from __future__ import annotations

"""Entrypoint for the jot-router container.

Continuously reads messages from the ``jot:output`` Redis stream and
dispatches each one via the DispatchOutputRouter.  Stops cleanly on SIGTERM
or SIGINT.
"""

import asyncio
import signal

from src.router.dispatch import DispatchOutputRouter
from src.streams.client import get_redis_client
from src.streams.streams import (
    OUTPUT_STREAM,
    ROUTER_CONSUMER_GROUP,
    ack_message,
    ensure_consumer_group,
    parse_message,
    read_messages,
)


async def router_worker(redis_client, stop_event: asyncio.Event) -> None:
    """Read from the output stream and dispatch each message via the router."""
    router = DispatchOutputRouter()
    await ensure_consumer_group(redis_client, OUTPUT_STREAM, ROUTER_CONSUMER_GROUP)

    while not stop_event.is_set():
        entries = await read_messages(
            redis_client, OUTPUT_STREAM, ROUTER_CONSUMER_GROUP, "jot-router-1"
        )
        for _stream, messages in entries:
            for entry_id, fields in messages:
                message = parse_message(fields["data"])
                await router.send(message)
                await ack_message(
                    redis_client, OUTPUT_STREAM, ROUTER_CONSUMER_GROUP, entry_id
                )


async def run() -> None:
    redis_client = await get_redis_client()
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    try:
        await router_worker(redis_client, stop_event)
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(run())

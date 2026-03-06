from __future__ import annotations

"""Entrypoint for the jot-core container.

Continuously reads messages from the ``jot:input`` Redis stream, passes them
to the Agent for processing, and writes the responses to the ``jot:output``
Redis stream.  Stops cleanly on SIGTERM or SIGINT.
"""

import asyncio
import signal

from src.agent.agent import Agent
from src.streams.client import get_redis_client
from src.streams.streams import (
    CORE_CONSUMER_GROUP,
    INPUT_STREAM,
    OUTPUT_STREAM,
    ack_message,
    ensure_consumer_group,
    parse_message,
    read_messages,
    write_message,
)


async def core_worker(redis_client, stop_event: asyncio.Event) -> None:
    """Read from the input stream, invoke the agent, write responses to the output stream."""
    agent = Agent()
    await agent.initialize()
    await ensure_consumer_group(redis_client, INPUT_STREAM, CORE_CONSUMER_GROUP)

    try:
        while not stop_event.is_set():
            entries = await read_messages(
                redis_client, INPUT_STREAM, CORE_CONSUMER_GROUP, "jot-core-1"
            )
            for _stream, messages in entries:
                for entry_id, fields in messages:
                    message = parse_message(fields["data"])
                    response = await agent.process(message)
                    await write_message(redis_client, OUTPUT_STREAM, response)
                    await ack_message(redis_client, INPUT_STREAM, CORE_CONSUMER_GROUP, entry_id)
    finally:
        await agent.close()


async def run() -> None:
    redis_client = await get_redis_client()
    stop_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    try:
        await core_worker(redis_client, stop_event)
    finally:
        await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(run())

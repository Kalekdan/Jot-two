from __future__ import annotations

import asyncio

from src.adapters.loader import load_input_adapters
from src.agent.agent import Agent
from src.router.dispatch import DispatchOutputRouter
from src.streams.client import get_redis_client
from src.streams.streams import (
    CORE_CONSUMER_GROUP,
    INPUT_STREAM,
    OUTPUT_STREAM,
    ROUTER_CONSUMER_GROUP,
    RedisStreamWriter,
    ack_message,
    ensure_consumer_group,
    parse_message,
    read_messages,
    write_message,
)


async def core_worker(redis_client, agent: Agent, stop_event: asyncio.Event) -> None:
    """Read from the input stream, invoke the agent, and write responses to the output stream."""
    await ensure_consumer_group(redis_client, INPUT_STREAM, CORE_CONSUMER_GROUP)

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


async def router_worker(
    redis_client, router: DispatchOutputRouter, stop_event: asyncio.Event
) -> None:
    """Read from the output stream and dispatch each message via the router."""
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

    writer = RedisStreamWriter(redis_client, INPUT_STREAM)
    adapters = load_input_adapters(input_queue=writer, stop_event=stop_event)
    if not adapters:
        raise RuntimeError("No input adapters found in src/adapters.")

    agent = Agent()
    router = DispatchOutputRouter()

    adapter_tasks = [asyncio.create_task(adapter.run()) for adapter in adapters]
    core_task = asyncio.create_task(core_worker(redis_client, agent, stop_event))
    router_task = asyncio.create_task(router_worker(redis_client, router, stop_event))

    await asyncio.gather(*adapter_tasks)
    stop_event.set()
    for task in (core_task, router_task):
        try:
            await task
        except Exception as exc:
            print(f"Worker error: {exc}")

    await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(run())

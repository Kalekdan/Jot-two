from __future__ import annotations

import json
from typing import Any, Protocol

import redis.asyncio as aioredis

from src.core.messages import Message

INPUT_STREAM = "jot:input"
OUTPUT_STREAM = "jot:output"
CORE_CONSUMER_GROUP = "jot-core"
ROUTER_CONSUMER_GROUP = "jot-router"
_BLOCK_MS = 1000


class MessageWriter(Protocol):
    """Protocol for objects that accept Message objects for queuing."""

    async def put(self, message: Message) -> None: ...


async def ensure_consumer_group(
    client: aioredis.Redis,
    stream: str,
    group: str,
) -> None:
    """Create a consumer group; silently ignore the error if it already exists."""
    try:
        await client.xgroup_create(stream, group, id="0", mkstream=True)
    except aioredis.ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def write_message(client: aioredis.Redis, stream: str, message: Message) -> str:
    """Serialize and append a Message to a Redis stream. Returns the entry ID."""
    entry_id: str = await client.xadd(stream, {"data": json.dumps(message.as_dict())})
    return entry_id


async def read_messages(
    client: aioredis.Redis,
    stream: str,
    group: str,
    consumer: str,
    count: int = 1,
) -> list[Any]:
    """Block-read from a Redis stream consumer group.

    Blocks for up to 1 second when no messages are available.
    Returns the raw xreadgroup output (empty list when nothing arrived).
    """
    result = await client.xreadgroup(
        groupname=group,
        consumername=consumer,
        streams={stream: ">"},
        count=count,
        block=_BLOCK_MS,
    )
    return result or []


async def ack_message(
    client: aioredis.Redis,
    stream: str,
    group: str,
    entry_id: str,
) -> None:
    """Acknowledge successful processing of a stream entry."""
    await client.xack(stream, group, entry_id)


def parse_message(data: str) -> Message:
    """Deserialize a JSON string into a Message."""
    return Message(**json.loads(data))


class RedisStreamWriter:
    """Wraps a Redis stream and exposes the same async put() interface as asyncio.Queue."""

    def __init__(self, client: aioredis.Redis, stream: str) -> None:
        self.client = client
        self.stream = stream

    async def put(self, message: Message) -> None:
        await write_message(self.client, self.stream, message)

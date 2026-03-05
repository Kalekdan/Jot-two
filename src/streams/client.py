from __future__ import annotations

import os

import redis.asyncio as aioredis

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")


async def get_redis_client() -> aioredis.Redis:
    """Create and return an async Redis client from REDIS_URL env var."""
    client: aioredis.Redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    return client

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg


DEFAULT_DATABASE_URL = "postgresql://jot:jot@postgres:5432/jot"


@dataclass(slots=True)
class ConversationSummary:
    summary_text: str
    created_at: datetime


class ConversationStore:
    """Persistent conversation storage backed by PostgreSQL."""

    def __init__(self) -> None:
        self.database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL).strip()
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(dsn=self.database_url, min_size=1, max_size=8)
        await self._init_schema()

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def _init_schema(self) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id BIGSERIAL PRIMARY KEY,
                    conversation_key TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    message_timestamp BIGINT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_conversation_messages_key_id
                    ON conversation_messages (conversation_key, id DESC);

                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    id BIGSERIAL PRIMARY KEY,
                    conversation_key TEXT NOT NULL,
                    summary_text TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );

                CREATE INDEX IF NOT EXISTS idx_conversation_summaries_key_id
                    ON conversation_summaries (conversation_key, id DESC);
                """
            )

    async def append_message(
        self,
        conversation_key: str,
        role: str,
        content: str,
        message_timestamp: int | None,
    ) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversation_messages (conversation_key, role, content, message_timestamp)
                VALUES ($1, $2, $3, $4)
                """,
                conversation_key,
                role,
                content,
                message_timestamp,
            )

    async def get_recent_messages(
        self,
        conversation_key: str,
        limit: int,
    ) -> list[dict[str, str]]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT role, content
                FROM conversation_messages
                WHERE conversation_key = $1
                ORDER BY id DESC
                LIMIT $2
                """,
                conversation_key,
                limit,
            )

        # Reverse so messages are returned oldest -> newest for chat payload ordering.
        return [
            {"role": str(row["role"]), "content": str(row["content"])}
            for row in reversed(rows)
        ]

    async def get_latest_summary(self, conversation_key: str) -> ConversationSummary | None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT summary_text, created_at
                FROM conversation_summaries
                WHERE conversation_key = $1
                ORDER BY id DESC
                LIMIT 1
                """,
                conversation_key,
            )

        if row is None:
            return None

        return ConversationSummary(
            summary_text=str(row["summary_text"]),
            created_at=row["created_at"],
        )

    async def count_messages_since(
        self,
        conversation_key: str,
        after: datetime | None,
    ) -> int:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            if after is None:
                value = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM conversation_messages
                    WHERE conversation_key = $1
                    """,
                    conversation_key,
                )
            else:
                value = await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM conversation_messages
                    WHERE conversation_key = $1 AND created_at > $2
                    """,
                    conversation_key,
                    after,
                )

        return int(value or 0)

    async def get_messages_since(
        self,
        conversation_key: str,
        after: datetime | None,
    ) -> list[dict[str, str]]:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            if after is None:
                rows = await conn.fetch(
                    """
                    SELECT role, content
                    FROM conversation_messages
                    WHERE conversation_key = $1
                    ORDER BY id ASC
                    """,
                    conversation_key,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT role, content
                    FROM conversation_messages
                    WHERE conversation_key = $1 AND created_at > $2
                    ORDER BY id ASC
                    """,
                    conversation_key,
                    after,
                )

        return [{"role": str(row["role"]), "content": str(row["content"])} for row in rows]

    async def add_summary(self, conversation_key: str, summary_text: str) -> None:
        assert self._pool is not None
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO conversation_summaries (conversation_key, summary_text)
                VALUES ($1, $2)
                """,
                conversation_key,
                summary_text,
            )

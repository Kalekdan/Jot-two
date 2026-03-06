from __future__ import annotations

"""FastAPI server for the Jot-two web UI.

Provides:
- REST endpoints for dashboard data (Redis streams, Postgres tables, service status)
- WebSocket endpoint for the chat interface
- Static file serving for the React frontend
"""

import asyncio
import json
import logging
import os
import re
from contextlib import asynccontextmanager
from pathlib import Path
from time import time
from typing import Any
from uuid import uuid4

import asyncpg
import docker as docker_sdk
import redis.asyncio as aioredis
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.streams.streams import (
    INPUT_STREAM,
    OUTPUT_STREAM,
    ensure_consumer_group,
    write_message,
)
from src.core.messages import Message

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parents[2] / "web-app" / "dist"
WEBAPP_CONSUMER_GROUP = "jot-webapp"
WEBAPP_CONSUMER_NAME = "jot-webapp-1"


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    stop_event = asyncio.Event()
    dispatcher_task = asyncio.create_task(output_dispatcher(stop_event))
    app.state.stop_event = stop_event
    app.state.dispatcher_task = dispatcher_task
    yield
    stop_event.set()
    try:
        await asyncio.wait_for(dispatcher_task, timeout=3.0)
    except (asyncio.TimeoutError, asyncio.CancelledError, Exception):
        pass


app = FastAPI(title="Jot-two Web UI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ConnectionManager:
    """Tracks active WebSocket connections keyed by user_id."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[user_id] = websocket

    def disconnect(self, user_id: str) -> None:
        self._connections.pop(user_id, None)

    async def send(self, user_id: str, data: dict[str, Any]) -> None:
        ws = self._connections.get(user_id)
        if ws is not None:
            try:
                await ws.send_json(data)
            except Exception:
                self.disconnect(user_id)


manager = ConnectionManager()


def _get_redis_url() -> str:
    return os.environ.get("REDIS_URL", "redis://localhost:6379")


def _get_database_url() -> str:
    return os.environ.get(
        "DATABASE_URL",
        "postgresql://jot:jot@localhost:5432/jot",
    )


async def _get_redis() -> aioredis.Redis:
    return await aioredis.from_url(_get_redis_url(), decode_responses=True)


async def _get_pg_conn() -> asyncpg.Connection:
    db_url = _get_database_url()
    # asyncpg accepts both postgresql:// and postgres:// schemes natively
    return await asyncpg.connect(db_url)


# ---------------------------------------------------------------------------
# REST API endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/streams")
async def get_streams() -> dict[str, Any]:
    """Return Redis stream information including lengths and consumer groups."""
    try:
        redis_client = await _get_redis()
        try:
            streams: dict[str, Any] = {}
            for stream_name in (INPUT_STREAM, OUTPUT_STREAM):
                length = await redis_client.xlen(stream_name)
                groups_raw = await redis_client.xinfo_groups(stream_name)
                groups = [
                    {
                        "name": g.get("name", ""),
                        "consumers": g.get("consumers", 0),
                        "pending": g.get("pending", 0),
                        "last_delivered_id": g.get("last-delivered-id", ""),
                    }
                    for g in groups_raw
                ]
                # Get a sample of recent messages to identify sources
                recent_raw = await redis_client.xrevrange(stream_name, count=50)
                sources: list[str] = []
                for _entry_id, fields in recent_raw:
                    try:
                        msg_data = json.loads(fields.get("data", "{}"))
                        src = msg_data.get("source", "")
                        if src and src not in sources:
                            sources.append(src)
                    except (json.JSONDecodeError, AttributeError):
                        pass
                streams[stream_name] = {
                    "length": length,
                    "groups": groups,
                    "recent_sources": sources,
                }
            return {"ok": True, "streams": streams}
        finally:
            await redis_client.aclose()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "streams": {}}


@app.get("/api/database")
async def get_database() -> dict[str, Any]:
    """Return PostgreSQL table list with row counts."""
    try:
        conn = await _get_pg_conn()
        try:
            table_rows = await conn.fetch(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
                """
            )
            tables: list[dict[str, Any]] = []
            for row in table_rows:
                table_name = row["table_name"]
                # Validate table name to only allow safe identifier characters
                # (letters, digits, underscore) before embedding in SQL
                if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", table_name):
                    tables.append({"name": table_name, "row_count": -1})
                    continue
                try:
                    count_row = await conn.fetchrow(
                        f'SELECT COUNT(*) AS cnt FROM "{table_name}"'
                    )
                    row_count = count_row["cnt"] if count_row else 0
                except Exception:
                    row_count = -1
                tables.append({"name": table_name, "row_count": row_count})
            return {"ok": True, "tables": tables}
        finally:
            await conn.close()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "tables": []}


@app.get("/api/status")
async def get_status() -> dict[str, Any]:
    """Return connectivity status for Redis and PostgreSQL."""
    status: dict[str, Any] = {}

    # Redis
    try:
        redis_client = await _get_redis()
        pong = await redis_client.ping()
        await redis_client.aclose()
        status["redis"] = {"connected": bool(pong)}
    except Exception as exc:
        status["redis"] = {"connected": False, "error": str(exc)}

    # PostgreSQL
    try:
        conn = await _get_pg_conn()
        await conn.fetchval("SELECT 1")
        await conn.close()
        status["postgres"] = {"connected": True}
    except Exception as exc:
        status["postgres"] = {"connected": False, "error": str(exc)}

    return {"ok": True, "status": status}


@app.get("/api/containers")
async def get_containers() -> dict[str, Any]:
    """Return Docker container names and their run status.

    Requires the Docker socket to be mounted at /var/run/docker.sock.
    """
    def _list_containers() -> list[dict[str, Any]]:
        client = docker_sdk.from_env()
        containers = client.containers.list(all=True)
        result = []
        for c in containers:
            result.append(
                {
                    "id": c.short_id,
                    "name": c.name,
                    "image": c.image.tags[0] if len(c.image.tags) > 0 else c.image.short_id,
                    "status": c.status,
                    "running": c.status == "running",
                }
            )
        client.close()
        return result

    try:
        containers = await asyncio.to_thread(_list_containers)
        return {"ok": True, "containers": containers}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "containers": []}


@app.get("/api/database/{table_name}/rows")
async def get_table_rows(
    table_name: str,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Return a paginated preview of rows from a PostgreSQL table."""
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", table_name):
        return {"ok": False, "error": "Invalid table name.", "columns": [], "rows": []}

    safe_limit = max(1, min(limit, 200))
    safe_offset = max(0, offset)

    try:
        conn = await _get_pg_conn()
        try:
            # Verify the table exists in the public schema before querying it
            exists = await conn.fetchval(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_type = 'BASE TABLE'
                      AND table_name = $1
                )
                """,
                table_name,
            )
            if not exists:
                return {"ok": False, "error": f"Table '{table_name}' not found.", "columns": [], "rows": []}

            rows = await conn.fetch(
                f'SELECT * FROM "{table_name}" LIMIT $1 OFFSET $2',
                safe_limit,
                safe_offset,
            )
            if rows:
                columns = list(rows[0].keys())
                data = [[str(v) if v is not None else None for v in r.values()] for r in rows]
            else:
                # Fetch column names even when the table is empty
                col_rows = await conn.fetch(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = $1
                    ORDER BY ordinal_position
                    """,
                    table_name,
                )
                columns = [r["column_name"] for r in col_rows]
                data = []
            return {"ok": True, "columns": columns, "rows": data}
        finally:
            await conn.close()
    except Exception as exc:
        return {"ok": False, "error": str(exc), "columns": [], "rows": []}


# ---------------------------------------------------------------------------
# WebSocket chat endpoint
# ---------------------------------------------------------------------------


@app.websocket("/ws/chat/{user_id}")
async def websocket_chat(websocket: WebSocket, user_id: str) -> None:
    """WebSocket endpoint for the chat interface.

    - Incoming text messages are written to the ``jot:input`` Redis stream
      with source='web-app' and reply_channel='web-app'.
    - Outgoing responses are delivered by the background dispatcher task.
    """
    await manager.connect(user_id, websocket)
    try:
        while True:
            raw = await websocket.receive_text()
            text = raw.strip()
            if not text:
                continue
            try:
                redis_client = await _get_redis()
                message = Message(
                    request_id=str(uuid4()),
                    source="web-app",
                    user_id=user_id,
                    reply_channel="web-app",
                    timestamp=int(time()),
                    payload={"text": text},
                )
                await write_message(redis_client, INPUT_STREAM, message)
                await redis_client.aclose()
            except Exception as exc:
                await websocket.send_json({"type": "error", "text": str(exc)})
    except WebSocketDisconnect:
        manager.disconnect(user_id)


# ---------------------------------------------------------------------------
# Background task: read jot:output and deliver web-app messages
# ---------------------------------------------------------------------------


async def output_dispatcher(stop_event: asyncio.Event) -> None:
    """Continuously read from jot:output and forward web-app messages to WS clients."""
    try:
        redis_client = await _get_redis()
    except Exception as exc:
        logger.warning("output_dispatcher: could not connect to Redis: %s", exc)
        return
    try:
        await ensure_consumer_group(redis_client, OUTPUT_STREAM, WEBAPP_CONSUMER_GROUP)
        while not stop_event.is_set():
            try:
                result = await redis_client.xreadgroup(
                    groupname=WEBAPP_CONSUMER_GROUP,
                    consumername=WEBAPP_CONSUMER_NAME,
                    streams={OUTPUT_STREAM: ">"},
                    count=10,
                    block=1000,
                )
                if not result:
                    continue
                for _stream, messages in result:
                    for entry_id, fields in messages:
                        try:
                            msg_data = json.loads(fields.get("data", "{}"))
                            if msg_data.get("reply_channel") == "web-app":
                                user_id = msg_data.get("user_id", "")
                                text = msg_data.get("payload", {}).get("text", "")
                                await manager.send(
                                    user_id,
                                    {"type": "message", "text": text, "role": "assistant"},
                                )
                        except (json.JSONDecodeError, AttributeError):
                            pass
                        await redis_client.xack(
                            OUTPUT_STREAM, WEBAPP_CONSUMER_GROUP, entry_id
                        )
            except aioredis.ResponseError as exc:
                logger.warning("Redis error in output dispatcher: %s", exc)
                await asyncio.sleep(1)
    except Exception as exc:
        logger.warning("output_dispatcher stopped: %s", exc)
    finally:
        await redis_client.aclose()


# ---------------------------------------------------------------------------
# Static file serving for the React frontend
# ---------------------------------------------------------------------------

if STATIC_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(STATIC_DIR / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        """Serve the SPA index.html for any non-API route."""
        index = STATIC_DIR / "index.html"
        return FileResponse(str(index))

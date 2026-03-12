"""
PostgresRegistryProvider

Startup:  load_all() via mod_schema → hydrate local cache
Fallback: get_tool() via mod_schema → cache miss lookup
Updates:  Postgres LISTEN/NOTIFY — instant push on INSERT or status change.
          A trigger in postgres/init.sql fires NOTIFY on every INSERT/UPDATE
          to the mods table, carrying the tool_id and new status.

All schema knowledge (SQL, column names, row mapping) lives in mod_schema.py.
This file owns only the Postgres connection and LISTEN/NOTIFY plumbing.
"""

from __future__ import annotations
import asyncio
import json
import logging

import asyncpg

from models import ToolDefinition
from mod_schema import NOTIFY_CHANNEL, LOAD_ALL_SQL, GET_TOOL_SQL, row_to_tool
from registry.base import ToolRegistryProvider, UpdateCallback

log = logging.getLogger("registry.postgres")


class PostgresRegistryProvider(ToolRegistryProvider):

    def __init__(self, dsn: str, reconnect_delay_seconds: int = 2):
        self._dsn = dsn
        self._reconnect_delay = reconnect_delay_seconds
        self._pool: asyncpg.Pool | None = None
        self._listen_task: asyncio.Task | None = None

    @property
    def flavor(self) -> str:
        return "postgres-notify"

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(self._dsn, min_size=2, max_size=10)
        await self._pool.fetchval("SELECT 1")
        log.info("[Postgres] Connected.")

    async def close(self) -> None:
        if self._listen_task:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
        if self._pool:
            await self._pool.close()
        log.info("[Postgres] Connections closed.")

    # ── Registry interface ────────────────────────────────────────────────────

    async def load_all(self) -> list[ToolDefinition]:
        rows = await self._pool.fetch(LOAD_ALL_SQL)
        tools = [row_to_tool(r) for r in rows]
        log.info(f"[Postgres] Loaded {len(tools)} ACTIVE tools.")
        return tools

    async def get_tool(self, tool_id: str) -> ToolDefinition | None:
        row = await self._pool.fetchrow(GET_TOOL_SQL, tool_id)
        return row_to_tool(row) if row else None

    async def subscribe(self, on_update: UpdateCallback) -> None:
        self._listen_task = asyncio.create_task(
            self._listen_loop(on_update),
            name="postgres-listen-loop",
        )
        log.info(f"[Postgres] Subscribed to LISTEN/{NOTIFY_CHANNEL}.")

    # ── LISTEN loop with auto-reconnect ──────────────────────────────────────

    async def _listen_loop(self, on_update: UpdateCallback) -> None:
        while True:
            conn: asyncpg.Connection | None = None
            try:
                conn = await asyncpg.connect(self._dsn)

                async def _on_notify(
                    connection: asyncpg.Connection,
                    pid: int,
                    channel: str,
                    payload: str,
                ) -> None:
                    await self._handle_notify(payload, on_update)

                await conn.add_listener(NOTIFY_CHANNEL, _on_notify)
                log.info("[Postgres] LISTEN connection established.")

                await asyncio.Future()  # hold open until cancelled or dropped

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.warning(
                    f"[Postgres] LISTEN connection lost ({e}); "
                    f"reconnecting in {self._reconnect_delay}s."
                )
                await asyncio.sleep(self._reconnect_delay)
            finally:
                if conn and not conn.is_closed():
                    try:
                        await conn.remove_listener(NOTIFY_CHANNEL, _on_notify)
                        await conn.close()
                    except Exception:
                        pass

    async def _handle_notify(self, payload: str, on_update: UpdateCallback) -> None:
        """
        Payload sent by the Postgres trigger:
          {"tool_id": "...", "status": "ACTIVE" | "DEPRECATED" | "RETIRED"}
        """
        try:
            data = json.loads(payload)
            tool_id: str = data["tool_id"]
            status: str = data["status"]
        except Exception as e:
            log.error(f"[Postgres] Malformed NOTIFY payload '{payload}': {e}")
            return

        if status == "RETIRED":
            log.info(f"[Postgres] NOTIFY → TOOL_RETIRED: {tool_id}")
            await on_update("TOOL_RETIRED", tool_id, None)
            return

        row = await self._pool.fetchrow(GET_TOOL_SQL, tool_id)
        if not row:
            log.warning(f"[Postgres] NOTIFY for {tool_id} but row not found.")
            return

        tool = row_to_tool(row)
        event = "TOOL_DEPRECATED" if status == "DEPRECATED" else "TOOL_REGISTERED"
        log.info(f"[Postgres] NOTIFY → {event}: {tool_id}")
        await on_update(event, tool_id, tool)

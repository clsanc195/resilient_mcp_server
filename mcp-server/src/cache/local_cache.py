"""
LocalCache — In-memory tool cache

Performance layer only. Never the authoritative source.
A cache miss always falls through to the registry provider (Redis/Kafka/Postgres).

Thread-safe for asyncio (single-threaded event loop). If you move to
multi-threaded execution, add asyncio.Lock around mutations.
"""

from __future__ import annotations
import logging
from models import ToolDefinition, ToolStatus

log = logging.getLogger("local-cache")


class LocalCache:

    def __init__(self):
        self._store: dict[str, ToolDefinition] = {}

    def get(self, tool_id: str) -> ToolDefinition | None:
        return self._store.get(tool_id)

    def set(self, tool_id: str, tool: ToolDefinition) -> None:
        self._store[tool_id] = tool

    def delete(self, tool_id: str) -> None:
        self._store.pop(tool_id, None)

    def load_all(self, tools: list[ToolDefinition]) -> None:
        """Bulk load — used during startup hydration."""
        for tool in tools:
            self._store[tool.toolId] = tool

    def list_active(self) -> list[ToolDefinition]:
        """All ACTIVE tools — used for tools/list responses."""
        return [t for t in self._store.values() if t.status == ToolStatus.ACTIVE]

    def clear(self) -> None:
        self._store.clear()

    def size(self) -> int:
        return len(self._store)

    def snapshot(self) -> list[dict]:
        """Debug snapshot — all tools with minimal fields."""
        return [
            {
                "toolId":  t.toolId,
                "name":    t.name,
                "version": t.version,
                "status":  t.status,
            }
            for t in self._store.values()
        ]

"""
ToolRegistryProvider — Abstract Interface

Every flavor of registry (Redis, Kafka, Postgres) implements this interface.
The MCP server depends only on this abstraction — it has zero knowledge of
which concrete provider is wired in at runtime.

Contract:
  - load_all()     → called once at startup to hydrate the local cache
  - get_tool()     → called on local cache miss as a fallback lookup
  - subscribe()    → called after startup to receive live update notifications
  - close()        → called on server shutdown to clean up connections

The on_update callback signature:
  async def on_update(event_type: str, tool_id: str, tool: ToolDefinition | None)
    event_type: "TOOL_REGISTERED" | "TOOL_UPDATED" | "TOOL_DEPRECATED" | "TOOL_RETIRED"
    tool:       the new ToolDefinition for REGISTERED/UPDATED/DEPRECATED, None for RETIRED
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable, Awaitable
from models import ToolDefinition

# Type alias for the update callback the MCP server passes to subscribe()
UpdateCallback = Callable[[str, str, ToolDefinition | None], Awaitable[None]]


class ToolRegistryProvider(ABC):
    """
    Abstract base class for all tool registry providers.

    Implementations:
      - RedisRegistryProvider    — Redis HGETALL on startup, pub/sub for updates, HGET for fallback
      - KafkaRegistryProvider    — Kafka topic replay on startup, consumer per-instance for updates
      - PostgresRegistryProvider — Direct Postgres queries, polling for updates (no Redis/Kafka needed)
    """

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connections to the underlying infrastructure.
        Called once before any other method.
        Should raise an exception if the connection cannot be established —
        the MCP server treats connection failure as a fatal startup error.
        """
        ...

    @abstractmethod
    async def load_all(self) -> list[ToolDefinition]:
        """
        Load all currently ACTIVE tool definitions.
        Called once at startup to hydrate the local in-memory cache.
        Must return a complete, consistent snapshot of the registry.
        """
        ...

    @abstractmethod
    async def get_tool(self, tool_id: str) -> ToolDefinition | None:
        """
        Fetch a single tool definition by toolId.
        Called on a local cache miss — this is the fan-out lag safety net.
        Must return None if the tool does not exist or has been RETIRED.
        Should be fast — this is in the hot path of tools/call.
        """
        ...

    @abstractmethod
    async def subscribe(self, on_update: UpdateCallback) -> None:
        """
        Subscribe to live tool registration and lifecycle events.
        Must call on_update whenever a tool is registered, updated,
        deprecated, or retired. This keeps the local cache fresh without
        the MCP server polling.

        Implementations should run their subscription loop as a background
        asyncio task — this method should return promptly after starting it.

        If the subscription connection drops, implementations should
        auto-reconnect. Missed events during a reconnect gap are covered
        by the MCP server's background revalidation sweep (which calls
        load_all periodically).
        """
        ...

    @abstractmethod
    async def close(self) -> None:
        """
        Clean up connections and cancel background tasks.
        Called on server shutdown.
        """
        ...

    @property
    @abstractmethod
    def flavor(self) -> str:
        """Human-readable name for this provider — used in logs and /health."""
        ...

"""
ToolRouter

Owns the three-layer tool resolution and delegates execution to mod_executor.

Resolution order:
  1. Local in-memory cache        (nanoseconds)
  2. Registry provider fallback   (direct Postgres query on cache miss)
  3. Not found

Every tools/call response includes _meta.source so you can observe which
layer served the request.
"""

from __future__ import annotations
import logging
from models import ToolDefinition
from cache.local_cache import LocalCache
from registry.base import ToolRegistryProvider
import mod_executor

log = logging.getLogger("tool-router")


class ToolRouter:

    def __init__(self, cache: LocalCache, registry: ToolRegistryProvider, instance_id: str):
        self._cache    = cache
        self._registry = registry
        self._instance = instance_id

    async def resolve(self, tool_id: str) -> tuple[ToolDefinition | None, str]:
        """
        Resolve a tool by ID using the three-layer lookup.
        Returns (tool, source) where source is one of:
          'local-cache' | 'registry-fallback' | 'not-found'
        """
        tool = self._cache.get(tool_id)
        if tool:
            return tool, "local-cache"

        log.info(f"[{self._instance}] Cache miss for {tool_id} — falling back to registry")
        tool = await self._registry.get_tool(tool_id)
        if tool:
            self._cache.set(tool_id, tool)
            return tool, "registry-fallback"

        return None, "not-found"

    async def call_tool(self, tool_id: str, args: dict) -> dict:
        """
        Resolve and execute a tool. Returns a result dict including _meta.
        """
        tool, source = await self.resolve(tool_id)

        if not tool:
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Tool not found: {tool_id}"}],
                "_meta":   {"instanceId": self._instance, "source": source},
            }

        if not tool.is_callable():
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Tool is retired and no longer available: {tool_id}"}],
                "_meta":   {"instanceId": self._instance, "source": source},
            }

        log.info(f"[{self._instance}] Calling {tool_id} (source={source})")

        try:
            result = await mod_executor.execute(tool, args)
            return {
                "content": [{"type": "text", "text": str(result)}],
                "_meta":   {"instanceId": self._instance, "source": source},
            }
        except Exception as e:
            log.error(f"[{self._instance}] Execution failed for {tool_id}: {e}")
            return {
                "isError": True,
                "content": [{"type": "text", "text": f"Tool execution failed: {e}"}],
                "_meta":   {"instanceId": self._instance, "source": source},
            }

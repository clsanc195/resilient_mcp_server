"""
HA MCP Tool Server

Entry point. Wires together:
  - ToolRegistryProvider (selected by REGISTRY_FLAVOR env var)
  - LocalCache
  - ToolRouter
  - MCP protocol server (SSE transport via official MCP Python SDK)
  - Background revalidation sweep
  - Debug/health HTTP endpoints
"""

import asyncio
import logging
import os
import socket

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Mount, Route

from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.types import Tool, TextContent

from models import ToolDefinition, ToolStatus
from cache.local_cache import LocalCache
from registry import build_registry_provider
from registry.base import ToolRegistryProvider
from tool_router import ToolRouter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s"
)
log = logging.getLogger("mcp-server")

# ── Config ────────────────────────────────────────────────────────────────────

MCP_PORT             = int(os.getenv("MCP_PORT", "3000"))
REVALIDATION_SECONDS = int(os.getenv("REVALIDATION_INTERVAL_SECONDS", "30"))
INSTANCE_ID          = socket.gethostname()

# ── Globals (initialized in lifespan) ─────────────────────────────────────────

cache:    LocalCache            = LocalCache()
registry: ToolRegistryProvider  = None
router:   ToolRouter            = None

# ── MCP Server setup ──────────────────────────────────────────────────────────

mcp = Server("mcp-tool-server")


@mcp.list_tools()
async def handle_list_tools() -> list[Tool]:
    """
    Return all ACTIVE tools from local cache in MCP protocol format.
    Always served from cache for latency — cache is kept fresh via provider subscription.
    """
    tools = cache.list_active()
    return [
        Tool(
            name=t.toolId,
            description=t.description,
            inputSchema=t.inputSchema,
        )
        for t in tools
    ]


@mcp.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    Execute a tool by name (toolId). Uses three-layer resolution:
      local cache → registry fallback → not found
    """
    result = await router.call_tool(name, arguments or {})

    text = result["content"][0]["text"] if result.get("content") else ""
    meta = result.get("_meta", {})

    # Append _meta to the response text so callers can observe resolution source
    full_text = f"{text}\n\n[_meta: {meta}]"
    return [TextContent(type="text", text=full_text)]


# ── Update callback (called by registry provider on tool changes) ─────────────

async def on_tool_update(event_type: str, tool_id: str, tool: ToolDefinition | None):
    """
    Handles live tool updates pushed by the registry provider.
    Updates the local cache so tools/list and tools/call stay consistent.
    """
    log.info(f"[{INSTANCE_ID}] Received update: {event_type} for {tool_id}")

    if event_type in ("TOOL_REGISTERED", "TOOL_UPDATED"):
        if tool:
            cache.set(tool_id, tool)
            log.info(f"[{INSTANCE_ID}] Cache updated: {tool_id}")

    elif event_type == "TOOL_DEPRECATED":
        if tool:
            cache.set(tool_id, tool)
            log.info(f"[{INSTANCE_ID}] Cache marked deprecated: {tool_id}")

    elif event_type == "TOOL_RETIRED":
        cache.delete(tool_id)
        log.info(f"[{INSTANCE_ID}] Cache evicted retired tool: {tool_id}")

    else:
        log.warning(f"[{INSTANCE_ID}] Unknown event type: {event_type}")


# ── Background revalidation sweep ─────────────────────────────────────────────

async def background_revalidation():
    """
    Safety net for missed pub/sub events (e.g. transient disconnects).
    Periodically reloads the full registry from the provider and refreshes
    the local cache. Does not replace the subscription — it only covers gaps.
    """
    while True:
        await asyncio.sleep(REVALIDATION_SECONDS)
        try:
            log.info(f"[{INSTANCE_ID}] Background revalidation sweep...")
            tools = await registry.load_all()
            cache.clear()
            cache.load_all(tools)
            log.info(f"[{INSTANCE_ID}] Revalidation complete. Cache has {cache.size()} tools.")
        except Exception as e:
            log.error(f"[{INSTANCE_ID}] Revalidation failed: {e}")


# ── SSE transport setup ───────────────────────────────────────────────────────

sse = SseServerTransport("/messages/")


async def handle_sse(request: Request):
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await mcp.run(
            streams[0],
            streams[1],
            mcp.create_initialization_options(),
        )


# ── Debug / health routes ─────────────────────────────────────────────────────

async def health(request: Request):
    return JSONResponse({
        "status":       "ok",
        "instanceId":   INSTANCE_ID,
        "registryFlavor": registry.flavor if registry else "uninitialized",
        "cachedTools":  cache.size(),
    })


async def debug_cache(request: Request):
    return JSONResponse({
        "instanceId":   INSTANCE_ID,
        "registryFlavor": registry.flavor,
        "cacheSize":    cache.size(),
        "tools":        cache.snapshot(),
    })


# ── Starlette app with lifespan ───────────────────────────────────────────────

async def lifespan(app):
    global registry, router

    log.info(f"[{INSTANCE_ID}] Starting MCP Tool Server...")

    # Build and connect the registry provider
    registry = build_registry_provider()
    log.info(f"[{INSTANCE_ID}] Using registry flavor: {registry.flavor}")

    await registry.connect()

    # Hydrate local cache from registry
    tools = await registry.load_all()
    cache.load_all(tools)
    log.info(f"[{INSTANCE_ID}] Local cache hydrated with {cache.size()} tools.")

    # Build the tool router
    router = ToolRouter(cache=cache, registry=registry, instance_id=INSTANCE_ID)

    # Subscribe to live updates from the registry
    await registry.subscribe(on_tool_update)

    # Start background revalidation sweep
    revalidation_task = asyncio.create_task(
        background_revalidation(),
        name="background-revalidation"
    )

    log.info(f"[{INSTANCE_ID}] MCP Tool Server ready on port {MCP_PORT}.")
    log.info(f"[{INSTANCE_ID}]   SSE endpoint:    http://localhost:{MCP_PORT}/sse")
    log.info(f"[{INSTANCE_ID}]   Health endpoint: http://localhost:{MCP_PORT}/health")
    log.info(f"[{INSTANCE_ID}]   Debug cache:     http://localhost:{MCP_PORT}/debug/cache")

    yield  # server is running

    # Shutdown
    log.info(f"[{INSTANCE_ID}] Shutting down...")
    revalidation_task.cancel()
    await registry.close()


app = Starlette(
    lifespan=lifespan,
    routes=[
        Route("/sse",          endpoint=handle_sse),
        Mount("/messages/",    app=sse.handle_post_message),
        Route("/health",       endpoint=health),
        Route("/debug/cache",  endpoint=debug_cache),
    ],
)


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=MCP_PORT,
        reload=False,
        log_level="info",
    )

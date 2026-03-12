"""
Mod Executor
============
Everything that knows how to call the Spring Boot executor lives here.
The rest of the codebase is shielded from the executor's HTTP contract.

Tomorrow, when the real executor contract is known:
  1. Update _build_request() — change URL pattern and request body shape
  2. Update _parse_response() — if the response structure differs

Nothing else needs to change — not the router, not the MCP server.
"""

import httpx
from models import ToolDefinition


async def execute(tool: ToolDefinition, args: dict) -> dict:
    """
    Call the mod executor and return the parsed response.
    Raises httpx.HTTPStatusError on non-2xx, or httpx.TimeoutException on timeout.
    """
    request = _build_request(tool, args)

    async with httpx.AsyncClient() as client:
        response = await client.request(
            method=request["method"],
            url=request["url"],
            json=request["body"],
            headers=request["headers"],
            timeout=request["timeout_seconds"],
        )
        response.raise_for_status()
        return _parse_response(response.json())


def _build_request(tool: ToolDefinition, args: dict) -> dict:
    """
    Construct the HTTP request for this mod invocation.

    Tomorrow: change the URL pattern and body shape here to match
    your real Spring Boot executor's API contract. The tool object
    carries the mod's ID, name, version, and any executor config
    fields mapped from the schema — use whatever the real contract needs.
    """
    return {
        "method":          tool.executor.httpMethod,
        "url":             tool.executor.url,
        "body":            args,
        "headers":         {"Content-Type": "application/json", **tool.executor.headers},
        "timeout_seconds": tool.executor.timeoutMs / 1000.0,
    }


def _parse_response(raw: dict) -> dict:
    """
    Normalize the executor response into a standard shape returned to the MCP caller.

    Tomorrow: update this if your real executor wraps results differently.
    """
    return raw

"""
Mod Schema Adapter
==================
Everything that knows about the Postgres schema for mods lives here.
The rest of the codebase is shielded from the schema entirely.

Tomorrow, when the real schema is available:
  1. Update TABLE if the table name differs
  2. Update LOAD_ALL_SQL and GET_TOOL_SQL to use real column names
  3. Update row_to_tool() to map real columns → ToolDefinition

Nothing else needs to change — not the registry, not the MCP server.
"""

import json
import asyncpg
from models import ToolDefinition, ToolStatus, ExecutorConfig, ToolMetadata

# ── Postgres LISTEN/NOTIFY channel ────────────────────────────────────────────
# Must match the channel name used in the Postgres trigger (postgres/init.sql).
NOTIFY_CHANNEL = "tool_updates"

# ── Table ─────────────────────────────────────────────────────────────────────
TABLE = "tools"

# ── Queries ───────────────────────────────────────────────────────────────────
# Tomorrow: replace column names with the ones from your real schema.

LOAD_ALL_SQL = f"""
    SELECT tool_id, name, version, status, description,
           input_schema, output_schema,
           executor_url, executor_method, executor_timeout_ms, executor_headers,
           owner_team, tags, rate_limit_rpm,
           approved_at, deprecated_at, retire_at
    FROM {TABLE}
    WHERE status = 'ACTIVE'
"""

GET_TOOL_SQL = f"""
    SELECT tool_id, name, version, status, description,
           input_schema, output_schema,
           executor_url, executor_method, executor_timeout_ms, executor_headers,
           owner_team, tags, rate_limit_rpm,
           approved_at, deprecated_at, retire_at
    FROM {TABLE}
    WHERE tool_id = $1 AND status != 'RETIRED'
"""


# ── Row mapping ───────────────────────────────────────────────────────────────

def row_to_tool(row: asyncpg.Record) -> ToolDefinition:
    """
    Map a Postgres row to a ToolDefinition.

    Tomorrow: update column references here to match your real schema.
    The return type (ToolDefinition) stays the same — only the mapping changes.
    """
    def _json(val):
        if val is None:
            return {}
        return json.loads(val) if isinstance(val, str) else dict(val)

    return ToolDefinition(
        toolId=row["tool_id"],
        name=row["name"],
        version=row["version"],
        status=ToolStatus(row["status"]),
        description=row["description"] or "",
        inputSchema=_json(row["input_schema"]),
        outputSchema=_json(row["output_schema"]),
        executor=ExecutorConfig(
            url=row["executor_url"],
            httpMethod=row["executor_method"],
            timeoutMs=row["executor_timeout_ms"],
            headers=_json(row["executor_headers"]),
        ),
        metadata=ToolMetadata(
            owner=row["owner_team"],
            tags=list(row["tags"]) if row["tags"] else [],
            rateLimitRpm=row["rate_limit_rpm"],
        ),
        approvedAt=row["approved_at"].isoformat() if row["approved_at"] else None,
        deprecatedAt=row["deprecated_at"].isoformat() if row["deprecated_at"] else None,
        retireAt=row["retire_at"].isoformat() if row["retire_at"] else None,
    )

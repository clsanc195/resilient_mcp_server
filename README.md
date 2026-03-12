# HA MCP Tool Server — Local Dev Guide

## Stack

| Service | Role |
|---|---|
| Postgres 16 | Source of truth for tool definitions |
| Observable Endpoint | Logs all tool invocation HTTP calls (port 10090) |
| MCP Server ×3 | Tool server instances (ports 4000–4002) |

---

## Run

```bash
docker compose up --scale mcp-server=3
```

---

## Endpoints

| URL | Description |
|---|---|
| http://localhost:4000/health | MCP Node 1 health |
| http://localhost:4001/health | MCP Node 2 health |
| http://localhost:4002/health | MCP Node 3 health |
| http://localhost:4000/debug/cache | Live cache snapshot (Node 1) |
| http://localhost:10090/health | Observable endpoint health |

**Postgres:** `localhost:5432` / db: `toolcatalog` / credentials from `.env`

---

## How It Works

1. On startup each MCP node loads all `ACTIVE` tools from Postgres into local memory
2. Each node opens a persistent `LISTEN` connection to Postgres
3. When a tool is registered, updated, deprecated, or retired — a Postgres trigger fires `NOTIFY` and all nodes update their cache instantly
4. A background sweep reloads the full registry every 5 minutes as a safety net for any missed notifications

---

## Tool Invocation Flow

```
MCP Client
  → MCP Server (resolves tool from local cache, reads executor_url from DB)
    → HTTP POST executor_url
      → Observable Endpoint (logs full request + response)
```

To point a tool at a real service, update `executor_url` in the `tools` table. Nothing else changes.

---

## Swap the DB Schema

All schema knowledge is isolated in `mcp-server/src/mod_schema.py`. To use a real schema:

1. Update `LOAD_ALL_SQL` and `GET_TOOL_SQL` with real column names
2. Update `row_to_tool()` to map real columns → `ToolDefinition`

No other files need to change.

---

## Test LISTEN/NOTIFY

Insert a new tool while the stack is running and watch all 3 MCP node logs update instantly:

```sql
INSERT INTO tools (
    tool_id, name, version, status, description,
    input_schema, executor_url, executor_method, executor_timeout_ms,
    executor_headers, owner_team, tags, rate_limit_rpm, approved_at
) VALUES (
    'com.acme.tools.invoice-lookup:1.0.0',
    'invoice_lookup',
    '1.0.0',
    'ACTIVE',
    'Looks up an invoice by ID',
    '{"type": "object", "properties": {"invoiceId": {"type": "string"}}, "required": ["invoiceId"]}',
    'http://remote-mod-service:8090/tools/invoice-lookup',
    'POST',
    5000,
    '{"Content-Type": "application/json"}',
    'finance-team',
    ARRAY['finance'],
    500,
    NOW()
);
```

---

## Test Scripts

| Script | What it shows |
|---|---|
| `./scripts/test-exec.sh` | Full e2e — MCP → cache → HTTP → observable endpoint (watch remote-mod-service logs) |
| `./scripts/test-list-tools.sh` | What an LLM sees when discovering tools via `tools/list` |
| `./scripts/test-not-found.sh` | Error response when calling a tool that doesn't exist |
| `./scripts/test-new-tool.sh` | Inserts invoice-lookup → NOTIFY fires → calls it immediately |

---

## Seeded Tools

| Tool ID | Endpoint |
|---|---|
| `com.acme.tools.customer-lookup:1.0.0` | `http://remote-mod-service:8090/platform/mod/customer-lookup` |
| `com.acme.tools.order-status:2.1.0` | `http://remote-mod-service:8090/platform/mod/order-status` |

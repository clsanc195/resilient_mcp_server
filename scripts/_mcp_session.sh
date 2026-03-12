#!/bin/bash
# Shared helper — sourced by other scripts
# Sets up an MCP SSE session and exposes mcp_call()

BASE="${MCP_BASE:-http://localhost:4000}"
SSE_OUT=$(mktemp)
SSE_PID=""
trap "rm -f $SSE_OUT; [ -n \"$SSE_PID\" ] && kill $SSE_PID 2>/dev/null" EXIT

curl -sN "$BASE/sse" >> "$SSE_OUT" &
SSE_PID=$!

ENDPOINT=""
for i in $(seq 1 50); do
    ENDPOINT=$(grep "^data:" "$SSE_OUT" 2>/dev/null | head -1 | sed 's/^data: //' | tr -d '\r')
    [ -n "$ENDPOINT" ] && break
    sleep 0.1
done
[ -z "$ENDPOINT" ] && { echo "ERROR: MCP server not reachable at $BASE"; exit 1; }

# Initialize session (required by MCP protocol)
curl -s -X POST "$BASE$ENDPOINT" \
    -H "Content-Type: application/json" \
    -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' > /dev/null
sleep 0.3

mcp_call() {
    local payload=$1
    curl -s -X POST "$BASE$ENDPOINT" \
        -H "Content-Type: application/json" \
        -d "$payload" > /dev/null
    sleep 0.5
    grep "^data:" "$SSE_OUT" | tail -1 | sed 's/^data: //' | python3 -m json.tool
}

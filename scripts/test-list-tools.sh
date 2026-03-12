#!/bin/bash
# tools/list — what an LLM sees when it discovers available tools

source "$(dirname "$0")/_mcp_session.sh"

echo "=== tools/list (LLM tool discovery) ==="
mcp_call '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'

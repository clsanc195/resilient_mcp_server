#!/bin/bash
# Call a tool that does not exist — expect a not-found error

source "$(dirname "$0")/_mcp_session.sh"

echo "=== tools/call: non-existent tool ==="
mcp_call '{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "com.acme.tools.does-not-exist:1.0.0",
    "arguments": {}
  }
}'

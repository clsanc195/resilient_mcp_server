#!/bin/bash
# Full end-to-end: MCP → local cache → HTTP call → observable endpoint
# Watch remote-mod-service logs to see the call land there

source "$(dirname "$0")/_mcp_session.sh"

echo "=== tools/call: customer_lookup (end-to-end) ==="
mcp_call '{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "com.acme.tools.customer-lookup:1.0.0",
    "arguments": {
      "identifier": "jane@acme.com",
      "identifierType": "EMAIL"
    }
  }
}'

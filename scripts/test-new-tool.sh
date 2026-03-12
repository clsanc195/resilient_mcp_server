#!/bin/bash
# Inserts invoice-lookup via test-notify.sh (triggers LISTEN/NOTIFY),
# then calls it immediately to prove the cache was updated in real time

echo "=== Inserting invoice-lookup tool ==="
"$(dirname "$0")/test-notify.sh"

echo ""
echo "=== Waiting for NOTIFY to propagate ==="
sleep 1

source "$(dirname "$0")/_mcp_session.sh"

echo "=== tools/call: invoice_lookup (just registered) ==="
mcp_call '{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "com.acme.tools.invoice-lookup:1.0.0",
    "arguments": {
      "invoiceId": "INV-00123"
    }
  }
}'

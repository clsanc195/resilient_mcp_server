#!/bin/bash
# Retires invoice-lookup via a status UPDATE (triggers LISTEN/NOTIFY),
# then tries to call it to prove the cache evicted it in real time

echo "=== Retiring invoice-lookup tool ==="
docker compose exec postgres psql -U mcpadmin -d toolcatalog -c "
UPDATE tools
SET    status = 'RETIRED', retired_at = NOW()
WHERE  tool_id = 'com.acme.tools.invoice-lookup:1.0.0';
"

echo ""
echo "=== Waiting for NOTIFY to propagate ==="
sleep 1

source "$(dirname "$0")/_mcp_session.sh"

echo "=== tools/call: invoice_lookup (should now be not found) ==="
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

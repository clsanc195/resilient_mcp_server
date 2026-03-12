#!/bin/bash
docker compose exec postgres psql -U mcpadmin -d toolcatalog -c "
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
    '{\"type\": \"object\", \"properties\": {\"invoiceId\": {\"type\": \"string\"}}, \"required\": [\"invoiceId\"]}',
    'http://remote-mod-service:8090/platform/mod/invoice-lookup',
    'POST',
    5000,
    '{\"Content-Type\": \"application/json\"}',
    'finance-team',
    ARRAY['finance'],
    500,
    NOW()
) ON CONFLICT (tool_id) DO UPDATE SET
    executor_url        = EXCLUDED.executor_url,
    status              = EXCLUDED.status,
    description         = EXCLUDED.description,
    input_schema        = EXCLUDED.input_schema,
    approved_at         = EXCLUDED.approved_at;
"

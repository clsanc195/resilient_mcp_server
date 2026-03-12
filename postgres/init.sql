-- ─────────────────────────────────────────────────────────────
-- Tool Catalog Schema
-- Source of truth for approved tool definitions
-- ─────────────────────────────────────────────────────────────

CREATE TYPE tool_status AS ENUM ('PENDING', 'ACTIVE', 'DEPRECATED', 'RETIRED');

CREATE TABLE tools (
    id                  SERIAL PRIMARY KEY,
    tool_id             VARCHAR(255)    NOT NULL UNIQUE,
    name                VARCHAR(255)    NOT NULL,
    version             VARCHAR(50)     NOT NULL,
    status              tool_status     NOT NULL DEFAULT 'PENDING',
    description         TEXT,
    input_schema        JSONB           NOT NULL,
    output_schema       JSONB,
    executor_url        VARCHAR(500)    NOT NULL,
    executor_method     VARCHAR(10)     NOT NULL DEFAULT 'POST',
    executor_timeout_ms INTEGER         NOT NULL DEFAULT 5000,
    executor_headers    JSONB,
    owner_team          VARCHAR(100),
    tags                TEXT[],
    rate_limit_rpm      INTEGER         DEFAULT 500,
    approved_at         TIMESTAMPTZ,
    deprecated_at       TIMESTAMPTZ,
    retire_at           TIMESTAMPTZ,
    retired_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tools_status ON tools(status);
CREATE INDEX idx_tools_name   ON tools(name);

-- Tool lifecycle event log (audit trail)
CREATE TABLE tool_events (
    id          SERIAL PRIMARY KEY,
    tool_id     VARCHAR(255) NOT NULL,
    event_type  VARCHAR(50)  NOT NULL,
    payload     JSONB,
    created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_tool_events_tool_id ON tool_events(tool_id);

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tools_updated_at
    BEFORE UPDATE ON tools
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- LISTEN/NOTIFY trigger — fires on INSERT and status changes
-- Payload: {"tool_id": "...", "status": "..."}
CREATE OR REPLACE FUNCTION notify_tool_change()
RETURNS TRIGGER AS $$
BEGIN
    PERFORM pg_notify(
        'tool_updates',
        json_build_object('tool_id', NEW.tool_id, 'status', NEW.status)::text
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tools_notify
    AFTER INSERT OR UPDATE ON tools
    FOR EACH ROW
    EXECUTE FUNCTION notify_tool_change();

-- ─────────────────────────────────────────────────────────────
-- Seed: two pre-approved ACTIVE tools for local testing
-- ─────────────────────────────────────────────────────────────

INSERT INTO tools (
    tool_id, name, version, status, description,
    input_schema, output_schema,
    executor_url, executor_method, executor_timeout_ms, executor_headers,
    owner_team, tags, rate_limit_rpm, approved_at
) VALUES
(
    'com.acme.tools.customer-lookup:1.0.0',
    'customer_lookup',
    '1.0.0',
    'ACTIVE',
    'Looks up a customer record by ID or email address',
    '{
        "type": "object",
        "properties": {
            "identifier":     { "type": "string", "description": "Customer ID or email" },
            "identifierType": { "type": "string", "enum": ["ID", "EMAIL"] }
        },
        "required": ["identifier", "identifierType"]
    }',
    '{
        "type": "object",
        "properties": {
            "customerId": { "type": "string" },
            "name":       { "type": "string" },
            "email":      { "type": "string" },
            "status":     { "type": "string" }
        }
    }',
    'http://remote-mod-service:8090/platform/mod/customer-lookup',
    'POST',
    5000,
    '{"Content-Type": "application/json", "X-Tool-Version": "1.0.0"}',
    'crm-team',
    ARRAY['crm', 'customer'],
    500,
    NOW()
),
(
    'com.acme.tools.order-status:2.1.0',
    'order_status',
    '2.1.0',
    'ACTIVE',
    'Returns current status and tracking info for an order',
    '{
        "type": "object",
        "properties": {
            "orderId": { "type": "string", "description": "The order identifier" }
        },
        "required": ["orderId"]
    }',
    '{
        "type": "object",
        "properties": {
            "orderId":           { "type": "string" },
            "status":            { "type": "string" },
            "trackingNumber":    { "type": "string" },
            "estimatedDelivery": { "type": "string" }
        }
    }',
    'http://remote-mod-service:8090/platform/mod/order-status',
    'POST',
    3000,
    '{"Content-Type": "application/json", "X-Tool-Version": "2.1.0"}',
    'fulfillment-team',
    ARRAY['orders', 'fulfillment'],
    1000,
    NOW()
);

-- Seed audit events
INSERT INTO tool_events (tool_id, event_type, payload)
SELECT tool_id, 'TOOL_REGISTERED', row_to_json(tools.*)::jsonb
FROM tools WHERE status = 'ACTIVE';

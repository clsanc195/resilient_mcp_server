"""
Observable Tool Endpoint Server

A local FastAPI server that acts as the target for all tool executor calls.
Every incoming request is logged in full so you can observe exactly what
the MCP server is calling, with what arguments, and what it gets back.

In production, replace executor_url in the DB to point to your real services.
Nothing else in the stack changes.
"""

import os
import json
import uuid
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Observable Tool Endpoint Server")

PORT = int(os.getenv("EXECUTOR_PORT", "8090"))


def log_call(method: str, path: str, headers: dict, body: dict, response: dict):
    ts = datetime.utcnow().isoformat() + "Z"
    relevant_headers = {
        k: v for k, v in headers.items()
        if k.lower() not in ("host", "content-length", "user-agent", "accept", "accept-encoding", "connection")
    }
    print("\n" + "=" * 60)
    print(f"[{ts}]  {method} {path}")
    print(f"  Headers  : {json.dumps(relevant_headers, indent=14)}")
    print(f"  Arguments: {json.dumps(body, indent=14)}")
    print(f"  Response : {json.dumps(response, indent=14)}")
    print("=" * 60)


@app.api_route("/platform/mod/{tool_name}", methods=["GET", "POST", "PUT", "PATCH"])
async def handle_tool_call(tool_name: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}

    response = {
        "toolName":   tool_name,
        "receivedAt": datetime.utcnow().isoformat() + "Z",
        "callId":     uuid.uuid4().hex,
        "status":     "ok",
        "echo":       body,
    }

    log_call(
        method=request.method,
        path=str(request.url.path),
        headers=dict(request.headers),
        body=body,
        response=response,
    )

    return JSONResponse(content=response)


@app.get("/health")
def health():
    return {"status": "ok", "service": "observable-tool-endpoint"}


if __name__ == "__main__":
    print(f"[ObservableEndpoint] Listening on port {PORT}")
    print(f"[ObservableEndpoint] All tool invocations will be logged here.")
    print(f"[ObservableEndpoint] To use real services: update executor_url in the tools table.")
    uvicorn.run(app, host="0.0.0.0", port=PORT)

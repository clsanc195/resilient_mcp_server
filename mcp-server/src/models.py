"""
Shared data models for the MCP Tool Server.
"""

from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel


class ToolStatus(str, Enum):
    PENDING    = "PENDING"
    ACTIVE     = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    RETIRED    = "RETIRED"


class ExecutorConfig(BaseModel):
    url:        str
    httpMethod: str = "POST"
    timeoutMs:  int = 5000
    headers:    dict[str, str] = {}


class ToolMetadata(BaseModel):
    owner:        str | None = None
    tags:         list[str] = []
    rateLimitRpm: int = 500


class ToolDefinition(BaseModel):
    toolId:       str
    name:         str
    version:      str
    status:       ToolStatus
    description:  str
    inputSchema:  dict[str, Any]
    outputSchema: dict[str, Any] = {}
    executor:     ExecutorConfig
    metadata:     ToolMetadata = ToolMetadata()
    approvedAt:   str | None = None
    deprecatedAt: str | None = None
    retireAt:     str | None = None

    def is_callable(self) -> bool:
        """A tool is callable if it's ACTIVE or still within its DEPRECATED grace period."""
        return self.status in (ToolStatus.ACTIVE, ToolStatus.DEPRECATED)

    def to_mcp_schema(self) -> dict:
        """Convert to the MCP protocol tool schema format for tools/list."""
        return {
            "name":        self.toolId,   # toolId is the unique MCP tool name
            "description": self.description,
            "inputSchema": self.inputSchema,
        }

"""Typed MCP registry models used by the v2 loader slice."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass(frozen=True, slots=True)
class MCPToolDefinition:
    """Declarative MCP tool shape without runtime bindings."""

    name: str
    description: Optional[str] = None
    operation_id: Optional[str] = None
    method: Optional[str] = None
    path: Optional[str] = None
    schema: Optional[str] = None
    enabled: bool = True
    enabled_env: Optional[str] = None


@dataclass(frozen=True, slots=True)
class MCPServerDefinition:
    """Configuration for an MCP server entry declared in YAML."""

    name: str
    url: str
    schema: Optional[str] = None
    enabled: bool = True
    enabled_env: Optional[str] = None
    tools: Tuple[MCPToolDefinition, ...] = field(default_factory=tuple)

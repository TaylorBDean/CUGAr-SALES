"""MCP v2 namespace for upcoming registry, runner, and adapter layers."""

from .registry.loader import load_mcp_registry_snapshot
from .registry.snapshot import RegistrySnapshot

__all__ = [
    "RegistrySnapshot",
    "load_mcp_registry_snapshot",
]

"""Immutable snapshot for MCP registry state."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Tuple

from .models import MCPServerDefinition


@dataclass(frozen=True, slots=True)
class RegistrySnapshot:
    """Value object representing a resolved MCP registry."""

    servers: Tuple[MCPServerDefinition, ...] = field(default_factory=tuple)
    sources: Tuple[Path, ...] = field(default_factory=tuple)

    @classmethod
    def empty(cls) -> "RegistrySnapshot":
        return cls()

    def with_servers(self, servers: Iterable[MCPServerDefinition]) -> "RegistrySnapshot":
        return RegistrySnapshot(servers=tuple(servers), sources=self.sources)

    def with_sources(self, sources: Iterable[Path]) -> "RegistrySnapshot":
        return RegistrySnapshot(servers=self.servers, sources=tuple(sources))

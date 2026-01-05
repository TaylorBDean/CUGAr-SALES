"""Plugin loading utilities for external tool integrations."""

from __future__ import annotations

import importlib
import importlib.machinery
import importlib.util
from dataclasses import dataclass
from importlib.metadata import entry_points
from pathlib import Path
from typing import Iterable, List, Sequence

from cuga.agents.registry import ToolRegistry


class ToolPlugin:
    """Standard plugin API for external tool providers.

    Plugins should subclass this and implement :meth:`register_tools` to add
    tools to the provided :class:`~cuga.agents.registry.ToolRegistry` instance.
    """

    name: str = "tool-plugin"
    description: str = ""

    def register_tools(self, registry: ToolRegistry) -> None:  # pragma: no cover - interface only
        raise NotImplementedError


@dataclass
class PluginLoadResult:
    """Result of a plugin discovery operation."""

    plugin: ToolPlugin | None
    source: str
    error: Exception | None = None

    @property
    def loaded(self) -> bool:
        return self.plugin is not None and self.error is None


def _load_module_from_path(path: Path):
    loader = importlib.machinery.SourceFileLoader(path.stem, str(path))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to create spec for plugin at {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _instantiate_plugin(module) -> ToolPlugin:
    if hasattr(module, "plugin") and isinstance(module.plugin, ToolPlugin):
        return module.plugin
    if hasattr(module, "Plugin"):
        plugin_cls = getattr(module, "Plugin")
        if issubclass(plugin_cls, ToolPlugin):
            return plugin_cls()
    raise ValueError("Module does not expose a ToolPlugin instance or subclass")


def discover_plugins(paths: Sequence[str] | None = None) -> List[PluginLoadResult]:
    """Discover plugins via entry points or explicit file paths."""

    discovered: List[PluginLoadResult] = []

    for entry in entry_points(group="cuga.plugins"):
        try:
            module = importlib.import_module(entry.module)
            plugin = _instantiate_plugin(module)
            discovered.append(PluginLoadResult(plugin=plugin, source=f"entry_point:{entry.name}"))
        except Exception as exc:  # pragma: no cover - defensive guard
            discovered.append(PluginLoadResult(plugin=None, source=f"entry_point:{entry.name}", error=exc))

    for raw_path in paths or []:
        path = Path(raw_path)
        try:
            module = _load_module_from_path(path)
            plugin = _instantiate_plugin(module)
            discovered.append(PluginLoadResult(plugin=plugin, source=str(path)))
        except Exception as exc:
            discovered.append(PluginLoadResult(plugin=None, source=str(path), error=exc))

    return discovered


def load_plugins(registry: ToolRegistry, paths: Sequence[str] | None = None) -> List[PluginLoadResult]:
    """Load plugins and register their tools into the registry."""

    results: List[PluginLoadResult] = []
    for result in discover_plugins(paths):
        results.append(result)
        if result.plugin is None:
            continue
        result.plugin.register_tools(registry)
    return results


def list_plugins(results: Iterable[PluginLoadResult]) -> List[str]:
    """Return human-readable plugin summaries."""

    summaries: List[str] = []
    for result in results:
        if result.loaded:
            summaries.append(f"{result.plugin.name} ({result.source})")
        else:
            summaries.append(f"failed:{result.source}")
    return summaries

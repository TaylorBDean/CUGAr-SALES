"""
Legacy observability module (deprecated in v1.1.0).

This module is deprecated as of v1.1.0 and will be removed in v1.3.0.
Use `cuga.observability` module instead with structured events via `emit_event()`.

Migration:
    # Old (deprecated):
    from cuga.modular.observability import BaseEmitter
    worker = WorkerAgent(registry=..., memory=..., observability=BaseEmitter())
    
    # New (v1.1.0+):
    from cuga.observability import emit_event
    worker = WorkerAgent(registry=..., memory=...)
    # Events automatically emitted via emit_event()
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass
import importlib
from typing import Any, Dict


class BaseEmitter:
    """
    Legacy event emitter interface.
    
    DEPRECATED: This class is deprecated as of v1.1.0 and will be removed in v1.3.0.
    Use `cuga.observability.emit_event()` instead.
    """
    
    def __init__(self):
        warnings.warn(
            "BaseEmitter is deprecated as of v1.1.0 and will be removed in v1.3.0. "
            "Use cuga.observability.emit_event() instead. "
            "Events are now automatically emitted by agents.",
            DeprecationWarning,
            stacklevel=2
        )
    
    def emit(self, payload: Dict[str, Any]) -> None:  # pragma: no cover - interface
        """Emit event payload (deprecated)."""
        raise NotImplementedError


@dataclass
class LangfuseEmitter(BaseEmitter):
    """
    Langfuse event emitter.
    
    DEPRECATED: This class is deprecated as of v1.1.0 and will be removed in v1.3.0.
    Use `cuga.observability.exporters.LangfuseExporter` instead.
    """
    
    def __init__(self):
        # Don't call super().__init__() to avoid double deprecation warning
        warnings.warn(
            "LangfuseEmitter is deprecated as of v1.1.0 and will be removed in v1.3.0. "
            "Use cuga.observability.exporters with OTEL/LangFuse integration instead.",
            DeprecationWarning,
            stacklevel=2
        )
    
    def emit(self, payload: Dict[str, Any]) -> None:
        if importlib.util.find_spec("langfuse") is None:  # type: ignore[attr-defined]
            return
        langfuse = importlib.import_module("langfuse")
        client = langfuse.Langfuse()
        client.trace(name=payload.get("event", "event"), input=payload)


@dataclass
class OpenInferenceEmitter(BaseEmitter):
    """
    OpenInference event emitter.
    
    DEPRECATED: This class is deprecated as of v1.1.0 and will be removed in v1.3.0.
    Use `cuga.observability.exporters` with OTEL integration instead.
    """
    
    def __init__(self):
        # Don't call super().__init__() to avoid double deprecation warning
        warnings.warn(
            "OpenInferenceEmitter is deprecated as of v1.1.0 and will be removed in v1.3.0. "
            "Use cuga.observability.exporters with OTEL integration instead.",
            DeprecationWarning,
            stacklevel=2
        )
    
    def emit(self, payload: Dict[str, Any]) -> None:
        if importlib.util.find_spec("openinference") is None:  # type: ignore[attr-defined]
            return
        openinference = importlib.import_module("openinference")  # type: ignore
        _ = openinference
        return None

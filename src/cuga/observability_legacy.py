"""
Legacy observability helpers (deprecated in v1.1.0).

This module provides lightweight observability helpers that stay offline-friendly.
DEPRECATED as of v1.1.0 in favor of the new structured observability system.

Migration:
    # Old (deprecated):
    from cuga.observability_legacy import InMemoryTracer
    tracer = InMemoryTracer()
    span = tracer.start_span("tool_execution")
    
    # New (v1.1.0+):
    from cuga.observability import emit_event, ToolCallEvent
    start_event = ToolCallEvent.create_start(trace_id="...", tool_name="...", inputs={})
    emit_event(start_event)

This module will be removed in v1.3.0.
"""

from __future__ import annotations

import contextvars
import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, List

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("trace_id", default="")


@dataclass
class Span:
    """
    Legacy span for tracing.
    
    DEPRECATED: Use `cuga.observability.StructuredEvent` instead.
    """
    name: str
    trace_id: str
    start_time: float = field(default_factory=time.time)
    attributes: Dict[str, Any] = field(default_factory=dict)

    def end(self, **attrs: Any) -> None:
        self.attributes.update(attrs)


class InMemoryTracer:
    """
    Legacy in-memory tracer.
    
    DEPRECATED: This class is deprecated as of v1.1.0 and will be removed in v1.3.0.
    Use `cuga.observability.ObservabilityCollector` via `get_collector()` instead.
    """
    
    def __init__(self) -> None:
        warnings.warn(
            "InMemoryTracer is deprecated as of v1.1.0 and will be removed in v1.3.0. "
            "Use cuga.observability.ObservabilityCollector via get_collector() instead. "
            "See docs/observability/AGENT_INTEGRATION.md for migration guide.",
            DeprecationWarning,
            stacklevel=2
        )
        self.spans: List[Span] = []

    def start_span(self, name: str, **attributes: Any) -> Span:
        tid = trace_id_var.get() or attributes.get("trace_id") or ""
        span = Span(name=name, trace_id=tid, attributes=_redact(attributes))
        self.spans.append(span)
        return span


def _redact(data: Dict[str, Any]) -> Dict[str, Any]:
    lowered = {k.lower(): v for k, v in data.items()}
    redacted = {}
    for key, value in data.items():
        if any(s in key.lower() for s in {"secret", "token", "password"}):
            redacted[key] = "[redacted]"
        elif isinstance(value, dict):
            redacted[key] = _redact(value)
        else:
            redacted[key] = value
    return redacted


def propagate_trace(trace_id: str) -> None:
    trace_id_var.set(trace_id)

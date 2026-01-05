"""
CUGAR Agent Observability Module

Provides structured event emission, golden signal tracking, and OTEL export
for comprehensive agent system monitoring.

Key Components:
- events: Structured event types (plan, route, tool_call, budget, approval)
- golden_signals: Golden signal tracking (success rate, latency, errors, traffic)
- exporters: OTEL and console exporters for metrics/events
- collector: Unified event collection and processing

Usage:
    >>> from cuga.observability import ObservabilityCollector, OTELExporter
    >>> 
    >>> # Initialize collector with OTEL exporter
    >>> collector = ObservabilityCollector(
    ...     exporters=[OTELExporter(endpoint="http://localhost:4318")]
    ... )
    >>> 
    >>> # Emit events
    >>> from cuga.observability.events import PlanEvent
    >>> event = PlanEvent.create(
    ...     trace_id="trace-123",
    ...     goal="Find flights",
    ...     steps_count=3,
    ...     tools_selected=["search", "filter"],
    ...     duration_ms=150.0,
    ... )
    >>> collector.emit_event(event)
    >>> 
    >>> # Get metrics
    >>> metrics = collector.get_metrics()
    >>> print(f"Success rate: {metrics['success_rate']:.2f}%")
"""

from __future__ import annotations

from .events import (
    EventType,
    StructuredEvent,
    PlanEvent,
    RouteEvent,
    ToolCallEvent,
    BudgetEvent,
    ApprovalEvent,
)
from .golden_signals import GoldenSignals
from .exporters import OTELExporter, ConsoleExporter, create_exporter
from .collector import ObservabilityCollector, get_collector, set_collector, emit_event

# Legacy support: Import from old observability.py module
# TODO v1.1: Remove after migrating agents to use get_collector()
try:
    from cuga.observability_legacy import InMemoryTracer, propagate_trace
except ImportError:
    # Fallback: Try importing from parent observability.py
    import sys
    from pathlib import Path
    parent_path = Path(__file__).parent.parent
    sys.path.insert(0, str(parent_path))
    from observability import InMemoryTracer, propagate_trace
    sys.path.pop(0)

__all__ = [
    # New observability system (v1.0.0+)
    "EventType",
    "StructuredEvent",
    "PlanEvent",
    "RouteEvent",
    "ToolCallEvent",
    "BudgetEvent",
    "ApprovalEvent",
    "GoldenSignals",
    "OTELExporter",
    "ConsoleExporter",
    "create_exporter",
    "ObservabilityCollector",
    "get_collector",
    "set_collector",
    "emit_event",
    # Legacy support (deprecated, will be removed in v1.1)
    "InMemoryTracer",
    "propagate_trace",
]

__all__ = [
    # Event types
    "EventType",
    "StructuredEvent",
    "PlanEvent",
    "RouteEvent",
    "ToolCallEvent",
    "BudgetEvent",
    "ApprovalEvent",
    # Golden signals
    "GoldenSignals",
    # Exporters
    "OTELExporter",
    "ConsoleExporter",
    "create_exporter",
    # Collector
    "ObservabilityCollector",
]

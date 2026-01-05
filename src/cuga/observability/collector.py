"""
Observability Collector for CUGAR Agent System

Unified event collection, golden signal computation, and export orchestration.
Integrates with existing InMemoryTracer and extends with structured events.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

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
from .exporters import OTELExporter, ConsoleExporter


class ObservabilityCollector:
    """
    Central collector for observability data.
    
    Collects structured events, updates golden signals, and exports
    to configured backends. Thread-safe for concurrent agent execution.
    
    Features:
    - Automatic event processing and golden signal updates
    - Multi-exporter support (OTEL, console, custom)
    - Thread-safe event buffering
    - Periodic metrics export
    - Integration with existing InMemoryTracer
    """
    
    def __init__(
        self,
        exporters: Optional[List[OTELExporter | ConsoleExporter]] = None,
        auto_export: bool = True,
        buffer_size: int = 1000,
    ) -> None:
        """
        Initialize observability collector.
        
        Args:
            exporters: List of exporters to use (default: console exporter)
            auto_export: Whether to auto-export events immediately
            buffer_size: Maximum event buffer size before forced flush
        """
        self.exporters = exporters or [ConsoleExporter(pretty=False)]
        self.auto_export = auto_export
        self.buffer_size = buffer_size
        
        # Golden signals tracker
        self.signals = GoldenSignals()
        
        # Event buffer (thread-safe)
        self._event_buffer: List[StructuredEvent] = []
        self._buffer_lock = threading.Lock()
        
        # Active traces for correlation
        self._active_traces: Dict[str, Dict[str, Any]] = {}
        self._traces_lock = threading.Lock()
    
    def emit_event(self, event: StructuredEvent) -> None:
        """
        Emit a structured event.
        
        Automatically updates golden signals and exports to configured backends.
        
        Args:
            event: Structured event to emit
        """
        # Update golden signals
        self._update_signals(event)
        
        # Buffer event
        with self._buffer_lock:
            self._event_buffer.append(event)
            
            # Auto-export if enabled
            if self.auto_export:
                for exporter in self.exporters:
                    exporter.export_event(event)
            
            # Flush if buffer full
            if len(self._event_buffer) >= self.buffer_size:
                self._flush_buffer()
    
    def start_trace(self, trace_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Start a new trace.
        
        Args:
            trace_id: Unique trace identifier
            metadata: Optional trace metadata
        """
        with self._traces_lock:
            self._active_traces[trace_id] = {
                "start_time": __import__('time').time(),
                "metadata": metadata or {},
                "events": [],
            }
    
    def end_trace(self, trace_id: str, success: bool = True) -> None:
        """
        End an active trace.
        
        Args:
            trace_id: Trace identifier to end
            success: Whether trace completed successfully
        """
        with self._traces_lock:
            if trace_id in self._active_traces:
                trace_data = self._active_traces.pop(trace_id)
                duration_ms = (__import__('time').time() - trace_data["start_time"]) * 1000
                
                # Record trace completion
                if success:
                    self.signals.record_request_success(duration_ms)
                else:
                    self.signals.record_request_failure(duration_ms)
    
    def _update_signals(self, event: StructuredEvent) -> None:
        """Update golden signals based on event type."""
        event_type = event.event_type
        
        if event_type == EventType.PLAN_CREATED:
            steps_count = event.attributes.get("steps_count", 0)
            if event.duration_ms:
                self.signals.record_plan_created(steps_count, event.duration_ms)
        
        elif event_type == EventType.ROUTE_DECISION:
            if event.duration_ms:
                self.signals.record_route_decision(event.duration_ms)
        
        elif event_type == EventType.TOOL_CALL_START:
            tool_name = event.attributes.get("tool_name", "unknown")
            self.signals.record_tool_call_start(tool_name)
        
        elif event_type == EventType.TOOL_CALL_COMPLETE:
            tool_name = event.attributes.get("tool_name", "unknown")
            if event.duration_ms:
                self.signals.record_tool_call_complete(tool_name, event.duration_ms)
        
        elif event_type == EventType.TOOL_CALL_ERROR:
            tool_name = event.attributes.get("tool_name", "unknown")
            error_type = event.attributes.get("error_type", "unknown")
            duration_ms = event.duration_ms or 0.0
            self.signals.record_tool_call_error(tool_name, error_type, duration_ms)
        
        elif event_type == EventType.BUDGET_WARNING:
            budget_type = event.attributes.get("budget_type", "cost")
            utilization_pct = event.attributes.get("utilization_pct", 0.0)
            self.signals.record_budget_warning(budget_type, utilization_pct)
        
        elif event_type == EventType.BUDGET_EXCEEDED:
            budget_type = event.attributes.get("budget_type", "cost")
            utilization_pct = event.attributes.get("utilization_pct", 100.0)
            self.signals.record_budget_exceeded(budget_type, utilization_pct)
        
        elif event_type == EventType.APPROVAL_REQUESTED:
            self.signals.record_approval_requested()
        
        elif event_type == EventType.APPROVAL_RECEIVED:
            if event.duration_ms:
                self.signals.record_approval_received(event.duration_ms)
        
        elif event_type == EventType.APPROVAL_TIMEOUT:
            self.signals.record_approval_timeout()
        
        elif event_type == EventType.EXECUTION_START:
            profile = event.attributes.get("profile", "default")
            self.signals.record_request_start(profile)
    
    def _flush_buffer(self) -> None:
        """Flush event buffer to exporters (internal)."""
        if not self._event_buffer:
            return
        
        events_to_export = self._event_buffer.copy()
        self._event_buffer.clear()
        
        for exporter in self.exporters:
            exporter.export_events_batch(events_to_export)
    
    def flush(self) -> None:
        """Force flush event buffer to all exporters."""
        with self._buffer_lock:
            self._flush_buffer()
    
    @property
    def events(self) -> List[StructuredEvent]:
        """Get copy of current event buffer for testing/inspection."""
        with self._buffer_lock:
            return self._event_buffer.copy()
    
    def get_events(self) -> List[StructuredEvent]:
        """
        Get copy of current event buffer.
        
        Alias for .events property for backward compatibility with tests.
        
        Returns:
            List of buffered events
        """
        return self.events
    
    def export_metrics(self) -> None:
        """Export current golden signals to all exporters."""
        for exporter in self.exporters:
            exporter.export_metrics(self.signals)
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current metrics as dictionary.
        
        Returns:
            Dictionary with all metric values
        """
        return self.signals.to_dict()
    
    def get_prometheus_metrics(self) -> str:
        """
        Get metrics in Prometheus format.
        
        Returns:
            Prometheus-compatible metric export
        """
        return self.signals.to_prometheus_format()
    
    def reset_metrics(self) -> None:
        """Reset all metrics (useful for testing)."""
        self.signals.reset()
        with self._buffer_lock:
            self._event_buffer.clear()
        with self._traces_lock:
            self._active_traces.clear()
    
    def shutdown(self) -> None:
        """Shutdown collector and all exporters."""
        self.flush()
        self.export_metrics()
        
        for exporter in self.exporters:
            exporter.shutdown()


# Global collector instance (singleton)
_global_collector: Optional[ObservabilityCollector] = None
_collector_lock = threading.Lock()


def get_collector() -> ObservabilityCollector:
    """
    Get or create global observability collector.
    
    Returns:
        Global ObservabilityCollector instance
    """
    global _global_collector
    
    if _global_collector is None:
        with _collector_lock:
            if _global_collector is None:
                _global_collector = ObservabilityCollector()
    
    return _global_collector


def set_collector(collector: ObservabilityCollector) -> None:
    """
    Set global observability collector.
    
    Args:
        collector: Collector instance to use globally
    """
    global _global_collector
    with _collector_lock:
        _global_collector = collector


def emit_event(event: StructuredEvent) -> None:
    """
    Convenience function to emit event to global collector.
    
    Args:
        event: Event to emit
    """
    get_collector().emit_event(event)

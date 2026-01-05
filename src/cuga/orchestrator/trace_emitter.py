"""
Canonical trace event emission per AGENTS.md observability requirements.
Ensures mandatory trace_id propagation and structured event logging.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid
import logging

logger = logging.getLogger(__name__)


class TraceEmitter:
    """
    Emits canonical trace events per AGENTS.md observability section.
    
    Per AGENTS.md:
    - Mandatory trace_id propagation
    - Canonical events only (no ad-hoc event names)
    - Structured, PII-safe logging
    - Golden signals tracking
    """
    
    # Canonical events per AGENTS.md
    CANONICAL_EVENTS = {
        "plan_created", "route_decision", "tool_call_start", "tool_call_complete",
        "tool_call_error", "budget_warning", "budget_exceeded",
        "approval_requested", "approval_received", "approval_timeout"
    }
    
    def __init__(self, trace_id: Optional[str] = None):
        """Initialize trace emitter with mandatory trace_id."""
        self.trace_id = trace_id or str(uuid.uuid4())
        self.events: List[Dict[str, Any]] = []
        self._start_time = datetime.now(timezone.utc)
    
    def emit(
        self, 
        event: str, 
        details: Dict[str, Any],
        status: str = "pending"
    ) -> None:
        """
        Emit a canonical trace event.
        
        Per AGENTS.md:
        - Event names must be canonical (from CANONICAL_EVENTS)
        - All events include trace_id, timestamp, status
        - Details are structured and PII-safe
        
        Args:
            event: Canonical event name
            details: Structured event details (will be logged)
            status: Event status (pending, success, error)
        
        Raises:
            ValueError: If event name is not canonical
        """
        if event not in self.CANONICAL_EVENTS:
            raise ValueError(
                f"Non-canonical event: {event}. "
                f"Must be one of {self.CANONICAL_EVENTS}"
            )
        
        event_data = {
            "event": event,
            "trace_id": self.trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details,
            "status": status
        }
        
        self.events.append(event_data)
        logger.info(f"Trace event emitted", extra=event_data)
    
    def get_trace(self) -> List[Dict[str, Any]]:
        """
        Return complete trace for UI consumption.
        
        Returns trace in format expected by frontend TraceViewer component.
        """
        return self.events
    
    def get_duration_ms(self) -> float:
        """Calculate total execution duration for golden signals."""
        return (datetime.now(timezone.utc) - self._start_time).total_seconds() * 1000
    
    def get_golden_signals(self) -> Dict[str, Any]:
        """
        Extract golden signals per AGENTS.md observability requirements.
        
        Golden Signals:
        - success_rate
        - latency (P50/P95/P99)
        - tool_error_rate
        - mean_steps_per_task
        - approval_wait_time
        - budget_utilization
        """
        tool_calls = [e for e in self.events if e["event"] == "tool_call_complete"]
        tool_errors = [e for e in self.events if e["event"] == "tool_call_error"]
        
        # Calculate latency percentiles from tool call durations
        latencies = []
        for event in self.events:
            if event["event"] == "tool_call_complete" and "metadata" in event:
                metadata = event.get("metadata", {})
                if "duration_ms" in metadata:
                    latencies.append(metadata["duration_ms"])
        
        latency_stats = {}
        if latencies:
            latencies_sorted = sorted(latencies)
            latency_stats = {
                "p50": latencies_sorted[len(latencies) // 2] if latencies else 0,
                "p95": latencies_sorted[int(len(latencies) * 0.95)] if latencies else 0,
                "p99": latencies_sorted[int(len(latencies) * 0.99)] if latencies else 0,
                "mean": sum(latencies) / len(latencies) if latencies else 0
            }
        else:
            latency_stats = {"p50": 0, "p95": 0, "p99": 0, "mean": 0}
        
        return {
            "trace_id": self.trace_id,
            "duration_ms": self.get_duration_ms(),
            "total_steps": len(tool_calls),
            "errors": len(tool_errors),
            "success_rate": (len(tool_calls) - len(tool_errors)) / max(len(tool_calls), 1),
            "error_rate": len(tool_errors) / max(len(tool_calls), 1),
            "latency": latency_stats,
            "total_events": len(self.events)
        }

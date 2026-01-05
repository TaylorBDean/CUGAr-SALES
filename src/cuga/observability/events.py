"""
Structured Event System for CUGAR Agent Observability

Emits structured events for every lifecycle stage with golden signal tracking.
All events are PII-safe, redacted, and OTEL-compatible.

Key Events:
- plan_created: Planning stage completed
- route_decision: Routing decision made
- tool_call_start: Tool execution started
- tool_call_complete: Tool execution finished
- tool_call_error: Tool execution failed
- budget_warning: Budget limit approaching
- budget_exceeded: Budget limit exceeded
- approval_requested: Human approval needed
- approval_received: Approval decision recorded
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


class EventType(str, Enum):
    """Canonical event types for structured observability."""
    
    # Lifecycle events
    PLAN_CREATED = "plan_created"
    ROUTE_DECISION = "route_decision"
    
    # Tool execution events
    TOOL_CALL_START = "tool_call_start"
    TOOL_CALL_COMPLETE = "tool_call_complete"
    TOOL_CALL_ERROR = "tool_call_error"
    
    # Budget events
    BUDGET_WARNING = "budget_warning"
    BUDGET_EXCEEDED = "budget_exceeded"
    BUDGET_UPDATED = "budget_updated"
    
    # Approval events
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RECEIVED = "approval_received"
    APPROVAL_TIMEOUT = "approval_timeout"
    
    # Orchestration events
    EXECUTION_START = "execution_start"
    EXECUTION_COMPLETE = "execution_complete"
    EXECUTION_ERROR = "execution_error"
    
    # Memory events
    MEMORY_QUERY = "memory_query"
    MEMORY_STORE = "memory_store"


@dataclass
class StructuredEvent:
    """
    Immutable structured event with OTEL-compatible fields.
    
    All events include trace_id, timestamp, event type, and optional
    attributes. Events are automatically redacted for PII safety.
    """
    
    # Required fields
    event_type: EventType
    trace_id: str
    timestamp: float = field(default_factory=time.time)
    
    # Optional identification
    request_id: str = ""
    session_id: str = ""
    user_id: str = ""
    
    # Event-specific attributes
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    # Performance metrics
    duration_ms: Optional[float] = None
    
    # Status
    status: str = "success"  # success, error, warning, info
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with ISO timestamp."""
        data = asdict(self)
        data["timestamp_iso"] = datetime.fromtimestamp(
            self.timestamp, tz=timezone.utc
        ).isoformat()
        data["event_type"] = self.event_type.value
        # Redact sensitive attributes
        data["attributes"] = _redact_dict(data["attributes"])
        return data
    
    def with_duration(self, start_time: float) -> StructuredEvent:
        """Create new event with calculated duration."""
        return StructuredEvent(
            event_type=self.event_type,
            trace_id=self.trace_id,
            timestamp=self.timestamp,
            request_id=self.request_id,
            session_id=self.session_id,
            user_id=self.user_id,
            attributes=self.attributes.copy(),
            duration_ms=(self.timestamp - start_time) * 1000,
            status=self.status,
            error_message=self.error_message,
        )


@dataclass
class PlanEvent(StructuredEvent):
    """Event emitted when a plan is created."""
    
    event_type: EventType = field(default=EventType.PLAN_CREATED, init=False)
    
    @staticmethod
    def create(
        trace_id: str,
        goal: str,
        steps_count: int,
        tools_selected: List[str],
        duration_ms: float,
        **kwargs: Any,
    ) -> PlanEvent:
        """Create a plan event with standard attributes."""
        return PlanEvent(
            trace_id=trace_id,
            duration_ms=duration_ms,
            attributes={
                "goal": goal[:200],  # Truncate for safety
                "steps_count": steps_count,
                "tools_selected": tools_selected,
                **kwargs,
            },
        )


@dataclass
class RouteEvent(StructuredEvent):
    """Event emitted when routing decision is made."""
    
    event_type: EventType = field(default=EventType.ROUTE_DECISION, init=False)
    
    @staticmethod
    def create(
        trace_id: str,
        agent_selected: str,
        routing_policy: str = "",
        alternatives_considered: Optional[List[str]] = None,
        reasoning: str = "",
        duration_ms: Optional[float] = None,
        # Legacy parameter names from tests
        alternatives: Optional[List[str]] = None,
        selection_criteria: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> RouteEvent:
        """Create a routing event with decision context."""
        # Support legacy test parameter names
        if alternatives is not None and alternatives_considered is None:
            alternatives_considered = alternatives
        if alternatives_considered is None:
            alternatives_considered = []
        
        attrs = {
            "agent_selected": agent_selected,
            "routing_policy": routing_policy,
            "alternatives_considered": alternatives_considered,
            "reasoning": reasoning[:500] if reasoning else "",
            **kwargs,
        }
        if selection_criteria:
            attrs["selection_criteria"] = selection_criteria
            
        return RouteEvent(
            trace_id=trace_id,
            duration_ms=duration_ms,
            attributes=attrs,
        )


@dataclass
class ToolCallEvent(StructuredEvent):
    """Event emitted for tool execution lifecycle."""
    
    # No default event_type because we have start/complete/error variants
    
    @staticmethod
    def start(
        trace_id: str,
        tool_name: str,
        tool_params: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ToolCallEvent:
        """Create a tool call start event."""
        return ToolCallEvent(
            event_type=EventType.TOOL_CALL_START,
            trace_id=trace_id,
            attributes={
                "tool_name": tool_name,
                "tool_params": _redact_dict(tool_params or {}),
                **kwargs,
            },
        )
    
    # Alias for test compatibility
    @staticmethod
    def create_start(
        trace_id: str,
        tool_name: str,
        inputs: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> ToolCallEvent:
        """Create a tool call start event (test-compatible alias)."""
        attrs = {"tool_name": tool_name, **kwargs}
        if inputs:
            attrs["inputs"] = _redact_dict(inputs)
        return ToolCallEvent(
            event_type=EventType.TOOL_CALL_START,
            trace_id=trace_id,
            attributes=attrs,
        )
    
    @staticmethod
    def complete(
        trace_id: str,
        tool_name: str,
        duration_ms: float,
        result_size: int = 0,
        **kwargs: Any,
    ) -> ToolCallEvent:
        """Create a tool call completion event."""
        return ToolCallEvent(
            event_type=EventType.TOOL_CALL_COMPLETE,
            trace_id=trace_id,
            duration_ms=duration_ms,
            attributes={
                "tool_name": tool_name,
                "result_size": result_size,
                **kwargs,
            },
        )
    
    # Alias for test compatibility
    @staticmethod
    def create_complete(
        trace_id: str,
        tool_name: str,
        result: Optional[Any] = None,
        duration_ms: float = 0.0,
        **kwargs: Any,
    ) -> ToolCallEvent:
        """Create a tool call completion event (test-compatible alias)."""
        attrs = {"tool_name": tool_name, **kwargs}
        if result is not None:
            # Calculate result size (simplified)
            if isinstance(result, dict):
                attrs["result_size"] = len(str(result))
            attrs["result"] = result
        return ToolCallEvent(
            event_type=EventType.TOOL_CALL_COMPLETE,
            trace_id=trace_id,
            duration_ms=duration_ms,
            attributes=attrs,
        )
    
    @staticmethod
    def error(
        trace_id: str,
        tool_name: str,
        error_type: str,
        error_message: str,
        duration_ms: float,
        **kwargs: Any,
    ) -> ToolCallEvent:
        """Create a tool call error event."""
        return ToolCallEvent(
            event_type=EventType.TOOL_CALL_ERROR,
            trace_id=trace_id,
            status="error",
            error_message=error_message[:500],
            duration_ms=duration_ms,
            attributes={
                "tool_name": tool_name,
                "error_type": error_type,
                **kwargs,
            },
        )
    
    # Alias for test compatibility
    @staticmethod
    def create_error(
        trace_id: str,
        tool_name: str,
        error_type: str,
        error_message: str,
        duration_ms: float = 0.0,
        # Legacy parameter name
        error: Optional[str] = None,
        **kwargs: Any,
    ) -> ToolCallEvent:
        """Create a tool call error event (test-compatible alias)."""
        # Support legacy 'error' parameter
        if error is not None and not error_message:
            error_message = error
            
        return ToolCallEvent(
            event_type=EventType.TOOL_CALL_ERROR,
            trace_id=trace_id,
            status="error",
            error_message=error_message[:500],
            duration_ms=duration_ms,
            attributes={
                "tool_name": tool_name,
                "error_type": error_type,
                **kwargs,
            },
        )


@dataclass
class BudgetEvent(StructuredEvent):
    """Event emitted for budget tracking and enforcement."""
    
    # No default event_type because we have warning/exceeded/updated variants
    
    @staticmethod
    def warning(
        trace_id: str,
        budget_type: str,
        spent: float,
        ceiling: float,
        threshold: float,
        **kwargs: Any,
    ) -> BudgetEvent:
        """Create a budget warning event."""
        return BudgetEvent(
            event_type=EventType.BUDGET_WARNING,
            trace_id=trace_id,
            status="warning",
            attributes={
                "budget_type": budget_type,
                "spent": spent,
                "ceiling": ceiling,
                "threshold": threshold,
                "utilization_pct": (spent / ceiling * 100) if ceiling > 0 else 0,
                **kwargs,
            },
        )
    
    # Alias for test compatibility
    @staticmethod
    def create_warning(
        trace_id: str,
        profile: str,
        budget_type: str,
        utilization_pct: float,
        current_value: float,
        limit: float,
        **kwargs: Any,
    ) -> BudgetEvent:
        """Create a budget warning event (test-compatible alias)."""
        return BudgetEvent(
            event_type=EventType.BUDGET_WARNING,
            trace_id=trace_id,
            status="warning",
            attributes={
                "profile": profile,
                "budget_type": budget_type,
                "utilization_pct": utilization_pct,
                "current_value": current_value,
                "limit": limit,
                **kwargs,
            },
        )
    
    @staticmethod
    def exceeded(
        trace_id: str,
        budget_type: str,
        spent: float,
        ceiling: float,
        policy: str,
        **kwargs: Any,
    ) -> BudgetEvent:
        """Create a budget exceeded event."""
        return BudgetEvent(
            event_type=EventType.BUDGET_EXCEEDED,
            trace_id=trace_id,
            status="error",
            attributes={
                "budget_type": budget_type,
                "spent": spent,
                "ceiling": ceiling,
                "policy": policy,
                "overage": spent - ceiling,
                **kwargs,
            },
        )
    
    # Alias for test compatibility
    @staticmethod
    def create_exceeded(
        trace_id: str,
        profile: str,
        budget_type: str,
        utilization_pct: float,
        current_value: float,
        limit: float,
        **kwargs: Any,
    ) -> BudgetEvent:
        """Create a budget exceeded event (test-compatible alias)."""
        return BudgetEvent(
            event_type=EventType.BUDGET_EXCEEDED,
            trace_id=trace_id,
            status="error",
            attributes={
                "profile": profile,
                "budget_type": budget_type,
                "utilization_pct": utilization_pct,
                "current_value": current_value,
                "limit": limit,
                "overage": current_value - limit,
                **kwargs,
            },
        )
    
    @staticmethod
    def updated(
        trace_id: str,
        budget_type: str,
        spent: float,
        ceiling: float,
        delta: float,
        **kwargs: Any,
    ) -> BudgetEvent:
        """Create a budget update event."""
        return BudgetEvent(
            event_type=EventType.BUDGET_UPDATED,
            trace_id=trace_id,
            attributes={
                "budget_type": budget_type,
                "spent": spent,
                "ceiling": ceiling,
                "delta": delta,
                "utilization_pct": (spent / ceiling * 100) if ceiling > 0 else 0,
                **kwargs,
            },
        )


@dataclass
class ApprovalEvent(StructuredEvent):
    """Event emitted for human-in-the-loop approval workflow."""
    
    @staticmethod
    def requested(
        trace_id: str,
        action_description: str,
        risk_level: str,
        timeout_seconds: int,
        **kwargs: Any,
    ) -> ApprovalEvent:
        """Create an approval request event."""
        return ApprovalEvent(
            event_type=EventType.APPROVAL_REQUESTED,
            trace_id=trace_id,
            attributes={
                "action_description": action_description[:500],
                "risk_level": risk_level,
                "timeout_seconds": timeout_seconds,
                **kwargs,
            },
        )
    
    # Alias for test compatibility
    @staticmethod
    def create_requested(
        trace_id: str,
        tool_name: str,
        risk_tier: str,
        request_id: str,
        timeout_seconds: int,
        **kwargs: Any,
    ) -> ApprovalEvent:
        """Create an approval request event (test-compatible alias)."""
        return ApprovalEvent(
            event_type=EventType.APPROVAL_REQUESTED,
            trace_id=trace_id,
            request_id=request_id,
            attributes={
                "tool_name": tool_name,
                "risk_tier": risk_tier,
                "timeout_seconds": timeout_seconds,
                **kwargs,
            },
        )
    
    @staticmethod
    def received(
        trace_id: str,
        approved: bool,
        wait_time_ms: float,
        reason: str = "",
        **kwargs: Any,
    ) -> ApprovalEvent:
        """Create an approval decision event."""
        return ApprovalEvent(
            event_type=EventType.APPROVAL_RECEIVED,
            trace_id=trace_id,
            duration_ms=wait_time_ms,
            attributes={
                "approved": approved,
                "reason": reason[:500],
                **kwargs,
            },
        )
    
    # Alias for test compatibility
    @staticmethod
    def create_received(
        trace_id: str,
        request_id: str,
        approved: bool,
        approved_by: str,
        wait_time_ms: float,
        **kwargs: Any,
    ) -> ApprovalEvent:
        """Create an approval decision event (test-compatible alias)."""
        return ApprovalEvent(
            event_type=EventType.APPROVAL_RECEIVED,
            trace_id=trace_id,
            request_id=request_id,
            duration_ms=wait_time_ms,
            attributes={
                "approved": approved,
                "approved_by": approved_by,
                **kwargs,
            },
        )
    
    @staticmethod
    def timeout(
        trace_id: str,
        wait_time_ms: float,
        default_action: str,
        **kwargs: Any,
    ) -> ApprovalEvent:
        """Create an approval timeout event."""
        return ApprovalEvent(
            event_type=EventType.APPROVAL_TIMEOUT,
            trace_id=trace_id,
            status="warning",
            duration_ms=wait_time_ms,
            attributes={
                "default_action": default_action,
                **kwargs,
            },
        )
    
    # Alias for test compatibility
    @staticmethod
    def create_timeout(
        trace_id: str,
        request_id: str,
        wait_time_ms: float,
        **kwargs: Any,
    ) -> ApprovalEvent:
        """Create an approval timeout event (test-compatible alias)."""
        return ApprovalEvent(
            event_type=EventType.APPROVAL_TIMEOUT,
            trace_id=trace_id,
            request_id=request_id,
            status="warning",
            duration_ms=wait_time_ms,
            attributes={
                "default_action": kwargs.get("default_action", "deny"),
                **kwargs,
            },
        )


def _redact_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Redact sensitive keys from dictionary (PII-safe).
    
    Redacts: secret, token, password, api_key, credential, auth
    """
    if not isinstance(data, dict):
        return data
    
    redacted = {}
    sensitive_keys = {
        "secret", "token", "password", "api_key", "apikey",
        "credential", "auth", "authorization", "bearer"
    }
    
    for key, value in data.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            redacted[key] = "[REDACTED]"
        elif isinstance(value, dict):
            redacted[key] = _redact_dict(value)
        elif isinstance(value, list):
            redacted[key] = [
                _redact_dict(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            redacted[key] = value
    
    return redacted

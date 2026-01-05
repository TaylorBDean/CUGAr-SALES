"""
Tests for CUGAR Observability System

Tests structured events, golden signals, OTEL export, and collector integration.
"""

from __future__ import annotations

import time
from typing import List

import pytest

from cuga.observability import (
    ObservabilityCollector,
    PlanEvent,
    RouteEvent,
    ToolCallEvent,
    BudgetEvent,
    ApprovalEvent,
    EventType,
    ConsoleExporter,
    GoldenSignals,
)


class TestStructuredEvents:
    """Test structured event creation and attributes."""
    
    def test_plan_event_creation(self):
        """Test plan event creation with all attributes."""
        event = PlanEvent.create(
            trace_id="test-123",
            goal="Test goal",
            steps_count=3,
            tools_selected=["tool1", "tool2", "tool3"],
            duration_ms=150.0,
            profile="test_profile",
        )
        
        assert event.event_type == EventType.PLAN_CREATED
        assert event.trace_id == "test-123"
        assert event.duration_ms == 150.0
        assert event.attributes["steps_count"] == 3
        assert event.attributes["tools_selected"] == ["tool1", "tool2", "tool3"]
        assert event.attributes["profile"] == "test_profile"
    
    def test_route_event_creation(self):
        """Test route event with decision context."""
        event = RouteEvent.create(
            trace_id="test-123",
            agent_selected="agent1",
            routing_policy="round_robin",
            alternatives_considered=["agent2", "agent3"],
            reasoning="Agent1 has lowest load",
        )
        
        assert event.event_type == EventType.ROUTE_DECISION
        assert event.attributes["agent_selected"] == "agent1"
        assert event.attributes["routing_policy"] == "round_robin"
        assert len(event.attributes["alternatives_considered"]) == 2
    
    def test_tool_call_lifecycle(self):
        """Test tool call start/complete/error events."""
        # Start
        start_event = ToolCallEvent.start(
            trace_id="test-123",
            tool_name="test_tool",
            tool_params={"key": "value", "secret": "should_be_redacted"},
        )
        assert start_event.event_type == EventType.TOOL_CALL_START
        
        # Complete
        complete_event = ToolCallEvent.complete(
            trace_id="test-123",
            tool_name="test_tool",
            duration_ms=250.0,
            result_size=1024,
        )
        assert complete_event.event_type == EventType.TOOL_CALL_COMPLETE
        assert complete_event.duration_ms == 250.0
        
        # Error
        error_event = ToolCallEvent.error(
            trace_id="test-123",
            tool_name="test_tool",
            error_type="timeout",
            error_message="Tool timed out",
            duration_ms=5000.0,
        )
        assert error_event.event_type == EventType.TOOL_CALL_ERROR
        assert error_event.status == "error"
        assert error_event.error_message == "Tool timed out"
    
    def test_budget_events(self):
        """Test budget warning and exceeded events."""
        # Warning
        warning_event = BudgetEvent.warning(
            trace_id="test-123",
            budget_type="cost",
            spent=85.0,
            ceiling=100.0,
            threshold=80.0,
        )
        assert warning_event.event_type == EventType.BUDGET_WARNING
        assert warning_event.status == "warning"
        assert warning_event.attributes["utilization_pct"] == 85.0
        
        # Exceeded
        exceeded_event = BudgetEvent.exceeded(
            trace_id="test-123",
            budget_type="cost",
            spent=105.0,
            ceiling=100.0,
            policy="warn",
        )
        assert exceeded_event.event_type == EventType.BUDGET_EXCEEDED
        assert exceeded_event.status == "error"
        assert exceeded_event.attributes["overage"] == 5.0
    
    def test_approval_events(self):
        """Test approval workflow events."""
        # Requested
        request_event = ApprovalEvent.requested(
            trace_id="test-123",
            action_description="Delete database",
            risk_level="high",
            timeout_seconds=300,
        )
        assert request_event.event_type == EventType.APPROVAL_REQUESTED
        
        # Received
        received_event = ApprovalEvent.received(
            trace_id="test-123",
            approved=True,
            wait_time_ms=15000.0,
            reason="Approved by admin",
        )
        assert received_event.event_type == EventType.APPROVAL_RECEIVED
        assert received_event.duration_ms == 15000.0
        
        # Timeout
        timeout_event = ApprovalEvent.timeout(
            trace_id="test-123",
            wait_time_ms=300000.0,
            default_action="deny",
        )
        assert timeout_event.event_type == EventType.APPROVAL_TIMEOUT
        assert timeout_event.status == "warning"
    
    def test_event_redaction(self):
        """Test sensitive data redaction in events."""
        event = ToolCallEvent.start(
            trace_id="test-123",
            tool_name="test_tool",
            tool_params={
                "api_key": "secret123",
                "password": "pass456",
                "token": "token789",
                "safe_param": "visible",
            },
        )
        
        event_dict = event.to_dict()
        params = event_dict["attributes"]["tool_params"]
        
        assert params["api_key"] == "[REDACTED]"
        assert params["password"] == "[REDACTED]"
        assert params["token"] == "[REDACTED]"
        assert params["safe_param"] == "visible"
    
    def test_event_to_dict(self):
        """Test event serialization to dictionary."""
        event = PlanEvent.create(
            trace_id="test-123",
            goal="Test",
            steps_count=2,
            tools_selected=["tool1"],
            duration_ms=100.0,
        )
        
        event_dict = event.to_dict()
        
        assert "event_type" in event_dict
        assert "trace_id" in event_dict
        assert "timestamp_iso" in event_dict
        assert event_dict["event_type"] == "plan_created"


class TestGoldenSignals:
    """Test golden signal tracking and computation."""
    
    def test_success_rate_tracking(self):
        """Test success rate calculation."""
        signals = GoldenSignals()
        
        # Record requests
        signals.record_request_start()
        signals.record_request_success(100.0)
        
        signals.record_request_start()
        signals.record_request_success(150.0)
        
        signals.record_request_start()
        signals.record_request_failure(200.0)
        
        # 2 successes out of 3 total
        assert signals.success_rate() == pytest.approx(66.67, rel=0.01)
        assert signals.error_rate() == pytest.approx(33.33, rel=0.01)
    
    def test_latency_percentiles(self):
        """Test latency percentile calculation."""
        signals = GoldenSignals()
        
        # Add latency samples
        for i in range(100):
            signals.end_to_end_latency.add(float(i))
        
        p50 = signals.end_to_end_latency.percentile(50)
        p95 = signals.end_to_end_latency.percentile(95)
        p99 = signals.end_to_end_latency.percentile(99)
        
        assert 45 <= p50 <= 55
        assert 90 <= p95 <= 99
        assert 95 <= p99 <= 99
    
    def test_tool_error_rate(self):
        """Test tool-specific error tracking."""
        signals = GoldenSignals()
        
        # Record tool calls
        for _ in range(10):
            signals.record_tool_call_start("tool1")
            signals.record_tool_call_complete("tool1", 100.0)
        
        # Record errors
        for _ in range(2):
            signals.record_tool_call_start("tool1")
            signals.record_tool_call_error("tool1", "timeout", 1000.0)
        
        # 2 errors out of 12 calls
        assert signals.tool_error_rate() == pytest.approx(16.67, rel=0.01)
    
    def test_mean_steps_per_task(self):
        """Test steps per task calculation."""
        signals = GoldenSignals()
        
        signals.record_plan_created(3, 100.0)
        signals.record_plan_created(5, 150.0)
        signals.record_plan_created(4, 120.0)
        
        assert signals.mean_steps_per_task() == 4.0
    
    def test_approval_wait_time(self):
        """Test approval wait time tracking."""
        signals = GoldenSignals()
        
        signals.record_approval_requested()
        signals.record_approval_received(5000.0)
        
        signals.record_approval_requested()
        signals.record_approval_received(15000.0)
        
        signals.record_approval_requested()
        signals.record_approval_timeout()
        
        assert signals.approval_requests.get() == 3
        assert signals.approval_timeouts.get() == 1
        assert len(signals.approval_wait_times.samples) == 2
    
    def test_budget_tracking(self):
        """Test budget warning and exceeded tracking."""
        signals = GoldenSignals()
        
        signals.record_budget_warning("cost", 85.0)
        signals.record_budget_warning("cost", 90.0)
        signals.record_budget_exceeded("cost", 105.0)
        
        assert signals.budget_warnings.get() == 2
        assert signals.budget_exceeded.get() == 1
        assert len(signals.budget_utilization["cost"]) == 3
    
    def test_prometheus_format(self):
        """Test Prometheus metric export format."""
        signals = GoldenSignals()
        
        signals.record_request_start()
        signals.record_request_success(100.0)
        
        prometheus_text = signals.to_prometheus_format()
        
        assert "cuga_requests_total 1" in prometheus_text
        assert "cuga_success_rate 100.00" in prometheus_text
        assert "# HELP" in prometheus_text
        assert "# TYPE" in prometheus_text
    
    def test_metrics_dict_export(self):
        """Test metrics export as dictionary."""
        signals = GoldenSignals()
        
        signals.record_request_start()
        signals.record_request_success(100.0)
        signals.record_plan_created(3, 150.0)
        signals.record_tool_call_start("tool1")
        signals.record_tool_call_complete("tool1", 50.0)
        
        metrics = signals.to_dict()
        
        assert "success_rate" in metrics
        assert "mean_steps_per_task" in metrics
        assert "latency" in metrics
        assert "tool_calls" in metrics
        assert metrics["success_rate"] == 100.0
        assert metrics["mean_steps_per_task"] == 3.0


class TestObservabilityCollector:
    """Test observability collector integration."""
    
    def test_collector_initialization(self):
        """Test collector initialization with exporters."""
        collector = ObservabilityCollector(
            exporters=[ConsoleExporter(pretty=False)],
            auto_export=False,
            buffer_size=100,
        )
        
        assert collector.buffer_size == 100
        assert not collector.auto_export
        assert len(collector.exporters) == 1
    
    def test_event_emission(self):
        """Test event emission and buffering."""
        collector = ObservabilityCollector(
            exporters=[ConsoleExporter(pretty=False)],
            auto_export=False,
        )
        
        event = PlanEvent.create(
            trace_id="test-123",
            goal="Test",
            steps_count=3,
            tools_selected=["tool1"],
            duration_ms=100.0,
        )
        
        collector.emit_event(event)
        
        assert len(collector._event_buffer) == 1
        assert collector.signals.mean_steps_per_task() == 3.0
    
    def test_signal_updates_from_events(self):
        """Test automatic signal updates from events."""
        collector = ObservabilityCollector(auto_export=False)
        
        # Emit plan event
        plan_event = PlanEvent.create(
            trace_id="test-123",
            goal="Test",
            steps_count=5,
            tools_selected=["tool1"],
            duration_ms=100.0,
        )
        collector.emit_event(plan_event)
        
        # Emit tool events
        start_event = ToolCallEvent.start(
            trace_id="test-123",
            tool_name="tool1",
            tool_params={},
        )
        collector.emit_event(start_event)
        
        complete_event = ToolCallEvent.complete(
            trace_id="test-123",
            tool_name="tool1",
            duration_ms=50.0,
            result_size=1024,
        )
        collector.emit_event(complete_event)
        
        # Check signals updated
        metrics = collector.get_metrics()
        assert metrics["mean_steps_per_task"] == 5.0
        assert metrics["tool_calls"] == 1
    
    def test_trace_lifecycle(self):
        """Test trace start/end tracking."""
        collector = ObservabilityCollector(auto_export=False)
        
        # Start trace
        collector.start_trace("test-123", {"user": "alice"})
        assert "test-123" in collector._active_traces
        
        # End trace
        time.sleep(0.01)  # Small delay
        collector.end_trace("test-123", success=True)
        assert "test-123" not in collector._active_traces
        
        # Check success recorded
        metrics = collector.get_metrics()
        assert metrics["successful_requests"] == 1
    
    def test_buffer_flush(self):
        """Test event buffer flushing."""
        collector = ObservabilityCollector(
            exporters=[ConsoleExporter(pretty=False)],
            auto_export=False,
            buffer_size=10,
        )
        
        # Add events
        for i in range(5):
            event = PlanEvent.create(
                trace_id=f"test-{i}",
                goal="Test",
                steps_count=2,
                tools_selected=["tool1"],
                duration_ms=100.0,
            )
            collector.emit_event(event)
        
        assert len(collector._event_buffer) == 5
        
        # Manual flush
        collector.flush()
        assert len(collector._event_buffer) == 0
    
    def test_auto_flush_on_buffer_full(self):
        """Test automatic flush when buffer is full."""
        collector = ObservabilityCollector(
            exporters=[ConsoleExporter(pretty=False)],
            auto_export=False,
            buffer_size=3,
        )
        
        # Add events to fill buffer
        for i in range(5):
            event = PlanEvent.create(
                trace_id=f"test-{i}",
                goal="Test",
                steps_count=2,
                tools_selected=["tool1"],
                duration_ms=100.0,
            )
            collector.emit_event(event)
        
        # Buffer should have flushed at least once
        assert len(collector._event_buffer) < 5
    
    def test_metrics_export(self):
        """Test metrics export to exporters."""
        collector = ObservabilityCollector(
            exporters=[ConsoleExporter(pretty=False)],
            auto_export=False,
        )
        
        # Add some events
        collector.signals.record_request_start()
        collector.signals.record_request_success(100.0)
        
        # Export metrics (should not raise)
        collector.export_metrics()
    
    def test_prometheus_metrics(self):
        """Test Prometheus metrics endpoint."""
        collector = ObservabilityCollector(auto_export=False)
        
        collector.signals.record_request_start()
        collector.signals.record_request_success(100.0)
        
        prometheus_text = collector.get_prometheus_metrics()
        
        assert "cuga_requests_total" in prometheus_text
        assert "cuga_success_rate" in prometheus_text
    
    def test_reset_metrics(self):
        """Test metrics reset functionality."""
        collector = ObservabilityCollector(auto_export=False)
        
        # Add events
        collector.signals.record_request_start()
        collector.signals.record_request_success(100.0)
        
        # Reset
        collector.reset_metrics()
        
        metrics = collector.get_metrics()
        assert metrics["total_requests"] == 0
        assert metrics["successful_requests"] == 0


class TestIntegration:
    """Integration tests for full observability flow."""
    
    def test_complete_execution_flow(self):
        """Test complete agent execution with observability."""
        collector = ObservabilityCollector(
            exporters=[ConsoleExporter(pretty=False)],
            auto_export=False,
        )
        
        trace_id = "integration-test-123"
        
        # Start trace
        collector.start_trace(trace_id)
        
        # Plan event
        plan_event = PlanEvent.create(
            trace_id=trace_id,
            goal="Complete task",
            steps_count=3,
            tools_selected=["tool1", "tool2", "tool3"],
            duration_ms=150.0,
        )
        collector.emit_event(plan_event)
        
        # Route event
        route_event = RouteEvent.create(
            trace_id=trace_id,
            agent_selected="agent1",
            routing_policy="capability",
            alternatives_considered=["agent2"],
            reasoning="Best capability match",
        )
        collector.emit_event(route_event)
        
        # Tool calls
        for tool in ["tool1", "tool2", "tool3"]:
            start = ToolCallEvent.start(
                trace_id=trace_id,
                tool_name=tool,
                tool_params={"param": "value"},
            )
            collector.emit_event(start)
            
            complete = ToolCallEvent.complete(
                trace_id=trace_id,
                tool_name=tool,
                duration_ms=50.0,
                result_size=512,
            )
            collector.emit_event(complete)
        
        # End trace
        collector.end_trace(trace_id, success=True)
        
        # Verify metrics
        metrics = collector.get_metrics()
        assert metrics["success_rate"] == 100.0
        assert metrics["mean_steps_per_task"] == 3.0
        assert metrics["tool_calls"] == 3
        assert metrics["tool_error_rate"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

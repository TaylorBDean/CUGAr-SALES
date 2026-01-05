"""
Tests for observability integration per AGENTS.md § Observability & Tracing.

Tests cover:
- OTEL collector initialization
- Structured event emission
- /metrics endpoint (Prometheus format)
- Event types (plan, route, tool_call, budget, approval)
"""

import pytest
from fastapi.testclient import TestClient

from cuga.backend.app import app
from cuga.observability import (
    ObservabilityCollector,
    ConsoleExporter,
    PlanEvent,
    RouteEvent,
    ToolCallEvent,
    BudgetEvent,
    ApprovalEvent,
)
from cuga.observability.collector import get_collector, set_collector


@pytest.fixture
def test_collector():
    """Create test collector with console exporter."""
    collector = ObservabilityCollector(
        exporters=[ConsoleExporter(pretty=False)],
        auto_export=False,  # Don't print during tests
        buffer_size=100,
    )
    set_collector(collector)
    yield collector
    collector.reset_metrics()


@pytest.fixture
def client(monkeypatch):
    """FastAPI test client with required env vars."""
    # Set required AGENT_TOKEN for budget_guard middleware
    monkeypatch.setenv("AGENT_TOKEN", "test-token-12345")
    return TestClient(app)


class TestCollectorInitialization:
    """Test OTEL collector initialization."""
    
    def test_get_collector_creates_default(self):
        """Test get_collector creates default instance."""
        collector = get_collector()
        assert collector is not None
        assert isinstance(collector, ObservabilityCollector)
    
    def test_set_collector_works(self, test_collector):
        """Test set_collector sets global instance."""
        collector = get_collector()
        assert collector is test_collector


class TestEventEmission:
    """Test structured event emission."""
    
    def test_emit_plan_event(self, test_collector):
        """Test plan event emission and metric update."""
        event = PlanEvent.create(
            trace_id="test-trace-123",
            goal="Find flights",
            steps_count=3,
            tools_selected=["search", "filter"],
            duration_ms=150.0,
        )
        
        test_collector.emit_event(event)
        
        # Check metrics updated
        metrics = test_collector.get_metrics()
        assert metrics["mean_steps_per_task"] == 3.0
        assert len(test_collector.signals.planning_latency.samples) == 1
        assert test_collector.signals.planning_latency.samples[0] == 150.0
    
    def test_emit_route_event(self, test_collector):
        """Test route event emission."""
        event = RouteEvent.create(
            trace_id="test-trace-123",
            agent_selected="worker-1",
            alternatives=["worker-2", "worker-3"],
            selection_criteria={"capability": "high"},
            duration_ms=50.0,
        )
        
        test_collector.emit_event(event)
        
        # Check routing latency tracked
        assert len(test_collector.signals.routing_latency.samples) == 1
        assert test_collector.signals.routing_latency.samples[0] == 50.0
    
    def test_emit_tool_call_events(self, test_collector):
        """Test tool call start/complete/error events."""
        # Start
        start_event = ToolCallEvent.create_start(
            trace_id="test-trace-123",
            tool_name="search_flights",
            inputs={"destination": "LAX"},
        )
        test_collector.emit_event(start_event)
        
        assert test_collector.signals.tool_calls.get() == 1
        
        # Complete
        complete_event = ToolCallEvent.create_complete(
            trace_id="test-trace-123",
            tool_name="search_flights",
            result={"flights": [{"id": 1}]},
            duration_ms=500.0,
        )
        test_collector.emit_event(complete_event)
        
        assert "search_flights" in test_collector.signals.tool_latency
        assert test_collector.signals.tool_latency["search_flights"].samples[0] == 500.0
        
        # Error
        error_event = ToolCallEvent.create_error(
            trace_id="test-trace-123",
            tool_name="search_flights",
            error_type="timeout",
            error_message="Request timed out",
            duration_ms=10000.0,
        )
        test_collector.emit_event(error_event)
        
        assert test_collector.signals.tool_errors.get() == 1
        assert test_collector.signals.tool_errors_by_tool["search_flights"].get() == 1
        assert test_collector.signals.tool_errors_by_type["timeout"].get() == 1
    
    def test_emit_budget_events(self, test_collector):
        """Test budget warning and exceeded events."""
        # Warning
        warning_event = BudgetEvent.create_warning(
            trace_id="test-trace-123",
            profile="test",
            budget_type="cost",
            utilization_pct=85.0,
            current_value=85.0,
            limit=100.0,
        )
        test_collector.emit_event(warning_event)
        
        assert test_collector.signals.budget_warnings.get() == 1
        
        # Exceeded
        exceeded_event = BudgetEvent.create_exceeded(
            trace_id="test-trace-123",
            profile="test",
            budget_type="cost",
            utilization_pct=105.0,
            current_value=105.0,
            limit=100.0,
        )
        test_collector.emit_event(exceeded_event)
        
        assert test_collector.signals.budget_exceeded.get() == 1
    
    def test_emit_approval_events(self, test_collector):
        """Test approval request/received/timeout events."""
        # Requested
        requested_event = ApprovalEvent.create_requested(
            trace_id="test-trace-123",
            tool_name="delete_file",
            risk_tier="DELETE",
            request_id="req-123",
            timeout_seconds=300,
        )
        test_collector.emit_event(requested_event)
        
        assert test_collector.signals.approval_requests.get() == 1
        
        # Received
        received_event = ApprovalEvent.create_received(
            trace_id="test-trace-123",
            request_id="req-123",
            approved=True,
            approved_by="admin@example.com",
            wait_time_ms=5000.0,
        )
        test_collector.emit_event(received_event)
        
        assert test_collector.signals.approval_wait_times.samples[0] == 5000.0
        
        # Timeout
        timeout_event = ApprovalEvent.create_timeout(
            trace_id="test-trace-123",
            request_id="req-124",
            wait_time_ms=300000.0,
        )
        test_collector.emit_event(timeout_event)
        
        assert test_collector.signals.approval_timeouts.get() == 1


class TestPrometheusMetrics:
    """Test /metrics endpoint."""
    
    def test_metrics_endpoint_exists(self, client):
        """Test /metrics endpoint is accessible."""
        response = client.get("/metrics", headers={"X-Token": "test-token-12345"})
        assert response.status_code == 200
        assert response.headers["content-type"] == "text/plain; charset=utf-8"
    
    def test_metrics_format(self, client, test_collector):
        """Test metrics are in Prometheus format."""
        # Emit some events
        plan_event = PlanEvent.create(
            trace_id="test-trace",
            goal="test",
            steps_count=5,
            tools_selected=["tool1"],
            duration_ms=100.0,
        )
        test_collector.emit_event(plan_event)
        
        response = client.get("/metrics", headers={"X-Token": "test-token-12345"})
        content = response.text
        
        # Check required Prometheus headers
        assert "# HELP cuga_requests_total" in content
        assert "# TYPE cuga_requests_total counter" in content
        
        # Check metrics present
        assert "cuga_success_rate" in content
        assert "cuga_latency_ms" in content
        assert "cuga_steps_per_task" in content
        assert "cuga_tool_calls_total" in content
        assert "cuga_tool_error_rate" in content
        assert "cuga_approval_requests_total" in content
        assert "cuga_budget_warnings_total" in content
        assert "cuga_budget_exceeded_total" in content
    
    def test_metrics_values_update(self, client, test_collector):
        """Test metrics reflect actual values."""
        # Record some activity
        test_collector.signals.record_request_start()
        test_collector.signals.record_request_success(150.0)
        test_collector.signals.record_plan_created(3, 50.0)
        test_collector.signals.record_tool_call_start("test_tool")
        test_collector.signals.record_tool_call_complete("test_tool", 100.0)
        
        response = client.get("/metrics", headers={"X-Token": "test-token-12345"})
        content = response.text
        
        # Check values
        assert "cuga_requests_total 1" in content
        assert "cuga_tool_calls_total 1" in content
        assert "cuga_steps_per_task 3.00" in content


class TestTraceCorrelation:
    """Test trace correlation across events."""
    
    def test_start_and_end_trace(self, test_collector):
        """Test trace lifecycle tracking."""
        trace_id = "test-trace-correlation"
        
        # Start trace
        test_collector.start_trace(trace_id, metadata={"user_id": "user-123"})
        
        # Emit events
        plan_event = PlanEvent.create(
            trace_id=trace_id,
            goal="test",
            steps_count=2,
            tools_selected=["tool1"],
            duration_ms=50.0,
        )
        test_collector.emit_event(plan_event)
        
        # End trace successfully
        test_collector.end_trace(trace_id, success=True)
        
        # Check metrics
        assert test_collector.signals.successful_requests.get() == 1
        assert test_collector.signals.failed_requests.get() == 0
    
    def test_failed_trace(self, test_collector):
        """Test failed trace recording."""
        trace_id = "test-trace-failed"
        
        test_collector.start_trace(trace_id)
        test_collector.end_trace(trace_id, success=False)
        
        assert test_collector.signals.successful_requests.get() == 0
        assert test_collector.signals.failed_requests.get() == 1


class TestMetricsReset:
    """Test metrics reset functionality."""
    
    def test_reset_clears_metrics(self, test_collector):
        """Test reset clears all metrics."""
        # Record activity
        test_collector.signals.record_request_start()
        test_collector.signals.record_tool_call_start("tool1")
        test_collector.signals.record_budget_warning("cost", 80.0)
        
        # Verify metrics exist
        assert test_collector.signals.total_requests.get() > 0
        
        # Reset
        test_collector.reset_metrics()
        
        # Verify cleared
        assert test_collector.signals.total_requests.get() == 0
        assert test_collector.signals.tool_calls.get() == 0
        assert test_collector.signals.budget_warnings.get() == 0


class TestBufferFlush:
    """Test event buffer management."""
    
    def test_auto_flush_on_buffer_full(self, test_collector):
        """Test automatic flush when buffer fills."""
        test_collector.buffer_size = 10  # Small buffer for testing
        
        # Emit more events than buffer size
        for i in range(15):
            event = PlanEvent.create(
                trace_id=f"trace-{i}",
                goal="test",
                steps_count=1,
                tools_selected=[],
                duration_ms=10.0,
            )
            test_collector.emit_event(event)
        
        # Buffer should have been flushed
        assert len(test_collector._event_buffer) < 15
    
    def test_manual_flush(self, test_collector):
        """Test manual flush clears buffer."""
        # Emit events
        for i in range(5):
            event = PlanEvent.create(
                trace_id=f"trace-{i}",
                goal="test",
                steps_count=1,
                tools_selected=[],
                duration_ms=10.0,
            )
            test_collector.emit_event(event)
        
        assert len(test_collector._event_buffer) == 5
        
        # Flush
        test_collector.flush()
        
        assert len(test_collector._event_buffer) == 0

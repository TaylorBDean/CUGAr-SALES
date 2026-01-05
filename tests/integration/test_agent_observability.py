"""
Integration tests for agent observability per AGENTS.md v1.1 requirements.

Tests validate that PlannerAgent, WorkerAgent, and CoordinatorAgent properly
emit observability events and integrate with guardrails enforcement.
"""

import pytest
from fastapi.testclient import TestClient

from cuga.backend.app import app
from cuga.modular.agents import (
    PlannerAgent,
    WorkerAgent,
    CoordinatorAgent,
    build_default_registry,
)
from cuga.modular.config import AgentConfig
from cuga.modular.memory import VectorMemory
from cuga.observability import (
    ObservabilityCollector,
    ConsoleExporter,
    PlanEvent,
    RouteEvent,
    ToolCallEvent,
    get_collector,
    set_collector,
)

# Check if guardrails are available
try:
    from cuga.backend.guardrails.policy import GuardrailPolicy, ToolBudget
    GUARDRAILS_AVAILABLE = True
except ImportError:
    GUARDRAILS_AVAILABLE = False


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
def registry():
    """Create test tool registry."""
    return build_default_registry()


@pytest.fixture
def memory():
    """Create test memory."""
    return VectorMemory(profile="test")


@pytest.fixture
def config():
    """Create test agent config."""
    return AgentConfig(profile="test", max_steps=3)


@pytest.fixture
def client(monkeypatch):
    """FastAPI test client with required env vars."""
    monkeypatch.setenv("AGENT_TOKEN", "test-token-12345")
    return TestClient(app)


class TestPlannerAgentObservability:
    """Test PlannerAgent emits plan_created events."""
    
    def test_plan_emits_plan_created_event(self, test_collector, registry, memory, config):
        """Test that PlannerAgent.plan() emits plan_created event."""
        planner = PlannerAgent(registry=registry, memory=memory, config=config)
        
        # Clear any existing events
        test_collector.reset_metrics()
        
        # Create plan
        plan = planner.plan("echo test message", metadata={"trace_id": "test-plan-001"})
        
        # Verify plan was created
        assert len(plan.steps) > 0
        assert plan.steps[0]["tool"] == "echo"
        
        # Verify plan_created event was emitted
        events = [e for e in test_collector.events if e.event_type.value == "plan_created"]
        assert len(events) == 1
        
        plan_event = events[0]
        assert plan_event.trace_id == "test-plan-001"
        assert plan_event.attributes["steps_count"] > 0
        assert "echo" in plan_event.attributes["tools_selected"]
        assert plan_event.duration_ms > 0
    
    def test_plan_includes_metadata(self, test_collector, registry, memory, config):
        """Test that plan_created event includes proper metadata."""
        planner = PlannerAgent(registry=registry, memory=memory, config=config)
        test_collector.reset_metrics()
        
        plan = planner.plan("echo hello", metadata={"trace_id": "test-plan-002", "profile": "test"})
        
        events = [e for e in test_collector.events if e.event_type.value == "plan_created"]
        assert len(events) == 1
        
        event = events[0]
        assert event.attributes["profile"] == "test"
        assert event.attributes["max_steps"] == 3


class TestWorkerAgentObservability:
    """Test WorkerAgent emits tool_call events."""
    
    def test_execute_emits_tool_call_start(self, test_collector, registry, memory):
        """Test that WorkerAgent.execute() emits tool_call_start event."""
        worker = WorkerAgent(registry=registry, memory=memory)
        test_collector.reset_metrics()
        
        steps = [{"tool": "echo", "input": {"text": "hello"}}]
        result = worker.execute(steps, metadata={"trace_id": "test-exec-001"})
        
        # Verify execution succeeded
        assert result.output == "hello"
        
        # Verify tool_call_start event
        start_events = [e for e in test_collector.events if e.event_type.value == "tool_call_start"]
        assert len(start_events) == 1
        
        start_event = start_events[0]
        assert start_event.trace_id == "test-exec-001"
        assert start_event.attributes["tool_name"] == "echo"
        assert start_event.attributes["inputs"]["text"] == "hello"
    
    def test_execute_emits_tool_call_complete(self, test_collector, registry, memory):
        """Test that WorkerAgent.execute() emits tool_call_complete event."""
        worker = WorkerAgent(registry=registry, memory=memory)
        test_collector.reset_metrics()
        
        steps = [{"tool": "echo", "input": {"text": "world"}}]
        result = worker.execute(steps, metadata={"trace_id": "test-exec-002"})
        
        # Verify tool_call_complete event
        complete_events = [e for e in test_collector.events if e.event_type.value == "tool_call_complete"]
        assert len(complete_events) == 1
        
        complete_event = complete_events[0]
        assert complete_event.trace_id == "test-exec-002"
        assert complete_event.attributes["tool_name"] == "echo"
        assert complete_event.attributes["result"] == "world"
        assert complete_event.duration_ms > 0
    
    def test_execute_emits_tool_call_error_on_failure(self, test_collector, registry, memory):
        """Test that WorkerAgent.execute() emits tool_call_error on tool failure."""
        worker = WorkerAgent(registry=registry, memory=memory)
        test_collector.reset_metrics()
        
        # Try to execute non-existent tool
        steps = [{"tool": "nonexistent", "input": {}}]
        
        with pytest.raises(ValueError, match="Tool nonexistent not registered"):
            worker.execute(steps, metadata={"trace_id": "test-exec-error-001"})
        
        # Verify tool_call_error event
        error_events = [e for e in test_collector.events if e.event_type.value == "tool_call_error"]
        assert len(error_events) == 1
        
        error_event = error_events[0]
        assert error_event.trace_id == "test-exec-error-001"
        assert error_event.attributes["tool_name"] == "nonexistent"
        # Error message is stored as top-level field, not in attributes
        assert "not registered" in error_event.error_message


class TestCoordinatorAgentObservability:
    """Test CoordinatorAgent emits route_decision events."""
    
    def test_dispatch_emits_route_decision(self, test_collector, registry, memory, config):
        """Test that CoordinatorAgent.dispatch() emits route_decision event."""
        planner = PlannerAgent(registry=registry, memory=memory, config=config)
        worker1 = WorkerAgent(registry=registry, memory=memory)
        worker2 = WorkerAgent(registry=registry, memory=memory)
        coordinator = CoordinatorAgent(planner=planner, workers=[worker1, worker2], memory=memory)
        
        test_collector.reset_metrics()
        
        result = coordinator.dispatch("echo test", trace_id="test-coord-001")
        
        # Verify result (echo tool returns the text input)
        assert result.output == "echo test"
        
        # Verify route_decision event
        route_events = [e for e in test_collector.events if e.event_type.value == "route_decision"]
        assert len(route_events) == 1
        
        route_event = route_events[0]
        assert route_event.trace_id == "test-coord-001"
        assert route_event.attributes["agent_selected"] in ["worker-0", "worker-1"]
        assert route_event.attributes["reason"] == "round_robin"
        assert len(route_event.attributes["alternatives_considered"]) == 2
    
    def test_round_robin_routing(self, test_collector, registry, memory, config):
        """Test that round-robin routing works and emits proper events."""
        planner = PlannerAgent(registry=registry, memory=memory, config=config)
        worker1 = WorkerAgent(registry=registry, memory=memory)
        worker2 = WorkerAgent(registry=registry, memory=memory)
        coordinator = CoordinatorAgent(planner=planner, workers=[worker1, worker2], memory=memory)
        
        test_collector.reset_metrics()
        
        # Dispatch twice to see round-robin
        coordinator.dispatch("echo first", trace_id="test-rr-001")
        coordinator.dispatch("echo second", trace_id="test-rr-002")
        
        route_events = [e for e in test_collector.events if e.event_type.value == "route_decision"]
        assert len(route_events) == 2
        
        # Verify different workers selected
        worker_1 = route_events[0].attributes["agent_selected"]
        worker_2 = route_events[1].attributes["agent_selected"]
        assert worker_1 != worker_2  # Round-robin should select different workers


class TestEndToEndObservability:
    """Test complete plan → route → execute flow with observability."""
    
    def test_full_flow_emits_all_events(self, test_collector, registry, memory, config):
        """Test that full agent flow emits plan, route, and tool events."""
        planner = PlannerAgent(registry=registry, memory=memory, config=config)
        worker = WorkerAgent(registry=registry, memory=memory)
        coordinator = CoordinatorAgent(planner=planner, workers=[worker], memory=memory)
        
        test_collector.reset_metrics()
        
        result = coordinator.dispatch("echo integration test", trace_id="test-e2e-001")
        
        # Verify result
        assert "integration test" in str(result.output)
        
        # Verify all event types emitted
        plan_events = [e for e in test_collector.events if e.event_type.value == "plan_created"]
        route_events = [e for e in test_collector.events if e.event_type.value == "route_decision"]
        start_events = [e for e in test_collector.events if e.event_type.value == "tool_call_start"]
        complete_events = [e for e in test_collector.events if e.event_type.value == "tool_call_complete"]
        
        assert len(plan_events) >= 1, "Should emit plan_created event"
        assert len(route_events) >= 1, "Should emit route_decision event"
        assert len(start_events) >= 1, "Should emit tool_call_start event"
        assert len(complete_events) >= 1, "Should emit tool_call_complete event"
        
        # Verify trace_id propagation
        for event in plan_events + route_events + start_events + complete_events:
            assert event.trace_id == "test-e2e-001"
    
    def test_golden_signals_updated(self, test_collector, registry, memory, config):
        """Test that golden signals are updated from agent operations."""
        planner = PlannerAgent(registry=registry, memory=memory, config=config)
        worker = WorkerAgent(registry=registry, memory=memory)
        coordinator = CoordinatorAgent(planner=planner, workers=[worker], memory=memory)
        
        test_collector.reset_metrics()
        
        # Execute multiple operations
        coordinator.dispatch("echo test1", trace_id="test-signals-001")
        coordinator.dispatch("echo test2", trace_id="test-signals-002")
        
        # Verify golden signals updated
        signals = test_collector.signals
        
        # Tool calls recorded
        assert signals.tool_calls.get() >= 2, "Should record at least 2 tool calls"
        
        # Mean steps per task should be calculated
        assert signals.mean_steps_per_task() > 0, "Should have non-zero mean steps"


@pytest.mark.skipif(not GUARDRAILS_AVAILABLE, reason="Guardrails not available")
class TestBudgetEnforcement:
    """Test budget enforcement with observability."""
    
    def test_budget_guard_blocks_over_budget_calls(self, test_collector, registry, memory):
        """Test that budget_guard blocks execution when budget exhausted."""
        # Create policy with very low budget
        policy = GuardrailPolicy(
            profile="test",
            tool_allowlist=["echo"],
            budget=ToolBudget(max_cost=0.05, max_calls=1, max_tokens=100),
            emit_events=False,  # Disable legacy event emission to avoid compatibility issues
        )
        
        worker = WorkerAgent(registry=registry, memory=memory, guardrail_policy=policy)
        test_collector.reset_metrics()
        
        # First call should succeed
        steps = [{"tool": "echo", "input": {"text": "first"}}]
        result = worker.execute(steps, metadata={"trace_id": "test-budget-001"})
        assert result.output == "first"
        
        # Second call should fail (budget exhausted)
        steps = [{"tool": "echo", "input": {"text": "second"}}]
        
        with pytest.raises(ValueError, match="Budget exhausted"):
            worker.execute(steps, metadata={"trace_id": "test-budget-002"})
        
        # Verify budget_exceeded event emitted
        budget_events = [e for e in test_collector.events if e.event_type.value == "budget_exceeded"]
        assert len(budget_events) == 1
        
        budget_event = budget_events[0]
        assert budget_event.trace_id == "test-budget-002"
        assert budget_event.attributes["profile"] == "test"


class TestMetricsEndpoint:
    """Test that agent events appear in /metrics endpoint."""
    
    def test_agent_events_in_prometheus_export(self, client, test_collector, registry, memory, config):
        """Test that agent-generated events appear in Prometheus metrics."""
        planner = PlannerAgent(registry=registry, memory=memory, config=config)
        worker = WorkerAgent(registry=registry, memory=memory)
        coordinator = CoordinatorAgent(planner=planner, workers=[worker], memory=memory)
        
        test_collector.reset_metrics()
        
        # Execute agent operations
        coordinator.dispatch("echo metrics test", trace_id="test-metrics-001")
        
        # Get metrics from endpoint
        response = client.get("/metrics", headers={"X-Token": "test-token-12345"})
        assert response.status_code == 200
        
        content = response.text
        
        # Verify metrics include tool calls
        assert "cuga_tool_calls_total" in content
        assert "cuga_steps_per_task" in content
        
        # Verify metrics have non-zero values (after agent operations)
        lines = content.split("\n")
        tool_calls_line = [l for l in lines if l.startswith("cuga_tool_calls_total")]
        if tool_calls_line:
            # Extract value and verify it's > 0
            value = tool_calls_line[0].split()[-1]
            assert float(value) > 0, "Tool calls should be recorded in metrics"

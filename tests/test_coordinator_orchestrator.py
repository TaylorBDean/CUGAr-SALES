"""
Test CoordinatorAgent as OrchestratorProtocol implementation.

Tests verify that CoordinatorAgent properly implements the canonical
OrchestratorProtocol interface with:
- Lifecycle stage emissions (INITIALIZE → PLAN → ROUTE → EXECUTE → COMPLETE)
- Routing decisions with justification
- Error handling with OrchestrationError
- Trace propagation through all stages
- Observability event emission

Version: 1.3.0+
"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from dataclasses import dataclass

from cuga.modular.agents import CoordinatorAgent, PlannerAgent, WorkerAgent, AgentResult
from cuga.modular.memory import VectorMemory
from cuga.modular.tools import ToolRegistry, ToolSpec
from cuga.modular.config import AgentConfig

from cuga.orchestrator.protocol import (
    OrchestratorProtocol,
    ExecutionContext,
    LifecycleStage,
    RoutingDecision,
    OrchestrationError,
    ErrorPropagation,
)


@pytest.fixture
def mock_memory():
    """Mock VectorMemory for testing."""
    memory = MagicMock(spec=VectorMemory)
    memory.config = AgentConfig(profile="test")
    return memory


@pytest.fixture
def mock_registry():
    """Mock ToolRegistry with echo tool."""
    def echo_handler(inputs, ctx):
        return inputs.get("text", "")
    
    echo_tool = ToolSpec(name="echo", description="Echo text", handler=echo_handler)
    return ToolRegistry(tools=[echo_tool])


@pytest.fixture
def mock_planner(mock_memory):
    """Mock PlannerAgent for testing."""
    planner = MagicMock(spec=PlannerAgent)
    planner.config = AgentConfig(profile="test")
    
    # Mock plan() to return a simple plan
    mock_plan = AgentResult(
        output="plan",
        trace=[{"event": "plan_created"}],
    )
    mock_plan.steps = [
        {"tool": "echo", "input": {"text": "hello"}},
    ]
    planner.plan.return_value = mock_plan
    
    # Mock startup/shutdown
    planner.startup = AsyncMock()
    planner.shutdown = AsyncMock()
    
    return planner


@pytest.fixture
def mock_worker(mock_registry):
    """Mock WorkerAgent for testing."""
    worker = MagicMock(spec=WorkerAgent)
    
    # Mock execute() to return a simple result
    worker.execute.return_value = AgentResult(
        output="hello",
        trace=[{"event": "tool_executed", "tool": "echo"}],
    )
    
    # Mock startup/shutdown
    worker.startup = AsyncMock()
    worker.shutdown = AsyncMock()
    
    return worker


@pytest.fixture
def coordinator(mock_planner, mock_worker, mock_memory):
    """Create CoordinatorAgent for testing."""
    return CoordinatorAgent(
        planner=mock_planner,
        workers=[mock_worker],
        memory=mock_memory,
    )


class TestCoordinatorOrchestratorProtocol:
    """Test CoordinatorAgent implements OrchestratorProtocol."""
    
    def test_implements_orchestrator_protocol(self, coordinator):
        """CoordinatorAgent implements OrchestratorProtocol."""
        assert isinstance(coordinator, OrchestratorProtocol)
    
    def test_has_orchestrate_method(self, coordinator):
        """CoordinatorAgent has orchestrate() async generator method."""
        assert hasattr(coordinator, "orchestrate")
        assert callable(coordinator.orchestrate)
    
    def test_has_make_routing_decision_method(self, coordinator):
        """CoordinatorAgent has make_routing_decision() method."""
        assert hasattr(coordinator, "make_routing_decision")
        assert callable(coordinator.make_routing_decision)
    
    def test_has_handle_error_method(self, coordinator):
        """CoordinatorAgent has handle_error() async method."""
        assert hasattr(coordinator, "handle_error")
        assert callable(coordinator.handle_error)
    
    def test_has_get_lifecycle_method(self, coordinator):
        """CoordinatorAgent has get_lifecycle() method."""
        assert hasattr(coordinator, "get_lifecycle")
        assert callable(coordinator.get_lifecycle)


class TestOrchestrateLifecycleStages:
    """Test orchestrate() method emits correct lifecycle stages."""
    
    @pytest.mark.asyncio
    async def test_lifecycle_stages_emitted_in_order(self, coordinator):
        """All lifecycle stages emitted in correct order."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        stages = []
        async for event in coordinator.orchestrate("test goal", context):
            stages.append(event["stage"])
        
        # Verify stages in order
        assert stages[0] == LifecycleStage.INITIALIZE
        assert stages[1] == LifecycleStage.PLAN
        assert stages[2] == LifecycleStage.ROUTE
        assert stages[3] == LifecycleStage.EXECUTE
        assert stages[4] == LifecycleStage.AGGREGATE
        assert stages[5] == LifecycleStage.COMPLETE
    
    @pytest.mark.asyncio
    async def test_initialize_stage_includes_goal(self, coordinator):
        """INITIALIZE stage includes goal and worker count."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        async for event in coordinator.orchestrate("test goal", context):
            if event["stage"] == LifecycleStage.INITIALIZE:
                assert event["data"]["goal"] == "test goal"
                assert event["data"]["workers_available"] == 1
                assert event["data"]["profile"] == "test"
                break
    
    @pytest.mark.asyncio
    async def test_plan_stage_includes_steps_count(self, coordinator):
        """PLAN stage includes plan and steps count."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        async for event in coordinator.orchestrate("test goal", context):
            if event["stage"] == LifecycleStage.PLAN:
                assert "plan" in event["data"]
                assert event["data"]["steps_count"] == 1
                assert "duration_ms" in event["data"]
                break
    
    @pytest.mark.asyncio
    async def test_route_stage_includes_decision(self, coordinator):
        """ROUTE stage includes routing decision."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        async for event in coordinator.orchestrate("test goal", context):
            if event["stage"] == LifecycleStage.ROUTE:
                assert "decision" in event["data"]
                decision = event["data"]["decision"]
                # After RoutingAuthority integration, decision is FullRoutingDecision
                from cuga.orchestrator.routing import RoutingDecision as FullRoutingDecision
                assert isinstance(decision, FullRoutingDecision)
                assert decision.selected.id == "worker-0"
                assert "duration_ms" in event["data"]
                break
    
    @pytest.mark.asyncio
    async def test_execute_stage_includes_result(self, coordinator):
        """EXECUTE stage includes worker result."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        async for event in coordinator.orchestrate("test goal", context):
            if event["stage"] == LifecycleStage.EXECUTE:
                assert "result" in event["data"]
                result = event["data"]["result"]
                assert result.output == "hello"
                assert "duration_ms" in event["data"]
                break
    
    @pytest.mark.asyncio
    async def test_aggregate_stage_includes_trace(self, coordinator):
        """AGGREGATE stage includes combined trace."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        async for event in coordinator.orchestrate("test goal", context):
            if event["stage"] == LifecycleStage.AGGREGATE:
                assert "trace_length" in event["data"]
                # After PlanningAuthority integration, authority_plan doesn't have trace
                # Only worker result has trace
                assert event["data"]["trace_length"] >= 1  # Execute traces
                assert event["data"]["output"] == "hello"
                break
    
    @pytest.mark.asyncio
    async def test_complete_stage_includes_metrics(self, coordinator):
        """COMPLETE stage includes all metrics."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        final_event = None
        async for event in coordinator.orchestrate("test goal", context):
            if event["stage"] == LifecycleStage.COMPLETE:
                final_event = event
        
        assert final_event is not None
        assert "output" in final_event["data"]
        assert "trace" in final_event["data"]
        assert "metrics" in final_event["data"]
        
        metrics = final_event["data"]["metrics"]
        assert "plan_duration_ms" in metrics
        assert "routing_duration_ms" in metrics
        assert "execute_duration_ms" in metrics
        assert "total_duration_ms" in metrics


class TestRoutingDecisions:
    """Test make_routing_decision() method."""
    
    def test_routing_decision_has_target(self, coordinator):
        """Routing decision includes target worker."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        decision = coordinator.make_routing_decision(
            task="test task",
            context=context,
            available_agents=["worker-0", "worker-1"],
        )
        
        assert decision.target in ["worker-0", "worker-1"]
    
    def test_routing_decision_has_reason(self, coordinator):
        """Routing decision includes reason."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        decision = coordinator.make_routing_decision(
            task="test task",
            context=context,
            available_agents=["worker-0"],
        )
        
        # After RoutingAuthority integration, reason is more descriptive
        assert "Round-robin" in decision.reason or "worker" in decision.reason
    
    def test_routing_decision_has_alternatives(self, coordinator):
        """Routing decision includes alternatives."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        decision = coordinator.make_routing_decision(
            task="test task",
            context=context,
            available_agents=["worker-0", "worker-1", "worker-2"],
        )
        
        assert "alternatives" in decision.metadata
        alternatives = decision.metadata["alternatives"]
        assert len(alternatives) == 2  # All except selected
        assert decision.target not in alternatives
    
    def test_routing_decision_has_fallback(self, coordinator):
        """Routing decision includes fallback field (may be None for some policies)."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        decision = coordinator.make_routing_decision(
            task="test task",
            context=context,
            available_agents=["worker-0", "worker-1"],
        )
        
        # After RoutingAuthority integration, fallback is policy-dependent
        # RoundRobinPolicy doesn't set fallback by default
        assert hasattr(decision, "fallback")  # Field exists
    
    def test_routing_decision_no_workers(self, coordinator):
        """Routing decision handles no workers gracefully."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        decision = coordinator.make_routing_decision(
            task="test task",
            context=context,
            available_agents=[],
        )
        
        assert decision.target == "none"
        assert decision.reason == "no_workers_available"


class TestErrorHandling:
    """Test handle_error() method."""
    
    @pytest.mark.asyncio
    async def test_fail_fast_strategy_raises_immediately(self, coordinator):
        """FAIL_FAST strategy re-raises error immediately."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        error = OrchestrationError(
            stage=LifecycleStage.EXECUTE,
            message="Test error",
            context=context,
            recoverable=False,
        )
        
        with pytest.raises(OrchestrationError) as exc_info:
            await coordinator.handle_error(error, ErrorPropagation.FAIL_FAST)
        
        assert exc_info.value == error
    
    @pytest.mark.asyncio
    async def test_continue_strategy_returns_recovery_result(self, coordinator):
        """CONTINUE strategy returns recovery result."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        error = OrchestrationError(
            stage=LifecycleStage.EXECUTE,
            message="Test error",
            context=context,
            recoverable=True,
        )
        
        result = await coordinator.handle_error(error, ErrorPropagation.CONTINUE)
        
        assert result is not None
        assert result["stage"] == LifecycleStage.FAILED
        assert "error" in result["data"]
        assert result["data"]["strategy"] == "continue"
    
    @pytest.mark.asyncio
    async def test_error_with_cause(self, coordinator):
        """OrchestrationError preserves original cause."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        original_error = ValueError("Original error")
        
        error = OrchestrationError(
            stage=LifecycleStage.EXECUTE,
            message="Wrapped error",
            context=context,
            cause=original_error,
            recoverable=False,
        )
        
        assert error.cause == original_error
        assert "ValueError" in str(error)


class TestContextPropagation:
    """Test ExecutionContext propagation through orchestration."""
    
    @pytest.mark.asyncio
    async def test_context_propagated_through_stages(self, coordinator):
        """ExecutionContext propagated through all stages."""
        context = ExecutionContext(
            trace_id="test-123",
            profile="test",
            user_intent="test goal",
        )
        
        async for event in coordinator.orchestrate("test goal", context):
            assert event["context"] == context
            assert event["context"].trace_id == "test-123"
            assert event["context"].profile == "test"
    
    @pytest.mark.asyncio
    async def test_trace_id_preserved(self, coordinator):
        """trace_id preserved across all stages."""
        context = ExecutionContext(trace_id="unique-trace-id", profile="test")
        
        trace_ids = []
        async for event in coordinator.orchestrate("test goal", context):
            trace_ids.append(event["context"].trace_id)
        
        # All trace_ids should be the same
        assert all(tid == "unique-trace-id" for tid in trace_ids)


class TestOrchestratorMetrics:
    """Test orchestrator metrics collection."""
    
    @pytest.mark.asyncio
    async def test_metrics_record_success(self, coordinator):
        """Metrics record successful orchestration."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        initial_success = coordinator._orchestrator_metrics.successful_steps
        
        async for event in coordinator.orchestrate("test goal", context):
            pass  # Consume all events
        
        # Success should be incremented
        assert coordinator._orchestrator_metrics.successful_steps > initial_success
    
    @pytest.mark.asyncio
    async def test_metrics_record_routing_decisions(self, coordinator):
        """Metrics record routing decisions made."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        initial_routing = coordinator._orchestrator_metrics.routing_decisions
        
        async for event in coordinator.orchestrate("test goal", context):
            pass  # Consume all events
        
        # Routing decisions should be incremented
        assert coordinator._orchestrator_metrics.routing_decisions > initial_routing
    
    def test_get_orchestrator_metrics(self, coordinator):
        """Can retrieve orchestrator metrics."""
        metrics = coordinator.get_orchestrator_metrics()
        
        assert hasattr(metrics, "successful_steps")
        assert hasattr(metrics, "failed_steps")
        assert hasattr(metrics, "routing_decisions")


class TestOrchestratorFailureScenarios:
    """Test orchestration failure scenarios."""
    
    @pytest.mark.asyncio
    async def test_no_workers_raises_error(self):
        """Orchestration fails with no workers configured."""
        # Create coordinator with no workers
        mock_planner = MagicMock()
        mock_planner.config = AgentConfig(profile="test")
        mock_planner.startup = AsyncMock()
        mock_planner.shutdown = AsyncMock()
        
        mock_plan = AgentResult(output="plan", trace=[])
        mock_plan.steps = [{"tool": "echo"}]
        mock_planner.plan.return_value = mock_plan
        
        mock_memory = MagicMock()
        mock_memory.config = AgentConfig(profile="test")
        
        coordinator = CoordinatorAgent(
            planner=mock_planner,
            workers=[],  # No workers
            memory=mock_memory,
        )
        
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        with pytest.raises(OrchestrationError) as exc_info:
            async for event in coordinator.orchestrate("test goal", context):
                pass
        
        assert exc_info.value.stage == LifecycleStage.ROUTE
        assert "No workers configured" in exc_info.value.message
    
    @pytest.mark.asyncio
    async def test_worker_failure_propagates(self, coordinator, mock_worker):
        """Worker failures propagate as OrchestrationError."""
        # Make worker raise exception
        mock_worker.execute.side_effect = RuntimeError("Worker failed")
        
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        with pytest.raises(OrchestrationError) as exc_info:
            async for event in coordinator.orchestrate("test goal", context):
                pass
        
        assert exc_info.value.stage == LifecycleStage.EXECUTE
        assert "Orchestration failed" in exc_info.value.message


class TestLifecycleManagerIntegration:
    """Test get_lifecycle() method and AgentLifecycle integration."""
    
    def test_get_lifecycle_returns_lifecycle_manager(self, coordinator):
        """get_lifecycle() returns AgentLifecycle-compatible object."""
        lifecycle = coordinator.get_lifecycle()
        
        assert hasattr(lifecycle, "initialize")
        assert hasattr(lifecycle, "teardown")
        assert hasattr(lifecycle, "get_stage")
    
    @pytest.mark.asyncio
    async def test_lifecycle_initialize_calls_startup(self, coordinator):
        """Lifecycle initialize() calls coordinator.startup()."""
        lifecycle = coordinator.get_lifecycle()
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        await lifecycle.initialize(context)
        
        # Verify coordinator is in READY state
        assert coordinator.get_state().value in ["ready", "initializing"]
    
    def test_lifecycle_get_stage_maps_state(self, coordinator):
        """Lifecycle get_stage() maps AgentState to LifecycleStage."""
        lifecycle = coordinator.get_lifecycle()
        
        stage = lifecycle.get_stage()
        
        # Should return a LifecycleStage
        assert isinstance(stage, LifecycleStage)

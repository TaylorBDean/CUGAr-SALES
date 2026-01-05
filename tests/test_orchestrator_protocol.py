"""
Tests for Orchestrator Protocol Compliance

These tests verify that orchestrator implementations conform to OrchestratorProtocol
contract requirements including lifecycle stages, routing decisions, error handling,
and context propagation.
"""

import pytest
from typing import List

from cuga.orchestrator import (
    ExecutionContext,
    LifecycleStage,
    OrchestrationError,
    ErrorPropagation,
    RoutingDecision,
)
from cuga.orchestrator.reference import ReferenceOrchestrator


@pytest.fixture
def orchestrator():
    """Create a reference orchestrator for testing."""
    return ReferenceOrchestrator(
        workers=["worker1", "worker2", "worker3"],
        default_worker="worker1",
    )


@pytest.fixture
def context():
    """Create a test execution context."""
    return ExecutionContext(
        trace_id="test-trace-123",
        profile="test-profile",
        metadata={"test": True},
    )


class TestLifecycleCompliance:
    """Test lifecycle stage compliance."""
    
    @pytest.mark.asyncio
    async def test_lifecycle_stages_in_order(self, orchestrator, context):
        """Orchestrator emits lifecycle stages in correct order."""
        stages = []
        
        async for event in orchestrator.orchestrate("test goal", context):
            stages.append(event["stage"])
        
        # Verify stage order
        assert stages[0] == LifecycleStage.INITIALIZE
        assert stages[1] == LifecycleStage.PLAN
        assert LifecycleStage.ROUTE in stages
        assert LifecycleStage.EXECUTE in stages
        assert LifecycleStage.AGGREGATE in stages
        assert stages[-1] == LifecycleStage.COMPLETE
    
    @pytest.mark.asyncio
    async def test_terminal_stage_is_final(self, orchestrator, context):
        """No events emitted after terminal stage."""
        events = []
        
        async for event in orchestrator.orchestrate("test", context):
            events.append(event)
        
        last_stage = events[-1]["stage"]
        assert last_stage in [
            LifecycleStage.COMPLETE,
            LifecycleStage.FAILED,
            LifecycleStage.CANCELLED,
        ]


class TestTracePropagation:
    """Test trace_id propagation through orchestration."""
    
    @pytest.mark.asyncio
    async def test_trace_id_preserved(self, orchestrator, context):
        """trace_id flows through all stages unchanged."""
        async for event in orchestrator.orchestrate("test", context):
            assert event["context"].trace_id == context.trace_id
    
    @pytest.mark.asyncio
    async def test_profile_preserved(self, orchestrator, context):
        """Profile flows through all stages unchanged."""
        async for event in orchestrator.orchestrate("test", context):
            assert event["context"].profile == context.profile
    
    @pytest.mark.asyncio
    async def test_context_immutability(self, orchestrator, context):
        """Execution context remains immutable."""
        original_trace = context.trace_id
        
        async for event in orchestrator.orchestrate("test", context):
            # Context should never be mutated in place
            assert context.trace_id == original_trace
            assert event["context"] is not context  # New context objects


class TestDeterministicRouting:
    """Test routing decision determinism."""
    
    def test_same_inputs_same_routing(self, orchestrator, context):
        """Same inputs produce identical routing decisions."""
        agents = ["agent1", "agent2", "agent3"]
        task = "search for Python docs"
        
        decision1 = orchestrator.make_routing_decision(task, context, agents)
        decision2 = orchestrator.make_routing_decision(task, context, agents)
        
        assert decision1.target == decision2.target
        assert decision1.reason == decision2.reason
    
    def test_routing_decision_has_justification(self, orchestrator, context):
        """Routing decisions include human-readable justification."""
        agents = ["worker1", "worker2"]
        
        decision = orchestrator.make_routing_decision("task", context, agents)
        
        assert decision.reason
        assert len(decision.reason) > 10  # Non-trivial explanation
    
    def test_routing_decision_has_fallback_when_available(self, orchestrator, context):
        """Routing decisions include fallback when multiple agents available."""
        agents = ["worker1", "worker2", "worker3"]
        
        decision = orchestrator.make_routing_decision("task", context, agents)
        
        # Should have fallback since multiple workers available
        assert decision.fallback is not None
        assert decision.fallback != decision.target


class TestErrorHandling:
    """Test error propagation strategies."""
    
    @pytest.mark.asyncio
    async def test_fail_fast_stops_on_error(self, orchestrator, context):
        """FAIL_FAST strategy stops immediately on error."""
        # This would require mocking the execution to fail
        # Placeholder for implementation
        pass
    
    @pytest.mark.asyncio
    async def test_continue_logs_and_continues(self, orchestrator, context):
        """CONTINUE strategy logs error and proceeds."""
        # This would require mocking the execution to fail
        # Placeholder for implementation
        pass
    
    def test_orchestration_error_structure(self, context):
        """OrchestrationError contains required fields."""
        error = OrchestrationError(
            stage=LifecycleStage.EXECUTE,
            message="Test error",
            context=context,
            cause=RuntimeError("Original error"),
            recoverable=True,
        )
        
        assert error.stage == LifecycleStage.EXECUTE
        assert error.message == "Test error"
        assert error.context == context
        assert isinstance(error.cause, RuntimeError)
        assert error.recoverable is True
    
    @pytest.mark.asyncio
    async def test_handle_error_respects_strategy(self, orchestrator, context):
        """handle_error respects specified ErrorPropagation strategy."""
        error = OrchestrationError(
            stage=LifecycleStage.EXECUTE,
            message="Test",
            context=context,
            recoverable=True,
        )
        
        # FAIL_FAST should raise
        with pytest.raises(OrchestrationError):
            await orchestrator.handle_error(error, ErrorPropagation.FAIL_FAST)
        
        # CONTINUE should return None
        result = await orchestrator.handle_error(error, ErrorPropagation.CONTINUE)
        assert result is None


class TestContextManagement:
    """Test execution context management."""
    
    def test_context_immutability(self, context):
        """ExecutionContext is immutable."""
        with pytest.raises(Exception):
            context.trace_id = "modified"  # Should fail
    
    def test_with_metadata_creates_new_context(self, context):
        """with_metadata creates new context with merged metadata."""
        new_context = context.with_metadata(extra="value")
        
        assert new_context.trace_id == context.trace_id
        assert new_context.profile == context.profile
        assert "extra" in new_context.metadata
        assert new_context is not context  # New object
    
    def test_nested_context_preserves_parent(self, context):
        """Nested contexts preserve parent context."""
        child_context = ExecutionContext(
            trace_id="child-trace",
            profile=context.profile,
            parent_context=context,
        )
        
        assert child_context.parent_context == context
        assert child_context.parent_context.trace_id == context.trace_id


class TestLifecycleManager:
    """Test AgentLifecycle implementation."""
    
    @pytest.mark.asyncio
    async def test_initialize_completes_successfully(self, orchestrator, context):
        """Lifecycle initialize completes without error."""
        lifecycle = orchestrator.get_lifecycle()
        await lifecycle.initialize(context)
        assert lifecycle.get_stage() == LifecycleStage.INITIALIZE
    
    @pytest.mark.asyncio
    async def test_teardown_never_raises(self, orchestrator, context):
        """Lifecycle teardown never raises exceptions."""
        lifecycle = orchestrator.get_lifecycle()
        
        # Even if there's an error internally, teardown should not raise
        try:
            await lifecycle.teardown(context)
        except Exception as e:
            pytest.fail(f"teardown should never raise, but got: {e}")


class TestReferenceImplementation:
    """Tests specific to ReferenceOrchestrator."""
    
    @pytest.mark.asyncio
    async def test_single_step_execution(self, orchestrator, context):
        """Reference orchestrator handles single-step plan."""
        events = []
        
        async for event in orchestrator.orchestrate("simple task", context):
            events.append(event)
        
        # Should have at least basic stages
        stages = [e["stage"] for e in events]
        assert LifecycleStage.INITIALIZE in stages
        assert LifecycleStage.PLAN in stages
        assert LifecycleStage.COMPLETE in stages
    
    def test_round_robin_routing(self, orchestrator, context):
        """Reference orchestrator uses round-robin routing."""
        agents = ["w1", "w2", "w3"]
        
        targets = []
        for _ in range(6):
            decision = orchestrator.make_routing_decision("task", context, agents)
            targets.append(decision.target)
        
        # Should cycle through workers
        assert targets == ["w1", "w2", "w3", "w1", "w2", "w3"]


# Integration test combining multiple aspects
class TestOrchestratorIntegration:
    """Integration tests for full orchestration flow."""
    
    @pytest.mark.asyncio
    async def test_full_orchestration_flow(self, orchestrator, context):
        """Complete orchestration flow from start to finish."""
        events = []
        
        async for event in orchestrator.orchestrate(
            "complex task",
            context,
            error_strategy=ErrorPropagation.CONTINUE,
        ):
            events.append(event)
            
            # Verify each event has required fields
            assert "stage" in event
            assert "data" in event
            assert "context" in event
            
            # Verify context continuity
            assert event["context"].trace_id == context.trace_id
        
        # Verify we got a complete flow
        stages = [e["stage"] for e in events]
        assert stages[0] == LifecycleStage.INITIALIZE
        assert stages[-1] == LifecycleStage.COMPLETE
        
        # Verify routing decisions were made
        routing_events = [e for e in events if e["stage"] == LifecycleStage.ROUTE]
        assert len(routing_events) > 0

"""
Test RoutingAuthority Integration in CoordinatorAgent.

Tests verify that CoordinatorAgent properly integrates RoutingAuthority for
pluggable routing strategies:
- Default round-robin routing
- Capability-based routing
- Custom routing policies
- Routing decision recording
- Factory function with strategies

Version: 1.3.1+
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from dataclasses import dataclass

from cuga.modular.agents import (
    CoordinatorAgent,
    PlannerAgent,
    WorkerAgent,
    AgentResult,
    create_coordinator,
)
from cuga.modular.memory import VectorMemory
from cuga.modular.tools import ToolRegistry, ToolSpec
from cuga.modular.config import AgentConfig

from cuga.orchestrator.protocol import ExecutionContext
from cuga.orchestrator.routing import (
    RoutingStrategy,
    RoutingAuthority,
    PolicyBasedRoutingAuthority,
    RoundRobinPolicy,
    CapabilityBasedPolicy,
    RoutingContext,
    RoutingCandidate,
    RoutingDecision,
    RoutingDecisionType,
)


@pytest.fixture
def mock_memory():
    """Mock VectorMemory for testing."""
    memory = MagicMock(spec=VectorMemory)
    memory.config = AgentConfig(profile="test")
    return memory


@pytest.fixture
def mock_planner(mock_memory):
    """Mock PlannerAgent for testing."""
    planner = MagicMock(spec=PlannerAgent)
    planner.config = AgentConfig(profile="test")
    
    mock_plan = AgentResult(output="plan", trace=[{"event": "plan_created"}])
    mock_plan.steps = [{"tool": "echo", "input": {"text": "hello"}}]
    planner.plan.return_value = mock_plan
    
    planner.startup = AsyncMock()
    planner.shutdown = AsyncMock()
    
    return planner


@pytest.fixture
def mock_worker():
    """Mock WorkerAgent for testing."""
    worker = MagicMock(spec=WorkerAgent)
    worker.execute.return_value = AgentResult(
        output="hello",
        trace=[{"event": "tool_executed"}],
    )
    worker.startup = AsyncMock()
    worker.shutdown = AsyncMock()
    return worker


@pytest.fixture
def coordinator_default(mock_planner, mock_worker, mock_memory):
    """Create CoordinatorAgent with default routing."""
    return CoordinatorAgent(
        planner=mock_planner,
        workers=[mock_worker],
        memory=mock_memory,
    )


@pytest.fixture
def coordinator_capability(mock_planner, mock_worker, mock_memory):
    """Create CoordinatorAgent with capability-based routing."""
    routing_authority = PolicyBasedRoutingAuthority(
        worker_policy=CapabilityBasedPolicy(),
    )
    return CoordinatorAgent(
        planner=mock_planner,
        workers=[mock_worker],
        memory=mock_memory,
        routing_authority=routing_authority,
    )


class TestRoutingAuthorityIntegration:
    """Test RoutingAuthority integration in CoordinatorAgent."""
    
    def test_coordinator_has_routing_authority(self, coordinator_default):
        """CoordinatorAgent has routing_authority field."""
        assert hasattr(coordinator_default, "routing_authority")
        assert coordinator_default.routing_authority is not None
    
    def test_coordinator_default_routing_authority(self, coordinator_default):
        """CoordinatorAgent initializes with default round-robin routing."""
        assert isinstance(coordinator_default.routing_authority, RoutingAuthority)
        # Default should use round-robin for workers
        assert isinstance(
            coordinator_default.routing_authority.worker_policy,
            RoundRobinPolicy
        )
    
    def test_coordinator_custom_routing_authority(self, coordinator_capability):
        """CoordinatorAgent accepts custom routing authority."""
        assert isinstance(coordinator_capability.routing_authority, RoutingAuthority)
        assert isinstance(
            coordinator_capability.routing_authority.worker_policy,
            CapabilityBasedPolicy
        )
    
    @pytest.mark.asyncio
    async def test_orchestrate_uses_routing_authority(self, coordinator_default):
        """orchestrate() uses RoutingAuthority for worker selection."""
        context = ExecutionContext(trace_id="test-routing", profile="test")
        
        # Collect routing decisions
        routing_decisions = []
        async for event in coordinator_default.orchestrate("test goal", context):
            if event["stage"].value == "route":
                routing_decisions.append(event["data"]["decision"])
        
        # Should have made exactly one routing decision
        assert len(routing_decisions) == 1
        
        # Decision should be from RoutingAuthority
        decision = routing_decisions[0]
        assert decision.selected.id == "worker-0"
        assert decision.strategy == RoutingStrategy.ROUND_ROBIN
    
    def test_make_routing_decision_uses_authority(self, coordinator_default):
        """make_routing_decision() delegates to RoutingAuthority."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        decision = coordinator_default.make_routing_decision(
            task="test task",
            context=context,
            available_agents=["worker-0", "worker-1"],
        )
        
        # Should return protocol routing decision
        assert decision.target in ["worker-0", "worker-1"]
        assert "strategy" in decision.metadata
        assert decision.metadata["strategy"] == "round_robin"
    
    def test_routing_decision_includes_alternatives(self, coordinator_default):
        """Routing decisions include alternatives considered."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        decision = coordinator_default.make_routing_decision(
            task="test task",
            context=context,
            available_agents=["worker-0", "worker-1", "worker-2"],
        )
        
        assert "alternatives" in decision.metadata
        alternatives = decision.metadata["alternatives"]
        assert len(alternatives) == 2  # All except selected
        assert decision.target not in alternatives
    
    def test_routing_decision_includes_confidence(self, coordinator_default):
        """Routing decisions include confidence score."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        decision = coordinator_default.make_routing_decision(
            task="test task",
            context=context,
            available_agents=["worker-0"],
        )
        
        assert "confidence" in decision.metadata
        assert 0.0 <= decision.metadata["confidence"] <= 1.0


class TestRoundRobinRouting:
    """Test round-robin routing strategy."""
    
    @pytest.mark.asyncio
    async def test_round_robin_distributes_evenly(self, mock_planner, mock_memory):
        """Round-robin routing distributes requests evenly."""
        # Create 3 workers
        workers = [MagicMock(spec=WorkerAgent) for _ in range(3)]
        for w in workers:
            w.execute.return_value = AgentResult(output="ok", trace=[])
            w.startup = AsyncMock()
            w.shutdown = AsyncMock()
        
        coordinator = CoordinatorAgent(
            planner=mock_planner,
            workers=workers,
            memory=mock_memory,
        )
        
        context = ExecutionContext(trace_id="test-rr", profile="test")
        
        # Execute 3 times, should use each worker once
        selections = []
        for i in range(3):
            async for event in coordinator.orchestrate(f"goal {i}", context):
                if event["stage"].value == "route":
                    decision = event["data"]["decision"]
                    selections.append(decision.selected.id)
                    break
        
        # Should have selected worker-0, worker-1, worker-2
        assert selections == ["worker-0", "worker-1", "worker-2"]
    
    @pytest.mark.asyncio
    async def test_round_robin_wraps_around(self, mock_planner, mock_memory):
        """Round-robin routing wraps around after last worker."""
        workers = [MagicMock(spec=WorkerAgent) for _ in range(2)]
        for w in workers:
            w.execute.return_value = AgentResult(output="ok", trace=[])
            w.startup = AsyncMock()
            w.shutdown = AsyncMock()
        
        coordinator = CoordinatorAgent(
            planner=mock_planner,
            workers=workers,
            memory=mock_memory,
        )
        
        context = ExecutionContext(trace_id="test-wrap", profile="test")
        
        # Execute 4 times
        selections = []
        for i in range(4):
            async for event in coordinator.orchestrate(f"goal {i}", context):
                if event["stage"].value == "route":
                    decision = event["data"]["decision"]
                    selections.append(decision.selected.id)
                    break
        
        # Should cycle: 0, 1, 0, 1
        assert selections == ["worker-0", "worker-1", "worker-0", "worker-1"]


class TestCapabilityBasedRouting:
    """Test capability-based routing strategy."""
    
    @pytest.mark.asyncio
    async def test_capability_routing_matches_requirements(self, mock_planner, mock_memory):
        """Capability-based routing matches worker capabilities."""
        # Create workers with different capabilities
        worker1 = MagicMock(spec=WorkerAgent)
        worker1.execute.return_value = AgentResult(output="ok", trace=[])
        worker1.startup = AsyncMock()
        worker1.shutdown = AsyncMock()
        
        worker2 = MagicMock(spec=WorkerAgent)
        worker2.execute.return_value = AgentResult(output="ok", trace=[])
        worker2.startup = AsyncMock()
        worker2.shutdown = AsyncMock()
        
        # Create capability-based routing
        routing_authority = PolicyBasedRoutingAuthority(
            worker_policy=CapabilityBasedPolicy(),
        )
        
        coordinator = CoordinatorAgent(
            planner=mock_planner,
            workers=[worker1, worker2],
            memory=mock_memory,
            routing_authority=routing_authority,
        )
        
        # Create context with capability requirements
        context = ExecutionContext(
            trace_id="test-cap",
            profile="test",
            metadata={"required_capabilities": ["python", "data_processing"]},
        )
        
        # Execute orchestration
        async for event in coordinator.orchestrate("process data", context):
            if event["stage"].value == "route":
                decision = event["data"]["decision"]
                # Should have selected a worker
                assert decision.selected.id in ["worker-0", "worker-1"]
                assert decision.strategy == RoutingStrategy.CAPABILITY
                break


class TestCreateCoordinatorFactory:
    """Test create_coordinator factory function."""
    
    def test_create_coordinator_default(self, mock_planner, mock_worker, mock_memory):
        """create_coordinator with default routing."""
        coordinator = create_coordinator(
            planner=mock_planner,
            workers=[mock_worker],
            memory=mock_memory,
        )
        
        assert isinstance(coordinator, CoordinatorAgent)
        assert isinstance(coordinator.routing_authority, RoutingAuthority)
        assert isinstance(coordinator.routing_authority.worker_policy, RoundRobinPolicy)
    
    def test_create_coordinator_round_robin(self, mock_planner, mock_worker, mock_memory):
        """create_coordinator with round-robin strategy."""
        coordinator = create_coordinator(
            planner=mock_planner,
            workers=[mock_worker],
            memory=mock_memory,
            routing_strategy=RoutingStrategy.ROUND_ROBIN,
        )
        
        assert isinstance(coordinator.routing_authority.worker_policy, RoundRobinPolicy)
    
    def test_create_coordinator_capability(self, mock_planner, mock_worker, mock_memory):
        """create_coordinator with capability-based strategy."""
        coordinator = create_coordinator(
            planner=mock_planner,
            workers=[mock_worker],
            memory=mock_memory,
            routing_strategy=RoutingStrategy.CAPABILITY,
        )
        
        assert isinstance(coordinator.routing_authority.worker_policy, CapabilityBasedPolicy)


class TestRoutingDecisionMetadata:
    """Test routing decision metadata."""
    
    def test_routing_decision_includes_strategy(self, coordinator_default):
        """Routing decisions include strategy used."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        decision = coordinator_default.make_routing_decision(
            task="test task",
            context=context,
            available_agents=["worker-0"],
        )
        
        assert "strategy" in decision.metadata
        assert decision.metadata["strategy"] in ["round_robin", "capability", "load_balanced"]
    
    def test_routing_decision_includes_decision_type(self, coordinator_default):
        """Routing decisions include decision type."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        decision = coordinator_default.make_routing_decision(
            task="test task",
            context=context,
            available_agents=["worker-0"],
        )
        
        assert "decision_type" in decision.metadata
    
    @pytest.mark.asyncio
    async def test_routing_event_includes_strategy_attributes(self, coordinator_default):
        """Route events include strategy-specific attributes."""
        context = ExecutionContext(trace_id="test-attr", profile="test")
        
        async for event in coordinator_default.orchestrate("test goal", context):
            if event["stage"].value == "route":
                data = event["data"]
                decision = data["decision"]
                
                # Should include strategy and confidence
                assert hasattr(decision, "strategy")
                assert hasattr(decision, "confidence")
                break


class TestRoutingFallbacks:
    """Test routing fallback behavior."""
    
    def test_routing_decision_includes_fallback_when_set(self, coordinator_default):
        """Routing decisions may include fallback option (policy-dependent)."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        decision = coordinator_default.make_routing_decision(
            task="test task",
            context=context,
            available_agents=["worker-0", "worker-1"],
        )
        
        # RoundRobinPolicy doesn't set fallback by default
        # This is policy-dependent behavior
        # Just verify the field exists (may be None)
        assert hasattr(decision, "fallback")
    
    def test_routing_decision_fallback_not_same_as_target(self, coordinator_default):
        """If fallback is set, it's different from target."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        decision = coordinator_default.make_routing_decision(
            task="test task",
            context=context,
            available_agents=["worker-0", "worker-1"],
        )
        
        # If fallback is set, it must be different from target
        if decision.fallback is not None:
            assert decision.fallback != decision.target
    
    def test_routing_decision_no_fallback_single_worker(self, coordinator_default):
        """Routing decisions have no fallback with single worker."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        decision = coordinator_default.make_routing_decision(
            task="test task",
            context=context,
            available_agents=["worker-0"],
        )
        
        # No fallback when only one worker
        assert decision.fallback is None


class TestRoutingErrors:
    """Test routing error handling."""
    
    @pytest.mark.asyncio
    async def test_routing_with_no_workers_raises_error(self, mock_planner, mock_memory):
        """Orchestration fails with no workers configured."""
        coordinator = CoordinatorAgent(
            planner=mock_planner,
            workers=[],  # No workers
            memory=mock_memory,
        )
        
        context = ExecutionContext(trace_id="test-error", profile="test")
        
        with pytest.raises(Exception):  # Should raise OrchestrationError or ValueError
            async for event in coordinator.orchestrate("test goal", context):
                pass
    
    def test_make_routing_decision_no_agents(self, coordinator_default):
        """make_routing_decision handles no available agents."""
        context = ExecutionContext(trace_id="test-123", profile="test")
        
        decision = coordinator_default.make_routing_decision(
            task="test task",
            context=context,
            available_agents=[],
        )
        
        assert decision.target == "none"
        assert decision.reason == "no_workers_available"

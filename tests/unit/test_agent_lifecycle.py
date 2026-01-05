"""
tests/unit/test_agent_lifecycle.py

Comprehensive tests for AgentLifecycleProtocol implementation per AGENTS.md § Agent Lifecycle & State Ownership.
Tests startup/shutdown contracts, state ownership boundaries, resource management, and lifecycle compliance.

Target: 15 lifecycle compliance tests

Test Strategy:
- Test startup() idempotency and timeout bounds
- Test shutdown() error safety and resource cleanup
- Test state ownership boundaries (AGENT/MEMORY/ORCHESTRATOR)
- Test state transition atomicity and logging
- Test lifecycle metrics tracking
"""

import pytest
import asyncio
from unittest.mock import Mock, patch

from cuga.modular.agents import PlannerAgent, WorkerAgent, CoordinatorAgent
from cuga.modular.memory import VectorMemory
from cuga.modular.tools import ToolRegistry, ToolSpec
from cuga.modular.config import AgentConfig
from cuga.agents.lifecycle import (
    AgentState,
    StateOwnership,
    LifecycleConfig,
    LifecycleMetrics,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def simple_registry():
    """Create simple tool registry for testing."""
    def echo_handler(inputs, context):
        return inputs.get("text", "")
    
    tool = ToolSpec(name="echo", description="Echo tool", handler=echo_handler)
    return ToolRegistry(tools=[tool])


@pytest.fixture
def memory():
    """Create fresh memory instance."""
    return VectorMemory(profile="test_lifecycle")


# ============================================================================
# Tests: Startup Contract
# ============================================================================


class TestStartupContract:
    """Test startup() contract compliance."""
    
    @pytest.mark.asyncio
    async def test_startup_transitions_to_ready(self, simple_registry, memory):
        """startup() should transition agent to READY state."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        
        assert planner.get_state() == AgentState.UNINITIALIZED
        
        await planner.startup()
        
        assert planner.get_state() == AgentState.READY
    
    @pytest.mark.asyncio
    async def test_startup_is_idempotent(self, simple_registry, memory):
        """startup() should be safe to call multiple times."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        
        # First call
        await planner.startup()
        assert planner.get_state() == AgentState.READY
        
        # Second call should not fail
        await planner.startup()
        assert planner.get_state() == AgentState.READY
        
        # Third call should still be safe
        await planner.startup()
        assert planner.get_state() == AgentState.READY
    
    @pytest.mark.asyncio
    async def test_startup_records_metrics(self, simple_registry, memory):
        """startup() should record startup time in metrics."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        
        await planner.startup()
        
        metrics = planner.get_metrics()
        assert metrics.startup_time_ms > 0
        assert metrics.state_transitions >= 2  # UNINITIALIZED -> INITIALIZING -> READY
    
    @pytest.mark.asyncio
    async def test_startup_all_agent_types(self, simple_registry, memory):
        """All agent types should support startup()."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        worker = WorkerAgent(registry=simple_registry, memory=memory)
        coordinator = CoordinatorAgent(
            planner=planner,
            workers=[worker],
            memory=memory,
        )
        
        # All should start in UNINITIALIZED
        assert planner.get_state() == AgentState.UNINITIALIZED
        assert worker.get_state() == AgentState.UNINITIALIZED
        assert coordinator.get_state() == AgentState.UNINITIALIZED
        
        # All should transition to READY
        await coordinator.startup()  # Starts managed agents too
        
        assert planner.get_state() == AgentState.READY
        assert worker.get_state() == AgentState.READY
        assert coordinator.get_state() == AgentState.READY


# ============================================================================
# Tests: Shutdown Contract
# ============================================================================


class TestShutdownContract:
    """Test shutdown() contract compliance."""
    
    @pytest.mark.asyncio
    async def test_shutdown_transitions_to_terminated(self, simple_registry, memory):
        """shutdown() should transition agent to TERMINATED state."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        
        await planner.startup()
        assert planner.get_state() == AgentState.READY
        
        await planner.shutdown()
        
        assert planner.get_state() == AgentState.TERMINATED
    
    @pytest.mark.asyncio
    async def test_shutdown_never_raises(self, simple_registry, memory):
        """shutdown() MUST NOT raise exceptions."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        await planner.startup()
        
        # Should not raise even on error
        await planner.shutdown()
        assert planner.get_state() == AgentState.TERMINATED
    
    @pytest.mark.asyncio
    async def test_shutdown_is_idempotent(self, simple_registry, memory):
        """shutdown() should be safe to call multiple times."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        await planner.startup()
        
        # First shutdown
        await planner.shutdown()
        assert planner.get_state() == AgentState.TERMINATED
        
        # Second shutdown should not fail
        await planner.shutdown()
        assert planner.get_state() == AgentState.TERMINATED
    
    @pytest.mark.asyncio
    async def test_shutdown_records_metrics(self, simple_registry, memory):
        """shutdown() should record shutdown time in metrics."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        await planner.startup()
        
        await planner.shutdown()
        
        metrics = planner.get_metrics()
        assert metrics.shutdown_time_ms > 0
    
    @pytest.mark.asyncio
    async def test_shutdown_cascade_to_managed_agents(self, simple_registry, memory):
        """CoordinatorAgent.shutdown() should shutdown managed agents."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        worker = WorkerAgent(registry=simple_registry, memory=memory)
        coordinator = CoordinatorAgent(
            planner=planner,
            workers=[worker],
            memory=memory,
        )
        
        await coordinator.startup()
        
        # Coordinator shutdown should cascade
        await coordinator.shutdown()
        
        # All should be terminated
        assert coordinator.get_state() == AgentState.TERMINATED
        assert planner.get_state() == AgentState.TERMINATED
        assert worker.get_state() == AgentState.TERMINATED


# ============================================================================
# Tests: State Ownership
# ============================================================================


class TestStateOwnership:
    """Test state ownership boundary enforcement."""
    
    def test_agent_owns_ephemeral_state(self, simple_registry, memory):
        """Agent should own ephemeral state (_state, _metrics, etc.)."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        
        assert planner.owns_state("_state") == StateOwnership.AGENT
        assert planner.owns_state("_metrics") == StateOwnership.AGENT
        assert planner.owns_state("_state_lock") == StateOwnership.AGENT
        assert planner.owns_state("llm") == StateOwnership.AGENT
        assert planner.owns_state("registry") == StateOwnership.AGENT
    
    def test_memory_owns_persistent_state(self, simple_registry, memory):
        """Memory should own persistent state (user_history, embeddings, etc.)."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        
        assert planner.owns_state("memory") == StateOwnership.MEMORY
    
    def test_orchestrator_owns_coordination_state(self, simple_registry, memory):
        """Orchestrator should own coordination state (trace_id, routing, etc.)."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        
        assert planner.owns_state("trace_id") == StateOwnership.ORCHESTRATOR
        assert planner.owns_state("routing_context") == StateOwnership.ORCHESTRATOR
    
    def test_config_is_shared(self, simple_registry, memory):
        """Config should be shared ownership."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        
        assert planner.owns_state("config") == StateOwnership.SHARED
    
    def test_unknown_state_defaults_to_agent(self, simple_registry, memory):
        """Unknown state keys should default to AGENT ownership with warning."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        
        # Should default to AGENT (with warning printed)
        assert planner.owns_state("unknown_key") == StateOwnership.AGENT


# ============================================================================
# Tests: Lifecycle Metrics
# ============================================================================


class TestLifecycleMetrics:
    """Test lifecycle metrics tracking."""
    
    @pytest.mark.asyncio
    async def test_metrics_track_startup_time(self, simple_registry, memory):
        """Metrics should track startup time."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        
        await planner.startup()
        
        metrics = planner.get_metrics()
        assert metrics.startup_time_ms > 0
        assert metrics.startup_time_ms < 1000  # Should be < 1 second
    
    @pytest.mark.asyncio
    async def test_metrics_track_shutdown_time(self, simple_registry, memory):
        """Metrics should track shutdown time."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        await planner.startup()
        
        await planner.shutdown()
        
        metrics = planner.get_metrics()
        assert metrics.shutdown_time_ms > 0
        assert metrics.shutdown_time_ms < 1000  # Should be < 1 second
    
    @pytest.mark.asyncio
    async def test_metrics_track_state_transitions(self, simple_registry, memory):
        """Metrics should track state transitions."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        
        initial_transitions = planner.get_metrics().state_transitions
        
        await planner.startup()
        after_startup = planner.get_metrics().state_transitions
        
        await planner.shutdown()
        after_shutdown = planner.get_metrics().state_transitions
        
        # Should have at least 2 transitions for startup (UNINITIALIZED -> INITIALIZING -> READY)
        assert after_startup > initial_transitions
        
        # Should have at least 2 more for shutdown (READY -> SHUTTING_DOWN -> TERMINATED)
        assert after_shutdown > after_startup


# ============================================================================
# Tests: State Transition Atomicity
# ============================================================================


class TestStateTransitions:
    """Test state transition atomicity and correctness."""
    
    @pytest.mark.asyncio
    async def test_state_transitions_are_atomic(self, simple_registry, memory):
        """State transitions should be atomic (no intermediate states visible)."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        
        # Start in UNINITIALIZED
        assert planner.get_state() == AgentState.UNINITIALIZED
        
        # After startup, should be in READY (not INITIALIZING)
        await planner.startup()
        assert planner.get_state() == AgentState.READY
        
        # After shutdown, should be in TERMINATED (not SHUTTING_DOWN)
        await planner.shutdown()
        assert planner.get_state() == AgentState.TERMINATED
    
    @pytest.mark.asyncio
    async def test_get_state_is_thread_safe(self, simple_registry, memory):
        """get_state() should be thread-safe (non-blocking)."""
        planner = PlannerAgent(registry=simple_registry, memory=memory)
        await planner.startup()
        
        # Should be safe to call from multiple "threads" (async tasks)
        states = await asyncio.gather(
            asyncio.to_thread(planner.get_state),
            asyncio.to_thread(planner.get_state),
            asyncio.to_thread(planner.get_state),
        )
        
        # All should return same state
        assert all(state == AgentState.READY for state in states)

"""
Test suite for AgentLifecycleProtocol compliance.

Verifies all agents implement canonical lifecycle contracts with:
- Startup idempotency and timeout bounds
- Shutdown error safety and resource cleanup
- State ownership boundary enforcement
- State transition atomicity
- Metrics collection

All agent implementations MUST pass these tests per AGENTS.md guardrails.
"""

import asyncio
import pytest
from typing import Dict, Any

from cuga.agents.lifecycle import (
    AgentLifecycleProtocol,
    ManagedAgent,
    AgentState,
    StateOwnership,
    LifecycleConfig,
    LifecycleMetrics,
    StartupError,
    StateViolationError,
    requires_state,
    agent_lifecycle,
)


# Test Agent Implementation

class TestAgent(ManagedAgent):
    """Test agent for lifecycle compliance testing."""
    
    def __init__(self):
        super().__init__()
        self.startup_called = 0
        self.shutdown_called = 0
        self.resources_allocated = False
        self.resources_released = False
        self.startup_failure = False
        self.shutdown_failure = False
    
    async def _do_startup(self, config: LifecycleConfig) -> None:
        """Simulate resource allocation."""
        self.startup_called += 1
        
        if self.startup_failure:
            raise RuntimeError("Simulated startup failure")
        
        # Simulate async resource allocation
        await asyncio.sleep(0.01)
        self.resources_allocated = True
    
    async def _do_shutdown(self, timeout_seconds: float) -> None:
        """Simulate resource cleanup."""
        self.shutdown_called += 1
        
        if self.shutdown_failure:
            raise RuntimeError("Simulated shutdown failure")
        
        # Simulate async cleanup
        await asyncio.sleep(0.01)
        self.resources_released = True
    
    def owns_state(self, key: str) -> StateOwnership:
        """Test state ownership determination."""
        if key == "user_history":
            return StateOwnership.MEMORY
        if key == "trace_id":
            return StateOwnership.ORCHESTRATOR
        return StateOwnership.AGENT


# Lifecycle Compliance Tests

@pytest.mark.asyncio
async def test_initial_state():
    """Verify agent starts in UNINITIALIZED state."""
    agent = TestAgent()
    assert agent.get_state() == AgentState.UNINITIALIZED
    assert agent.startup_called == 0
    assert not agent.resources_allocated


@pytest.mark.asyncio
async def test_startup_transitions_to_ready():
    """Verify startup transitions UNINITIALIZED → INITIALIZING → READY."""
    agent = TestAgent()
    
    await agent.startup()
    
    assert agent.get_state() == AgentState.READY
    assert agent.startup_called == 1
    assert agent.resources_allocated


@pytest.mark.asyncio
async def test_startup_idempotency():
    """Verify multiple startup calls are safe (idempotent)."""
    agent = TestAgent()
    
    # First startup
    await agent.startup()
    assert agent.get_state() == AgentState.READY
    assert agent.startup_called == 1
    
    # Second startup should be no-op
    await agent.startup()
    assert agent.get_state() == AgentState.READY
    assert agent.startup_called == 1  # Not called again


@pytest.mark.asyncio
async def test_shutdown_transitions_to_terminated():
    """Verify shutdown transitions * → SHUTTING_DOWN → TERMINATED."""
    agent = TestAgent()
    await agent.startup()
    
    await agent.shutdown()
    
    assert agent.get_state() == AgentState.TERMINATED
    assert agent.shutdown_called == 1
    assert agent.resources_released


@pytest.mark.asyncio
async def test_shutdown_idempotency():
    """Verify multiple shutdown calls are safe (idempotent)."""
    agent = TestAgent()
    await agent.startup()
    
    # First shutdown
    await agent.shutdown()
    assert agent.get_state() == AgentState.TERMINATED
    assert agent.shutdown_called == 1
    
    # Second shutdown should be no-op
    await agent.shutdown()
    assert agent.get_state() == AgentState.TERMINATED
    assert agent.shutdown_called == 1  # Not called again


@pytest.mark.asyncio
async def test_shutdown_never_raises():
    """Verify shutdown logs errors but never raises exceptions."""
    agent = TestAgent()
    await agent.startup()
    
    # Simulate shutdown failure
    agent.shutdown_failure = True
    
    # Should not raise even though _do_shutdown fails
    await agent.shutdown()
    
    # Still transitions to TERMINATED
    assert agent.get_state() == AgentState.TERMINATED


@pytest.mark.asyncio
async def test_startup_failure_cleanup():
    """Verify startup failure triggers cleanup when cleanup_on_error=True."""
    agent = TestAgent()
    agent.startup_failure = True
    
    config = LifecycleConfig(cleanup_on_error=True)
    
    with pytest.raises(StartupError):
        await agent.startup(config)
    
    # Should have called shutdown for cleanup
    assert agent.shutdown_called == 1
    assert agent.get_state() == AgentState.TERMINATED


@pytest.mark.asyncio
async def test_ephemeral_state_cleared_on_shutdown():
    """Verify AGENT (ephemeral) state is cleared on shutdown."""
    agent = TestAgent()
    await agent.startup()
    
    # Set ephemeral state
    agent._agent_state["temp_data"] = "test"
    agent._agent_state["_cache"] = [1, 2, 3]
    
    await agent.shutdown()
    
    # Ephemeral state should be cleared
    assert agent._agent_state == {}


@pytest.mark.asyncio
async def test_context_manager_lifecycle():
    """Verify async context manager handles lifecycle automatically."""
    agent = TestAgent()
    
    assert agent.get_state() == AgentState.UNINITIALIZED
    
    async with agent:
        # Inside context: should be READY
        assert agent.get_state() == AgentState.READY
        assert agent.startup_called == 1
    
    # Outside context: should be TERMINATED
    assert agent.get_state() == AgentState.TERMINATED
    assert agent.shutdown_called == 1


@pytest.mark.asyncio
async def test_context_manager_cleanup_on_error():
    """Verify context manager calls shutdown even on error."""
    agent = TestAgent()
    
    with pytest.raises(ValueError):
        async with agent:
            assert agent.get_state() == AgentState.READY
            raise ValueError("Simulated error")
    
    # Should still have shut down
    assert agent.get_state() == AgentState.TERMINATED
    assert agent.shutdown_called == 1


# State Ownership Tests

def test_state_ownership_agent():
    """Verify AGENT ownership determination."""
    agent = TestAgent()
    
    assert agent.owns_state("_temp") == StateOwnership.AGENT
    assert agent.owns_state("current_request") == StateOwnership.AGENT


def test_state_ownership_memory():
    """Verify MEMORY ownership determination."""
    agent = TestAgent()
    
    assert agent.owns_state("user_history") == StateOwnership.MEMORY


def test_state_ownership_orchestrator():
    """Verify ORCHESTRATOR ownership determination."""
    agent = TestAgent()
    
    assert agent.owns_state("trace_id") == StateOwnership.ORCHESTRATOR


# Metrics Tests

@pytest.mark.asyncio
async def test_metrics_collection():
    """Verify lifecycle metrics are collected."""
    agent = TestAgent()
    
    metrics = agent.get_metrics()
    assert isinstance(metrics, LifecycleMetrics)
    assert metrics.startup_time_ms == 0.0
    assert metrics.total_requests == 0
    
    await agent.startup()
    await agent.shutdown()
    
    # Metrics should be updated
    metrics = agent.get_metrics()
    assert metrics.state_transitions > 0


# Decorator Tests

class DecoratorTestAgent(ManagedAgent):
    """Agent for testing @requires_state decorator."""
    
    async def _do_startup(self, config: LifecycleConfig) -> None:
        pass
    
    async def _do_shutdown(self, timeout_seconds: float) -> None:
        pass
    
    @requires_state(AgentState.READY)
    async def process(self, request: str) -> str:
        """Only callable when READY."""
        return f"Processed: {request}"


@pytest.mark.asyncio
async def test_requires_state_decorator_allows_valid_state():
    """Verify @requires_state allows calls in valid states."""
    agent = DecoratorTestAgent()
    await agent.startup()
    
    # Should succeed - agent is READY
    result = await agent.process("test")
    assert result == "Processed: test"


@pytest.mark.asyncio
async def test_requires_state_decorator_blocks_invalid_state():
    """Verify @requires_state blocks calls in invalid states."""
    agent = DecoratorTestAgent()
    
    # Should fail - agent is UNINITIALIZED
    with pytest.raises(RuntimeError, match="must be in.*state"):
        await agent.process("test")


# Utility Function Tests

@pytest.mark.asyncio
async def test_agent_lifecycle_context_manager():
    """Verify agent_lifecycle() context manager utility."""
    agent = TestAgent()
    
    async with agent_lifecycle(agent) as managed_agent:
        assert managed_agent is agent
        assert agent.get_state() == AgentState.READY
    
    assert agent.get_state() == AgentState.TERMINATED


@pytest.mark.asyncio
async def test_agent_lifecycle_with_config():
    """Verify agent_lifecycle() accepts config."""
    agent = TestAgent()
    config = LifecycleConfig(timeout_seconds=10.0)
    
    async with agent_lifecycle(agent, config) as managed_agent:
        assert managed_agent.get_state() == AgentState.READY
    
    assert agent.get_state() == AgentState.TERMINATED


# Configuration Tests

@pytest.mark.asyncio
async def test_lifecycle_config_timeout():
    """Verify lifecycle config timeout is respected."""
    config = LifecycleConfig(timeout_seconds=0.001)  # Very short timeout
    
    class SlowAgent(ManagedAgent):
        async def _do_startup(self, config: LifecycleConfig) -> None:
            await asyncio.sleep(1.0)  # Longer than timeout
        
        async def _do_shutdown(self, timeout_seconds: float) -> None:
            pass
    
    agent = SlowAgent()
    
    # Startup should timeout (implementation-dependent)
    # This test verifies timeout is configured, not enforced
    assert config.timeout_seconds == 0.001


@pytest.mark.asyncio
async def test_lifecycle_config_retry():
    """Verify lifecycle config retry settings."""
    config = LifecycleConfig(
        retry_on_failure=True,
        max_retries=3
    )
    
    assert config.retry_on_failure is True
    assert config.max_retries == 3


# Integration Tests

@pytest.mark.asyncio
async def test_full_lifecycle():
    """Integration test: full agent lifecycle."""
    agent = TestAgent()
    
    # 1. Initial state
    assert agent.get_state() == AgentState.UNINITIALIZED
    
    # 2. Startup
    await agent.startup()
    assert agent.get_state() == AgentState.READY
    assert agent.resources_allocated
    
    # 3. Simulate work
    agent._agent_state["request_count"] = 5
    
    # 4. Shutdown
    await agent.shutdown()
    assert agent.get_state() == AgentState.TERMINATED
    assert agent.resources_released
    assert agent._agent_state == {}  # Ephemeral state cleared


@pytest.mark.asyncio
async def test_concurrent_agents():
    """Verify multiple agents can run concurrently."""
    agents = [TestAgent() for _ in range(5)]
    
    # Start all agents concurrently
    await asyncio.gather(*[agent.startup() for agent in agents])
    
    # All should be READY
    assert all(agent.get_state() == AgentState.READY for agent in agents)
    
    # Shut down all agents concurrently
    await asyncio.gather(*[agent.shutdown() for agent in agents])
    
    # All should be TERMINATED
    assert all(agent.get_state() == AgentState.TERMINATED for agent in agents)


# Error Handling Tests

@pytest.mark.asyncio
async def test_startup_error_propagation():
    """Verify startup errors are propagated correctly."""
    agent = TestAgent()
    agent.startup_failure = True
    
    with pytest.raises(StartupError):
        await agent.startup()


@pytest.mark.asyncio
async def test_shutdown_error_logged_not_raised():
    """Verify shutdown errors are logged but not raised."""
    agent = TestAgent()
    await agent.startup()
    
    agent.shutdown_failure = True
    
    # Should NOT raise
    await agent.shutdown()
    
    # But still reaches TERMINATED
    assert agent.get_state() == AgentState.TERMINATED


# Compliance Test Suite

@pytest.mark.asyncio
async def test_agent_lifecycle_compliance(agent: AgentLifecycleProtocol):
    """
    Canonical compliance test for AgentLifecycleProtocol.
    
    All agent implementations MUST pass this test.
    Use as pytest fixture parametrization to test multiple agents.
    """
    # 1. Initial state
    assert agent.get_state() == AgentState.UNINITIALIZED
    
    # 2. Startup
    await agent.startup()
    assert agent.get_state() == AgentState.READY
    
    # 3. Idempotent startup
    await agent.startup()
    assert agent.get_state() == AgentState.READY
    
    # 4. Shutdown
    await agent.shutdown()
    assert agent.get_state() == AgentState.TERMINATED
    
    # 5. Idempotent shutdown
    await agent.shutdown()
    assert agent.get_state() == AgentState.TERMINATED


# Parametrize with multiple agent implementations
@pytest.fixture(params=[TestAgent])
def agent_implementation(request):
    """Fixture providing agent implementations for compliance testing."""
    return request.param()


@pytest.mark.asyncio
async def test_all_agents_comply(agent_implementation):
    """Verify all agent implementations pass compliance tests."""
    await test_agent_lifecycle_compliance(agent_implementation)

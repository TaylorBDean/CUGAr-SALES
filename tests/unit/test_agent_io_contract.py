"""
Tests for AgentProtocol I/O Contract compliance.

Validates that all agents (PlannerAgent, WorkerAgent, CoordinatorAgent)
accept AgentRequest and return AgentResponse as per the canonical contract.

Test Coverage:
    - Request structure validation
    - Response structure validation
    - Backward compatibility with existing methods
    - Error handling and error responses
    - Metadata propagation (trace_id, profile)
    - Success and failure scenarios
"""

import pytest
from typing import Dict, Any

from cuga.modular.agents import PlannerAgent, WorkerAgent, CoordinatorAgent
from cuga.modular.tools import ToolRegistry, ToolSpec
from cuga.modular.memory import VectorMemory
from cuga.agents.contracts import (
    AgentRequest,
    AgentResponse,
    RequestMetadata,
    ResponseStatus,
    ErrorType,
)


# ========== Fixtures ==========

@pytest.fixture
def simple_registry():
    """Create simple tool registry for testing."""
    def echo_handler(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> str:
        return inputs.get("text", "")
    
    echo_tool = ToolSpec(
        name="echo",
        description="Echo text back",
        handler=echo_handler,
    )
    return ToolRegistry(tools=[echo_tool])


@pytest.fixture
def memory():
    """Create memory instance for testing."""
    return VectorMemory(profile="test_io_contract", backend_name="local")


@pytest.fixture
def planner(simple_registry, memory):
    """Create PlannerAgent for testing."""
    return PlannerAgent(registry=simple_registry, memory=memory)


@pytest.fixture
def worker(simple_registry, memory):
    """Create WorkerAgent for testing."""
    return WorkerAgent(registry=simple_registry, memory=memory)


@pytest.fixture
def coordinator(planner, worker, memory):
    """Create CoordinatorAgent for testing."""
    return CoordinatorAgent(
        planner=planner,
        workers=[worker],
        memory=memory,
    )


# ========== Test Request Validation ==========

class TestRequestValidation:
    """Test request structure validation."""
    
    @pytest.mark.asyncio
    async def test_valid_request_accepted(self, planner):
        """Valid request is accepted."""
        request = AgentRequest(
            goal="Find files",
            task="Search for Python files",
            metadata=RequestMetadata(trace_id="req-123"),
        )
        
        response = await planner.process(request)
        
        assert response.status == ResponseStatus.SUCCESS
        assert response.result is not None
    
    @pytest.mark.asyncio
    async def test_missing_goal_rejected(self, planner):
        """Request with empty goal is rejected."""
        request = AgentRequest(
            goal="",  # Empty goal
            task="Search files",
            metadata=RequestMetadata(trace_id="req-123"),
        )
        
        response = await planner.process(request)
        
        assert response.status == ResponseStatus.ERROR
        assert response.error is not None
        assert response.error.type == ErrorType.VALIDATION
        assert "goal" in response.error.message.lower()
    
    @pytest.mark.asyncio
    async def test_missing_task_rejected(self, planner):
        """Request with empty task is rejected."""
        request = AgentRequest(
            goal="Find files",
            task="",  # Empty task
            metadata=RequestMetadata(trace_id="req-123"),
        )
        
        response = await planner.process(request)
        
        assert response.status == ResponseStatus.ERROR
        assert response.error is not None
        assert response.error.type == ErrorType.VALIDATION
        assert "task" in response.error.message.lower()


# ========== Test Response Structure ==========

class TestResponseStructure:
    """Test response structure compliance."""
    
    @pytest.mark.asyncio
    async def test_success_response_has_result(self, planner):
        """Success response includes result field."""
        request = AgentRequest(
            goal="Echo test",
            task="Echo the word test",
            metadata=RequestMetadata(trace_id="req-123"),
        )
        
        response = await planner.process(request)
        
        assert response.status == ResponseStatus.SUCCESS
        assert response.result is not None
        assert "steps" in response.result
        assert "steps_count" in response.result
    
    @pytest.mark.asyncio
    async def test_error_response_has_error(self, planner):
        """Error response includes error field."""
        request = AgentRequest(
            goal="",  # Invalid goal
            task="Search files",
            metadata=RequestMetadata(trace_id="req-123"),
        )
        
        response = await planner.process(request)
        
        assert response.status == ResponseStatus.ERROR
        assert response.error is not None
        assert response.error.type in ErrorType
        assert response.error.message != ""
    
    @pytest.mark.asyncio
    async def test_response_includes_trace(self, planner):
        """Response includes execution trace."""
        request = AgentRequest(
            goal="Echo test",
            task="Echo the word test",
            metadata=RequestMetadata(trace_id="req-123"),
        )
        
        response = await planner.process(request)
        
        assert isinstance(response.trace, list)
        assert len(response.trace) > 0
    
    @pytest.mark.asyncio
    async def test_response_includes_metadata(self, planner):
        """Response includes metadata."""
        request = AgentRequest(
            goal="Echo test",
            task="Echo the word test",
            metadata=RequestMetadata(trace_id="req-123", profile="test_profile"),
        )
        
        response = await planner.process(request)
        
        assert isinstance(response.metadata, dict)
        assert "trace_id" in response.metadata
        assert response.metadata["trace_id"] == "req-123"
        assert "duration_ms" in response.metadata


# ========== Test Metadata Propagation ==========

class TestMetadataPropagation:
    """Test trace_id and profile propagation."""
    
    @pytest.mark.asyncio
    async def test_trace_id_propagated(self, planner):
        """trace_id propagates from request to response."""
        request = AgentRequest(
            goal="Echo test",
            task="Echo the word test",
            metadata=RequestMetadata(trace_id="custom-trace-123"),
        )
        
        response = await planner.process(request)
        
        assert response.metadata["trace_id"] == "custom-trace-123"
    
    @pytest.mark.asyncio
    async def test_profile_propagated(self, planner):
        """profile propagates from request to response."""
        request = AgentRequest(
            goal="Echo test",
            task="Echo the word test",
            metadata=RequestMetadata(trace_id="req-123", profile="custom_profile"),
        )
        
        response = await planner.process(request)
        
        assert response.metadata["profile"] == "custom_profile"


# ========== Test Agent-Specific Behavior ==========

class TestPlannerAgentContract:
    """Test PlannerAgent I/O contract."""
    
    @pytest.mark.asyncio
    async def test_planner_returns_plan_steps(self, planner):
        """PlannerAgent returns plan with steps."""
        request = AgentRequest(
            goal="Echo test",
            task="Create plan to echo text",
            metadata=RequestMetadata(trace_id="req-123"),
        )
        
        response = await planner.process(request)
        
        assert response.status == ResponseStatus.SUCCESS
        assert "steps" in response.result
        assert "steps_count" in response.result
        assert response.result["steps_count"] > 0
        assert "agent_type" in response.metadata
        assert response.metadata["agent_type"] == "planner"


class TestWorkerAgentContract:
    """Test WorkerAgent I/O contract."""
    
    @pytest.mark.asyncio
    async def test_worker_requires_steps_in_inputs(self, worker):
        """WorkerAgent requires 'steps' in request.inputs."""
        request = AgentRequest(
            goal="Execute plan",
            task="Execute echo steps",
            metadata=RequestMetadata(trace_id="req-123"),
            inputs={},  # Missing steps
        )
        
        response = await worker.process(request)
        
        assert response.status == ResponseStatus.ERROR
        assert response.error is not None
        assert "steps" in response.error.message.lower()
    
    @pytest.mark.asyncio
    async def test_worker_executes_steps(self, worker):
        """WorkerAgent executes provided steps."""
        steps = [
            {"tool": "echo", "input": {"text": "hello"}},
        ]
        
        request = AgentRequest(
            goal="Execute plan",
            task="Execute echo steps",
            metadata=RequestMetadata(trace_id="req-123"),
            inputs={"steps": steps},
        )
        
        response = await worker.process(request)
        
        assert response.status == ResponseStatus.SUCCESS
        assert "output" in response.result
        assert "steps_executed" in response.result
        assert response.result["steps_executed"] == 1
        assert response.metadata["agent_type"] == "worker"


class TestCoordinatorAgentContract:
    """Test CoordinatorAgent I/O contract."""
    
    @pytest.mark.asyncio
    async def test_coordinator_dispatches_goal(self, coordinator):
        """CoordinatorAgent dispatches goal to planner and worker."""
        request = AgentRequest(
            goal="Echo test",
            task="Coordinate echo workflow",
            metadata=RequestMetadata(trace_id="req-123"),
        )
        
        response = await coordinator.process(request)
        
        assert response.status == ResponseStatus.SUCCESS
        assert "output" in response.result
        assert "trace_length" in response.result
        assert response.metadata["agent_type"] == "coordinator"
        assert "workers_available" in response.metadata


# ========== Test Backward Compatibility ==========

class TestBackwardCompatibility:
    """Test that new process() method maintains backward compatibility."""
    
    @pytest.mark.asyncio
    async def test_planner_plan_still_works(self, planner):
        """Old plan() method still works alongside process()."""
        # Use old API
        old_result = planner.plan(goal="Echo test", metadata={"trace_id": "old-123"})
        
        assert old_result.steps is not None
        assert len(old_result.steps) > 0
    
    @pytest.mark.asyncio
    async def test_worker_execute_still_works(self, worker):
        """Old execute() method still works alongside process()."""
        steps = [{"tool": "echo", "input": {"text": "hello"}}]
        
        # Use old API
        old_result = worker.execute(steps=steps, metadata={"trace_id": "old-123"})
        
        assert old_result.output is not None
        assert len(old_result.trace) > 0
    
    @pytest.mark.asyncio
    async def test_coordinator_dispatch_still_works(self, coordinator):
        """Old dispatch() method still works alongside process()."""
        # Use old API
        old_result = coordinator.dispatch(goal="Echo test", trace_id="old-123")
        
        assert old_result.output is not None
        assert len(old_result.trace) > 0


# ========== Test Error Handling ==========

class TestErrorHandling:
    """Test error handling and error responses."""
    
    @pytest.mark.asyncio
    async def test_validation_error_is_recoverable_false(self, planner):
        """Validation errors are marked as non-recoverable."""
        request = AgentRequest(
            goal="",  # Invalid
            task="Search files",
            metadata=RequestMetadata(trace_id="req-123"),
        )
        
        response = await planner.process(request)
        
        assert response.status == ResponseStatus.ERROR
        assert response.error is not None
        assert response.error.type == ErrorType.VALIDATION
        assert response.error.recoverable is False
    
    @pytest.mark.asyncio
    async def test_execution_error_details_preserved(self, worker):
        """Execution errors preserve exception details."""
        # Force error by providing invalid steps
        request = AgentRequest(
            goal="Execute plan",
            task="Execute invalid steps",
            metadata=RequestMetadata(trace_id="req-123"),
            inputs={"steps": [{"tool": "nonexistent_tool", "input": {}}]},
        )
        
        response = await worker.process(request)
        
        assert response.status == ResponseStatus.ERROR
        assert response.error is not None
        assert response.error.type == ErrorType.EXECUTION
        assert "exception" in response.error.details

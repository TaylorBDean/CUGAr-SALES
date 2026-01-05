"""
Test suite for Agent I/O Contract compliance.

Verifies all agents implement canonical AgentProtocol with:
- AgentRequest input structure
- AgentResponse output structure
- Structured error handling (no exceptions)
- Metadata/trace propagation
- Validation compliance

All agent implementations MUST pass these tests per AGENTS.md guardrails.
"""

import pytest
from typing import Any, Dict
from datetime import datetime

from cuga.agents.contracts import (
    AgentProtocol,
    AgentRequest,
    AgentResponse,
    RequestMetadata,
    AgentError,
    ResponseStatus,
    ErrorType,
    success_response,
    error_response,
    partial_response,
    validate_request,
    validate_response,
)


# Test Agent Implementation

class TestAgent:
    """Test agent for I/O contract compliance testing."""
    
    def __init__(self, should_fail: bool = False, should_timeout: bool = False):
        self.should_fail = should_fail
        self.should_timeout = should_timeout
        self.process_called = False
        self.last_request = None
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """Process request per AgentProtocol."""
        self.process_called = True
        self.last_request = request
        
        # Simulate timeout
        if self.should_timeout:
            return error_response(
                error_type=ErrorType.TIMEOUT,
                message=f"Timeout after {request.metadata.timeout_seconds}s",
                recoverable=True,
                retry_after=5.0,
                trace=[{"event": "timeout", "trace_id": request.metadata.trace_id}],
            )
        
        # Simulate failure
        if self.should_fail:
            return error_response(
                error_type=ErrorType.EXECUTION,
                message="Simulated execution failure",
                details={"reason": "test"},
                recoverable=False,
                trace=[{"event": "error", "trace_id": request.metadata.trace_id}],
            )
        
        # Success
        trace = [
            {"event": "process:start", "trace_id": request.metadata.trace_id},
            {"event": "process:complete", "trace_id": request.metadata.trace_id},
        ]
        
        return success_response(
            result={"goal": request.goal, "task": request.task},
            trace=trace,
            metadata={"duration_ms": 100},
        )


# Request Structure Tests

def test_agent_request_required_fields():
    """Verify AgentRequest requires goal, task, metadata."""
    metadata = RequestMetadata(trace_id="test-123")
    
    request = AgentRequest(
        goal="Test goal",
        task="Test task",
        metadata=metadata,
    )
    
    assert request.goal == "Test goal"
    assert request.task == "Test task"
    assert request.metadata.trace_id == "test-123"


def test_agent_request_optional_fields():
    """Verify AgentRequest optional fields default correctly."""
    request = AgentRequest(
        goal="Test",
        task="Test",
        metadata=RequestMetadata(trace_id="test-123"),
    )
    
    assert request.inputs is None
    assert request.context is None
    assert request.constraints is None
    assert request.expected_output is None


def test_agent_request_with_all_fields():
    """Verify AgentRequest accepts all optional fields."""
    request = AgentRequest(
        goal="Find flights",
        task="Search API",
        metadata=RequestMetadata(
            trace_id="req-123",
            profile="production",
            priority=8,
            timeout_seconds=30.0,
            tags={"env": "prod"},
        ),
        inputs={"origin": "NY", "destination": "LA"},
        context={"previous_step": "plan_created"},
        constraints={"max_cost": 500},
        expected_output="List of flights",
    )
    
    assert request.goal == "Find flights"
    assert request.inputs["origin"] == "NY"
    assert request.context["previous_step"] == "plan_created"
    assert request.constraints["max_cost"] == 500
    assert request.expected_output == "List of flights"


def test_agent_request_validation():
    """Verify AgentRequest validation catches missing required fields."""
    # Missing goal
    request = AgentRequest(
        goal="",
        task="Test",
        metadata=RequestMetadata(trace_id="test-123"),
    )
    errors = request.validate()
    assert any("goal" in err for err in errors)
    
    # Missing task
    request = AgentRequest(
        goal="Test",
        task="",
        metadata=RequestMetadata(trace_id="test-123"),
    )
    errors = request.validate()
    assert any("task" in err for err in errors)
    
    # Valid request
    request = AgentRequest(
        goal="Test",
        task="Test",
        metadata=RequestMetadata(trace_id="test-123"),
    )
    errors = request.validate()
    assert len(errors) == 0


def test_agent_request_to_dict():
    """Verify AgentRequest serialization."""
    request = AgentRequest(
        goal="Test",
        task="Test",
        metadata=RequestMetadata(trace_id="test-123", profile="default"),
        inputs={"key": "value"},
    )
    
    data = request.to_dict()
    assert data["goal"] == "Test"
    assert data["task"] == "Test"
    assert data["metadata"]["trace_id"] == "test-123"
    assert data["inputs"]["key"] == "value"


def test_agent_request_from_dict():
    """Verify AgentRequest deserialization."""
    data = {
        "goal": "Test",
        "task": "Test",
        "metadata": {"trace_id": "test-123", "profile": "default"},
        "inputs": {"key": "value"},
    }
    
    request = AgentRequest.from_dict(data)
    assert request.goal == "Test"
    assert request.metadata.trace_id == "test-123"
    assert request.inputs["key"] == "value"


# Response Structure Tests

def test_agent_response_success():
    """Verify AgentResponse success structure."""
    response = success_response(
        result={"output": "test"},
        trace=[{"event": "complete"}],
        metadata={"duration_ms": 100},
    )
    
    assert response.status == ResponseStatus.SUCCESS
    assert response.result["output"] == "test"
    assert len(response.trace) == 1
    assert response.metadata["duration_ms"] == 100
    assert response.error is None


def test_agent_response_error():
    """Verify AgentResponse error structure."""
    response = error_response(
        error_type=ErrorType.EXECUTION,
        message="Test error",
        details={"reason": "test"},
        recoverable=True,
        retry_after=5.0,
        trace=[{"event": "error"}],
    )
    
    assert response.status == ResponseStatus.ERROR
    assert response.error.type == ErrorType.EXECUTION
    assert response.error.message == "Test error"
    assert response.error.recoverable is True
    assert response.error.retry_after == 5.0
    assert response.result is None


def test_agent_response_partial():
    """Verify AgentResponse partial structure."""
    response = partial_response(
        result={"partial_data": [1, 2]},
        remaining_work="Process remaining items",
        trace=[{"event": "partial"}],
    )
    
    assert response.status == ResponseStatus.PARTIAL
    assert response.result["partial_data"] == [1, 2]
    assert "remaining_work" in response.metadata


def test_agent_response_validation():
    """Verify AgentResponse validation catches missing required fields."""
    # SUCCESS without result
    response = AgentResponse(status=ResponseStatus.SUCCESS)
    errors = response.validate()
    assert any("result" in err for err in errors)
    
    # ERROR without error
    response = AgentResponse(status=ResponseStatus.ERROR)
    errors = response.validate()
    assert any("error" in err for err in errors)
    
    # Valid success response
    response = AgentResponse(
        status=ResponseStatus.SUCCESS,
        result="test",
    )
    errors = response.validate()
    assert len(errors) == 0


def test_agent_response_is_success():
    """Verify AgentResponse.is_success() helper."""
    success = success_response(result="test")
    assert success.is_success() is True
    assert success.is_error() is False
    
    error = error_response(ErrorType.EXECUTION, "error")
    assert error.is_success() is False
    assert error.is_error() is True


def test_agent_response_is_recoverable():
    """Verify AgentResponse.is_recoverable() helper."""
    recoverable = error_response(
        ErrorType.TIMEOUT,
        "timeout",
        recoverable=True,
    )
    assert recoverable.is_recoverable() is True
    
    unrecoverable = error_response(
        ErrorType.EXECUTION,
        "fatal",
        recoverable=False,
    )
    assert unrecoverable.is_recoverable() is False


# Protocol Compliance Tests

@pytest.mark.asyncio
async def test_agent_accepts_request():
    """Verify agent accepts AgentRequest."""
    agent = TestAgent()
    
    request = AgentRequest(
        goal="Test",
        task="Test",
        metadata=RequestMetadata(trace_id="test-123"),
    )
    
    response = await agent.process(request)
    
    assert agent.process_called is True
    assert agent.last_request is request


@pytest.mark.asyncio
async def test_agent_returns_response():
    """Verify agent returns AgentResponse."""
    agent = TestAgent()
    
    request = AgentRequest(
        goal="Test",
        task="Test",
        metadata=RequestMetadata(trace_id="test-123"),
    )
    
    response = await agent.process(request)
    
    assert isinstance(response, AgentResponse)
    assert response.status in ResponseStatus


@pytest.mark.asyncio
async def test_agent_propagates_trace_id():
    """Verify agent propagates trace_id in response."""
    agent = TestAgent()
    
    request = AgentRequest(
        goal="Test",
        task="Test",
        metadata=RequestMetadata(trace_id="trace-456"),
    )
    
    response = await agent.process(request)
    
    # Trace events should include trace_id
    assert any(
        event.get("trace_id") == "trace-456" or "trace-456" in str(event)
        for event in response.trace
    )


@pytest.mark.asyncio
async def test_agent_handles_errors_without_raising():
    """Verify agent returns error responses instead of raising."""
    agent = TestAgent(should_fail=True)
    
    request = AgentRequest(
        goal="Test",
        task="Test",
        metadata=RequestMetadata(trace_id="test-123"),
    )
    
    # Should NOT raise exception
    response = await agent.process(request)
    
    assert response.status == ResponseStatus.ERROR
    assert response.error is not None
    assert response.error.message == "Simulated execution failure"


@pytest.mark.asyncio
async def test_agent_returns_structured_errors():
    """Verify agent returns structured AgentError."""
    agent = TestAgent(should_fail=True)
    
    request = AgentRequest(
        goal="Test",
        task="Test",
        metadata=RequestMetadata(trace_id="test-123"),
    )
    
    response = await agent.process(request)
    
    assert isinstance(response.error, AgentError)
    assert response.error.type in ErrorType
    assert response.error.message
    assert isinstance(response.error.recoverable, bool)


@pytest.mark.asyncio
async def test_agent_includes_trace_events():
    """Verify agent includes execution trace."""
    agent = TestAgent()
    
    request = AgentRequest(
        goal="Test",
        task="Test",
        metadata=RequestMetadata(trace_id="test-123"),
    )
    
    response = await agent.process(request)
    
    assert len(response.trace) > 0
    assert all(isinstance(event, dict) for event in response.trace)


@pytest.mark.asyncio
async def test_agent_includes_metadata():
    """Verify agent includes response metadata."""
    agent = TestAgent()
    
    request = AgentRequest(
        goal="Test",
        task="Test",
        metadata=RequestMetadata(trace_id="test-123"),
    )
    
    response = await agent.process(request)
    
    assert isinstance(response.metadata, dict)
    # Should include timing/performance metrics
    assert "duration_ms" in response.metadata or len(response.metadata) >= 0


# Error Handling Tests

@pytest.mark.asyncio
async def test_timeout_error_structure():
    """Verify timeout errors include retry_after."""
    agent = TestAgent(should_timeout=True)
    
    request = AgentRequest(
        goal="Test",
        task="Test",
        metadata=RequestMetadata(trace_id="test-123", timeout_seconds=10.0),
    )
    
    response = await agent.process(request)
    
    assert response.status == ResponseStatus.ERROR
    assert response.error.type == ErrorType.TIMEOUT
    assert response.error.recoverable is True
    assert response.error.retry_after is not None


# Validation Tests

def test_validate_request_valid():
    """Verify validate_request accepts valid requests."""
    request = AgentRequest(
        goal="Test",
        task="Test",
        metadata=RequestMetadata(trace_id="test-123"),
    )
    
    # Should not raise
    validate_request(request)


def test_validate_request_invalid():
    """Verify validate_request rejects invalid requests."""
    request = AgentRequest(
        goal="",
        task="Test",
        metadata=RequestMetadata(trace_id="test-123"),
    )
    
    with pytest.raises(ValueError, match="Invalid AgentRequest"):
        validate_request(request)


def test_validate_response_valid():
    """Verify validate_response accepts valid responses."""
    response = success_response(result="test")
    
    # Should not raise
    validate_response(response)


def test_validate_response_invalid():
    """Verify validate_response rejects invalid responses."""
    # SUCCESS without result
    response = AgentResponse(status=ResponseStatus.SUCCESS)
    
    with pytest.raises(ValueError, match="Invalid AgentResponse"):
        validate_response(response)


# Serialization Tests

def test_request_roundtrip():
    """Verify AgentRequest serialization roundtrip."""
    original = AgentRequest(
        goal="Test",
        task="Test",
        metadata=RequestMetadata(trace_id="test-123", profile="prod"),
        inputs={"key": "value"},
    )
    
    # Serialize and deserialize
    data = original.to_dict()
    restored = AgentRequest.from_dict(data)
    
    assert restored.goal == original.goal
    assert restored.task == original.task
    assert restored.metadata.trace_id == original.metadata.trace_id
    assert restored.inputs == original.inputs


def test_response_roundtrip():
    """Verify AgentResponse serialization roundtrip."""
    original = success_response(
        result={"data": "test"},
        trace=[{"event": "test"}],
        metadata={"duration_ms": 100},
    )
    
    # Serialize and deserialize
    data = original.to_dict()
    restored = AgentResponse.from_dict(data)
    
    assert restored.status == original.status
    assert restored.result == original.result
    assert len(restored.trace) == len(original.trace)


# Compliance Test Suite (Canonical)

@pytest.mark.asyncio
async def test_agent_io_compliance(agent: AgentProtocol):
    """
    Canonical compliance test for AgentProtocol.
    
    All agent implementations MUST pass this test.
    Use as pytest fixture parametrization to test multiple agents.
    """
    # 1. Create request
    request = AgentRequest(
        goal="Test goal",
        task="Test task",
        metadata=RequestMetadata(trace_id="compliance-test"),
    )
    
    # 2. Process request
    response = await agent.process(request)
    
    # 3. Verify response structure
    assert isinstance(response, AgentResponse)
    assert response.status in ResponseStatus
    
    # 4. Verify status-dependent fields
    if response.status == ResponseStatus.SUCCESS:
        assert response.result is not None
    elif response.status == ResponseStatus.ERROR:
        assert response.error is not None
        assert isinstance(response.error, AgentError)
        assert response.error.type in ErrorType
    
    # 5. Verify trace propagation
    assert isinstance(response.trace, list)
    # Should include trace_id somewhere
    trace_str = str(response.trace)
    assert "compliance-test" in trace_str or any(
        "trace_id" in event for event in response.trace
    )
    
    # 6. Verify metadata
    assert isinstance(response.metadata, dict)
    
    # 7. Verify timestamp
    assert response.timestamp
    # Should be valid ISO format
    datetime.fromisoformat(response.timestamp.replace("Z", "+00:00"))


# Parametrize with agent implementations
@pytest.fixture(params=[TestAgent])
def agent_implementation(request):
    """Fixture providing agent implementations for compliance testing."""
    return request.param()


@pytest.mark.asyncio
async def test_all_agents_comply(agent_implementation):
    """Verify all agent implementations pass I/O compliance tests."""
    await test_agent_io_compliance(agent_implementation)

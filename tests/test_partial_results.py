"""
Tests for Partial Result Preservation (Task #7)

Tests WorkerAgent's enhanced partial result tracking, failure recovery,
and execute_from_partial() method for robust multi-step workflow execution.

Enhanced in v1.3.2 to support step-level result tracking, timestamps,
and recovery from mid-execution failures.
"""

import pytest
import time
from typing import Any, Dict

from cuga.modular.agents import WorkerAgent, AgentResult
from cuga.modular.tools import ToolRegistry, ToolSpec
from cuga.modular.memory import VectorMemory
from cuga.orchestrator.failures import (
    PartialResult,
    FailureMode,
    create_retry_policy,
)


# Test Tools

def tool_success(inputs: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Tool that always succeeds."""
    return f"success_{inputs.get('value', 'default')}"


def tool_failure(inputs: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Tool that always fails."""
    raise ValueError("Tool failed intentionally")


def tool_timeout(inputs: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Tool that simulates timeout."""
    raise TimeoutError("Tool execution timeout")


def tool_conditional_failure(inputs: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Tool that fails on specific input."""
    if inputs.get("should_fail", False):
        raise ValueError("Conditional failure triggered")
    return f"success_{inputs.get('value', 'ok')}"


# Fixtures

@pytest.fixture
def registry():
    """Create test tool registry."""
    reg = ToolRegistry()
    reg.register(ToolSpec(name="success", handler=tool_success, description="Success tool"))
    reg.register(ToolSpec(name="failure", handler=tool_failure, description="Failure tool"))
    reg.register(ToolSpec(name="timeout", handler=tool_timeout, description="Timeout tool"))
    reg.register(ToolSpec(name="conditional", handler=tool_conditional_failure, description="Conditional tool"))
    return reg


@pytest.fixture
def memory():
    """Create test memory."""
    return VectorMemory(profile="test")


@pytest.fixture
def worker(registry, memory):
    """Create test WorkerAgent."""
    retry_policy = create_retry_policy(strategy="none")  # No retries for predictable tests
    return WorkerAgent(registry=registry, memory=memory, retry_policy=retry_policy)


# Test 1: PartialResult Enhancement

def test_partial_result_create_empty():
    """Test PartialResult.create_empty() factory method."""
    partial = PartialResult.create_empty(total_steps=5, trace_id="trace-123")
    
    assert partial.total_steps == 5
    assert partial.trace_id == "trace-123"
    assert len(partial.completed_steps) == 0
    assert len(partial.failed_steps) == 0
    assert partial.completion_ratio == 0.0
    assert partial.remaining_steps == 5
    assert partial.failure_mode == FailureMode.PARTIAL_STEP_FAILURES


def test_partial_result_add_completed_step():
    """Test adding completed steps to PartialResult."""
    partial = PartialResult.create_empty(total_steps=3)
    
    # Add first step
    partial.add_completed_step("step_0", result="output_0", timestamp=100.0)
    assert len(partial.completed_steps) == 1
    assert partial.completed_steps[0] == "step_0"
    assert partial.get_step_result("step_0") == "output_0"
    assert partial.step_timestamps["step_0"] == 100.0
    assert partial.completion_ratio == pytest.approx(1/3)
    
    # Add second step
    partial.add_completed_step("step_1", result="output_1", timestamp=102.0)
    assert len(partial.completed_steps) == 2
    assert partial.completion_ratio == pytest.approx(2/3)
    
    # Add third step
    partial.add_completed_step("step_2", result="output_2", timestamp=105.0)
    assert len(partial.completed_steps) == 3
    assert partial.completion_ratio == 1.0
    assert partial.remaining_steps == 0


def test_partial_result_add_failed_step():
    """Test adding failed steps to PartialResult."""
    partial = PartialResult.create_empty(total_steps=3)
    
    # Add completed step
    partial.add_completed_step("step_0", result="output_0")
    
    # Add failed step
    partial.add_failed_step("step_1", FailureMode.AGENT_TIMEOUT)
    
    assert len(partial.completed_steps) == 1
    assert len(partial.failed_steps) == 1
    assert partial.failed_steps[0] == "step_1"
    assert partial.failure_point == "step_1"
    assert partial.failure_mode == FailureMode.AGENT_TIMEOUT
    assert partial.completion_ratio == pytest.approx(1/3)
    assert partial.remaining_steps == 1


def test_partial_result_recovery_hints():
    """Test PartialResult recovery hint generation."""
    # No progress - full retry
    partial = PartialResult.create_empty(total_steps=10)
    partial.add_failed_step("step_0", FailureMode.SYSTEM_TIMEOUT)
    hint = partial.get_recovery_hint()
    assert "No steps completed" in hint
    assert "retry entire workflow" in hint.lower()
    
    # 30% progress - partial retry
    partial = PartialResult.create_empty(total_steps=10)
    for i in range(3):
        partial.add_completed_step(f"step_{i}", f"output_{i}")
    partial.add_failed_step("step_3", FailureMode.SYSTEM_NETWORK)
    hint = partial.get_recovery_hint()
    assert "Minimal progress (30%)" in hint or "Partial progress" in hint
    
    # 95% progress - retry only failed
    partial = PartialResult.create_empty(total_steps=10)
    for i in range(9):
        partial.add_completed_step(f"step_{i}", f"output_{i}")
    partial.add_failed_step("step_9", FailureMode.RESOURCE_TOOL_UNAVAILABLE)
    hint = partial.get_recovery_hint()
    assert "Near complete (90%)" in hint
    assert "retry only failed steps" in hint.lower()
    
    # Terminal failure - manual intervention
    partial = PartialResult.create_empty(total_steps=5)
    partial.add_completed_step("step_0", "output_0")
    partial.add_failed_step("step_1", FailureMode.POLICY_SECURITY)
    hint = partial.get_recovery_hint()
    assert "manual intervention" in hint.lower()


def test_partial_result_is_recoverable():
    """Test PartialResult.is_recoverable property."""
    # No progress + retryable = not recoverable
    partial = PartialResult.create_empty(total_steps=5)
    partial.add_failed_step("step_0", FailureMode.SYSTEM_TIMEOUT)
    assert not partial.is_recoverable  # No completed steps
    
    # Some progress + retryable = recoverable
    partial = PartialResult.create_empty(total_steps=5)
    partial.add_completed_step("step_0", "output_0")
    partial.add_failed_step("step_1", FailureMode.SYSTEM_NETWORK)
    assert partial.is_recoverable
    
    # Some progress + terminal = not recoverable
    partial = PartialResult.create_empty(total_steps=5)
    partial.add_completed_step("step_0", "output_0")
    partial.add_failed_step("step_1", FailureMode.POLICY_SECURITY)
    assert not partial.is_recoverable


def test_partial_result_to_dict():
    """Test PartialResult.to_dict() serialization."""
    partial = PartialResult.create_empty(total_steps=5, trace_id="trace-456")
    partial.add_completed_step("step_0", result="output_0", timestamp=100.0)
    partial.add_completed_step("step_1", result="output_1", timestamp=102.0)
    partial.add_failed_step("step_2", FailureMode.AGENT_VALIDATION)
    
    data = partial.to_dict()
    
    assert data["trace_id"] == "trace-456"
    assert data["total_steps"] == 5
    assert data["completed_steps"] == ["step_0", "step_1"]
    assert data["failed_steps"] == ["step_2"]
    assert data["failure_point"] == "step_2"
    assert data["failure_mode"] == "agent_validation"
    assert data["completion_ratio"] == pytest.approx(2/5)
    assert data["remaining_steps"] == 2
    assert "recovery_hint" in data


# Test 2: WorkerAgent Partial Result Tracking

def test_worker_execute_tracks_partial_results_success(worker, registry, memory):
    """Test WorkerAgent tracks partial results on successful execution."""
    steps = [
        {"tool": "success", "input": {"value": "1"}},
        {"tool": "success", "input": {"value": "2"}},
        {"tool": "success", "input": {"value": "3"}},
    ]
    
    result = worker.execute(steps, metadata={"trace_id": "trace-success"})
    
    assert result.output == "success_3"
    assert len(result.trace) == 3


def test_worker_execute_saves_partial_on_failure(worker):
    """Test WorkerAgent saves partial results on mid-execution failure."""
    steps = [
        {"tool": "success", "input": {"value": "1"}},
        {"tool": "success", "input": {"value": "2"}},
        {"tool": "failure", "input": {}},  # This step fails
        {"tool": "success", "input": {"value": "4"}},
    ]
    
    with pytest.raises(ValueError) as exc_info:
        worker.execute(steps, metadata={"trace_id": "trace-fail"})
    
    # Check that partial result was attached to exception
    partial = getattr(exc_info.value, "partial_result", None)
    assert partial is not None
    assert len(partial.completed_steps) == 2  # First two steps completed
    assert len(partial.failed_steps) == 1  # Third step failed
    assert partial.failure_point == "step_2_failure"
    assert partial.completion_ratio == pytest.approx(2/4)
    assert partial.remaining_steps == 1


def test_worker_execute_partial_result_contains_outputs(worker):
    """Test PartialResult contains step outputs."""
    steps = [
        {"tool": "success", "input": {"value": "A"}},
        {"tool": "success", "input": {"value": "B"}},
        {"tool": "failure", "input": {}},
    ]
    
    with pytest.raises(ValueError) as exc_info:
        worker.execute(steps)
    
    partial = exc_info.value.partial_result
    assert partial is not None
    assert "last_output" in partial.partial_data
    assert partial.partial_data["last_output"] == "success_B"
    assert "step_0_output" in partial.partial_data
    assert partial.partial_data["step_0_output"] == "success_A"
    assert "step_1_output" in partial.partial_data
    assert partial.partial_data["step_1_output"] == "success_B"


# Test 3: execute_from_partial() Recovery

def test_execute_from_partial_resumes_execution(worker):
    """Test execute_from_partial() resumes from last completed step."""
    steps = [
        {"tool": "success", "input": {"value": "1"}},
        {"tool": "success", "input": {"value": "2"}},
        {"tool": "conditional", "input": {"should_fail": True}},  # Fails first time
        {"tool": "success", "input": {"value": "4"}},
    ]
    
    # First execution fails at step 2
    with pytest.raises(ValueError) as exc_info:
        worker.execute(steps, metadata={"trace_id": "trace-recovery"})
    
    partial = exc_info.value.partial_result
    assert len(partial.completed_steps) == 2
    
    # Fix the failing step
    steps[2]["input"]["should_fail"] = False
    
    # Resume execution from partial result
    result = worker.execute_from_partial(steps, partial)
    
    # Should complete successfully
    assert result.output == "success_4"
    # Should have executed remaining 2 steps (step 2 and step 3)


def test_execute_from_partial_rejects_unrecoverable(worker):
    """Test execute_from_partial() rejects unrecoverable partial results."""
    # Create partial result with terminal failure
    partial = PartialResult.create_empty(total_steps=5)
    partial.add_failed_step("step_0", FailureMode.POLICY_SECURITY)
    
    steps = [{"tool": "success", "input": {"value": "1"}}]
    
    with pytest.raises(ValueError) as exc_info:
        worker.execute_from_partial(steps, partial)
    
    assert "not recoverable" in str(exc_info.value).lower()


def test_execute_from_partial_preserves_trace_id(worker):
    """Test execute_from_partial() preserves trace_id for continuity."""
    original_trace_id = "trace-original-789"
    
    steps = [
        {"tool": "success", "input": {"value": "1"}},
        {"tool": "failure", "input": {}},
    ]
    
    # First execution fails
    with pytest.raises(ValueError) as exc_info:
        worker.execute(steps, metadata={"trace_id": original_trace_id})
    
    partial = exc_info.value.partial_result
    assert partial.trace_id == original_trace_id
    
    # Fix and resume
    steps[1] = {"tool": "success", "input": {"value": "2"}}
    result = worker.execute_from_partial(steps, partial)
    
    # Trace ID should be preserved
    assert result.trace[0]["trace_id"] == original_trace_id


def test_get_partial_result_from_exception(worker):
    """Test get_partial_result_from_exception() helper method."""
    steps = [
        {"tool": "success", "input": {"value": "1"}},
        {"tool": "failure", "input": {}},
    ]
    
    try:
        worker.execute(steps)
    except Exception as exc:
        partial = worker.get_partial_result_from_exception(exc)
        assert partial is not None
        assert len(partial.completed_steps) == 1
    else:
        pytest.fail("Expected exception")


# Test 4: Failure Mode Detection

def test_failure_mode_detection_timeout(worker):
    """Test failure mode detection classifies timeout errors."""
    steps = [
        {"tool": "success", "input": {"value": "1"}},
        {"tool": "timeout", "input": {}},
    ]
    
    with pytest.raises(TimeoutError) as exc_info:
        worker.execute(steps)
    
    partial = exc_info.value.partial_result
    assert partial.failure_mode == FailureMode.SYSTEM_TIMEOUT


def test_failure_mode_detection_generic(worker):
    """Test failure mode detection defaults to PARTIAL_STEP_FAILURES for mid-execution errors."""
    steps = [
        {"tool": "success", "input": {"value": "1"}},
        {"tool": "failure", "input": {}},
    ]
    
    with pytest.raises(ValueError) as exc_info:
        worker.execute(steps)
    
    partial = exc_info.value.partial_result
    # Generic ValueError during execution should be classified as PARTIAL_STEP_FAILURES
    # (more recoverable than AGENT_LOGIC)
    assert partial.failure_mode == FailureMode.PARTIAL_STEP_FAILURES


# Test 5: Recovery Strategy Suggestion

def test_recovery_strategy_high_completion(worker):
    """Test recovery strategy suggests retry_failed for high completion."""
    steps = [
        {"tool": "success", "input": {"value": f"{i}"}}
        for i in range(10)
    ]
    steps[9] = {"tool": "failure", "input": {}}  # Last step fails
    
    with pytest.raises(ValueError) as exc_info:
        worker.execute(steps)
    
    partial = exc_info.value.partial_result
    assert partial.completion_ratio >= 0.75
    assert partial.recovery_strategy == "retry_failed"


def test_recovery_strategy_medium_completion(worker):
    """Test recovery strategy suggests retry_from_checkpoint for medium completion."""
    steps = [
        {"tool": "success", "input": {"value": "1"}},
        {"tool": "success", "input": {"value": "2"}},
        {"tool": "failure", "input": {}},  # Midway failure
        {"tool": "success", "input": {"value": "4"}},
        {"tool": "success", "input": {"value": "5"}},
    ]
    
    with pytest.raises(ValueError) as exc_info:
        worker.execute(steps)
    
    partial = exc_info.value.partial_result
    assert 0.25 <= partial.completion_ratio < 0.75
    assert partial.recovery_strategy == "retry_from_checkpoint"


def test_recovery_strategy_low_completion(worker):
    """Test recovery strategy suggests retry_all for low completion."""
    steps = [
        {"tool": "failure", "input": {}},  # First step fails
        {"tool": "success", "input": {"value": "2"}},
        {"tool": "success", "input": {"value": "3"}},
        {"tool": "success", "input": {"value": "4"}},
    ]
    
    with pytest.raises(ValueError) as exc_info:
        worker.execute(steps)
    
    partial = exc_info.value.partial_result
    assert partial.completion_ratio < 0.25
    assert partial.recovery_strategy == "retry_all"


def test_recovery_strategy_terminal_failure(worker, registry):
    """Test recovery strategy suggests manual for terminal failures."""
    # Create tool that raises a "permission" error (terminal)
    def tool_permission_error(inputs, context):
        raise PermissionError("Access denied")
    
    registry.register(ToolSpec(
        name="permission_error",
        handler=tool_permission_error,
        description="Permission error tool"
    ))
    
    steps = [
        {"tool": "success", "input": {"value": "1"}},
        {"tool": "permission_error", "input": {}},
    ]
    
    with pytest.raises(PermissionError) as exc_info:
        worker.execute(steps)
    
    partial = exc_info.value.partial_result
    assert partial.failure_mode == FailureMode.USER_PERMISSION
    assert partial.recovery_strategy == "manual"


# Test 6: Edge Cases

def test_partial_result_empty_steps(worker):
    """Test partial result with empty steps list."""
    steps = []
    result = worker.execute(steps)
    assert result.output is None
    assert len(result.trace) == 0


def test_partial_result_single_step_failure(worker):
    """Test partial result with single failing step."""
    steps = [{"tool": "failure", "input": {}}]
    
    with pytest.raises(ValueError) as exc_info:
        worker.execute(steps)
    
    partial = exc_info.value.partial_result
    assert len(partial.completed_steps) == 0
    assert len(partial.failed_steps) == 1
    assert partial.completion_ratio == 0.0
    assert not partial.is_recoverable  # No progress made


def test_execute_from_partial_with_new_metadata(worker):
    """Test execute_from_partial() accepts new metadata while preserving trace_id."""
    steps = [
        {"tool": "success", "input": {"value": "1"}},
        {"tool": "failure", "input": {}},
        {"tool": "success", "input": {"value": "3"}},
    ]
    
    # First execution
    with pytest.raises(ValueError) as exc_info:
        worker.execute(steps, metadata={"trace_id": "trace-001", "profile": "prod"})
    
    partial = exc_info.value.partial_result
    
    # Fix and resume with new metadata
    steps[1] = {"tool": "success", "input": {"value": "2"}}
    result = worker.execute_from_partial(
        steps,
        partial,
        metadata={"profile": "staging"},  # New profile, but trace_id preserved
    )
    
    # Should complete successfully
    assert result.output == "success_3"
    # Trace ID should be preserved from partial result
    assert result.trace[0]["trace_id"] == "trace-001"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

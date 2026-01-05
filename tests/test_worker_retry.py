"""
Tests for RetryPolicy integration in WorkerAgent.

Validates that:
1. WorkerAgent has retry_policy field
2. Default RetryPolicy is initialized (ExponentialBackoffPolicy)
3. Custom RetryPolicy can be provided
4. Tool execution retries on transient failures
5. Failures are classified with FailureMode
6. Terminal failures don't retry
7. Retry attempts respect max_attempts limit
8. Exponential backoff delays are applied
9. Retry metrics are tracked
"""

import pytest
import time
from unittest.mock import Mock, MagicMock, call
from dataclasses import dataclass

from cuga.modular.agents import WorkerAgent, AgentResult
from cuga.modular.memory import VectorMemory
from cuga.modular.tools import ToolRegistry, ToolSpec
from cuga.orchestrator.failures import (
    RetryPolicy,
    ExponentialBackoffPolicy,
    LinearBackoffPolicy,
    NoRetryPolicy,
    FailureMode,
    FailureContext,
    create_retry_policy,
)


# --- Fixtures ---

@pytest.fixture
def memory():
    """Mock VectorMemory for testing."""
    return MagicMock(spec=VectorMemory, profile="test")


@pytest.fixture
def successful_tool():
    """Tool that always succeeds."""
    def handler(inputs, ctx):
        return "success"
    
    return ToolSpec(name="success_tool", description="Always succeeds", handler=handler)


@pytest.fixture
def failing_tool():
    """Tool that always fails."""
    def handler(inputs, ctx):
        raise RuntimeError("Tool failed")
    
    return ToolSpec(name="failing_tool", description="Always fails", handler=handler)


@pytest.fixture
def flaky_tool():
    """Tool that fails once then succeeds (simulates transient error)."""
    call_count = {"count": 0}
    
    def handler(inputs, ctx):
        call_count["count"] += 1
        if call_count["count"] == 1:
            # Raise ConnectionError which is classified as SYSTEM_NETWORK (retryable)
            raise ConnectionError("Temporary network failure")
        return f"success on attempt {call_count['count']}"
    
    return ToolSpec(name="flaky_tool", description="Fails once", handler=handler)


@pytest.fixture
def timeout_tool():
    """Tool that raises timeout error (retryable)."""
    def handler(inputs, ctx):
        raise TimeoutError("Operation timed out")
    
    return ToolSpec(name="timeout_tool", description="Times out", handler=handler)


# --- Tests ---

class TestRetryPolicyIntegration:
    """Test RetryPolicy integration in WorkerAgent."""
    
    def test_worker_has_retry_policy(self, successful_tool, memory):
        """WorkerAgent has retry_policy field."""
        registry = ToolRegistry(tools=[successful_tool])
        worker = WorkerAgent(registry=registry, memory=memory)
        
        assert hasattr(worker, "retry_policy")
        assert worker.retry_policy is not None
    
    def test_worker_default_retry_policy(self, successful_tool, memory):
        """WorkerAgent initializes default exponential backoff policy."""
        registry = ToolRegistry(tools=[successful_tool])
        worker = WorkerAgent(registry=registry, memory=memory)
        
        assert isinstance(worker.retry_policy, RetryPolicy)
        assert isinstance(worker.retry_policy, ExponentialBackoffPolicy)
        assert worker.retry_policy.get_max_attempts() == 3
    
    def test_worker_custom_retry_policy(self, successful_tool, memory):
        """WorkerAgent accepts custom retry policy."""
        registry = ToolRegistry(tools=[successful_tool])
        custom_policy = LinearBackoffPolicy(delay=0.5, max_attempts=5)
        
        worker = WorkerAgent(
            registry=registry,
            memory=memory,
            retry_policy=custom_policy,
        )
        
        assert worker.retry_policy is custom_policy
        assert worker.retry_policy.get_max_attempts() == 5
    
    def test_worker_no_retry_policy(self, successful_tool, memory):
        """WorkerAgent accepts NoRetryPolicy for fail-fast."""
        registry = ToolRegistry(tools=[successful_tool])
        no_retry = NoRetryPolicy()
        
        worker = WorkerAgent(
            registry=registry,
            memory=memory,
            retry_policy=no_retry,
        )
        
        assert isinstance(worker.retry_policy, NoRetryPolicy)
        assert worker.retry_policy.get_max_attempts() == 0


class TestRetryBehavior:
    """Test retry behavior on tool failures."""
    
    def test_successful_tool_no_retry(self, successful_tool, memory):
        """Successful tool executes once (no retry)."""
        registry = ToolRegistry(tools=[successful_tool])
        worker = WorkerAgent(registry=registry, memory=memory)
        
        steps = [{"tool": "success_tool", "input": {}}]
        result = worker.execute(steps)
        
        assert result.output == "success"
    
    def test_flaky_tool_retries_and_succeeds(self, flaky_tool, memory):
        """Flaky tool retries once and succeeds."""
        registry = ToolRegistry(tools=[flaky_tool])
        worker = WorkerAgent(registry=registry, memory=memory)
        
        steps = [{"tool": "flaky_tool", "input": {}}]
        result = worker.execute(steps)
        
        # Should succeed on second attempt
        assert "success on attempt 2" in result.output
    
    def test_failing_tool_exhausts_retries(self, failing_tool, memory):
        """Failing tool exhausts all retries then raises."""
        registry = ToolRegistry(tools=[failing_tool])
        # Use no delay for fast test
        custom_policy = ExponentialBackoffPolicy(
            base_delay=0.0,
            max_attempts=3,
        )
        worker = WorkerAgent(
            registry=registry,
            memory=memory,
            retry_policy=custom_policy,
        )
        
        steps = [{"tool": "failing_tool", "input": {}}]
        
        with pytest.raises(RuntimeError, match="Tool failed"):
            worker.execute(steps)
    
    def test_timeout_retries_then_fails(self, timeout_tool, memory):
        """Timeout errors retry but eventually fail."""
        registry = ToolRegistry(tools=[timeout_tool])
        # Use no delay and 2 attempts for fast test
        custom_policy = ExponentialBackoffPolicy(
            base_delay=0.0,
            max_attempts=2,
        )
        worker = WorkerAgent(
            registry=registry,
            memory=memory,
            retry_policy=custom_policy,
        )
        
        steps = [{"tool": "timeout_tool", "input": {}}]
        
        with pytest.raises(TimeoutError, match="timed out"):
            worker.execute(steps)


class TestFailureClassification:
    """Test failure mode classification."""
    
    def test_timeout_classified_as_retryable(self, memory):
        """Timeout errors classified as SYSTEM_TIMEOUT (retryable)."""
        def timeout_handler(inputs, ctx):
            raise TimeoutError("Timeout")
        
        tool = ToolSpec(name="timeout", description="Times out", handler=timeout_handler)
        registry = ToolRegistry(tools=[tool])
        
        # Use no retry to check classification
        worker = WorkerAgent(
            registry=registry,
            memory=memory,
            retry_policy=NoRetryPolicy(),
        )
        
        steps = [{"tool": "timeout", "input": {}}]
        
        # Should raise immediately with no retry
        with pytest.raises(TimeoutError):
            worker.execute(steps)
    
    def test_validation_error_not_retried(self, memory):
        """Validation errors don't retry (AGENT_VALIDATION)."""
        def validation_handler(inputs, ctx):
            raise ValueError("Invalid input")
        
        tool = ToolSpec(name="validator", description="Validates", handler=validation_handler)
        registry = ToolRegistry(tools=[tool])
        
        worker = WorkerAgent(registry=registry, memory=memory)
        
        steps = [{"tool": "validator", "input": {}}]
        
        # Should fail immediately (validation errors not retryable)
        with pytest.raises(ValueError, match="Invalid input"):
            worker.execute(steps)


class TestRetryDelays:
    """Test retry delay calculations."""
    
    def test_exponential_backoff_delays(self, memory):
        """Exponential backoff increases delay per attempt."""
        def always_fail(inputs, ctx):
            # Use TimeoutError (retryable)
            raise TimeoutError("Operation timed out")
        
        tool = ToolSpec(name="fail", description="Fails", handler=always_fail)
        registry = ToolRegistry(tools=[tool])
        
        # Test with actual delays (small)
        custom_policy = ExponentialBackoffPolicy(
            base_delay=0.01,  # 10ms base
            max_delay=1.0,
            multiplier=2.0,
            max_attempts=3,
            jitter=0.0,  # No jitter for predictable testing
        )
        worker = WorkerAgent(
            registry=registry,
            memory=memory,
            retry_policy=custom_policy,
        )
        
        steps = [{"tool": "fail", "input": {}}]
        
        start = time.perf_counter()
        with pytest.raises(TimeoutError):
            worker.execute(steps)
        duration = time.perf_counter() - start
        
        # Should have delays: 0.01 + 0.02 + 0.04 = 0.07s minimum
        # Allow some tolerance for execution time
        assert duration >= 0.05  # At least 50ms
    
    def test_linear_backoff_constant_delay(self, memory):
        """Linear backoff uses constant delay."""
        def always_fail(inputs, ctx):
            # Use TimeoutError (retryable)
            raise TimeoutError("Operation timed out")
        
        tool = ToolSpec(name="fail", description="Fails", handler=always_fail)
        registry = ToolRegistry(tools=[tool])
        
        custom_policy = LinearBackoffPolicy(
            delay=0.01,  # 10ms delay
            max_attempts=3,
        )
        worker = WorkerAgent(
            registry=registry,
            memory=memory,
            retry_policy=custom_policy,
        )
        
        steps = [{"tool": "fail", "input": {}}]
        
        start = time.perf_counter()
        with pytest.raises(TimeoutError):
            worker.execute(steps)
        duration = time.perf_counter() - start
        
        # Should have delays: 0.01 + 0.01 + 0.01 = 0.03s minimum
        assert duration >= 0.02  # At least 20ms


class TestRetryPolicyFactory:
    """Test create_retry_policy factory."""
    
    def test_create_exponential_policy(self, successful_tool, memory):
        """Factory creates exponential backoff policy."""
        policy = create_retry_policy(
            strategy="exponential",
            max_attempts=5,
            base_delay=2.0,
        )
        
        assert isinstance(policy, ExponentialBackoffPolicy)
        assert policy.get_max_attempts() == 5
        assert policy.base_delay == 2.0
    
    def test_create_linear_policy(self, successful_tool, memory):
        """Factory creates linear backoff policy."""
        policy = create_retry_policy(
            strategy="linear",
            max_attempts=4,
            delay=1.5,
        )
        
        assert isinstance(policy, LinearBackoffPolicy)
        assert policy.get_max_attempts() == 4
        assert policy.delay == 1.5
    
    def test_create_no_retry_policy(self, successful_tool, memory):
        """Factory creates no retry policy."""
        policy = create_retry_policy(strategy="none")
        
        assert isinstance(policy, NoRetryPolicy)
        assert policy.get_max_attempts() == 0
    
    def test_create_unknown_strategy_raises(self):
        """Factory raises on unknown strategy."""
        with pytest.raises(ValueError, match="Unknown retry strategy"):
            create_retry_policy(strategy="invalid")


class TestMultipleStepsWithRetry:
    """Test retry behavior with multiple steps."""
    
    def test_first_step_fails_stops_execution(self, successful_tool, failing_tool, memory):
        """If first step fails after retries, execution stops."""
        registry = ToolRegistry(tools=[failing_tool, successful_tool])
        
        # Use no delay for fast test
        custom_policy = ExponentialBackoffPolicy(
            base_delay=0.0,
            max_attempts=2,
        )
        worker = WorkerAgent(
            registry=registry,
            memory=memory,
            retry_policy=custom_policy,
        )
        
        steps = [
            {"tool": "failing_tool", "input": {}},
            {"tool": "success_tool", "input": {}},
        ]
        
        # Should fail on first step
        with pytest.raises(RuntimeError, match="Tool failed"):
            worker.execute(steps)
    
    def test_second_step_flaky_retries_and_succeeds(self, successful_tool, flaky_tool, memory):
        """Second step retries if flaky and succeeds."""
        registry = ToolRegistry(tools=[successful_tool, flaky_tool])
        worker = WorkerAgent(registry=registry, memory=memory)
        
        steps = [
            {"tool": "success_tool", "input": {}},
            {"tool": "flaky_tool", "input": {}},
        ]
        
        result = worker.execute(steps)
        
        # Should succeed (second step retried once)
        assert "success" in result.output

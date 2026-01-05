"""
Tests for Failure Modes and Retry Semantics

Validates failure taxonomy, retry policies, partial results, and integration
with orchestrator error propagation.
"""

import asyncio
import pytest
from unittest.mock import Mock, AsyncMock

from cuga.orchestrator.failures import (
    FailureMode,
    FailureCategory,
    FailureSeverity,
    FailureContext,
    PartialResult,
    RetryPolicy,
    ExponentialBackoffPolicy,
    LinearBackoffPolicy,
    NoRetryPolicy,
    RetryExecutor,
    create_retry_policy,
)
from cuga.orchestrator.protocol import (
    LifecycleStage,
    ExecutionContext,
    OrchestrationError,
)


class TestFailureMode:
    """Test FailureMode enum and properties."""
    
    def test_agent_failure_category(self):
        """Test agent failure modes have AGENT category."""
        agent_modes = [
            FailureMode.AGENT_VALIDATION,
            FailureMode.AGENT_TIMEOUT,
            FailureMode.AGENT_LOGIC,
            FailureMode.AGENT_CONTRACT,
            FailureMode.AGENT_STATE,
        ]
        
        for mode in agent_modes:
            assert mode.category == FailureCategory.AGENT
    
    def test_system_failure_category(self):
        """Test system failure modes have SYSTEM category."""
        system_modes = [
            FailureMode.SYSTEM_NETWORK,
            FailureMode.SYSTEM_TIMEOUT,
            FailureMode.SYSTEM_CRASH,
            FailureMode.SYSTEM_OOM,
            FailureMode.SYSTEM_DISK,
        ]
        
        for mode in system_modes:
            assert mode.category == FailureCategory.SYSTEM
    
    def test_resource_failure_category(self):
        """Test resource failure modes have RESOURCE category."""
        resource_modes = [
            FailureMode.RESOURCE_TOOL_UNAVAILABLE,
            FailureMode.RESOURCE_API_UNAVAILABLE,
            FailureMode.RESOURCE_MEMORY_FULL,
            FailureMode.RESOURCE_QUOTA,
            FailureMode.RESOURCE_CIRCUIT_OPEN,
        ]
        
        for mode in resource_modes:
            assert mode.category == FailureCategory.RESOURCE
    
    def test_policy_failure_category(self):
        """Test policy failure modes have POLICY category."""
        policy_modes = [
            FailureMode.POLICY_SECURITY,
            FailureMode.POLICY_BUDGET,
            FailureMode.POLICY_ALLOWLIST,
            FailureMode.POLICY_RATE_LIMIT,
        ]
        
        for mode in policy_modes:
            assert mode.category == FailureCategory.POLICY
    
    def test_retryable_modes(self):
        """Test retryable failure modes."""
        retryable = [
            FailureMode.SYSTEM_NETWORK,
            FailureMode.SYSTEM_TIMEOUT,
            FailureMode.RESOURCE_TOOL_UNAVAILABLE,
            FailureMode.RESOURCE_API_UNAVAILABLE,
            FailureMode.RESOURCE_CIRCUIT_OPEN,
            FailureMode.POLICY_RATE_LIMIT,
            FailureMode.AGENT_TIMEOUT,
            FailureMode.PARTIAL_TIMEOUT,
        ]
        
        for mode in retryable:
            assert mode.retryable is True, f"{mode} should be retryable"
    
    def test_terminal_modes(self):
        """Test terminal failure modes."""
        terminal = [
            FailureMode.POLICY_SECURITY,
            FailureMode.POLICY_BUDGET,
            FailureMode.POLICY_ALLOWLIST,
            FailureMode.SYSTEM_CRASH,
            FailureMode.SYSTEM_OOM,
            FailureMode.USER_CANCELLED,
            FailureMode.AGENT_CONTRACT,
        ]
        
        for mode in terminal:
            assert mode.terminal is True, f"{mode} should be terminal"
    
    def test_partial_results_possible(self):
        """Test modes where partial results possible."""
        partial_possible = [
            FailureMode.AGENT_TIMEOUT,
            FailureMode.SYSTEM_TIMEOUT,
            FailureMode.RESOURCE_QUOTA,
            FailureMode.PARTIAL_TOOL_FAILURES,
            FailureMode.PARTIAL_STEP_FAILURES,
            FailureMode.PARTIAL_TIMEOUT,
        ]
        
        for mode in partial_possible:
            assert mode.partial_results_possible is True
    
    def test_severity_classification(self):
        """Test severity classification."""
        # Terminal = CRITICAL
        assert FailureMode.POLICY_SECURITY.severity == FailureSeverity.CRITICAL
        assert FailureMode.SYSTEM_CRASH.severity == FailureSeverity.CRITICAL
        
        # System = HIGH
        assert FailureMode.SYSTEM_NETWORK.severity == FailureSeverity.HIGH
        assert FailureMode.SYSTEM_TIMEOUT.severity == FailureSeverity.HIGH
        
        # Resource/Policy = MEDIUM
        assert FailureMode.RESOURCE_TOOL_UNAVAILABLE.severity == FailureSeverity.MEDIUM
        assert FailureMode.POLICY_RATE_LIMIT.severity == FailureSeverity.MEDIUM
        
        # Agent/User = LOW
        assert FailureMode.AGENT_VALIDATION.severity == FailureSeverity.LOW
        assert FailureMode.USER_INVALID_INPUT.severity == FailureSeverity.LOW


class TestPartialResult:
    """Test PartialResult representation."""
    
    def test_completion_ratio(self):
        """Test completion ratio calculation."""
        partial = PartialResult(
            completed_steps=["step1", "step2"],
            failed_steps=["step3"],
            partial_data={"step1": "result1", "step2": "result2"},
            failure_mode=FailureMode.PARTIAL_TIMEOUT,
        )
        
        assert partial.completion_ratio == pytest.approx(0.67, rel=0.01)
    
    def test_completion_ratio_all_failed(self):
        """Test completion ratio when all failed."""
        partial = PartialResult(
            completed_steps=[],
            failed_steps=["step1", "step2"],
            partial_data={},
            failure_mode=FailureMode.PARTIAL_TOOL_FAILURES,
        )
        
        assert partial.completion_ratio == 0.0
    
    def test_completion_ratio_all_succeeded(self):
        """Test completion ratio when all succeeded."""
        partial = PartialResult(
            completed_steps=["step1", "step2"],
            failed_steps=[],
            partial_data={"step1": "result1", "step2": "result2"},
            failure_mode=FailureMode.PARTIAL_TIMEOUT,
        )
        
        assert partial.completion_ratio == 1.0
    
    def test_is_recoverable_retryable_with_progress(self):
        """Test recoverable when retryable mode and progress."""
        partial = PartialResult(
            completed_steps=["step1"],
            failed_steps=["step2"],
            partial_data={"step1": "result1"},
            failure_mode=FailureMode.PARTIAL_TIMEOUT,  # Retryable
        )
        
        assert partial.is_recoverable is True
    
    def test_not_recoverable_terminal_mode(self):
        """Test not recoverable when terminal mode."""
        partial = PartialResult(
            completed_steps=["step1"],
            failed_steps=["step2"],
            partial_data={"step1": "result1"},
            failure_mode=FailureMode.POLICY_BUDGET,  # Terminal, not retryable
        )
        
        # Terminal mode is not retryable
        assert partial.failure_mode.retryable is False
        assert partial.is_recoverable is False
    
    def test_to_dict(self):
        """Test partial result serialization."""
        partial = PartialResult(
            completed_steps=["step1"],
            failed_steps=["step2"],
            partial_data={"step1": "result1"},
            failure_mode=FailureMode.PARTIAL_TIMEOUT,
            recovery_strategy="retry_failed",
            metadata={"attempt": 1},
        )
        
        result_dict = partial.to_dict()
        
        assert result_dict["completed_steps"] == ["step1"]
        assert result_dict["failed_steps"] == ["step2"]
        assert result_dict["partial_data"] == {"step1": "result1"}
        assert result_dict["failure_mode"] == "partial_timeout"
        assert result_dict["completion_ratio"] == 0.5
        assert result_dict["recovery_strategy"] == "retry_failed"
        assert result_dict["metadata"] == {"attempt": 1}


class TestFailureContext:
    """Test FailureContext creation and conversion."""
    
    def test_from_exception_auto_detect_timeout(self):
        """Test auto-detection of timeout errors."""
        exc = asyncio.TimeoutError("Operation timed out")
        
        failure = FailureContext.from_exception(
            exc=exc,
            stage=LifecycleStage.EXECUTE,
            context=ExecutionContext(trace_id="test123"),
        )
        
        assert failure.mode == FailureMode.SYSTEM_TIMEOUT
        assert failure.stage == LifecycleStage.EXECUTE
        assert failure.message == "Operation timed out"
        assert failure.cause is exc
        assert failure.execution_context.trace_id == "test123"
    
    def test_from_exception_auto_detect_network(self):
        """Test auto-detection of network errors."""
        exc = ConnectionError("Network unreachable")
        
        failure = FailureContext.from_exception(
            exc=exc,
            stage=LifecycleStage.ROUTE,
        )
        
        assert failure.mode == FailureMode.SYSTEM_NETWORK
    
    def test_from_exception_auto_detect_validation(self):
        """Test auto-detection of validation errors."""
        exc = ValueError("Invalid input: missing required field")
        
        failure = FailureContext.from_exception(
            exc=exc,
            stage=LifecycleStage.PLAN,
        )
        
        assert failure.mode == FailureMode.AGENT_VALIDATION
    
    def test_from_exception_auto_detect_rate_limit(self):
        """Test auto-detection of rate limit errors."""
        exc = Exception("Rate limit exceeded: too many requests")
        
        failure = FailureContext.from_exception(
            exc=exc,
            stage=LifecycleStage.EXECUTE,
        )
        
        assert failure.mode == FailureMode.POLICY_RATE_LIMIT
    
    def test_from_exception_auto_detect_circuit(self):
        """Test auto-detection of circuit breaker errors."""
        exc = RuntimeError("Circuit breaker is open")
        
        failure = FailureContext.from_exception(
            exc=exc,
            stage=LifecycleStage.EXECUTE,
        )
        
        assert failure.mode == FailureMode.RESOURCE_CIRCUIT_OPEN
    
    def test_from_exception_explicit_mode(self):
        """Test explicit failure mode overrides auto-detection."""
        exc = RuntimeError("Some error")
        
        failure = FailureContext.from_exception(
            exc=exc,
            stage=LifecycleStage.EXECUTE,
            mode=FailureMode.RESOURCE_API_UNAVAILABLE,
        )
        
        assert failure.mode == FailureMode.RESOURCE_API_UNAVAILABLE
    
    def test_to_orchestration_error(self):
        """Test conversion to OrchestrationError."""
        context = ExecutionContext(trace_id="test123")
        
        failure = FailureContext(
            mode=FailureMode.SYSTEM_NETWORK,
            stage=LifecycleStage.EXECUTE,
            message="Network failure",
            cause=ConnectionError("Connection refused"),
            execution_context=context,
            retry_count=2,
        )
        
        error = failure.to_orchestration_error()
        
        assert isinstance(error, OrchestrationError)
        assert error.stage == LifecycleStage.EXECUTE
        assert error.message == "Network failure"
        assert error.recoverable is True  # SYSTEM_NETWORK is retryable
        assert error.metadata["failure_mode"] == "system_network"
        assert error.metadata["category"] == "system"
        assert error.metadata["severity"] == "high"
        assert error.metadata["retry_count"] == 2


class TestRetryPolicies:
    """Test retry policy implementations."""
    
    def test_exponential_backoff_delays(self):
        """Test exponential backoff delay calculation."""
        policy = ExponentialBackoffPolicy(
            base_delay=1.0,
            multiplier=2.0,
            jitter=0.0,  # No jitter for deterministic test
            max_attempts=3,
        )
        
        assert policy.get_delay(0) == 1.0
        assert policy.get_delay(1) == 2.0
        assert policy.get_delay(2) == 4.0
        assert policy.get_delay(3) == 8.0
    
    def test_exponential_backoff_max_delay(self):
        """Test exponential backoff respects max delay."""
        policy = ExponentialBackoffPolicy(
            base_delay=10.0,
            multiplier=3.0,
            max_delay=50.0,
            jitter=0.0,
            max_attempts=5,
        )
        
        assert policy.get_delay(0) == 10.0   # 10 * 3^0 = 10
        assert policy.get_delay(1) == 30.0   # 10 * 3^1 = 30
        assert policy.get_delay(2) == 50.0   # 10 * 3^2 = 90 → capped at 50
        assert policy.get_delay(3) == 50.0   # Still capped
    
    def test_exponential_backoff_jitter(self):
        """Test exponential backoff applies jitter."""
        policy = ExponentialBackoffPolicy(
            base_delay=10.0,
            jitter=0.2,  # 20% jitter
            max_attempts=3,
        )
        
        delay = policy.get_delay(0)
        
        # Should be 10.0 ± 2.0 (20% of 10.0)
        assert 8.0 <= delay <= 12.0
    
    def test_exponential_backoff_should_retry_retryable_mode(self):
        """Test exponential backoff retries retryable modes."""
        policy = ExponentialBackoffPolicy(max_attempts=3)
        
        failure = FailureContext(
            mode=FailureMode.SYSTEM_NETWORK,  # Retryable
            stage=LifecycleStage.EXECUTE,
            message="Network error",
            retry_count=0,
        )
        
        assert policy.should_retry(failure) is True
    
    def test_exponential_backoff_should_not_retry_terminal_mode(self):
        """Test exponential backoff doesn't retry terminal modes."""
        policy = ExponentialBackoffPolicy(max_attempts=3)
        
        failure = FailureContext(
            mode=FailureMode.POLICY_SECURITY,  # Terminal
            stage=LifecycleStage.EXECUTE,
            message="Security violation",
            retry_count=0,
        )
        
        assert policy.should_retry(failure) is False
    
    def test_exponential_backoff_max_attempts_exhausted(self):
        """Test exponential backoff stops after max attempts."""
        policy = ExponentialBackoffPolicy(max_attempts=3)
        
        failure = FailureContext(
            mode=FailureMode.SYSTEM_NETWORK,
            stage=LifecycleStage.EXECUTE,
            message="Network error",
            retry_count=3,  # Already at max
        )
        
        assert policy.should_retry(failure) is False
    
    def test_linear_backoff_delay(self):
        """Test linear backoff fixed delay."""
        policy = LinearBackoffPolicy(delay=5.0, max_attempts=3)
        
        assert policy.get_delay(0) == 5.0
        assert policy.get_delay(1) == 5.0
        assert policy.get_delay(2) == 5.0
    
    def test_no_retry_policy(self):
        """Test no retry policy never retries."""
        policy = NoRetryPolicy()
        
        failure = FailureContext(
            mode=FailureMode.SYSTEM_NETWORK,  # Even retryable mode
            stage=LifecycleStage.EXECUTE,
            message="Network error",
            retry_count=0,
        )
        
        assert policy.should_retry(failure) is False
        assert policy.get_max_attempts() == 0
    
    def test_create_retry_policy_exponential(self):
        """Test factory creates exponential policy."""
        policy = create_retry_policy(
            strategy="exponential",
            max_attempts=5,
            base_delay=0.5,
            multiplier=1.5,
        )
        
        assert isinstance(policy, ExponentialBackoffPolicy)
        assert policy.max_attempts == 5
        assert policy.base_delay == 0.5
        assert policy.multiplier == 1.5
    
    def test_create_retry_policy_linear(self):
        """Test factory creates linear policy."""
        policy = create_retry_policy(
            strategy="linear",
            max_attempts=3,
            delay=2.0,
        )
        
        assert isinstance(policy, LinearBackoffPolicy)
        assert policy.max_attempts == 3
        assert policy.delay == 2.0
    
    def test_create_retry_policy_none(self):
        """Test factory creates no retry policy."""
        policy = create_retry_policy(strategy="none")
        
        assert isinstance(policy, NoRetryPolicy)
    
    def test_create_retry_policy_unknown_strategy(self):
        """Test factory raises on unknown strategy."""
        with pytest.raises(ValueError, match="Unknown retry strategy"):
            create_retry_policy(strategy="invalid")


class TestRetryExecutor:
    """Test RetryExecutor integration."""
    
    @pytest.mark.asyncio
    async def test_execute_success_first_attempt(self):
        """Test successful execution on first attempt."""
        policy = ExponentialBackoffPolicy(max_attempts=3)
        executor = RetryExecutor(policy)
        
        call_count = 0
        
        async def operation():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await executor.execute_with_retry(
            operation=operation,
            stage=LifecycleStage.EXECUTE,
            context=ExecutionContext(trace_id="test"),
            operation_name="test_op",
        )
        
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_execute_success_after_retries(self):
        """Test successful execution after retries."""
        policy = ExponentialBackoffPolicy(
            max_attempts=3,
            base_delay=0.01,  # Fast retries for test
        )
        executor = RetryExecutor(policy)
        
        call_count = 0
        
        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Transient network error")
            return "success"
        
        result = await executor.execute_with_retry(
            operation=flaky_operation,
            stage=LifecycleStage.EXECUTE,
            context=ExecutionContext(trace_id="test"),
            operation_name="flaky_op",
        )
        
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_execute_all_retries_exhausted(self):
        """Test failure after all retries exhausted."""
        policy = ExponentialBackoffPolicy(
            max_attempts=2,
            base_delay=0.01,
        )
        executor = RetryExecutor(policy)
        
        call_count = 0
        
        async def failing_operation():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Persistent network error")
        
        with pytest.raises(OrchestrationError) as exc_info:
            await executor.execute_with_retry(
                operation=failing_operation,
                stage=LifecycleStage.EXECUTE,
                context=ExecutionContext(trace_id="test"),
                operation_name="failing_op",
            )
        
        # Should try: initial + 2 retries = 3 total
        assert call_count == 3
        
        error = exc_info.value
        assert "network" in error.message.lower()
        assert error.metadata["retry_count"] == 2
    
    @pytest.mark.asyncio
    async def test_execute_terminal_failure_no_retry(self):
        """Test terminal failure stops immediately."""
        policy = ExponentialBackoffPolicy(max_attempts=3)
        executor = RetryExecutor(policy)
        
        call_count = 0
        
        async def terminal_operation():
            nonlocal call_count
            call_count += 1
            # Validation error is not retryable
            raise ValueError("Invalid input: missing required field")
        
        with pytest.raises(OrchestrationError) as exc_info:
            await executor.execute_with_retry(
                operation=terminal_operation,
                stage=LifecycleStage.EXECUTE,
                context=ExecutionContext(trace_id="test"),
                operation_name="terminal_op",
            )
        
        # Should fail immediately (no retries)
        assert call_count == 1
        
        error = exc_info.value
        assert error.metadata["failure_mode"] == "agent_validation"
        assert error.metadata["retry_count"] == 0
    
    @pytest.mark.asyncio
    async def test_execute_sync_operation(self):
        """Test executor handles sync operations."""
        policy = ExponentialBackoffPolicy(max_attempts=3)
        executor = RetryExecutor(policy)
        
        def sync_operation():
            return "sync_result"
        
        # Should not raise
        result = await executor.execute_with_retry(
            operation=sync_operation,
            stage=LifecycleStage.EXECUTE,
            context=ExecutionContext(trace_id="test"),
            operation_name="sync_op",
        )
        
        assert result == "sync_result"


class TestRetryCompliance:
    """Test retry policy compliance with orchestrator integration."""
    
    def test_retry_policy_respects_mode_retryable(self):
        """Test all retry policies respect mode.retryable property."""
        policies = [
            ExponentialBackoffPolicy(max_attempts=3),
            LinearBackoffPolicy(max_attempts=3),
        ]
        
        retryable_failure = FailureContext(
            mode=FailureMode.SYSTEM_NETWORK,
            stage=LifecycleStage.EXECUTE,
            message="Network error",
            retry_count=0,
        )
        
        non_retryable_failure = FailureContext(
            mode=FailureMode.AGENT_VALIDATION,
            stage=LifecycleStage.EXECUTE,
            message="Validation error",
            retry_count=0,
        )
        
        for policy in policies:
            assert policy.should_retry(retryable_failure) is True
            assert policy.should_retry(non_retryable_failure) is False
    
    def test_failure_mode_consistency(self):
        """Test failure mode properties are consistent."""
        for mode in FailureMode:
            # Terminal modes should be critical severity
            if mode.terminal:
                assert mode.severity == FailureSeverity.CRITICAL
            
            # Terminal modes should not be retryable
            if mode.terminal and mode != FailureMode.PARTIAL_TIMEOUT:
                assert mode.retryable is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

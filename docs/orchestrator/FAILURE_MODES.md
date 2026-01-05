# Failure Modes and Retry Semantics

**Status**: Canonical  
**Last Updated**: 2025-12-31  
**Owner**: Orchestrator Team

## Problem Statement

### Before: Unclear Failure Handling

```
Failures not categorized
   ├── Agent error? System error?
   ├── Retryable? Terminal?
   └── Partial success?

Orchestrator cannot decide:
   ├── Should I retry?
   ├── Can I continue?
   └── Are there partial results?

Impact:
   ├── Over-retrying transient errors
   ├── Swallowing recoverable failures
   └── Losing partial results
```

### After: Clear Failure Taxonomy

```
FailureMode Classification
   ├── Category: AGENT | SYSTEM | RESOURCE | POLICY | USER
   ├── Retryable: bool (can retry)
   ├── Terminal: bool (must stop)
   ├── Partial Results: bool (may have data)
   └── Severity: LOW | MEDIUM | HIGH | CRITICAL

Orchestrator knows:
   ├── Retry with ExponentialBackoff (transient errors)
   ├── Stop execution (terminal failures)
   ├── Preserve partial results (timeout/quota)
   └── Escalate critical failures
```

## Core Components

### 1. FailureMode Enum

Comprehensive failure taxonomy with automatic classification:

```python
from cuga.orchestrator.failures import FailureMode, FailureCategory

# Agent errors (validation/logic)
FailureMode.AGENT_VALIDATION      # Input validation failed
FailureMode.AGENT_TIMEOUT         # Agent exceeded timeout (retryable)
FailureMode.AGENT_LOGIC           # Agent logic error
FailureMode.AGENT_CONTRACT        # I/O contract violation (terminal)
FailureMode.AGENT_STATE           # Invalid agent state

# System errors (infrastructure)
FailureMode.SYSTEM_NETWORK        # Network connectivity (retryable)
FailureMode.SYSTEM_TIMEOUT        # System timeout (retryable)
FailureMode.SYSTEM_CRASH          # Process crash (terminal)
FailureMode.SYSTEM_OOM            # Out of memory (terminal)
FailureMode.SYSTEM_DISK           # Disk space/IO

# Resource errors (availability)
FailureMode.RESOURCE_TOOL_UNAVAILABLE   # Tool unavailable (retryable)
FailureMode.RESOURCE_API_UNAVAILABLE    # API unavailable (retryable)
FailureMode.RESOURCE_MEMORY_FULL        # Memory full
FailureMode.RESOURCE_QUOTA              # Quota exceeded
FailureMode.RESOURCE_CIRCUIT_OPEN       # Circuit breaker open (retryable)

# Policy errors (security/constraints)
FailureMode.POLICY_SECURITY       # Security violation (terminal)
FailureMode.POLICY_BUDGET         # Budget exceeded (terminal)
FailureMode.POLICY_ALLOWLIST      # Allowlist violation (terminal)
FailureMode.POLICY_RATE_LIMIT     # Rate limit (retryable)

# User errors (input/cancellation)
FailureMode.USER_INVALID_INPUT    # Invalid user input
FailureMode.USER_CANCELLED        # User cancellation (terminal)
FailureMode.USER_PERMISSION       # Permission denied

# Partial success states
FailureMode.PARTIAL_TOOL_FAILURES # Some tools failed
FailureMode.PARTIAL_STEP_FAILURES # Some steps failed
FailureMode.PARTIAL_TIMEOUT       # Partial completion before timeout

# Properties
mode = FailureMode.SYSTEM_NETWORK
mode.category         # FailureCategory.SYSTEM
mode.retryable        # True
mode.terminal         # False
mode.partial_results_possible  # False
mode.severity         # FailureSeverity.HIGH
```

### 2. FailureContext

Comprehensive failure context with auto-detection:

```python
from cuga.orchestrator.failures import FailureContext, PartialResult
from cuga.orchestrator.protocol import LifecycleStage, ExecutionContext

# Create from exception (auto-detects mode)
try:
    result = await agent.process(request)
except Exception as exc:
    failure = FailureContext.from_exception(
        exc=exc,
        stage=LifecycleStage.EXECUTE,
        context=execution_context,
        mode=None,  # Auto-detect from exception
    )
    
    # Access failure properties
    failure.mode                    # FailureMode (auto-detected)
    failure.mode.retryable          # Should retry?
    failure.mode.terminal           # Should stop?
    failure.retry_count             # Current attempt
    failure.stack_trace             # Debug trace
    
    # Convert to OrchestrationError
    error = failure.to_orchestration_error()
    raise error

# Create with partial results
partial = PartialResult(
    completed_steps=["step1", "step2"],
    failed_steps=["step3"],
    partial_data={"step1": "result1", "step2": "result2"},
    failure_mode=FailureMode.PARTIAL_TIMEOUT,
    recovery_strategy="retry_failed_steps",
)

failure = FailureContext(
    mode=FailureMode.PARTIAL_TIMEOUT,
    stage=LifecycleStage.EXECUTE,
    message="Execution timed out with partial results",
    partial_result=partial,
    execution_context=context,
)

# Check partial result properties
partial.completion_ratio    # 0.67 (2/3 completed)
partial.is_recoverable      # True (retryable + progress)
```

### 3. RetryPolicy

Pluggable retry strategies:

```python
from cuga.orchestrator.failures import (
    RetryPolicy,
    ExponentialBackoffPolicy,
    LinearBackoffPolicy,
    NoRetryPolicy,
    create_retry_policy,
)

# Exponential backoff (default)
policy = ExponentialBackoffPolicy(
    base_delay=1.0,      # Start at 1s
    max_delay=60.0,      # Cap at 60s
    multiplier=2.0,      # Double each time
    jitter=0.1,          # 10% random jitter
    max_attempts=3,      # Max 3 retries
    retryable_modes=None,  # Use mode.retryable (default)
)

# Delays: 1s, 2s, 4s (with jitter)
policy.get_delay(0)  # ~1.0s ± 0.1s
policy.get_delay(1)  # ~2.0s ± 0.2s
policy.get_delay(2)  # ~4.0s ± 0.4s

# Linear backoff
policy = LinearBackoffPolicy(
    delay=2.0,           # Fixed 2s delay
    max_attempts=3,
)

# No retry (fail-fast)
policy = NoRetryPolicy()

# Factory function
policy = create_retry_policy(
    strategy="exponential",
    max_attempts=5,
    base_delay=0.5,
    multiplier=1.5,
)
```

### 4. RetryExecutor

Execute operations with retry logic:

```python
from cuga.orchestrator.failures import (
    RetryExecutor,
    ExponentialBackoffPolicy,
    FailureMode,
)
from cuga.orchestrator.protocol import LifecycleStage

# Create executor with policy
policy = ExponentialBackoffPolicy(max_attempts=3)
executor = RetryExecutor(policy)

# Execute with automatic retry
async def risky_operation():
    response = await external_api.call()
    if not response.ok:
        raise RuntimeError(f"API error: {response.error}")
    return response.data

try:
    result = await executor.execute_with_retry(
        operation=risky_operation,
        stage=LifecycleStage.EXECUTE,
        context=execution_context,
        operation_name="external_api_call",
    )
except OrchestrationError as err:
    # All retries exhausted or terminal failure
    print(f"Failed: {err.message}")
    print(f"Mode: {err.metadata['failure_mode']}")
    print(f"Retries: {err.metadata['retry_count']}")
```

## Integration with OrchestratorProtocol

### Error Propagation with Retry

```python
from cuga.orchestrator.protocol import (
    OrchestratorProtocol,
    ErrorPropagation,
    ExecutionContext,
)
from cuga.orchestrator.failures import (
    RetryExecutor,
    ExponentialBackoffPolicy,
    FailureMode,
)

class SmartOrchestrator(OrchestratorProtocol):
    def __init__(self):
        # Create retry executor
        retry_policy = ExponentialBackoffPolicy(max_attempts=3)
        self.retry_executor = RetryExecutor(retry_policy)
    
    async def execute(
        self,
        context: ExecutionContext,
        error_strategy: ErrorPropagation = ErrorPropagation.FAIL_FAST,
    ) -> Dict[str, Any]:
        """Execute with smart retry based on error_strategy."""
        
        # Map ErrorPropagation to retry behavior
        if error_strategy == ErrorPropagation.RETRY:
            # Use retry executor
            return await self.retry_executor.execute_with_retry(
                operation=lambda: self._execute_internal(context),
                stage=LifecycleStage.EXECUTE,
                context=context,
                operation_name="orchestration_execute",
            )
        
        elif error_strategy == ErrorPropagation.FAIL_FAST:
            # No retry
            return await self._execute_internal(context)
        
        elif error_strategy == ErrorPropagation.CONTINUE:
            # Try without retry, log on error
            try:
                return await self._execute_internal(context)
            except OrchestrationError as err:
                logger.warning(f"Continuing despite error: {err}")
                return {"status": "partial", "error": str(err)}
    
    async def _execute_internal(
        self,
        context: ExecutionContext,
    ) -> Dict[str, Any]:
        """Internal execution (may raise OrchestrationError)."""
        # ... actual execution logic
        pass
```

### Handling Partial Results

```python
from cuga.orchestrator.failures import PartialResult, FailureMode

async def execute_with_partial_results(
    self,
    context: ExecutionContext,
) -> Dict[str, Any]:
    """Execute with partial result handling."""
    
    try:
        return await self.execute_all_steps(context)
    
    except OrchestrationError as err:
        # Check for partial results
        partial = err.metadata.get("partial_result")
        
        if partial and isinstance(partial, dict):
            # Reconstruct PartialResult
            partial_result = PartialResult(
                completed_steps=partial["completed_steps"],
                failed_steps=partial["failed_steps"],
                partial_data=partial["partial_data"],
                failure_mode=FailureMode(partial["failure_mode"]),
            )
            
            # Decide on recovery
            if partial_result.is_recoverable:
                # Retry only failed steps
                return await self.retry_failed_steps(
                    partial_result,
                    context,
                )
            else:
                # Return partial results to user
                return {
                    "status": "partial_success",
                    "completed": partial_result.partial_data,
                    "failed": partial_result.failed_steps,
                    "completion_ratio": partial_result.completion_ratio,
                }
        
        # No partial results, propagate
        raise
```

## Failure Mode Decision Matrix

| Failure Mode | Category | Retryable | Terminal | Partial Results | Severity |
|--------------|----------|-----------|----------|-----------------|----------|
| `AGENT_VALIDATION` | AGENT | ❌ | ❌ | ❌ | LOW |
| `AGENT_TIMEOUT` | AGENT | ✅ | ❌ | ✅ | MEDIUM |
| `AGENT_LOGIC` | AGENT | ❌ | ❌ | ❌ | LOW |
| `AGENT_CONTRACT` | AGENT | ❌ | ✅ | ❌ | CRITICAL |
| `AGENT_STATE` | AGENT | ❌ | ❌ | ❌ | MEDIUM |
| `SYSTEM_NETWORK` | SYSTEM | ✅ | ❌ | ❌ | HIGH |
| `SYSTEM_TIMEOUT` | SYSTEM | ✅ | ❌ | ✅ | HIGH |
| `SYSTEM_CRASH` | SYSTEM | ❌ | ✅ | ❌ | CRITICAL |
| `SYSTEM_OOM` | SYSTEM | ❌ | ✅ | ❌ | CRITICAL |
| `SYSTEM_DISK` | SYSTEM | ❌ | ❌ | ❌ | HIGH |
| `RESOURCE_TOOL_UNAVAILABLE` | RESOURCE | ✅ | ❌ | ❌ | MEDIUM |
| `RESOURCE_API_UNAVAILABLE` | RESOURCE | ✅ | ❌ | ❌ | MEDIUM |
| `RESOURCE_MEMORY_FULL` | RESOURCE | ❌ | ❌ | ✅ | MEDIUM |
| `RESOURCE_QUOTA` | RESOURCE | ❌ | ❌ | ✅ | MEDIUM |
| `RESOURCE_CIRCUIT_OPEN` | RESOURCE | ✅ | ❌ | ❌ | MEDIUM |
| `POLICY_SECURITY` | POLICY | ❌ | ✅ | ❌ | CRITICAL |
| `POLICY_BUDGET` | POLICY | ❌ | ✅ | ❌ | CRITICAL |
| `POLICY_ALLOWLIST` | POLICY | ❌ | ✅ | ❌ | CRITICAL |
| `POLICY_RATE_LIMIT` | POLICY | ✅ | ❌ | ❌ | MEDIUM |
| `USER_INVALID_INPUT` | USER | ❌ | ❌ | ❌ | LOW |
| `USER_CANCELLED` | USER | ❌ | ✅ | ❌ | LOW |
| `USER_PERMISSION` | USER | ❌ | ❌ | ❌ | MEDIUM |
| `PARTIAL_TOOL_FAILURES` | AGENT | ❌ | ❌ | ✅ | MEDIUM |
| `PARTIAL_STEP_FAILURES` | AGENT | ❌ | ❌ | ✅ | MEDIUM |
| `PARTIAL_TIMEOUT` | AGENT | ✅ | ❌ | ✅ | MEDIUM |

## Retry Strategies Comparison

| Strategy | Use Case | Delay Pattern | Jitter | Max Attempts |
|----------|----------|---------------|--------|--------------|
| **ExponentialBackoff** | Network errors, rate limits | 1s → 2s → 4s → 8s | ✅ | Configurable |
| **LinearBackoff** | Predictable retries | 2s → 2s → 2s | ❌ | Configurable |
| **NoRetry** | Fail-fast scenarios | N/A | ❌ | 0 |

### When to Use Each Strategy

**ExponentialBackoff** (Recommended Default):
- Network connectivity issues
- Rate limit errors (with jitter to avoid thundering herd)
- Resource temporarily unavailable
- Circuit breaker recovery

**LinearBackoff**:
- Deterministic retry timing required
- Testing scenarios
- Short-lived transient errors

**NoRetry**:
- Policy violations (security, budget)
- Contract violations
- User cancellation
- Development/testing (fast feedback)

## Auto-Detection Examples

The `FailureContext.from_exception()` method automatically detects failure modes:

```python
# Network error → SYSTEM_NETWORK
except ConnectionError as exc:
    failure = FailureContext.from_exception(exc, stage, context)
    # failure.mode == FailureMode.SYSTEM_NETWORK (retryable)

# Timeout → SYSTEM_TIMEOUT
except asyncio.TimeoutError as exc:
    failure = FailureContext.from_exception(exc, stage, context)
    # failure.mode == FailureMode.SYSTEM_TIMEOUT (retryable)

# Validation error → AGENT_VALIDATION
except ValueError("Invalid input: ...") as exc:
    failure = FailureContext.from_exception(exc, stage, context)
    # failure.mode == FailureMode.AGENT_VALIDATION (not retryable)

# Rate limit → POLICY_RATE_LIMIT
except Exception("Rate limit exceeded") as exc:
    failure = FailureContext.from_exception(exc, stage, context)
    # failure.mode == FailureMode.POLICY_RATE_LIMIT (retryable)

# Circuit breaker → RESOURCE_CIRCUIT_OPEN
except Exception("Circuit breaker open") as exc:
    failure = FailureContext.from_exception(exc, stage, context)
    # failure.mode == FailureMode.RESOURCE_CIRCUIT_OPEN (retryable)
```

## Integration with MCP Circuit Breaker

The existing MCP `CircuitState` integrates seamlessly:

```python
from cuga.mcp.lifecycle import CircuitState
from cuga.orchestrator.failures import (
    FailureMode,
    FailureContext,
    LifecycleStage,
)

# MCP circuit breaker
circuit = CircuitState(threshold=3, cooldown_s=10.0)

try:
    if not circuit.allow():
        # Circuit open → map to FailureMode
        raise RuntimeError("Circuit breaker open")
    
    result = await mcp_tool.call(request)
    circuit.record_success()

except Exception as exc:
    circuit.record_failure()
    
    # Map to failure mode
    if "circuit" in str(exc).lower():
        mode = FailureMode.RESOURCE_CIRCUIT_OPEN
    else:
        mode = None  # Auto-detect
    
    failure = FailureContext.from_exception(
        exc=exc,
        stage=LifecycleStage.EXECUTE,
        context=context,
        mode=mode,
    )
    
    # Propagate with failure context
    raise failure.to_orchestration_error()
```

## Testing

### Test Failure Mode Properties

```python
def test_failure_mode_classification():
    """Test failure mode automatic classification."""
    
    # Agent timeout is retryable, not terminal
    mode = FailureMode.AGENT_TIMEOUT
    assert mode.category == FailureCategory.AGENT
    assert mode.retryable is True
    assert mode.terminal is False
    assert mode.partial_results_possible is True
    assert mode.severity == FailureSeverity.MEDIUM

def test_failure_mode_terminal():
    """Test terminal failure modes."""
    
    terminal_modes = [
        FailureMode.POLICY_SECURITY,
        FailureMode.POLICY_BUDGET,
        FailureMode.SYSTEM_CRASH,
        FailureMode.USER_CANCELLED,
    ]
    
    for mode in terminal_modes:
        assert mode.terminal is True
        assert mode.severity == FailureSeverity.CRITICAL
```

### Test Retry Policies

```python
import pytest
from cuga.orchestrator.failures import (
    ExponentialBackoffPolicy,
    FailureContext,
    FailureMode,
)

def test_exponential_backoff_delays():
    """Test exponential backoff delay calculation."""
    
    policy = ExponentialBackoffPolicy(
        base_delay=1.0,
        multiplier=2.0,
        jitter=0.0,  # No jitter for deterministic test
        max_attempts=3,
    )
    
    assert policy.get_delay(0) == 1.0  # 1 * 2^0
    assert policy.get_delay(1) == 2.0  # 1 * 2^1
    assert policy.get_delay(2) == 4.0  # 1 * 2^2

def test_retry_policy_respects_mode():
    """Test retry policy respects failure mode retryable property."""
    
    policy = ExponentialBackoffPolicy(max_attempts=3)
    
    # Retryable mode
    retryable_failure = FailureContext(
        mode=FailureMode.SYSTEM_NETWORK,
        stage=LifecycleStage.EXECUTE,
        message="Network error",
        retry_count=0,
    )
    assert policy.should_retry(retryable_failure) is True
    
    # Terminal mode
    terminal_failure = FailureContext(
        mode=FailureMode.POLICY_SECURITY,
        stage=LifecycleStage.EXECUTE,
        message="Security violation",
        retry_count=0,
    )
    assert policy.should_retry(terminal_failure) is False
```

### Test RetryExecutor

```python
@pytest.mark.asyncio
async def test_retry_executor_success_after_retry():
    """Test retry executor succeeds after transient error."""
    
    policy = ExponentialBackoffPolicy(max_attempts=3, base_delay=0.01)
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
        operation_name="flaky_test",
    )
    
    assert result == "success"
    assert call_count == 3  # Failed twice, succeeded third time

@pytest.mark.asyncio
async def test_retry_executor_terminal_failure():
    """Test retry executor stops on terminal failure."""
    
    policy = ExponentialBackoffPolicy(max_attempts=3)
    executor = RetryExecutor(policy)
    
    async def terminal_operation():
        raise ValueError("Policy violation")
    
    with pytest.raises(OrchestrationError) as exc_info:
        await executor.execute_with_retry(
            operation=terminal_operation,
            stage=LifecycleStage.EXECUTE,
            context=ExecutionContext(trace_id="test"),
            operation_name="terminal_test",
        )
    
    # Should fail immediately (no retries on terminal)
    error = exc_info.value
    assert error.metadata["retry_count"] == 0
```

### Test Partial Results

```python
def test_partial_result_completion_ratio():
    """Test partial result completion ratio calculation."""
    
    partial = PartialResult(
        completed_steps=["step1", "step2"],
        failed_steps=["step3"],
        partial_data={"step1": "result1", "step2": "result2"},
        failure_mode=FailureMode.PARTIAL_TIMEOUT,
    )
    
    assert partial.completion_ratio == pytest.approx(0.67, rel=0.01)
    assert partial.is_recoverable is True  # Retryable + progress

def test_partial_result_not_recoverable():
    """Test non-recoverable partial result."""
    
    partial = PartialResult(
        completed_steps=["step1"],
        failed_steps=["step2"],
        partial_data={"step1": "result1"},
        failure_mode=FailureMode.POLICY_BUDGET,  # Not retryable
    )
    
    assert partial.is_recoverable is False  # Terminal mode
```

## FAQ

### Q: How does this relate to OrchestratorProtocol.handle_error()?

**A**: `OrchestratorProtocol.handle_error()` receives `ErrorPropagation` strategy and returns recovery result. With failure modes:

1. **ErrorPropagation.RETRY** → Use `RetryExecutor` with appropriate policy
2. **ErrorPropagation.FAIL_FAST** → Check if `mode.terminal`, raise immediately
3. **ErrorPropagation.CONTINUE** → Log failure, check for partial results
4. **ErrorPropagation.FALLBACK** → Check if `mode.retryable`, attempt fallback

### Q: Should every exception create a FailureContext?

**A**: Use `FailureContext.from_exception()` at orchestrator boundaries (orchestrator entry, agent boundaries, tool execution). Internal exceptions can propagate normally until caught at boundary.

### Q: How do I add a custom FailureMode?

**A**: Extend `FailureMode` enum in `failures.py`:

```python
class FailureMode(str, Enum):
    # ... existing modes
    
    # Custom modes
    CUSTOM_DATABASE = "custom_database"
    CUSTOM_CACHE = "custom_cache"
```

Update `category` property to return appropriate `FailureCategory`.

### Q: Can I override auto-detection of failure modes?

**A**: Yes, pass explicit `mode` to `FailureContext.from_exception()`:

```python
failure = FailureContext.from_exception(
    exc=exc,
    stage=stage,
    context=context,
    mode=FailureMode.RESOURCE_API_UNAVAILABLE,  # Explicit mode
)
```

### Q: How do partial results integrate with agent I/O contracts?

**A**: Agents return `AgentResponse` with `status=PARTIAL`:

```python
from cuga.agents.contracts import AgentResponse, ResponseStatus

# Agent returns partial result
response = AgentResponse(
    status=ResponseStatus.PARTIAL,
    result={
        "completed": partial_result.partial_data,
        "failed": partial_result.failed_steps,
    },
    metadata={
        "failure_mode": partial_result.failure_mode.value,
        "completion_ratio": partial_result.completion_ratio,
    },
)
```

Orchestrator converts to `PartialResult` internally.

### Q: What's the difference between FailureMode and ErrorPropagation?

**A**: 
- **FailureMode**: Categorizes *what* failed (agent error, network error, etc.)
- **ErrorPropagation**: Decides *how* to handle failures (retry, fail-fast, continue)

`FailureMode` informs `ErrorPropagation` decisions. Example: `SYSTEM_NETWORK` (retryable) + `ErrorPropagation.RETRY` → use exponential backoff.

### Q: How do I disable retries for specific agents?

**A**: Use `NoRetryPolicy` or configure orchestrator per-agent:

```python
# Per-agent retry policy
agent_retry_policies = {
    "critical_agent": NoRetryPolicy(),  # Never retry
    "flaky_agent": ExponentialBackoffPolicy(max_attempts=5),  # Aggressive retry
}

# In orchestrator
policy = agent_retry_policies.get(agent_name, default_policy)
executor = RetryExecutor(policy)
```

## Change Management

Failure mode and retry policy changes require:

1. **Update `failures.py`**: Add/modify failure modes or policies
2. **Update tests**: Cover new failure modes and policy behavior
3. **Update this doc**: Document new modes in decision matrix
4. **Update `AGENTS.md`**: Guardrail changes if terminal/retryable semantics change
5. **Update `CHANGELOG.md`**: Record failure taxonomy additions

All changes MUST maintain backward compatibility for existing `FailureMode` values used in logs/metrics.

---

**See Also**:
- `docs/orchestrator/ORCHESTRATOR_CONTRACT.md` - Error propagation integration
- `docs/orchestrator/ROUTING_AUTHORITY.md` - Routing with failure handling
- `docs/agents/AGENT_IO_CONTRACT.md` - Agent error responses
- `src/cuga/orchestrator/failures.py` - Implementation
- `src/cuga/mcp/lifecycle.py` - MCP circuit breaker integration

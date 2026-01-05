# RetryPolicy Integration (v1.3.1)

**Status:** ✅ Complete (Task #4)  
**Tests:** 87/87 passing (18 retry + 69 orchestrator)  
**Date:** 2026-01-03

## Overview

WorkerAgent now integrates comprehensive retry logic for resilient tool execution. Failed tool calls are automatically retried with intelligent failure classification and configurable backoff strategies.

## Architecture

### RetryPolicy Infrastructure

All retry components live in `src/cuga/orchestrator/failures.py`:

#### FailureMode Taxonomy (30+ modes)
- **Agent Errors**: AGENT_VALIDATION, AGENT_TIMEOUT, AGENT_LOGIC, AGENT_CONTRACT, AGENT_STATE
- **System Errors**: SYSTEM_NETWORK, SYSTEM_TIMEOUT, SYSTEM_CRASH, SYSTEM_OOM, SYSTEM_DISK
- **Resource Errors**: RESOURCE_TOOL_UNAVAILABLE, RESOURCE_API_UNAVAILABLE, RESOURCE_MEMORY_FULL, RESOURCE_QUOTA, RESOURCE_CIRCUIT_OPEN
- **Policy Errors**: POLICY_SECURITY, POLICY_BUDGET, POLICY_ALLOWLIST, POLICY_RATE_LIMIT
- **User Errors**: USER_INVALID_INPUT, USER_CANCELLED, USER_PERMISSION
- **Partial Success**: PARTIAL_TOOL_FAILURES, PARTIAL_STEP_FAILURES, PARTIAL_TIMEOUT

Each mode has properties:
- `category`: Agent/System/Resource/Policy/User
- `retryable`: Whether transient failure (bool)
- `terminal`: Whether stops execution (bool)
- `partial_results_possible`: Whether partial outputs exist (bool)
- `severity`: LOW/MEDIUM/HIGH/CRITICAL

#### Retry Strategies

**ExponentialBackoffPolicy** (default):
- base_delay: Starting delay (default 1.0s)
- max_delay: Maximum delay (default 30.0s)
- multiplier: Exponential growth factor (default 2.0x)
- jitter: Random variation (default 0.1 = ±10%)
- max_attempts: Maximum retries (default 3)

**LinearBackoffPolicy**:
- delay: Constant delay between retries
- max_attempts: Maximum retries

**NoRetryPolicy**:
- Fail-fast behavior (0 retries)

#### FailureContext
Auto-classifies exceptions into FailureModes:
- `FailureContext.from_exception(exc, stage, context)` → Detects mode from exception type/message
- Detection heuristics:
  - "timeout" in type/message → SYSTEM_TIMEOUT
  - "connection" in type OR "network" in message → SYSTEM_NETWORK
  - "validation"/"invalid" → AGENT_VALIDATION
  - "rate limit" → POLICY_RATE_LIMIT
  - Default → AGENT_LOGIC

### WorkerAgent Integration

**Field Added:**
```python
retry_policy: Optional[RetryPolicy] = None
```

**Default Initialization** (`__post_init__`):
```python
if self.retry_policy is None:
    self.retry_policy = create_retry_policy(
        strategy="exponential",
        max_attempts=3,
        base_delay=1.0,
        max_delay=30.0,
        multiplier=2.0,
        jitter=0.1,
    )
```

**Retry Helper** (`_execute_tool_with_retry`):
1. Execute tool.handler(tool_input, context)
2. On exception:
   - Create FailureContext.from_exception()
   - Check if terminal (mode.terminal) → raise immediately
   - Check if should_retry(failure_ctx) → raise if exhausted
   - Calculate delay with policy.get_delay(attempt)
   - Sleep for delay
   - Increment attempt
   - Loop
3. Return result on success

**Execute Method Updated:**
```python
# OLD: Direct call
result = tool.handler(tool_input, context)

# NEW: Retry-enabled
result = self._execute_tool_with_retry(
    tool=tool,
    tool_name=tool_name,
    tool_input=tool_input,
    context=context,
    trace_id=trace_id,
)
```

## Retry Behavior

### Retryable Failures (Will Retry)
- SYSTEM_NETWORK (ConnectionError, network errors)
- SYSTEM_TIMEOUT (TimeoutError)
- RESOURCE_TOOL_UNAVAILABLE
- RESOURCE_API_UNAVAILABLE  
- RESOURCE_CIRCUIT_OPEN
- POLICY_RATE_LIMIT
- AGENT_TIMEOUT
- PARTIAL_TIMEOUT

### Terminal Failures (No Retry)
- POLICY_SECURITY (security violations)
- POLICY_BUDGET (budget exceeded)
- POLICY_ALLOWLIST (allowlist violations)
- SYSTEM_CRASH (process crash)
- SYSTEM_OOM (out of memory)
- USER_CANCELLED (user cancellation)
- AGENT_CONTRACT (I/O contract violations)

### Non-Retryable Failures (Fail Fast)
- AGENT_VALIDATION (validation errors)
- AGENT_LOGIC (logic errors, RuntimeError by default)
- USER_INVALID_INPUT

## Usage Examples

### Default Exponential Backoff
```python
from cuga.modular.agents import WorkerAgent
from cuga.modular.tools import ToolRegistry

worker = WorkerAgent(registry=registry, memory=memory)
# Automatically uses ExponentialBackoffPolicy (3 attempts, 1s→2s→4s)

steps = [{"tool": "flaky_api_call", "input": {}}]
result = worker.execute(steps)  # Retries on transient failures
```

### Custom Linear Backoff
```python
from cuga.orchestrator.failures import LinearBackoffPolicy

custom_policy = LinearBackoffPolicy(
    delay=2.0,  # 2s constant delay
    max_attempts=5,
)
worker = WorkerAgent(
    registry=registry, 
    memory=memory,
    retry_policy=custom_policy,
)
```

### No Retry (Fail-Fast)
```python
from cuga.orchestrator.failures import NoRetryPolicy

worker = WorkerAgent(
    registry=registry,
    memory=memory,
    retry_policy=NoRetryPolicy(),
)
```

### Custom Exponential with Longer Delays
```python
from cuga.orchestrator.failures import create_retry_policy

long_backoff = create_retry_policy(
    strategy="exponential",
    max_attempts=5,
    base_delay=2.0,  # Start at 2s
    max_delay=120.0,  # Cap at 2 minutes
    multiplier=3.0,  # Triple each time (2s → 6s → 18s → 54s → 120s)
    jitter=0.2,  # ±20% randomization
)
worker = WorkerAgent(
    registry=registry,
    memory=memory, 
    retry_policy=long_backoff,
)
```

## Testing

### Test Coverage (18 tests, 100% passing)

**TestRetryPolicyIntegration** (4 tests):
- Worker has retry_policy field
- Default policy is ExponentialBackoffPolicy
- Custom policies work
- NoRetryPolicy disables retries

**TestRetryBehavior** (4 tests):
- Successful tools don't retry
- Flaky tools retry and succeed on second attempt
- Failing tools exhaust retries then raise
- Timeout errors retry then fail

**TestFailureClassification** (2 tests):
- TimeoutError → SYSTEM_TIMEOUT (retryable)
- Validation errors → AGENT_VALIDATION (not retried)

**TestRetryDelays** (2 tests):
- Exponential backoff timing (0.01s → 0.02s → 0.04s)
- Linear backoff constant delay

**TestRetryPolicyFactory** (4 tests):
- create_retry_policy("exponential")
- create_retry_policy("linear")
- create_retry_policy("none")
- Unknown strategy raises ValueError

**TestMultipleStepsWithRetry** (2 tests):
- First step failure stops execution
- Second step flaky retries and succeeds

### Running Tests
```bash
# Retry tests only
pytest tests/test_worker_retry.py -v

# Full orchestrator suite (87 tests)
pytest tests/test_coordinator_orchestrator.py \
       tests/test_coordinator_routing.py \
       tests/test_coordinator_planning.py \
       tests/test_worker_retry.py -v
```

## Implementation Details

### Bug Fixed: ConnectionError Classification

**Issue:** ConnectionError was classified as AGENT_LOGIC (not retryable) instead of SYSTEM_NETWORK.

**Root Cause:** Detection logic checked:
```python
elif "network" in exc_type.lower() or "connection" in exc_msg:
```

But:
- `exc_type.lower()` = "connectionerror" (no spaces, doesn't contain "network")
- `exc_msg` = "Temporary network failure" (doesn't contain "connection")

**Fix:** Check for "connection" in exception type:
```python
elif "connection" in exc_type.lower() or "network" in exc_msg or "connection" in exc_msg:
```

This correctly classifies:
- ConnectionError → SYSTEM_NETWORK (retryable)
- TimeoutError → SYSTEM_TIMEOUT (retryable)
- RuntimeError → AGENT_LOGIC (not retryable)

### Observability Integration

Current events emitted by WorkerAgent:
- `tool_call_start`: Before each attempt
- `tool_call_complete`: On success
- `tool_call_error`: On failure

**TODO (Future Enhancement):**
- `retry_attempt`: Before sleeping for backoff delay
- `retry_succeeded`: When retry succeeds after failures
- Include `attempt_number`, `delay_ms`, `failure_mode` in event metadata

### PartialResult Support

WorkerAgent already preserves results per step in `execute()`:
```python
results = []
for step in steps:
    try:
        result = self._execute_tool_with_retry(...)
        results.append(result)
    except Exception as e:
        # Store partial results before raising
        tool_error = e
        break

return AgentResponse(
    status="error" if tool_error else "success",
    output=results[-1] if results else None,
    metadata={
        "partial_results": results,
        "failed_step_index": step_index if tool_error else None,
    }
)
```

**TODO (Task #7):** Enhance with PartialResult dataclass and recovery strategies.

## Integration with Other Components

### CoordinatorAgent
CoordinatorAgent delegates execution to WorkerAgent, which now automatically retries failed tool calls. No changes needed in coordinator routing/planning logic.

### PlanningAuthority
Plans created by PlanningAuthority are executed by WorkerAgent with retry logic. Plan steps remain unchanged; retry is transparent at execution layer.

### RoutingAuthority
Routing decisions are unaffected. If a worker's tool execution fails after exhausting retries, the error propagates to coordinator's error handler (fail-fast/retry/continue strategies).

### AuditTrail (Upcoming - Task #5)
Retry attempts should be recorded to audit trail:
- Decision: "retry_tool_call"
- Reason: "Transient failure (SYSTEM_NETWORK)"
- Alternatives: ["fail_fast"]
- Outcome: "success_after_2_attempts" or "exhausted_retries"

## Configuration

### Environment Variables
None required - retry policy is code-configured via WorkerAgent constructor.

**Future Enhancement:** Support env-based configuration:
```bash
# Example (not yet implemented)
WORKER_RETRY_STRATEGY=exponential
WORKER_RETRY_MAX_ATTEMPTS=5
WORKER_RETRY_BASE_DELAY=2.0
WORKER_RETRY_MAX_DELAY=120.0
```

### Profiles
Retry policies can vary by profile:
```python
# Production: Conservative retries
prod_worker = WorkerAgent(
    retry_policy=create_retry_policy("exponential", max_attempts=3, base_delay=1.0)
)

# Development: Aggressive retries for flaky local services
dev_worker = WorkerAgent(
    retry_policy=create_retry_policy("exponential", max_attempts=10, base_delay=0.5)
)

# Testing: No retries for fast failures
test_worker = WorkerAgent(
    retry_policy=NoRetryPolicy()
)
```

## Performance Characteristics

### Latency Impact

**Default Policy (3 attempts, exponential backoff):**
- Success on first attempt: +0ms overhead (direct execution)
- Success on second attempt: +1s delay (1 retry)
- Success on third attempt: +3s delay (1s + 2s)
- Failure after exhaustion: +7s delay (1s + 2s + 4s)

**Timing Breakdown:**
```
Attempt 0: Execute (fail) → 0ms
  Sleep 1.0s ± 0.1s (jitter)
Attempt 1: Execute (fail) → 1000ms
  Sleep 2.0s ± 0.2s (jitter)  
Attempt 2: Execute (fail) → 3000ms
  Sleep 4.0s ± 0.4s (jitter)
Attempt 3: Execute (fail) → 7000ms
  Raise exception
```

### Throughput

Retries are synchronous per tool call but don't block other workers:
- Single worker: Throughput reduced by retry delays
- Multiple workers (round-robin): Other workers continue while one retries
- Coordinator with 3 workers: ~3x throughput during retries

### Resource Usage

**CPU:** Minimal overhead (FailureContext creation, backoff calculation)
**Memory:** ~1KB per FailureContext (exception, stack trace, metadata)
**Network:** Retry attempts may duplicate API calls (consider idempotency)

## Best Practices

### 1. Choose Appropriate Strategy
- **Exponential:** Network/API calls with increasing backoff
- **Linear:** Database connections with constant retry intervals
- **None:** Testing, non-idempotent operations, user-facing actions

### 2. Set Reasonable Limits
- Max attempts: 3-5 for production, 10+ for development
- Max delay: Cap at 30-60s to avoid infinite waits
- Jitter: 10-20% to avoid thundering herd

### 3. Handle Idempotency
Retries may cause duplicate operations. Ensure tools are idempotent or use:
- Request IDs (include in tool_input)
- Conditional writes (check-then-update)
- Deduplication layers

### 4. Monitor Retry Metrics
Track via observability (future enhancement):
- Retry rate: `retries / total_calls`
- Retry success rate: `success_after_retry / retries`
- Average attempts: `total_attempts / completed_calls`
- P95/P99 latency with retries

### 5. Fail Fast on Terminal Errors
Don't retry:
- Security violations (POLICY_SECURITY)
- User cancellations (USER_CANCELLED)
- Budget exhaustion (POLICY_BUDGET)
- Validation errors (AGENT_VALIDATION)

### 6. Use PartialResults for Long Tasks
Break long operations into steps:
```python
steps = [
    {"tool": "fetch_data", "input": {"query": "..."}},
    {"tool": "process_data", "input": {"batch": 1}},
    {"tool": "process_data", "input": {"batch": 2}},
    {"tool": "save_results", "input": {"output": "..."}},
]
```
If step 2 fails after retries, steps 0-1 results are preserved.

## Migration Guide

### From Direct tool.handler() Calls

**Before:**
```python
result = tool.handler(tool_input, context)
```

**After (Automatic):**
```python
# WorkerAgent.execute() now calls _execute_tool_with_retry() internally
# No code changes needed - retry logic is transparent
result = worker.execute(steps)
```

### Adding Retry to Custom Agents

If you have a custom agent that calls tool handlers:

**Pattern:**
```python
from cuga.orchestrator.failures import (
    FailureContext, LifecycleStage, create_retry_policy
)

class CustomAgent:
    def __init__(self):
        self.retry_policy = create_retry_policy("exponential", max_attempts=3)
    
    def execute_tool(self, tool, tool_input, context):
        attempt = 0
        last_error = None
        
        while attempt <= self.retry_policy.get_max_attempts():
            try:
                return tool.handler(tool_input, context)
            except Exception as exc:
                last_error = exc
                
                failure_ctx = FailureContext.from_exception(
                    exc, LifecycleStage.EXECUTE, None
                )
                failure_ctx.retry_count = attempt
                
                if failure_ctx.mode.terminal or not self.retry_policy.should_retry(failure_ctx):
                    raise exc
                
                delay = self.retry_policy.get_delay(attempt)
                if delay > 0:
                    time.sleep(delay)
                
                attempt += 1
        
        raise last_error
```

## Future Enhancements (Post-v1.3.1)

### 1. Circuit Breaker Integration
Prevent retry storms by opening circuit after N consecutive failures:
```python
circuit_policy = CircuitBreakerRetryPolicy(
    base_policy=ExponentialBackoffPolicy(...),
    failure_threshold=5,  # Open after 5 failures
    recovery_timeout=60.0,  # Test recovery after 60s
)
```

### 2. Adaptive Backoff
Adjust delays based on observed success rates:
```python
adaptive_policy = AdaptiveBackoffPolicy(
    initial_delay=1.0,
    success_threshold=0.8,  # < 80% success → increase delay
    adjustment_factor=1.5,
)
```

### 3. Retry Budget
Limit total retry time across all tool calls:
```python
worker = WorkerAgent(
    retry_policy=...,
    retry_budget=RetryBudget(max_total_delay_ms=30000),  # 30s max
)
```

### 4. Conditional Retry Predicates
Custom retry conditions:
```python
def should_retry_fn(exc: Exception, attempt: int) -> bool:
    if isinstance(exc, APIError):
        return exc.status_code in [429, 500, 503]  # Retry rate limits and server errors
    return False

custom_policy = ConditionalRetryPolicy(
    predicate=should_retry_fn,
    base_policy=LinearBackoffPolicy(...),
)
```

### 5. Async Retry Support
Non-blocking retries for async operations:
```python
async def execute_tool_async(self, tool, tool_input, context):
    attempt = 0
    while attempt <= self.retry_policy.get_max_attempts():
        try:
            return await tool.handler_async(tool_input, context)
        except Exception as exc:
            # ... (same logic)
            await asyncio.sleep(delay)
            attempt += 1
```

## References

- **Implementation:** `src/cuga/modular/agents.py` (WorkerAgent)
- **Retry Logic:** `src/cuga/orchestrator/failures.py` (RetryPolicy, FailureMode)
- **Tests:** `tests/test_worker_retry.py` (18 tests)
- **Orchestrator Contract:** `docs/orchestrator/ORCHESTRATOR_CONTRACT.md`
- **Failure Modes:** `docs/orchestrator/FAILURE_MODES.md`

## Changelog

**v1.3.1 (2026-01-03):**
- ✅ Added retry_policy field to WorkerAgent
- ✅ Implemented _execute_tool_with_retry() helper
- ✅ Integrated FailureMode classification
- ✅ Default ExponentialBackoffPolicy (3 attempts, 1s→30s)
- ✅ 18 comprehensive tests (100% passing)
- ✅ Fixed ConnectionError classification bug
- ✅ No regressions (87/87 orchestrator tests passing)

**Next (v1.3.2 - Task #5):**
- AuditTrail integration for retry decisions
- Retry attempt events in observability
- Retry metrics (rate, success rate, latency)

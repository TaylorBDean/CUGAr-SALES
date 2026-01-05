# Orchestrator Module

**Status**: Canonical (Dec 2025)  
**Priority**: Critical — Blocking for Clean Integration

---

## Overview

This module defines the **single, canonical orchestrator contract** for the CUGAR agent system. All orchestration implementations MUST conform to `OrchestratorProtocol` to ensure consistent behavior across the system.

## Quick Start

### Using the Reference Implementation

```python
from cuga.orchestrator import ExecutionContext, ErrorPropagation
from cuga.orchestrator.reference import ReferenceOrchestrator

# Create orchestrator
orchestrator = ReferenceOrchestrator(
    workers=["worker1", "worker2"],
    default_worker="worker1",
)

# Create execution context
context = ExecutionContext(
    trace_id="abc123",
    profile="demo",
    metadata={"user_id": "user123"},
)

# Run orchestration
async for event in orchestrator.orchestrate(
    goal="search for Python docs",
    context=context,
    error_strategy=ErrorPropagation.FAIL_FAST,
):
    print(f"Stage: {event['stage']}")
    print(f"Data: {event['data']}")
    print(f"Trace ID: {event['context'].trace_id}")
```

### Implementing Custom Orchestrator

```python
from cuga.orchestrator import OrchestratorProtocol, LifecycleStage

class MyOrchestrator(OrchestratorProtocol):
    async def orchestrate(self, goal, context, *, error_strategy):
        # Emit lifecycle events
        yield {"stage": LifecycleStage.INITIALIZE, "data": {...}, "context": context}
        yield {"stage": LifecycleStage.PLAN, "data": {...}, "context": context}
        # ... more stages
        yield {"stage": LifecycleStage.COMPLETE, "data": {...}, "context": context}
    
    def make_routing_decision(self, task, context, available_agents):
        # Implement deterministic routing
        return RoutingDecision(
            target="best_worker",
            reason="Selected based on ...",
            fallback="backup_worker",
        )
    
    async def handle_error(self, error, strategy):
        # Implement error handling per strategy
        if strategy == ErrorPropagation.FAIL_FAST:
            raise error
        # ... handle other strategies
    
    def get_lifecycle(self):
        return self._lifecycle_manager
```

## Key Concepts

### Lifecycle Stages

All orchestrators emit events at these stages:

1. **INITIALIZE** — Agent/resource setup
2. **PLAN** — Task decomposition
3. **ROUTE** — Routing decision made
4. **EXECUTE** — Tool/step execution
5. **AGGREGATE** — Results collection
6. **COMPLETE** / **FAILED** / **CANCELLED** — Terminal stage

### Execution Context

Immutable context passed through all operations:

```python
context = ExecutionContext(
    trace_id="unique-trace-id",     # REQUIRED: unique identifier
    profile="security-profile",      # Security/config profile
    metadata={"key": "value"},       # Additional context
    parent_context=None,             # For nested orchestrations
)

# Create new context with updated metadata
new_context = context.with_metadata(step=1, result="success")
```

### Routing Decisions

Explicit, justified routing with optional fallback:

```python
decision = RoutingDecision(
    target="worker1",
    reason="Lowest latency for search tasks",
    metadata={"confidence": 0.95},
    fallback="worker2",  # If worker1 fails
)
```

### Error Propagation

Four strategies for handling errors:

- **FAIL_FAST** — Stop immediately (default)
- **CONTINUE** — Log error, continue remaining steps
- **RETRY** — Retry with exponential backoff
- **FALLBACK** — Use fallback routing decision

```python
try:
    async for event in orchestrator.orchestrate(
        goal,
        context,
        error_strategy=ErrorPropagation.FALLBACK,
    ):
        process(event)
except OrchestrationError as err:
    logger.error(f"Failed at {err.stage}: {err.message}")
    if err.recoverable:
        # Attempt recovery
        ...
```

## Module Structure

```
src/cuga/orchestrator/
├── __init__.py       # Public API exports
├── protocol.py       # OrchestratorProtocol + types
└── reference.py      # Reference implementation
```

## Documentation

- **[ORCHESTRATOR_CONTRACT.md](../../docs/orchestrator/ORCHESTRATOR_CONTRACT.md)** — Full specification, architecture, testing requirements
- **[AGENTS.md](../../AGENTS.md)** — Guardrails and policy
- **[AGENT-CORE.md](../../docs/AGENT-CORE.md)** — Controller/Planner/Executor/Registry

## Testing

Run orchestrator tests:

```bash
pytest tests/test_orchestrator_protocol.py -v
```

Key test requirements:
- ✅ Lifecycle stages in correct order
- ✅ Trace ID propagation through all events
- ✅ Deterministic routing (same inputs → same output)
- ✅ Error handling per strategy
- ✅ Context immutability

## Migration Guide

### For Existing Code

If you have existing orchestration logic:

1. **Implement `OrchestratorProtocol`**
   ```python
   from cuga.orchestrator import OrchestratorProtocol
   
   class MyOrchestrator(OrchestratorProtocol):
       # Implement required methods
   ```

2. **Replace bare exceptions**
   ```python
   # Before
   raise RuntimeError("Failed")
   
   # After
   raise OrchestrationError(
       stage=LifecycleStage.EXECUTE,
       message="Failed",
       context=context,
       recoverable=True,
   )
   ```

3. **Add lifecycle emissions**
   ```python
   yield {"stage": LifecycleStage.PLAN, "data": plan, "context": context}
   ```

4. **Make routing explicit**
   ```python
   decision = self.make_routing_decision(task, context, agents)
   ```

## Anti-Patterns

❌ **Don't**: Directly call tool handlers
```python
# BAD
result = tool.handler(inputs, context)
```

✅ **Do**: Delegate to WorkerAgent
```python
# GOOD
result = await worker.execute(step, context)
```

❌ **Don't**: Mutate execution context
```python
# BAD
context.trace_id = "new-id"  # Immutable!
```

✅ **Do**: Create new context
```python
# GOOD
new_context = context.with_metadata(key="value")
```

❌ **Don't**: Swallow errors silently
```python
# BAD
try:
    execute_step()
except Exception:
    pass  # Silent failure
```

✅ **Do**: Propagate structured errors
```python
# GOOD
try:
    execute_step()
except Exception as e:
    raise OrchestrationError(
        stage=LifecycleStage.EXECUTE,
        message="Step failed",
        context=context,
        cause=e,
    )
```

## FAQ

### Q: Why a separate orchestrator module?

**A**: Previously, orchestration logic was scattered across multiple components without explicit contracts. This caused duplicated logic, inconsistent error handling, and fragile coupling. A canonical protocol provides a single source of truth.

### Q: Can I skip lifecycle stages?

**A**: You MUST emit `INITIALIZE` and one terminal stage (`COMPLETE`/`FAILED`/`CANCELLED`). Other stages are optional but recommended.

### Q: How do I test my orchestrator?

**A**: Implement the protocol, then run the compliance tests in `tests/test_orchestrator_protocol.py`. Add your orchestrator to the test fixtures.

### Q: What about sync vs async?

**A**: The protocol is async-first, but you can wrap sync implementations. See `ReferenceOrchestrator` for async patterns.

## Contributing

When modifying orchestrator code:

1. Update `protocol.py` for interface changes
2. Update `ORCHESTRATOR_CONTRACT.md` for documentation
3. Add/update tests in `tests/test_orchestrator_protocol.py`
4. Update `CHANGELOG.md` and `AGENTS.md`
5. Run `pytest tests/test_orchestrator_protocol.py` to verify compliance

---

**Last Updated**: December 2025  
**Status**: Canonical (blocking for integration)

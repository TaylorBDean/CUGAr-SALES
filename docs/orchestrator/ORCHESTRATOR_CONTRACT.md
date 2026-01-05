# Canonical Orchestrator Contract

**Status**: Canonical (as of Dec 2025)  
**Location**: `src/cuga/orchestrator/protocol.py`  
**Priority**: Critical — Blocking for Clean Integration

---

## 📋 Overview

This document defines the **single, canonical orchestrator contract** for the CUGAR agent system. All orchestration logic — whether in `Coordinator`, `CoordinatorAgent`, `AgentRunner`, or future implementations — MUST conform to this protocol.

### Problem Statement

Previously, multiple components behaved as orchestrators without explicit contracts:
- ❌ **Duplicated logic** across `Coordinator`, `CoordinatorAgent`, `AgentRunner`
- ❌ **Unclear ownership** of lifecycle, routing, error handling
- ❌ **Fragile coupling** between orchestrators and other components
- ❌ **No explicit error propagation** strategy
- ❌ **Inconsistent execution context** management

### Solution

Define `OrchestratorProtocol` as the **single source of truth** with:
- ✅ **Explicit lifecycle stages** (initialize → plan → route → execute → complete)
- ✅ **Typed execution context** (immutable, trace_id propagation)
- ✅ **Deterministic routing decisions** (with justification and fallback)
- ✅ **Structured error handling** (fail-fast, retry, fallback, continue)
- ✅ **Clear boundaries** (orchestration only, delegates to registry/policy/memory)

---

## 🏗️ Architecture

### Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                    OrchestratorProtocol                      │
│  (Canonical Interface - All orchestrators implement this)    │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ implements
                            ▼
        ┌───────────────────────────────────────────┐
        │                                           │
        │  Coordinator  │  CoordinatorAgent  │  Custom  │
        │  (async)      │  (sync)            │  (yours) │
        │                                           │
        └───────────────────────────────────────────┘
                            │
                            │ uses
                            ▼
        ┌───────────────────────────────────────────┐
        │   AgentLifecycle  │  ExecutionContext     │
        │   RoutingDecision │  OrchestrationError   │
        └───────────────────────────────────────────┘
```

### Delegation Pattern

The orchestrator **ONLY** handles coordination. It delegates to:

| Component         | Responsibility                          |
|-------------------|-----------------------------------------|
| `ToolRegistry`    | Tool resolution, sandboxing             |
| `PolicyEnforcer`  | Input/output validation, guardrails     |
| `VectorMemory`    | Memory storage and retrieval            |
| `BaseEmitter`     | Observability (traces, metrics)         |
| `PlannerAgent`    | Task decomposition into steps           |
| `WorkerAgent`     | Step execution via tools                |

**Anti-pattern**: Orchestrator MUST NOT directly call tool handlers or enforce policies.

---

## 📐 Protocol Definition

### `OrchestratorProtocol`

```python
from cuga.orchestrator import OrchestratorProtocol, ExecutionContext

class MyOrchestrator(OrchestratorProtocol):
    async def orchestrate(
        self,
        goal: str,
        context: ExecutionContext,
        *,
        error_strategy: ErrorPropagation = ErrorPropagation.FAIL_FAST,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Primary orchestration method.
        Yields events as orchestration progresses.
        """
        ...
    
    def make_routing_decision(
        self,
        task: str,
        context: ExecutionContext,
        available_agents: List[str],
    ) -> RoutingDecision:
        """
        Deterministic routing decision.
        MUST return same result for same inputs.
        """
        ...
    
    async def handle_error(
        self,
        error: OrchestrationError,
        strategy: ErrorPropagation,
    ) -> Optional[Dict[str, Any]]:
        """
        Handle errors per strategy (fail-fast, retry, fallback).
        """
        ...
    
    def get_lifecycle(self) -> AgentLifecycle:
        """
        Return lifecycle manager for initialize/teardown.
        """
        ...
```

---

## 🔄 Lifecycle Stages

Orchestrators MUST emit events at these stages (in order):

```
┌──────────────┐
│  INITIALIZE  │  ← Agent/resource setup
└──────────────┘
       │
       ▼
┌──────────────┐
│     PLAN     │  ← Task decomposition
└──────────────┘
       │
       ▼
┌──────────────┐
│    ROUTE     │  ← Routing decision made
└──────────────┘
       │
       ▼
┌──────────────┐
│   EXECUTE    │  ← Tool/step execution
└──────────────┘
       │
       ▼
┌──────────────┐
│  AGGREGATE   │  ← Results collection
└──────────────┘
       │
       ▼
┌──────────────┐
│   COMPLETE   │  ← Success exit
└──────────────┘

      OR

┌──────────────┐
│    FAILED    │  ← Error exit
└──────────────┘

      OR

┌──────────────┐
│  CANCELLED   │  ← User cancellation
└──────────────┘
```

### Stage Guarantees

- **INITIALIZE** MUST complete before PLAN
- **PLAN** MUST complete before ROUTE
- **ROUTE** MUST be emitted for each task
- **EXECUTE** MAY be repeated per routing decision
- **COMPLETE**, **FAILED**, or **CANCELLED** MUST be terminal (no further events)

---

## 🎯 Execution Context

```python
@dataclass(frozen=True)
class ExecutionContext:
    """Immutable context passed through orchestration."""
    
    trace_id: str                               # REQUIRED: unique trace ID
    profile: str = "default"                    # Security profile name
    metadata: Dict[str, Any] = field(...)       # Read-only metadata
    parent_context: Optional[ExecutionContext]  # For nested orchestrations
```

### Context Flow

```
User Request
     │
     ├─► Create ExecutionContext(trace_id="abc123", profile="demo")
     │
     ▼
Orchestrator.orchestrate(goal, context)
     │
     ├─► PlannerAgent receives context
     ├─► RoutingDecision includes context
     ├─► WorkerAgent receives context
     ├─► Tool handlers receive context in ctx param
     │
     ▼
All events include updated context
```

### Context Immutability

- **MUST NOT** mutate `trace_id` or `profile`
- Use `context.with_metadata(key=value)` to add metadata
- Parent context preserved for nested orchestrations

---

## 🛤️ Routing Decisions

```python
@dataclass(frozen=True)
class RoutingDecision:
    """Explicit routing decision with justification."""
    
    target: str              # Target agent/worker ID
    reason: str              # Human-readable justification
    metadata: Dict[str, Any] # Additional routing context
    fallback: Optional[str]  # Fallback target if primary fails
```

### Routing Requirements

1. **Deterministic**: Same inputs → same routing decision
2. **Justified**: `reason` explains why target was selected
3. **Fallback-aware**: Specify fallback for critical paths
4. **Logged**: Emit routing decision in trace

### Example

```python
decision = orchestrator.make_routing_decision(
    task="search web for Python docs",
    context=ExecutionContext(trace_id="xyz", profile="research"),
    available_agents=["web_search", "rag_query", "llm_generate"],
)

# RoutingDecision(
#     target="web_search",
#     reason="Task contains 'search web' and web_search has lowest latency",
#     metadata={"confidence": 0.95},
#     fallback="rag_query"
# )
```

---

## ⚠️ Error Propagation

### Error Strategy

```python
class ErrorPropagation(str, Enum):
    FAIL_FAST = "fail_fast"    # Stop immediately (default)
    CONTINUE = "continue"      # Log error, continue remaining steps
    RETRY = "retry"            # Retry with exponential backoff
    FALLBACK = "fallback"      # Use fallback routing decision
```

### Orchestration Error

```python
@dataclass
class OrchestrationError(Exception):
    stage: LifecycleStage       # Where error occurred
    message: str                # Human-readable description
    context: ExecutionContext   # Context at failure time
    cause: Optional[Exception]  # Original exception
    recoverable: bool           # Can this be recovered?
    metadata: Dict[str, Any]    # Additional error context
```

### Error Handling Flow

```python
try:
    async for event in orchestrator.orchestrate(goal, context):
        process_event(event)
except OrchestrationError as err:
    logger.error(f"Orchestration failed at {err.stage}: {err.message}")
    logger.error(f"trace_id: {err.context.trace_id}")
    if err.recoverable:
        # Attempt recovery
        result = await orchestrator.handle_error(err, ErrorPropagation.RETRY)
    else:
        raise
```

### Error Handling Requirements

1. **Never silent**: All errors MUST be logged with trace_id
2. **Structured**: Use `OrchestrationError` (not bare exceptions)
3. **Contextual**: Include stage, context, cause
4. **Recoverable flag**: Indicate if retry/fallback is possible
5. **Strategy-aware**: Respect `ErrorPropagation` setting

---

## 🧪 Testing Requirements

All orchestrator implementations MUST pass these tests:

### 1. Lifecycle Compliance

```python
async def test_lifecycle_stages():
    """Orchestrator emits stages in correct order."""
    orchestrator = MyOrchestrator(...)
    context = ExecutionContext(trace_id="test", profile="demo")
    
    stages = []
    async for event in orchestrator.orchestrate("test goal", context):
        stages.append(event["stage"])
    
    assert stages == [
        LifecycleStage.INITIALIZE,
        LifecycleStage.PLAN,
        LifecycleStage.ROUTE,
        LifecycleStage.EXECUTE,
        LifecycleStage.AGGREGATE,
        LifecycleStage.COMPLETE,
    ]
```

### 2. Trace Propagation

```python
async def test_trace_propagation():
    """trace_id flows through all stages."""
    trace_id = "unique-trace-123"
    context = ExecutionContext(trace_id=trace_id, profile="demo")
    
    async for event in orchestrator.orchestrate("test", context):
        assert event["context"].trace_id == trace_id
```

### 3. Deterministic Routing

```python
def test_deterministic_routing():
    """Same inputs produce same routing decision."""
    context = ExecutionContext(trace_id="abc", profile="demo")
    agents = ["agent1", "agent2"]
    
    decision1 = orchestrator.make_routing_decision("task", context, agents)
    decision2 = orchestrator.make_routing_decision("task", context, agents)
    
    assert decision1.target == decision2.target
    assert decision1.reason == decision2.reason
```

### 4. Error Recovery

```python
async def test_error_recovery():
    """Orchestrator handles errors per strategy."""
    context = ExecutionContext(trace_id="err", profile="demo")
    
    with mock.patch.object(orchestrator, "_execute_step", side_effect=RuntimeError("fail")):
        async for event in orchestrator.orchestrate(
            "test",
            context,
            error_strategy=ErrorPropagation.FALLBACK,
        ):
            if event["stage"] == LifecycleStage.FAILED:
                assert "fallback" in event["data"]
```

---

## 📝 Migration Guide

### For Existing Orchestrators

If you have existing orchestration logic:

1. **Implement `OrchestratorProtocol`**
   ```python
   from cuga.orchestrator import OrchestratorProtocol
   
   class MyOrchestrator(OrchestratorProtocol):
       # Implement required methods
   ```

2. **Replace bare exceptions with `OrchestrationError`**
   ```python
   # Before
   raise RuntimeError("Tool failed")
   
   # After
   raise OrchestrationError(
       stage=LifecycleStage.EXECUTE,
       message="Tool failed",
       context=current_context,
       cause=RuntimeError("Tool failed"),
       recoverable=True,
   )
   ```

3. **Add lifecycle stage emissions**
   ```python
   yield {"stage": LifecycleStage.PLAN, "data": plan, "context": context}
   ```

4. **Make routing decisions explicit**
   ```python
   decision = self.make_routing_decision(task, context, agents)
   yield {"stage": LifecycleStage.ROUTE, "data": decision, "context": context}
   ```

5. **Update tests** to verify protocol compliance

---

## 🔗 Related Documentation

- [AGENTS.md](../../AGENTS.md) — Guardrail hierarchy and policy
- [AGENT-CORE.md](../AGENT-CORE.md) — Controller/Planner/Executor/Registry
- [observability/README.md](../observability/README.md) — Tracing and metrics
- [testing/orchestrator.md](../testing/orchestrator.md) — Test patterns

---

## ❓ FAQ

### Q: Why a separate orchestrator protocol?

**A**: Previously, orchestration logic was scattered across `Coordinator`, `CoordinatorAgent`, `AgentRunner`, and `LifecycleManager`. This caused:
- Duplicated lifecycle logic
- Inconsistent error handling
- Unclear ownership of routing decisions
- Fragile integration points

A canonical protocol provides **single source of truth** and **type-safe contracts**.

### Q: Can I have multiple orchestrators?

**A**: Yes! You can implement multiple orchestrators (sync/async, simple/complex) as long as they ALL implement `OrchestratorProtocol`. The contract ensures they're interchangeable.

### Q: What about legacy code?

**A**: Legacy orchestrators (e.g., existing `Coordinator`, `CoordinatorAgent`) will be migrated incrementally. New code MUST use the protocol. See migration guide above.

### Q: How do I handle custom routing logic?

**A**: Implement `make_routing_decision()` with your logic. The protocol only requires:
1. Deterministic behavior (same inputs → same output)
2. Justified decision (return `RoutingDecision` with `reason`)
3. Optional fallback

### Q: What if my orchestrator doesn't need all lifecycle stages?

**A**: You MUST emit at least `INITIALIZE` and one terminal stage (`COMPLETE`/`FAILED`/`CANCELLED`). Other stages are optional but recommended.

---

## ✅ Checklist for Implementers

When implementing `OrchestratorProtocol`:

- [ ] Implement all abstract methods (`orchestrate`, `make_routing_decision`, `handle_error`, `get_lifecycle`)
- [ ] Emit lifecycle stages in correct order
- [ ] Propagate `trace_id` through all events
- [ ] Use `ExecutionContext` (immutable)
- [ ] Return `RoutingDecision` with justification
- [ ] Raise `OrchestrationError` (not bare exceptions)
- [ ] Respect `ErrorPropagation` strategy
- [ ] Add tests for lifecycle compliance
- [ ] Add tests for deterministic routing
- [ ] Add tests for error recovery
- [ ] Document any custom routing logic
- [ ] Update `CHANGELOG.md` if breaking changes

---

**Last Updated**: December 2025  
**Status**: Canonical (blocking for integration)  
**Owner**: Core Agent Team

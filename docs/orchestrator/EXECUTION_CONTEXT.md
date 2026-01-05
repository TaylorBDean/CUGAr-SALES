# Execution Context: Explicit State Propagation

**Status**: Canonical  
**Last Updated**: 2025-12-31  
**Owner**: Orchestrator Team

## Problem Statement

### Before: Implicit Context

```
Context scattered across:
   ├── trace_id (sometimes in metadata, sometimes in args)
   ├── user_intent (implied in goal/task strings)
   ├── request_id (missing - no request tracking)
   ├── memory_scope (not formalized - isolation unclear)
   ├── conversation_id (missing - no multi-turn tracking)
   └── session_id (missing - no session management)

Impact:
   ├── Observability gaps (can't trace requests end-to-end)
   ├── Memory isolation unclear (cross-user leakage possible)
   ├── Session management broken (can't resume conversations)
   └── Orchestrators can't safely coordinate across agents
```

### After: Explicit ExecutionContext

```python
from cuga.orchestrator import ExecutionContext

# All context explicit and type-checked
context = ExecutionContext(
    trace_id="trace-abc123",          # Unique trace (required)
    request_id="req-456",              # Request tracking
    user_intent="Find flight to NYC",  # Explicit intent
    user_id="user-alice",              # User identification
    memory_scope="user:alice/sess:789",# Memory isolation
    conversation_id="conv-101",        # Multi-turn conversations
    session_id="sess-789",             # Session tracking
    profile="production",              # Config/security profile
    metadata={"priority": "high"},     # Additional context
)

# Immutable - create new contexts with with_* methods
child = context.with_user_intent("Book cheapest flight")
child.parent_context == context  # True (nested orchestration)
child.trace_id == context.trace_id  # True (trace continuity)
```

## Core Concept: ExecutionContext

### Structure

```python
@dataclass(frozen=True)
class ExecutionContext:
    """
    Explicit, immutable execution context for orchestrator operations.
    
    Required:
        trace_id: Unique trace identifier (immutable across all operations)
    
    Request Tracking:
        request_id: API/user request identifier
    
    User Context:
        user_intent: Explicit goal/intent (not buried in strings)
        user_id: User identifier for access control
    
    Memory & Session:
        memory_scope: Namespace for memory isolation (e.g., "user:alice/session:789")
        conversation_id: Multi-turn conversation thread
        session_id: User session identifier
    
    Configuration:
        profile: Security/config profile (e.g., "production", "demo")
    
    Additional:
        metadata: Arbitrary key-value context
        parent_context: Parent context for nested orchestrations
        created_at: ISO 8601 timestamp
    """
    
    # Required
    trace_id: str
    
    # Optional but recommended
    request_id: str = ""
    user_intent: str = ""
    user_id: str = ""
    memory_scope: str = ""
    conversation_id: str = ""
    session_id: str = ""
    profile: str = "default"
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_context: Optional[ExecutionContext] = None
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
```

### Key Properties

**1. Immutability**
```python
context = ExecutionContext(trace_id="abc123")
context.trace_id = "xyz"  # ❌ FrozenInstanceError (frozen=True)

# ✅ Create new context instead
new_context = context.with_metadata(step="planning")
```

**2. Trace Continuity**
```python
root = ExecutionContext(trace_id="trace-123", user_intent="Book flight")
child = root.with_user_intent("Search flights to NYC")

child.trace_id == root.trace_id  # ✅ True (same trace)
child.parent_context == root     # ✅ True (nested)
child.user_intent != root.user_intent  # ✅ True (refined intent)
```

**3. Type Safety**
```python
# All fields are typed - no Dict[str, Any] soup
context.trace_id: str
context.user_intent: str
context.memory_scope: str
context.parent_context: Optional[ExecutionContext]
```

## Context Lifecycle

### 1. Creation (Entry Points)

```python
# FastAPI endpoint
@app.post("/orchestrate")
async def orchestrate(
    goal: str,
    x_trace_id: str | None = Header(default=None),
    x_request_id: str | None = Header(default=None),
    user_id: str = Depends(get_current_user),
):
    context = ExecutionContext(
        trace_id=x_trace_id or generate_trace_id(),
        request_id=x_request_id or generate_request_id(),
        user_intent=goal,
        user_id=user_id,
        memory_scope=f"user:{user_id}/session:{session_id}",
        session_id=session_id,
        conversation_id=conversation_id,
        profile="production",
    )
    
    result = await orchestrator.orchestrate(goal, context)
    return result

# CLI invocation
def main():
    context = ExecutionContext(
        trace_id=f"cli-{uuid.uuid4()}",
        request_id=f"req-{uuid.uuid4()}",
        user_intent=args.goal,
        user_id="cli-user",
        profile=args.profile or "default",
    )
    
    loop.run_until_complete(orchestrator.orchestrate(args.goal, context))
```

### 2. Propagation (Orchestrator → Agents)

```python
class MyOrchestrator(OrchestratorProtocol):
    async def orchestrate(
        self,
        goal: str,
        context: ExecutionContext,
        error_strategy: ErrorPropagation = ErrorPropagation.FAIL_FAST,
    ) -> Dict[str, Any]:
        # Phase 1: Initialize
        await self.initialize(context)
        
        # Phase 2: Plan (context flows to planner)
        plan = await self.plan(goal, context)
        
        # Phase 3: Route (convert to RoutingContext)
        routing_ctx = RoutingContext(
            trace_id=context.trace_id,
            profile=context.profile,
            goal=goal,
            metadata=context.metadata,
            parent_context=context,  # Link back to ExecutionContext
        )
        decision = self.routing_authority.route_to_agent(routing_ctx, agents)
        
        # Phase 4: Execute (pass context to agent)
        result = await self.execute_step(
            step=plan[0],
            context=context.with_metadata(routing_decision=decision.selected),
        )
        
        return result
```

### 3. Nested Orchestration

```python
# Parent orchestrator
parent_context = ExecutionContext(
    trace_id="trace-123",
    user_intent="Book round-trip flight",
    user_id="alice",
)

# Child orchestrator (refined intent)
child_context = parent_context.with_user_intent("Find outbound flights")
outbound = await orchestrator.orchestrate("Search NYC flights", child_context)

# Another child (sibling)
child_context2 = parent_context.with_user_intent("Find return flights")
inbound = await orchestrator.orchestrate("Search return flights", child_context2)

# Both children share same trace_id and parent_context
assert child_context.trace_id == child_context2.trace_id == parent_context.trace_id
assert child_context.parent_context == parent_context
assert child_context2.parent_context == parent_context
```

### 4. Memory Isolation

```python
# User-scoped memory
alice_context = ExecutionContext(
    trace_id="trace-123",
    user_id="user-alice",
    memory_scope="user:alice",
    user_intent="Show my orders",
)

bob_context = ExecutionContext(
    trace_id="trace-456",
    user_id="user-bob",
    memory_scope="user:bob",
    user_intent="Show my orders",
)

# Memory system uses memory_scope for isolation
alice_memories = memory_system.retrieve(alice_context.memory_scope, query)
bob_memories = memory_system.retrieve(bob_context.memory_scope, query)

# ✅ No cross-user leakage (different memory_scopes)
assert alice_memories != bob_memories
```

### 5. Observability Integration

```python
from cuga.observability import emit_span

async def execute_step(step, context: ExecutionContext):
    with emit_span(
        name="execute_step",
        trace_id=context.trace_id,            # ✅ Explicit trace
        request_id=context.request_id,        # ✅ Request tracking
        user_id=context.user_id,              # ✅ User attribution
        user_intent=context.user_intent,      # ✅ Business context
        memory_scope=context.memory_scope,    # ✅ Isolation scope
        step_name=step.name,
    ):
        result = await worker.execute(step)
        return result
```

## with_* Update Methods

### with_metadata()

Add/merge metadata without changing other fields:

```python
context = ExecutionContext(trace_id="abc123")
updated = context.with_metadata(stage="planning", retry_count=1)

updated.metadata == {"stage": "planning", "retry_count": 1}  # ✅ True
updated.trace_id == context.trace_id  # ✅ True (preserved)
```

### with_user_intent()

Create nested context with refined intent:

```python
parent = ExecutionContext(
    trace_id="trace-123",
    user_intent="Book flight",
)

child = parent.with_user_intent("Search NYC flights")

child.user_intent == "Search NYC flights"  # ✅ True (updated)
child.trace_id == parent.trace_id          # ✅ True (preserved)
child.parent_context == parent             # ✅ True (nested)
child.created_at > parent.created_at       # ✅ True (new timestamp)
```

### with_request_id()

Create context for new request in same trace:

```python
context = ExecutionContext(
    trace_id="trace-123",
    request_id="req-001",
)

next_request = context.with_request_id("req-002")

next_request.request_id == "req-002"    # ✅ True (updated)
next_request.trace_id == context.trace_id  # ✅ True (same trace)
```

### with_profile()

Switch configuration profile:

```python
dev_context = ExecutionContext(trace_id="abc123", profile="development")
prod_context = dev_context.with_profile("production")

prod_context.profile == "production"  # ✅ True
prod_context.trace_id == dev_context.trace_id  # ✅ True
```

## Integration with Other Contexts

### RoutingContext

```python
# ExecutionContext → RoutingContext
execution_ctx = ExecutionContext(
    trace_id="trace-123",
    user_intent="Book flight",
    profile="production",
)

routing_ctx = RoutingContext(
    trace_id=execution_ctx.trace_id,
    profile=execution_ctx.profile,
    goal=execution_ctx.user_intent,
    parent_context=execution_ctx,  # Link back
)

# RoutingAuthority uses RoutingContext
decision = routing_authority.route_to_agent(routing_ctx, candidates)
```

### FailureContext

```python
# ExecutionContext → FailureContext
try:
    result = await risky_operation()
except Exception as exc:
    failure = FailureContext.from_exception(
        exc=exc,
        stage=LifecycleStage.EXECUTE,
        context=execution_context,  # Pass ExecutionContext
    )
    
    # FailureContext extracts trace_id from ExecutionContext
    failure.execution_context.trace_id == execution_context.trace_id  # ✅ True
    
    # Convert to OrchestrationError
    error = failure.to_orchestration_error()
    raise error
```

### RequestMetadata (Agent Contracts)

```python
from cuga.agents.contracts import RequestMetadata, AgentRequest

# ExecutionContext → RequestMetadata
execution_ctx = ExecutionContext(
    trace_id="trace-123",
    request_id="req-456",
    user_id="alice",
    profile="production",
)

request_metadata = RequestMetadata(
    trace_id=execution_ctx.trace_id,
    profile=execution_ctx.profile,
    priority=5,
    timeout_seconds=30,
)

# Use in AgentRequest
agent_request = AgentRequest(
    goal=execution_ctx.user_intent,
    metadata=request_metadata,
)

# Agent receives standardized metadata
response = await agent.process(agent_request)
```

## Validation

### Context Validation

```python
context = ExecutionContext(
    trace_id="",  # ❌ Empty trace_id
    memory_scope="user:alice",
    user_id="",   # ❌ memory_scope requires user_id
)

errors = context.validate()
# errors == [
#     "trace_id is required",
#     "memory_scope requires user_id to be set",
# ]
```

### Validation Rules

1. **trace_id** is always required
2. **memory_scope** requires **user_id** to be set
3. **conversation_id** requires **session_id** to be set

## Serialization

### to_dict() / from_dict()

```python
context = ExecutionContext(
    trace_id="trace-123",
    request_id="req-456",
    user_intent="Book flight",
    user_id="alice",
    memory_scope="user:alice",
    profile="production",
)

# Serialize
context_dict = context.to_dict()
# {
#     "trace_id": "trace-123",
#     "request_id": "req-456",
#     "user_intent": "Book flight",
#     "user_id": "alice",
#     "memory_scope": "user:alice",
#     "profile": "production",
#     "has_parent": False,
#     "created_at": "2025-12-31T12:00:00.000000",
#     ...
# }

# Deserialize
restored = ExecutionContext.from_dict(context_dict)
restored.trace_id == context.trace_id  # ✅ True
```

## Migration Guide

### Before: Implicit Context

```python
# Old pattern (implicit context)
async def orchestrate(goal: str, trace_id: str, profile: str = "default"):
    # trace_id passed separately
    # No user_intent, memory_scope, request_id
    steps = await planner.plan(goal, metadata={"trace_id": trace_id})
    
    for step in steps:
        # trace_id passed in metadata dict
        result = await worker.execute(step, {"trace_id": trace_id})
    
    return result
```

### After: Explicit Context

```python
# New pattern (explicit context)
async def orchestrate(
    goal: str,
    context: ExecutionContext,
    error_strategy: ErrorPropagation = ErrorPropagation.FAIL_FAST,
) -> Dict[str, Any]:
    # All context explicit and type-checked
    steps = await planner.plan(goal, context)
    
    for step in steps:
        # Context passed directly (no dict wrangling)
        result = await worker.execute(step, context)
    
    return result
```

## Testing

### Test Context Immutability

```python
def test_execution_context_immutability():
    """Test ExecutionContext is immutable."""
    context = ExecutionContext(trace_id="abc123")
    
    # Attempt mutation
    with pytest.raises(FrozenInstanceError):
        context.trace_id = "xyz"
    
    # ✅ with_* methods create new instances
    updated = context.with_metadata(step="planning")
    assert updated is not context
    assert updated.trace_id == context.trace_id

def test_trace_continuity():
    """Test trace_id preserved across context updates."""
    root = ExecutionContext(
        trace_id="trace-123",
        user_intent="Book flight",
    )
    
    child = root.with_user_intent("Search flights")
    grandchild = child.with_metadata(attempt=1)
    
    # All share same trace_id
    assert child.trace_id == root.trace_id
    assert grandchild.trace_id == root.trace_id
    
    # Parent chain preserved
    assert child.parent_context == root
    assert grandchild.parent_context == child

def test_context_validation():
    """Test context validation rules."""
    # Missing trace_id
    context1 = ExecutionContext(trace_id="")
    assert "trace_id is required" in context1.validate()
    
    # memory_scope without user_id
    context2 = ExecutionContext(
        trace_id="abc123",
        memory_scope="user:alice",
        user_id="",
    )
    assert "memory_scope requires user_id" in context2.validate()

def test_context_serialization():
    """Test context serialization round-trip."""
    original = ExecutionContext(
        trace_id="trace-123",
        request_id="req-456",
        user_intent="Book flight",
        user_id="alice",
        memory_scope="user:alice",
    )
    
    # Serialize
    data = original.to_dict()
    
    # Deserialize
    restored = ExecutionContext.from_dict(data)
    
    # Verify
    assert restored.trace_id == original.trace_id
    assert restored.user_intent == original.user_intent
    assert restored.memory_scope == original.memory_scope
```

## FAQ

### Q: Do I always need to provide all fields?

**A**: No. Only `trace_id` is required. Other fields are optional but recommended for full observability:

```python
# Minimal (just trace_id)
minimal = ExecutionContext(trace_id="abc123")

# Recommended (full context)
full = ExecutionContext(
    trace_id="abc123",
    request_id="req-456",
    user_intent="Book flight",
    user_id="alice",
    memory_scope="user:alice",
    profile="production",
)
```

### Q: How does this relate to RequestMetadata in Agent Contracts?

**A**: `ExecutionContext` is orchestrator-level context. `RequestMetadata` is agent-level metadata:

```python
# ExecutionContext (orchestrator)
execution_ctx = ExecutionContext(
    trace_id="trace-123",
    request_id="req-456",
    user_id="alice",
)

# RequestMetadata (agent contracts)
request_metadata = RequestMetadata(
    trace_id=execution_ctx.trace_id,  # Extract trace_id
    profile=execution_ctx.profile,
    priority=5,
)

# AgentRequest uses RequestMetadata
agent_request = AgentRequest(
    goal=execution_ctx.user_intent,
    metadata=request_metadata,
)
```

### Q: Should I use memory_scope or session_id for memory isolation?

**A**: Use `memory_scope` for fine-grained isolation:

```python
# User-level isolation
memory_scope="user:alice"

# Session-level isolation (multiple sessions per user)
memory_scope="user:alice/session:789"

# Conversation-level isolation (multiple conversations per session)
memory_scope="user:alice/session:789/conv:101"
```

### Q: How do I handle legacy code expecting Dict[str, Any] context?

**A**: Use `context.to_dict()` at boundaries:

```python
# Legacy function expecting dict
def legacy_function(context_dict: Dict[str, Any]):
    trace_id = context_dict["trace_id"]
    ...

# Call from new code
context = ExecutionContext(trace_id="abc123", user_intent="Book flight")
legacy_function(context.to_dict())  # Convert to dict
```

### Q: Can I nest ExecutionContext indefinitely?

**A**: Yes, via `parent_context`. Useful for hierarchical orchestrations:

```python
root = ExecutionContext(trace_id="trace-123", user_intent="Book trip")
child1 = root.with_user_intent("Book flight")
child2 = child1.with_user_intent("Search NYC flights")
grandchild = child2.with_metadata(attempt=3)

# Depth = 3
grandchild.parent_context.parent_context.parent_context == root  # ✅ True
```

### Q: How does this improve observability?

**A**: Explicit fields enable structured logging and distributed tracing:

```python
logger.info(
    "Executing step",
    extra={
        "trace_id": context.trace_id,        # ✅ Always present
        "request_id": context.request_id,    # ✅ Request tracking
        "user_id": context.user_id,          # ✅ User attribution
        "user_intent": context.user_intent,  # ✅ Business context
        "memory_scope": context.memory_scope,# ✅ Isolation scope
    },
)
```

Before: `trace_id` sometimes in metadata, sometimes in args, no request/user tracking.  
After: All context explicit and type-checked.

## Change Management

ExecutionContext changes require:

1. **Update `protocol.py`**: Modify ExecutionContext dataclass
2. **Update tests**: Cover new fields and validation rules
3. **Update this doc**: Document new fields and usage patterns
4. **Update `AGENTS.md`**: Guardrail changes if validation rules change
5. **Update `CHANGELOG.md`**: Record ExecutionContext enhancements

All changes MUST maintain backward compatibility for existing `trace_id` and `profile` fields.

---

**See Also**:
- `docs/orchestrator/ORCHESTRATOR_CONTRACT.md` - Orchestrator protocol
- `docs/orchestrator/ROUTING_AUTHORITY.md` - Routing context integration
- `docs/orchestrator/FAILURE_MODES.md` - Failure context integration
- `docs/agents/AGENT_IO_CONTRACT.md` - Agent request metadata
- `src/cuga/orchestrator/protocol.py` - Implementation

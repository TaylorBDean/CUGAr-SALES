# State Ownership Contract

> **Status**: Canonical  
> **Last Updated**: 2025-12-31  
> **Supersedes**: Implicit state management in AgentState, VariablesManager, VectorMemory

## Problem Statement

Current state management is fragmented across multiple systems with unclear ownership:

- **AgentState** (LangGraph): 855-line state class mixing coordination and ephemeral data
- **VariablesManager**: Standalone variable storage
- **StateVariablesManager**: Per-thread storage within AgentState  
- **VectorMemory**: Agent memory with embeddings and history
- **ExecutionContext**: Orchestrator coordination context

This ambiguity leads to:
- Uncertain persistence boundaries (what survives restarts?)
- Mutation conflicts (who can modify what?)
- Memory leaks (ephemeral data never discarded)
- Coupling (agents tightly bound to specific state systems)

## Ownership Model

State is owned by exactly ONE of three owners:

```
┌─────────────┬──────────────┬─────────────┬─────────────────┐
│ Owner       │ Scope        │ Lifetime    │ Examples        │
├─────────────┼──────────────┼─────────────┼─────────────────┤
│ AGENT       │ Request      │ Ephemeral   │ current_request │
│             │              │             │ temp_data       │
│             │              │             │ _internal_cache │
├─────────────┼──────────────┼─────────────┼─────────────────┤
│ MEMORY      │ Cross-request│ Persistent  │ user_history    │
│             │              │             │ embeddings      │
│             │              │             │ learned_facts   │
├─────────────┼──────────────┼─────────────┼─────────────────┤
│ ORCHESTRATOR│ Coordination │ Trace-scoped│ trace_id        │
│             │              │             │ routing_context │
│             │              │             │ parent_context  │
└─────────────┴──────────────┴─────────────┴─────────────────┘
```

### StateOwnership Enum

```python
class StateOwnership(str, Enum):
    AGENT = "agent"              # Owned by agent (ephemeral)
    MEMORY = "memory"            # Owned by memory system (persistent)
    ORCHESTRATOR = "orchestrator"  # Owned by orchestrator (coordination)
    SHARED = "shared"            # Shared ownership with explicit protocol
```

## Ownership Boundaries

### 1. AGENT State (Ephemeral)

**Definition**: State that exists only during agent execution and is discarded on shutdown.

**Characteristics**:
- **Lifetime**: Request-scoped (startup → shutdown)
- **Persistence**: None (cleared on termination)
- **Access**: Read/write by owning agent only
- **Storage**: In-memory (`_agent_state` dict in ManagedAgent)

**Examples**:
```python
# Ephemeral state managed by agent
agent._agent_state = {
    "_current_request": {...},      # Transient request data
    "_temp_cache": {...},           # Temporary cache
    "_internal_counters": {...},    # Execution counters
    "processing_context": {...}     # Per-request context
}
```

**Mutation Rules**:
- ✅ Agent CAN: Read, write, delete own ephemeral state
- ❌ Agent CANNOT: Persist beyond shutdown
- ❌ Memory CANNOT: Read or write agent state
- ❌ Orchestrator CANNOT: Modify agent state (read-only for observability)

**Storage Contract**:
```python
# Agent owns this - cleared on shutdown
async def shutdown(self):
    self._agent_state.clear()  # Discard ephemeral state
```

---

### 2. MEMORY State (Persistent)

**Definition**: State that persists across agent restarts and represents learned knowledge.

**Characteristics**:
- **Lifetime**: Cross-request (survives restarts)
- **Persistence**: Durable storage (filesystem, DB, vector store)
- **Access**: Read/write by memory system, read-only for agents
- **Storage**: VectorMemory, MemoryBackend implementations

**Examples**:
```python
# Persistent state managed by memory system
memory.store({
    "user_history": [...],         # Conversation history
    "embeddings": [...],           # Vector embeddings
    "learned_facts": [...],        # Extracted knowledge
    "preferences": {...}           # User preferences
})
```

**Mutation Rules**:
- ✅ Memory CAN: Read, write, persist, delete memory state
- ✅ Agent CAN: Read memory state (query)
- ❌ Agent CANNOT: Directly modify memory state (must call memory.update())
- ❌ Orchestrator CANNOT: Modify memory state (read-only for routing)

**Storage Contract**:
```python
# Agent reads via memory system
history = await memory.query("user_history")

# Agent writes via memory system (not direct)
await memory.update("learned_facts", new_fact)  # ✅ Correct
# memory_state["learned_facts"].append(new_fact)  # ❌ Wrong - bypasses memory
```

---

### 3. ORCHESTRATOR State (Coordination)

**Definition**: State that coordinates agent execution and maintains trace context.

**Characteristics**:
- **Lifetime**: Trace-scoped (parent trace → child traces)
- **Persistence**: Observability backends (OTEL, LangFuse)
- **Access**: Read-only for agents, write by orchestrator
- **Storage**: ExecutionContext (immutable), trace backends

**Examples**:
```python
# Coordination state managed by orchestrator
context = ExecutionContext(
    trace_id="req-123",           # Unique trace ID
    profile="default",            # Execution profile
    parent_context=parent_ctx,    # Parent trace link
    metadata={"routing": "rr"}    # Coordination metadata
)
```

**Mutation Rules**:
- ✅ Orchestrator CAN: Create, propagate, log trace context
- ✅ Agent CAN: Read context for tracing/logging
- ❌ Agent CANNOT: Modify trace_id or routing context
- ❌ Memory CANNOT: Access orchestrator state

**Storage Contract**:
```python
# Agent reads trace context
trace_id = context.trace_id  # ✅ Read-only access

# Agent logs with trace context
logger.info("Processing", extra={"trace_id": trace_id})

# Agent CANNOT modify
# context.trace_id = "new-id"  # ❌ Frozen dataclass prevents this
```

---

## Mapping to Current Systems

### AgentState → Ownership Mapping

`AgentState` (872 lines) currently mixes ownership. Split as follows:

```python
# src/cuga/backend/cuga_graph/state/agent_state.py

# ORCHESTRATOR state (coordination)
trace_id: str                      # → ExecutionContext.trace_id
routing_metadata: dict             # → ExecutionContext.metadata

# MEMORY state (persistent)
user_history: List[Message]        # → VectorMemory.history
embeddings: List[float]            # → VectorMemory.embeddings

# AGENT state (ephemeral)
current_request: dict              # → agent._agent_state
temp_cache: dict                   # → agent._agent_state
```

**Migration Path**:
1. Identify which fields persist across requests → MEMORY
2. Identify coordination fields (trace_id, routing) → ORCHESTRATOR  
3. Remaining fields → AGENT (ephemeral)
4. Refactor AgentState to delegate to correct owners

### VariablesManager vs StateVariablesManager

**VariablesManager** (standalone):
- **Current**: Global variable storage
- **Ownership**: AGENT (ephemeral if request-scoped) or MEMORY (if persisted)
- **Migration**: Clarify persistence semantics - if variables survive restarts → MEMORY, else → AGENT

**StateVariablesManager** (per-thread in AgentState):
- **Current**: Thread-local storage within LangGraph state
- **Ownership**: AGENT (per-thread ephemeral state)
- **Migration**: Clearly document as ephemeral per-thread storage

### VectorMemory

**VectorMemory**:
- **Current**: Agent memory with embeddings
- **Ownership**: MEMORY (persistent)
- **No changes needed**: Already correctly scoped as persistent

### ExecutionContext

**ExecutionContext**:
- **Current**: Orchestrator coordination context
- **Ownership**: ORCHESTRATOR (coordination)
- **No changes needed**: Already correctly scoped as coordination

---

## Violation Detection

### Runtime Checks

Agents implementing `AgentLifecycleProtocol` must declare ownership:

```python
def owns_state(self, key: str) -> StateOwnership:
    """Determine who owns a specific state key."""
    if key.startswith("_"):
        return StateOwnership.AGENT
    if key in {"history", "embeddings", "facts"}:
        return StateOwnership.MEMORY
    if key in {"trace_id", "routing"}:
        return StateOwnership.ORCHESTRATOR
    return StateOwnership.AGENT
```

### Enforcement

Raise `StateViolationError` when ownership is violated:

```python
def set_state(self, key: str, value: Any):
    owner = self.owns_state(key)
    if owner == StateOwnership.MEMORY:
        raise StateViolationError(
            key, StateOwnership.MEMORY, StateOwnership.AGENT
        )
    self._agent_state[key] = value
```

### Testing

Assert ownership boundaries in tests:

```python
def test_state_ownership():
    agent = MyAgent()
    
    # Agent can modify own state
    agent.set_state("_temp", 123)
    
    # Agent CANNOT modify memory state directly
    with pytest.raises(StateViolationError):
        agent.set_state("user_history", [...])
    
    # Agent CANNOT modify orchestrator state
    with pytest.raises(StateViolationError):
        agent.set_state("trace_id", "new-id")
```

---

## Persistence Contracts

### AGENT State Persistence

**Contract**: MUST NOT persist beyond shutdown.

```python
async def shutdown(self):
    # Ephemeral state discarded
    self._agent_state.clear()
```

### MEMORY State Persistence

**Contract**: MUST persist across agent restarts.

```python
async def shutdown(self):
    # Memory state persisted before shutdown
    if self._memory_dirty:
        await self.memory.flush()
```

### ORCHESTRATOR State Persistence

**Contract**: MUST emit to observability backends.

```python
async def complete(self, context: ExecutionContext):
    # Emit trace completion event
    await self.emitter.emit(
        "orchestration.complete",
        trace_id=context.trace_id
    )
```

---

## Migration Guide

### Step 1: Identify Current State

Audit existing agents for state usage:

```bash
# Find all state reads/writes
rg "(self\._state|agent_state\[|memory\.|context\.)" src/
```

### Step 2: Classify by Ownership

For each state field, ask:
- Does it survive agent restarts? → MEMORY
- Is it coordination metadata? → ORCHESTRATOR
- Is it request-scoped? → AGENT

### Step 3: Refactor Storage

**Before** (mixed ownership):
```python
class MyAgent:
    def __init__(self):
        self.state = {
            "user_history": [],      # Should be MEMORY
            "trace_id": None,        # Should be ORCHESTRATOR
            "temp_data": {}          # Correctly AGENT
        }
```

**After** (explicit ownership):
```python
class MyAgent(ManagedAgent):
    def __init__(self, memory: VectorMemory):
        super().__init__()
        self.memory = memory         # MEMORY state
        # self.context via orchestrator  # ORCHESTRATOR state
        # self._agent_state inherited    # AGENT state
    
    def owns_state(self, key: str) -> StateOwnership:
        if key == "user_history":
            return StateOwnership.MEMORY
        if key == "trace_id":
            return StateOwnership.ORCHESTRATOR
        return StateOwnership.AGENT
```

### Step 4: Update Tests

Assert ownership boundaries:

```python
def test_state_ownership():
    agent = MyAgent(memory=mock_memory)
    
    assert agent.owns_state("user_history") == StateOwnership.MEMORY
    assert agent.owns_state("trace_id") == StateOwnership.ORCHESTRATOR
    assert agent.owns_state("_temp") == StateOwnership.AGENT
```

---

## FAQ

### Q: What if state is shared between agent and memory?

**A**: Use `StateOwnership.SHARED` and document explicit protocol:

```python
def owns_state(self, key: str) -> StateOwnership:
    if key == "working_memory":
        return StateOwnership.SHARED  # Both can modify
    ...
```

Then document the shared protocol:
```python
# SHARED state protocol for "working_memory":
# - Agent: Read/write during request
# - Memory: Persist on agent shutdown
# - Coordination: Memory.flush() called by agent.shutdown()
```

### Q: How do I migrate AgentState?

**A**: Incrementally split fields by ownership:

1. Add `owns_state()` to classify fields
2. Delegate to correct systems (memory.update(), context.trace_id)
3. Remove redundant storage from AgentState
4. Update tests to assert ownership

### Q: What about StateVariablesManager?

**A**: Document as ephemeral per-thread storage:

```python
# StateVariablesManager: AGENT ownership (ephemeral, per-thread)
# - Lifetime: Single request/thread
# - Persistence: None
# - Use for: Thread-local temp data
```

### Q: Can orchestrator read agent state?

**A**: Read-only for observability, never modify:

```python
# ✅ Orchestrator can read for logging
logger.info("Agent state", agent_counters=agent._agent_state.get("_counters"))

# ❌ Orchestrator CANNOT modify
# agent._agent_state["_counters"] = 0  # Violates ownership
```

---

## References

- **AgentLifecycleProtocol**: `src/cuga/agents/lifecycle.py`
- **OrchestratorProtocol**: `src/cuga/orchestrator/protocol.py`
- **AgentState**: `src/cuga/backend/cuga_graph/state/agent_state.py`
- **VectorMemory**: `src/cuga/backend/memory/`
- **ExecutionContext**: `src/cuga/orchestrator/protocol.py`

---

## Changelog

- **2025-12-31**: Initial state ownership contract defining AGENT/MEMORY/ORCHESTRATOR boundaries

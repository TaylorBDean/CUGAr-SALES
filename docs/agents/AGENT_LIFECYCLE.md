# Agent Lifecycle Contract

> **Status**: Canonical  
> **Last Updated**: 2025-12-31  
> **Related**: `STATE_OWNERSHIP.md`, `docs/orchestrator/ORCHESTRATOR_CONTRACT.md`

## Overview

This document defines the **canonical agent lifecycle contract** for all agents in the cugar-agent system. It addresses:

1. **Unclear startup/shutdown expectations** - when and how agents initialize/terminate
2. **Missing lifecycle hooks** - no documented or enforced lifecycle methods
3. **Resource management ambiguity** - unclear who owns cleanup responsibilities
4. **State ownership confusion** - ambiguous boundaries between agent/memory/orchestrator state

All agents (PlannerAgent, WorkerAgent, CoordinatorAgent, MCP agents, custom agents) MUST follow this contract.

---

## Lifecycle States

Agents transition through well-defined states:

```
UNINITIALIZED → INITIALIZING → READY → BUSY → READY → SHUTTING_DOWN → TERMINATED
                      ↓                    ↓
                   [ERROR] ──────────→ SHUTTING_DOWN
```

### State Definitions

```python
class AgentState(str, Enum):
    UNINITIALIZED = "uninitialized"  # Created but not initialized
    INITIALIZING = "initializing"    # Startup in progress
    READY = "ready"                  # Ready for work
    BUSY = "busy"                    # Actively processing
    PAUSED = "paused"                # Temporarily suspended
    SHUTTING_DOWN = "shutting_down" # Cleanup in progress
    TERMINATED = "terminated"        # Fully cleaned up
```

### State Transitions

| From | To | Trigger | Guarantees |
|------|-----|---------|------------|
| UNINITIALIZED | INITIALIZING | `startup()` called | Resources being allocated |
| INITIALIZING | READY | Startup success | Agent ready for requests |
| INITIALIZING | SHUTTING_DOWN | Startup failure + cleanup | Partial resources freed |
| READY | BUSY | Request starts | Agent processing |
| BUSY | READY | Request completes | Agent idle again |
| READY | PAUSED | `pause()` called | Agent suspended |
| PAUSED | READY | `resume()` called | Agent active again |
| * | SHUTTING_DOWN | `shutdown()` called | Cleanup starting |
| SHUTTING_DOWN | TERMINATED | Cleanup complete | All resources freed |

**Invariant**: Once TERMINATED, state CANNOT transition again (final state).

---

## Lifecycle Protocol

### AgentLifecycleProtocol

All agents MUST implement:

```python
class AgentLifecycleProtocol(Protocol):
    async def startup(self, config: Optional[LifecycleConfig] = None) -> None:
        """Initialize agent resources."""
        ...
    
    async def shutdown(self, timeout_seconds: Optional[float] = None) -> None:
        """Clean up agent resources."""
        ...
    
    def get_state(self) -> AgentState:
        """Get current lifecycle state."""
        ...
    
    def get_metrics(self) -> LifecycleMetrics:
        """Get lifecycle metrics."""
        ...
    
    def owns_state(self, key: str) -> StateOwnership:
        """Determine who owns a specific state key."""
        ...
```

**Location**: `src/cuga/agents/lifecycle.py`

---

## Startup Contract

### `async def startup(config: Optional[LifecycleConfig] = None) -> None`

**Responsibilities**:
1. Allocate resources (connections, memory, caches)
2. Validate configuration
3. Load MEMORY state if exists
4. Register with orchestrator (if managed)
5. Transition UNINITIALIZED → INITIALIZING → READY

**Guarantees**:
- ✅ **Idempotent**: Multiple calls are safe (no-op if already READY)
- ✅ **Atomic**: Either fully succeeds (READY) or rolls back (TERMINATED if cleanup_on_error)
- ✅ **Timeout-bounded**: Completes within `config.timeout_seconds` or raises `StartupError`
- ✅ **State transitions logged**: Emits lifecycle events for observability

**Error Handling**:
```python
async def startup(self, config: Optional[LifecycleConfig] = None) -> None:
    if self._state != AgentState.UNINITIALIZED:
        return  # Idempotent - already started
    
    self._state = AgentState.INITIALIZING
    
    try:
        await self._do_startup(config or self._config)
        self._state = AgentState.READY
    except Exception:
        if self._config.cleanup_on_error:
            await self.shutdown()  # Rollback partial initialization
        raise StartupError("Initialization failed") from e
```

**State Ownership**:
- **AGENT state**: Initialized empty (`_agent_state = {}`)
- **MEMORY state**: Loaded if exists (via `memory.load()`)
- **ORCHESTRATOR state**: NOT managed by agent (provided via context)

**Example**:
```python
class MyAgent(ManagedAgent):
    async def _do_startup(self, config: LifecycleConfig) -> None:
        # 1. Allocate resources
        self.connection = await create_connection()
        
        # 2. Load memory state
        self.history = await self.memory.load("history")
        
        # 3. Initialize ephemeral state
        self._agent_state["request_count"] = 0
        
        # 4. Register with orchestrator
        await self.orchestrator.register(self)
```

---

## Shutdown Contract

### `async def shutdown(timeout_seconds: Optional[float] = None) -> None`

**Responsibilities**:
1. Release resources (close connections, free memory)
2. Persist MEMORY state if dirty
3. Deregister from orchestrator (if managed)
4. Discard AGENT state (ephemeral)
5. Transition * → SHUTTING_DOWN → TERMINATED

**Guarantees**:
- ✅ **MUST NOT raise exceptions**: Log errors, never fail shutdown
- ✅ **Timeout-bounded**: Completes within `timeout_seconds` or forcefully terminates
- ✅ **Idempotent**: Multiple calls are safe (no-op if already TERMINATED)
- ✅ **Final state**: TERMINATED is permanent (no further transitions)

**Error Handling**:
```python
async def shutdown(self, timeout_seconds: Optional[float] = None) -> None:
    if self._state == AgentState.TERMINATED:
        return  # Idempotent - already shut down
    
    self._state = AgentState.SHUTTING_DOWN
    
    try:
        await asyncio.wait_for(
            self._do_shutdown(timeout_seconds or self._config.timeout_seconds),
            timeout=timeout_seconds
        )
    except Exception as e:
        # Log but DON'T raise - shutdown must succeed
        logging.error(f"Shutdown error: {e}", exc_info=True)
    finally:
        self._state = AgentState.TERMINATED
        self._agent_state.clear()  # Discard ephemeral state
```

**State Ownership**:
- **AGENT state**: Discarded (`_agent_state.clear()`)
- **MEMORY state**: Persisted if dirty (`memory.flush()`)
- **ORCHESTRATOR state**: Notified of shutdown (`orchestrator.deregister()`)

**Example**:
```python
class MyAgent(ManagedAgent):
    async def _do_shutdown(self, timeout_seconds: float) -> None:
        # 1. Persist memory state
        if self._memory_dirty:
            await self.memory.flush()
        
        # 2. Release resources
        await self.connection.close()
        
        # 3. Deregister
        await self.orchestrator.deregister(self)
        
        # 4. Ephemeral state discarded automatically by ManagedAgent
```

---

## Resource Management

### Resource Types

| Resource | Owner | Lifecycle | Cleanup |
|----------|-------|-----------|---------|
| Database connections | AGENT | startup → shutdown | `connection.close()` |
| Memory state | MEMORY | Cross-request | `memory.flush()` |
| Temp files | AGENT | startup → shutdown | `os.remove(temp_file)` |
| Background tasks | AGENT | startup → shutdown | `task.cancel()` |
| Embeddings | MEMORY | Persistent | `memory.persist()` |

### Context Manager Pattern

**Recommended**: Use async context managers for automatic lifecycle:

```python
async with agent_lifecycle(my_agent) as agent:
    result = await agent.process(request)
# shutdown() called automatically even on error
```

Or inherit `ManagedAgent`:

```python
class MyAgent(ManagedAgent):
    async def _do_startup(self, config: LifecycleConfig) -> None:
        # Startup logic
        ...
    
    async def _do_shutdown(self, timeout_seconds: float) -> None:
        # Cleanup logic
        ...

# Usage
async with MyAgent() as agent:
    await agent.process(request)
```

---

## Hook Execution Order

### Startup Hooks

```
1. __init__()                    # Object construction
2. startup(config)               # Lifecycle start
   ├─ _state = INITIALIZING
   ├─ _do_startup(config)        # Subclass logic
   │  ├─ Allocate resources
   │  ├─ Load memory state
   │  ├─ Register with orchestrator
   │  └─ Initialize ephemeral state
   └─ _state = READY
```

### Shutdown Hooks

```
1. shutdown(timeout)             # Lifecycle end
   ├─ _state = SHUTTING_DOWN
   ├─ _do_shutdown(timeout)      # Subclass logic
   │  ├─ Persist memory state
   │  ├─ Release resources
   │  └─ Deregister from orchestrator
   ├─ _agent_state.clear()       # Discard ephemeral state
   └─ _state = TERMINATED
```

### Request Hooks (Optional)

Agents MAY implement request-level hooks:

```
1. @requires_state(AgentState.READY)  # Enforce preconditions
2. _state = BUSY                      # Mark active
3. process(request)                   # Business logic
4. _state = READY                     # Mark idle
```

---

## State Ownership

See `STATE_OWNERSHIP.md` for detailed rules. Summary:

| Owner | Scope | Lifetime | Mutation |
|-------|-------|----------|----------|
| **AGENT** | Request-scoped | startup → shutdown | Agent read/write |
| **MEMORY** | Cross-request | Persistent | Memory read/write, Agent read-only |
| **ORCHESTRATOR** | Trace-scoped | Trace lifecycle | Orchestrator write, Agent read-only |

**Key Rules**:
- Agents CANNOT modify MEMORY state directly (use `memory.update()`)
- Agents CANNOT modify ORCHESTRATOR state (read-only `context.trace_id`)
- AGENT state is ephemeral (discarded on shutdown)

**Violation Detection**:
```python
def owns_state(self, key: str) -> StateOwnership:
    if key.startswith("_"):
        return StateOwnership.AGENT
    if key in {"history", "embeddings"}:
        return StateOwnership.MEMORY
    if key in {"trace_id", "routing"}:
        return StateOwnership.ORCHESTRATOR
    return StateOwnership.AGENT

def set_state(self, key: str, value: Any):
    owner = self.owns_state(key)
    if owner != StateOwnership.AGENT:
        raise StateViolationError(key, owner, StateOwnership.AGENT)
    self._agent_state[key] = value
```

---

## Error Handling

### Startup Errors

**Behavior**: Fail fast, optionally rollback.

```python
try:
    await agent.startup(config)
except StartupError as e:
    logger.error(f"Agent startup failed: {e}")
    # Agent already cleaned up if cleanup_on_error=True
```

**Configuration**:
```python
config = LifecycleConfig(
    retry_on_failure=True,     # Retry failed startup
    max_retries=3,             # Max retry attempts
    cleanup_on_error=True      # Rollback on failure
)
```

### Shutdown Errors

**Behavior**: Log but don't raise (shutdown must succeed).

```python
async def shutdown(self):
    try:
        await self._do_shutdown()
    except Exception as e:
        logging.error(f"Shutdown error: {e}", exc_info=True)
        # Continue - mark TERMINATED anyway
    finally:
        self._state = AgentState.TERMINATED
```

### Request Errors

**Behavior**: Preserve READY state unless fatal.

```python
@requires_state(AgentState.READY)
async def process(self, request):
    self._state = AgentState.BUSY
    try:
        result = await self._do_process(request)
        return result
    except RecoverableError:
        # Recover to READY
        self._state = AgentState.READY
        raise
    except FatalError:
        # Force shutdown
        await self.shutdown()
        raise
    finally:
        if self._state == AgentState.BUSY:
            self._state = AgentState.READY
```

---

## Testing Requirements

### Lifecycle Compliance Tests

All agent implementations MUST pass:

```python
async def test_lifecycle_compliance(agent: AgentLifecycleProtocol):
    # 1. Initial state
    assert agent.get_state() == AgentState.UNINITIALIZED
    
    # 2. Startup
    await agent.startup()
    assert agent.get_state() == AgentState.READY
    
    # 3. Idempotent startup
    await agent.startup()  # Should be no-op
    assert agent.get_state() == AgentState.READY
    
    # 4. Shutdown
    await agent.shutdown()
    assert agent.get_state() == AgentState.TERMINATED
    
    # 5. Idempotent shutdown
    await agent.shutdown()  # Should be no-op
    assert agent.get_state() == AgentState.TERMINATED
```

### State Ownership Tests

```python
def test_state_ownership(agent: AgentLifecycleProtocol):
    # Agent can modify own state
    agent.set_state("_temp", 123)
    assert agent.owns_state("_temp") == StateOwnership.AGENT
    
    # Agent CANNOT modify memory state
    with pytest.raises(StateViolationError):
        agent.set_state("user_history", [])
    
    # Agent CANNOT modify orchestrator state
    with pytest.raises(StateViolationError):
        agent.set_state("trace_id", "new-id")
```

### Resource Cleanup Tests

```python
async def test_resource_cleanup(agent: ManagedAgent):
    await agent.startup()
    
    # Verify resources allocated
    assert agent.connection is not None
    
    await agent.shutdown()
    
    # Verify resources released
    assert agent.connection.is_closed()
    assert agent._agent_state == {}  # Ephemeral state cleared
```

### Error Handling Tests

```python
async def test_startup_failure_cleanup(agent: ManagedAgent):
    # Simulate startup failure
    with pytest.raises(StartupError):
        await agent.startup(fail_config)
    
    # Verify cleanup happened
    assert agent.get_state() == AgentState.TERMINATED
    assert agent.connection is None
```

---

## Migration Guide

### Step 1: Identify Current Agents

Find all agent implementations:

```bash
rg "class.*Agent.*:" src/ --type py
```

### Step 2: Add Lifecycle Protocol

**Before** (no lifecycle):
```python
class MyAgent:
    def __init__(self):
        self.connection = create_connection()  # ❌ Synchronous init
    
    def process(self, request):
        return do_work(request)
```

**After** (with lifecycle):
```python
class MyAgent(ManagedAgent):
    async def _do_startup(self, config: LifecycleConfig) -> None:
        self.connection = await create_connection()  # ✅ Async init
    
    async def _do_shutdown(self, timeout_seconds: float) -> None:
        await self.connection.close()  # ✅ Cleanup
    
    @requires_state(AgentState.READY)
    async def process(self, request):
        self._state = AgentState.BUSY
        try:
            return await self._do_work(request)
        finally:
            self._state = AgentState.READY
```

### Step 3: Clarify State Ownership

Use `owns_state()` to declare ownership:

```python
def owns_state(self, key: str) -> StateOwnership:
    if key == "user_history":
        return StateOwnership.MEMORY  # Persistent
    if key == "trace_id":
        return StateOwnership.ORCHESTRATOR  # Coordination
    return StateOwnership.AGENT  # Ephemeral by default
```

### Step 4: Update Usage

**Before**:
```python
agent = MyAgent()
agent.process(request)  # ❌ No lifecycle management
```

**After**:
```python
async with MyAgent() as agent:
    await agent.process(request)  # ✅ Automatic lifecycle
```

Or explicit:
```python
agent = MyAgent()
await agent.startup()
try:
    await agent.process(request)
finally:
    await agent.shutdown()
```

### Step 5: Add Tests

Create lifecycle compliance tests:

```python
@pytest.mark.asyncio
async def test_my_agent_lifecycle():
    agent = MyAgent()
    
    # Test startup
    await agent.startup()
    assert agent.get_state() == AgentState.READY
    
    # Test processing
    result = await agent.process(request)
    assert result is not None
    
    # Test shutdown
    await agent.shutdown()
    assert agent.get_state() == AgentState.TERMINATED
```

---

## Integration with Orchestration

### OrchestratorProtocol Integration

Orchestrators manage agent lifecycles:

```python
class MyOrchestrator(OrchestratorProtocol):
    async def orchestrate(self, context: ExecutionContext):
        # 1. Initialize agents
        lifecycle = await self.get_lifecycle()
        await lifecycle.initialize(context)
        
        # 2. Route and execute
        decision = await self.make_routing_decision(context)
        agent = self._get_agent(decision.target)
        
        if agent.get_state() != AgentState.READY:
            await agent.startup()
        
        result = await agent.process(context)
        
        # 3. Cleanup
        await lifecycle.teardown(context)
```

### Lifecycle Propagation

Trace context propagates through lifecycle:

```python
async def startup(self, config: LifecycleConfig) -> None:
    self._state = AgentState.INITIALIZING
    
    # Emit lifecycle event with trace context
    await self.emitter.emit(
        "agent.startup",
        trace_id=self.context.trace_id,
        state="initializing"
    )
    
    await self._do_startup(config)
    
    await self.emitter.emit(
        "agent.startup",
        trace_id=self.context.trace_id,
        state="ready"
    )
```

---

## FAQ

### Q: When should I call `startup()`?

**A**: Before any work. Orchestrators typically call it, or use context managers for automatic startup.

```python
# Option 1: Explicit
await agent.startup()
await agent.process(request)

# Option 2: Context manager (preferred)
async with agent_lifecycle(agent) as a:
    await a.process(request)
```

### Q: Must agents implement `AgentLifecycleProtocol`?

**A**: Yes, all agents MUST implement the protocol. Use `ManagedAgent` base class for defaults.

### Q: What if startup fails?

**A**: Configure `cleanup_on_error=True` to automatically rollback:

```python
config = LifecycleConfig(cleanup_on_error=True)
await agent.startup(config)  # Auto-cleanup on failure
```

### Q: Can agents be reused after shutdown?

**A**: No, TERMINATED is final. Create a new instance:

```python
agent = MyAgent()
await agent.startup()
await agent.shutdown()
# agent.startup()  # ❌ Won't work - create new instance
agent = MyAgent()  # ✅ Create fresh instance
```

### Q: How do I pause/resume agents?

**A**: Implement PAUSED state transitions:

```python
async def pause(self):
    if self._state == AgentState.READY:
        self._state = AgentState.PAUSED

async def resume(self):
    if self._state == AgentState.PAUSED:
        self._state = AgentState.READY
```

### Q: What about synchronous agents?

**A**: Convert to async or use `asyncio.to_thread()`:

```python
async def _do_startup(self, config: LifecycleConfig) -> None:
    # Wrap sync code in async
    await asyncio.to_thread(self._sync_startup, config)
```

---

## References

- **AgentLifecycleProtocol**: `src/cuga/agents/lifecycle.py`
- **State Ownership**: `docs/agents/STATE_OWNERSHIP.md`
- **OrchestratorProtocol**: `docs/orchestrator/ORCHESTRATOR_CONTRACT.md`
- **AGENTS.md Guardrails**: `docs/AGENTS.md`

---

## Changelog

- **2025-12-31**: Initial agent lifecycle contract defining startup/shutdown guarantees, state ownership, resource management

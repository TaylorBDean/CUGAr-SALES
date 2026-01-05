# Agent Lifecycle and State Ownership - Implementation Summary

> **Date**: 2025-12-31  
> **Priority**: P1 Critical  
> **Status**: Complete (Protocol Definition & Documentation)

## Problem Statement

**Original Issue**: Priority 1 "Clarify Agent Lifecycle and Ownership"

Unclear startup/shutdown expectations and state ownership ambiguity across the codebase:

1. **Unclear startup/shutdown expectations** - no documented lifecycle contracts
2. **No lifecycle hooks documented or enforced** - agents lack initialize/terminate methods
3. **State ownership ambiguity** between:
   - AgentState (LangGraph, 855+ lines mixing concerns)
   - VariablesManager (standalone storage)
   - StateVariablesManager (per-thread in AgentState)
   - VectorMemory (agent memory)
   - ExecutionContext (orchestrator coordination)

This made orchestration brittle and limited agent composability.

---

## Solution Overview

Created **canonical lifecycle and state ownership contracts** resolving all ambiguities:

### 1. AgentLifecycleProtocol (Canonical)

**Location**: `src/cuga/agents/lifecycle.py` (400+ lines)

Defines explicit contracts for:
- **startup()**: Idempotent, timeout-bounded, atomic initialization
- **shutdown()**: Error-safe cleanup (MUST NOT raise)
- **get_state()**: Current lifecycle state (UNINITIALIZED → READY → TERMINATED)
- **owns_state()**: State ownership determination (AGENT/MEMORY/ORCHESTRATOR)
- **get_metrics()**: Lifecycle metrics collection

**Key Features**:
- Lifecycle states: UNINITIALIZED → INITIALIZING → READY → BUSY → SHUTTING_DOWN → TERMINATED
- Resource management guarantees (cleanup even on errors)
- Context manager support (`async with agent:`)
- Base class `ManagedAgent` with defaults

### 2. State Ownership Contract

**Location**: `docs/agents/STATE_OWNERSHIP.md` (comprehensive guide)

Clarified who owns what state:

| Owner | Scope | Lifetime | Examples | Mutation |
|-------|-------|----------|----------|----------|
| **AGENT** | Request-scoped | startup → shutdown | `current_request`, `_cache` | Agent read/write |
| **MEMORY** | Cross-request | Persistent | `user_history`, `embeddings` | Memory read/write, Agent read-only |
| **ORCHESTRATOR** | Trace-scoped | Trace lifecycle | `trace_id`, `routing` | Orchestrator write, Agent read-only |

**Key Rules**:
- AGENT state is ephemeral (discarded on shutdown)
- MEMORY state persists across restarts
- ORCHESTRATOR state is read-only for agents
- `StateViolationError` raised on mutation violations

### 3. Comprehensive Documentation

**Created Files**:
- `docs/agents/AGENT_LIFECYCLE.md` (800+ lines): Complete lifecycle contract
- `docs/agents/STATE_OWNERSHIP.md` (600+ lines): State ownership boundaries
- `src/cuga/agents/README.md` (400+ lines): Module quick start guide

**Updated Files**:
- `AGENTS.md`: Added "Agent Lifecycle & State Ownership" section
- `docs/AGENTS.md`: Mirrored root file updates
- `CHANGELOG.md`: Documented lifecycle protocol addition

### 4. Test Suite

**Location**: `tests/test_agent_lifecycle.py` (400+ lines)

Comprehensive tests covering:
- Startup/shutdown idempotency
- State transition atomicity
- Error handling (startup failures, shutdown errors)
- State ownership enforcement
- Context manager lifecycle
- Metrics collection
- Decorator enforcement (`@requires_state`)
- Compliance test suite for all agents

---

## Files Created/Modified

### Created Files

1. **`src/cuga/agents/lifecycle.py`** (400 lines)
   - AgentLifecycleProtocol, ManagedAgent, AgentState, StateOwnership
   - Lifecycle configuration and metrics
   - Utilities: `@requires_state`, `agent_lifecycle()`
   - Exceptions: StartupError, ShutdownError, StateViolationError

2. **`docs/agents/AGENT_LIFECYCLE.md`** (800 lines)
   - Lifecycle states and transitions
   - Startup/shutdown contracts
   - Resource management patterns
   - Hook execution order
   - Error handling strategies
   - Testing requirements
   - Migration guide

3. **`docs/agents/STATE_OWNERSHIP.md`** (600 lines)
   - Ownership model (AGENT/MEMORY/ORCHESTRATOR)
   - Ownership boundaries per system
   - Mapping to current systems (AgentState, VariablesManager, VectorMemory)
   - Violation detection and enforcement
   - Persistence contracts
   - Migration guide

4. **`src/cuga/agents/README.md`** (400 lines)
   - Quick start guide
   - API reference
   - Usage examples
   - Testing guidance
   - Migration steps
   - FAQ

5. **`tests/test_agent_lifecycle.py`** (400 lines)
   - Lifecycle compliance tests (startup, shutdown, idempotency)
   - State ownership tests
   - Context manager tests
   - Decorator tests
   - Integration tests
   - Canonical compliance test suite

### Modified Files

1. **`src/cuga/agents/__init__.py`**
   - Added lifecycle exports to existing module

2. **`AGENTS.md`** (root)
   - Added "Agent Lifecycle & State Ownership" section
   - Added AgentLifecycleProtocol to canonical contracts

3. **`docs/AGENTS.md`** (canonical)
   - Mirrored root file changes

4. **`CHANGELOG.md`**
   - Documented lifecycle protocol under "## vNext"

---

## Architecture

### Lifecycle State Machine

```
┌──────────────┐
│UNINITIALIZED │
└──────┬───────┘
       │ startup()
       ▼
┌──────────────┐
│ INITIALIZING │──────┐
└──────┬───────┘      │ error + cleanup
       │ success      │
       ▼              ▼
┌──────────────┐  ┌───────────────┐
│    READY     │  │ SHUTTING_DOWN │
└──────┬───────┘  └───────┬───────┘
       │ request          │
       ▼                  │
┌──────────────┐          │
│     BUSY     │──────────┘
└──────┬───────┘ shutdown()
       │ complete
       ▼
    [READY]
       │ shutdown()
       ▼
┌───────────────┐
│ SHUTTING_DOWN │
└───────┬───────┘
        │
        ▼
┌───────────────┐
│  TERMINATED   │ [FINAL]
└───────────────┘
```

### State Ownership Architecture

```
┌─────────────────────────────────────────────────────┐
│                   ORCHESTRATOR                      │
│  ┌─────────────────────────────────────────────┐   │
│  │ ExecutionContext (Coordination State)       │   │
│  │ - trace_id (immutable)                      │   │
│  │ - profile                                   │   │
│  │ - parent_context                            │   │
│  └─────────────────────────────────────────────┘   │
│                       │ read-only                   │
│                       ▼                             │
│  ┌─────────────────────────────────────────────┐   │
│  │              AGENT (Ephemeral)              │   │
│  │ ┌────────────────────────────────────────┐  │   │
│  │ │ _agent_state: Dict[str, Any]           │  │   │
│  │ │ - current_request                      │  │   │
│  │ │ - temp_cache                           │  │   │
│  │ │ - _internal_counters                   │  │   │
│  │ │ [Discarded on shutdown]                │  │   │
│  │ └────────────────────────────────────────┘  │   │
│  │         │ query()              │ update()     │   │
│  │         ▼                      ▼              │   │
│  │ ┌───────────────┐      ┌─────────────────┐  │   │
│  │ │    MEMORY     │      │ ORCHESTRATOR    │  │   │
│  │ │  (Read-Only)  │      │  (Read-Only)    │  │   │
│  │ └───────────────┘      └─────────────────┘  │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
                      │
                      ▼
        ┌──────────────────────────────┐
        │   MEMORY (Persistent State)  │
        │ - user_history               │
        │ - embeddings                 │
        │ - learned_facts              │
        │ [Survives restarts]          │
        └──────────────────────────────┘
```

---

## Testing Strategy

### 1. Lifecycle Compliance Tests

Every agent MUST pass:

```python
@pytest.mark.asyncio
async def test_agent_lifecycle_compliance(agent):
    # Initial state
    assert agent.get_state() == AgentState.UNINITIALIZED
    
    # Startup
    await agent.startup()
    assert agent.get_state() == AgentState.READY
    
    # Idempotent startup
    await agent.startup()
    assert agent.get_state() == AgentState.READY
    
    # Shutdown
    await agent.shutdown()
    assert agent.get_state() == AgentState.TERMINATED
    
    # Idempotent shutdown
    await agent.shutdown()
    assert agent.get_state() == AgentState.TERMINATED
```

### 2. State Ownership Tests

```python
def test_state_ownership(agent):
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

### 3. Resource Cleanup Tests

```python
async def test_resource_cleanup(agent):
    await agent.startup()
    assert agent.connection is not None
    
    await agent.shutdown()
    
    # Verify cleanup
    assert agent.connection.is_closed()
    assert agent._agent_state == {}
```

---

## Migration Path

### Phase 1: Protocol Definition (COMPLETE ✅)

- [x] Define AgentLifecycleProtocol
- [x] Create ManagedAgent base class
- [x] Document state ownership boundaries
- [x] Create comprehensive documentation
- [x] Create test suite
- [x] Update AGENTS.md guardrails

### Phase 2: Modular Agent Implementation (TODO)

- [ ] Implement lifecycle in PlannerAgent
- [ ] Implement lifecycle in WorkerAgent
- [ ] Implement lifecycle in CoordinatorAgent
- [ ] Update agent tests for compliance

### Phase 3: Backend Agent Migration (TODO)

- [ ] Refactor AgentState to delegate to correct owners
- [ ] Clarify VariablesManager persistence semantics
- [ ] Document StateVariablesManager as ephemeral
- [ ] Migrate AgentRunner to use AgentLifecycleProtocol

### Phase 4: MCP Agent Migration (TODO)

- [ ] Update MCP agents to implement lifecycle protocol
- [ ] Integrate with existing LifecycleManager
- [ ] Add lifecycle compliance tests

---

## Integration Points

### With OrchestratorProtocol

Orchestrators manage agent lifecycles:

```python
class MyOrchestrator(OrchestratorProtocol):
    async def orchestrate(self, context: ExecutionContext):
        # Initialize agents
        lifecycle = await self.get_lifecycle()
        await lifecycle.initialize(context)
        
        # Route to agent
        agent = self._get_agent(target)
        if agent.get_state() != AgentState.READY:
            await agent.startup()
        
        result = await agent.process(context)
        
        # Cleanup
        await lifecycle.teardown(context)
```

### With VectorMemory

Memory is persistent, agents read-only:

```python
class MyAgent(ManagedAgent):
    async def _do_startup(self, config):
        # Load memory state
        self.history = await self.memory.load("history")
    
    async def process(self, request):
        # Read memory
        history = await self.memory.query("history")
        
        # Write via memory system (not direct)
        await self.memory.update("learned_facts", new_fact)
    
    async def _do_shutdown(self, timeout_seconds):
        # Memory persisted by memory system
        if self._memory_dirty:
            await self.memory.flush()
```

---

## Success Criteria

### Protocol Definition (COMPLETE ✅)

- [x] AgentLifecycleProtocol defines startup/shutdown contracts
- [x] State ownership boundaries documented (AGENT/MEMORY/ORCHESTRATOR)
- [x] ManagedAgent provides default implementation
- [x] Context manager support for automatic lifecycle
- [x] Comprehensive test suite created
- [x] Documentation covers all aspects (lifecycle, ownership, migration)
- [x] AGENTS.md updated with new requirements
- [x] CHANGELOG.md documents changes

### Implementation (TODO)

- [ ] PlannerAgent, WorkerAgent, CoordinatorAgent implement protocol
- [ ] All agents pass lifecycle compliance tests
- [ ] AgentState refactored to delegate correctly
- [ ] State ownership enforced at runtime
- [ ] Migration complete with no regressions

---

## References

### Documentation

- **AGENT_LIFECYCLE.md**: `docs/agents/AGENT_LIFECYCLE.md`
- **STATE_OWNERSHIP.md**: `docs/agents/STATE_OWNERSHIP.md`
- **Module README**: `src/cuga/agents/README.md`
- **Guardrails**: `AGENTS.md`, `docs/AGENTS.md`
- **Orchestrator Contract**: `docs/orchestrator/ORCHESTRATOR_CONTRACT.md`

### Code

- **Protocol**: `src/cuga/agents/lifecycle.py`
- **Tests**: `tests/test_agent_lifecycle.py`
- **Existing Agents**: `src/cuga/modular/agents.py`, `src/cuga/backend/cuga_graph/`

### Related Work

- **OrchestratorProtocol**: Completed Priority 1 task, defines orchestration contracts
- **AGENTS.md Guardrails**: Root canonical source for all agent contracts

---

## Next Steps

1. **Implement Lifecycle in Modular Agents** (Task 3)
   - Modify `src/cuga/modular/agents.py`
   - Add startup/shutdown methods to PlannerAgent, WorkerAgent, CoordinatorAgent
   - Preserve existing plan()/execute() logic

2. **State Ownership Refactoring**
   - Split AgentState by ownership (AGENT/MEMORY/ORCHESTRATOR)
   - Clarify VariablesManager persistence
   - Enforce ownership boundaries at runtime

3. **Testing and Validation**
   - Run compliance tests on all agents
   - Verify state ownership enforcement
   - Check resource cleanup under errors

4. **Documentation Updates**
   - Add migration notes for existing agents
   - Update examples to use lifecycle protocol
   - Create video/tutorial for developers

---

**Status**: ✅ **Protocol Definition Complete**  
**Remaining**: Implementation in existing agents (incremental migration)  
**Priority**: P1 Critical (blocks clean integration)

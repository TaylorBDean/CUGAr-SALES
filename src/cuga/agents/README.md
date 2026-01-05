# Agent Lifecycle Management

> **Status**: Canonical  
> **Module**: `src/cuga/agents/`  
> **Documentation**: `docs/agents/AGENT_LIFECYCLE.md`, `docs/agents/STATE_OWNERSHIP.md`

## Overview

This module provides **canonical lifecycle protocols** for all agents in cugar-agent, addressing:

- ✅ **Clear startup/shutdown contracts** with idempotency, timeouts, and error handling
- ✅ **Unambiguous state ownership** separating AGENT (ephemeral), MEMORY (persistent), and ORCHESTRATOR (coordination) state
- ✅ **Resource management guarantees** ensuring cleanup even on errors
- ✅ **Composability** across PlannerAgent, WorkerAgent, CoordinatorAgent, and custom agents

## Quick Start

### Basic Usage

```python
from cuga.agents import ManagedAgent, AgentState, AgentLifecycleProtocol

class MyAgent(ManagedAgent):
    async def _do_startup(self, config):
        """Initialize resources."""
        self.connection = await create_connection()
        self.cache = {}
    
    async def _do_shutdown(self, timeout_seconds):
        """Release resources."""
        await self.connection.close()
        # self._agent_state cleared automatically

# Context manager (recommended)
async with MyAgent() as agent:
    result = await agent.process(request)
# Automatic cleanup even on error
```

### State Ownership

```python
from cuga.agents import StateOwnership

class MyAgent(ManagedAgent):
    def owns_state(self, key: str) -> StateOwnership:
        """Declare state ownership."""
        if key == "user_history":
            return StateOwnership.MEMORY  # Persistent
        if key == "trace_id":
            return StateOwnership.ORCHESTRATOR  # Coordination
        return StateOwnership.AGENT  # Ephemeral by default
```

### Lifecycle Enforcement

```python
from cuga.agents import requires_state, AgentState

class MyAgent(ManagedAgent):
    @requires_state(AgentState.READY, AgentState.BUSY)
    async def process(self, request):
        """Only callable when READY or BUSY."""
        self._state = AgentState.BUSY
        try:
            return await self._do_process(request)
        finally:
            self._state = AgentState.READY
```

## Lifecycle States

Agents transition through well-defined states:

```
UNINITIALIZED → INITIALIZING → READY → BUSY → READY → SHUTTING_DOWN → TERMINATED
                      ↓                    ↓
                   [ERROR] ──────────→ SHUTTING_DOWN
```

### State Definitions

| State | Meaning | Transitions |
|-------|---------|-------------|
| `UNINITIALIZED` | Created but not initialized | → INITIALIZING |
| `INITIALIZING` | Startup in progress | → READY, SHUTTING_DOWN |
| `READY` | Ready for work | → BUSY, PAUSED, SHUTTING_DOWN |
| `BUSY` | Actively processing | → READY, SHUTTING_DOWN |
| `PAUSED` | Temporarily suspended | → READY, SHUTTING_DOWN |
| `SHUTTING_DOWN` | Cleanup in progress | → TERMINATED |
| `TERMINATED` | Fully cleaned up | [FINAL] |

## State Ownership

Clear boundaries between agent, memory, and orchestrator state:

| Owner | Scope | Lifetime | Examples | Mutation |
|-------|-------|----------|----------|----------|
| **AGENT** | Request | startup → shutdown | `_cache`, `current_request` | Agent read/write |
| **MEMORY** | Cross-request | Persistent | `user_history`, `embeddings` | Memory read/write, Agent read-only |
| **ORCHESTRATOR** | Trace | Trace lifecycle | `trace_id`, `routing` | Orchestrator write, Agent read-only |

### Key Rules

✅ **Allowed**:
- Agents CAN modify own ephemeral state
- Agents CAN read memory state via `memory.query()`
- Agents CAN read orchestrator context via `context.trace_id`

❌ **Forbidden**:
- Agents CANNOT directly modify memory state (use `memory.update()`)
- Agents CANNOT modify orchestrator state
- Memory CANNOT access agent ephemeral state

## API Reference

### AgentLifecycleProtocol

```python
class AgentLifecycleProtocol(Protocol):
    async def startup(self, config: Optional[LifecycleConfig] = None) -> None:
        """Initialize agent resources. Idempotent, timeout-bounded."""
        ...
    
    async def shutdown(self, timeout_seconds: Optional[float] = None) -> None:
        """Release resources. MUST NOT raise exceptions."""
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

### ManagedAgent

```python
class ManagedAgent(ABC):
    """Base class with default lifecycle implementation."""
    
    @abstractmethod
    async def _do_startup(self, config: LifecycleConfig) -> None:
        """Subclass-specific startup logic."""
        ...
    
    @abstractmethod
    async def _do_shutdown(self, timeout_seconds: float) -> None:
        """Subclass-specific cleanup logic."""
        ...
```

### LifecycleConfig

```python
@dataclass(frozen=True)
class LifecycleConfig:
    """Configuration for agent lifecycle management."""
    
    timeout_seconds: float = 30.0          # Max startup/shutdown time
    retry_on_failure: bool = False         # Retry failed startup
    max_retries: int = 3                   # Max retry attempts
    cleanup_on_error: bool = True          # Rollback on startup failure
    state_persistence: StateOwnership = StateOwnership.MEMORY
```

### Utilities

```python
# Decorator: enforce state preconditions
@requires_state(AgentState.READY)
async def process(self, request):
    ...

# Context manager: automatic lifecycle
async with agent_lifecycle(my_agent) as agent:
    await agent.process(request)
```

### Exceptions

```python
class StartupError(Exception):
    """Raised when startup fails unrecoverably."""
    pass

class ShutdownError(Exception):
    """Raised when shutdown fails (should be logged, not raised)."""
    pass

class StateViolationError(Exception):
    """Raised when state ownership rules are violated."""
    pass
```

## Testing

All agent implementations MUST pass lifecycle compliance tests:

```python
import pytest
from cuga.agents import AgentState

@pytest.mark.asyncio
async def test_lifecycle_compliance(agent):
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

## Migration Guide

### Step 1: Inherit ManagedAgent

**Before**:
```python
class MyAgent:
    def __init__(self):
        self.connection = create_connection()  # ❌ Sync init
```

**After**:
```python
class MyAgent(ManagedAgent):
    async def _do_startup(self, config):
        self.connection = await create_connection()  # ✅ Async init
    
    async def _do_shutdown(self, timeout_seconds):
        await self.connection.close()
```

### Step 2: Declare State Ownership

```python
def owns_state(self, key: str) -> StateOwnership:
    if key == "user_history":
        return StateOwnership.MEMORY
    if key == "trace_id":
        return StateOwnership.ORCHESTRATOR
    return StateOwnership.AGENT
```

### Step 3: Use Context Managers

**Before**:
```python
agent = MyAgent()
agent.process(request)  # ❌ No lifecycle management
```

**After**:
```python
async with MyAgent() as agent:
    await agent.process(request)  # ✅ Automatic cleanup
```

## Integration with Orchestration

Orchestrators manage agent lifecycles:

```python
from cuga.orchestrator import OrchestratorProtocol, ExecutionContext

class MyOrchestrator(OrchestratorProtocol):
    async def orchestrate(self, context: ExecutionContext):
        # Initialize agents
        lifecycle = await self.get_lifecycle()
        await lifecycle.initialize(context)
        
        # Route to agent
        decision = await self.make_routing_decision(context)
        agent = self._get_agent(decision.target)
        
        if agent.get_state() != AgentState.READY:
            await agent.startup()
        
        result = await agent.process(context)
        
        # Cleanup
        await lifecycle.teardown(context)
```

## Documentation

### Comprehensive Guides
- **[AGENT_LIFECYCLE.md](../../docs/agents/AGENT_LIFECYCLE.md)**: Complete lifecycle contract documentation
- **[STATE_OWNERSHIP.md](../../docs/agents/STATE_OWNERSHIP.md)**: State ownership boundaries and rules
- **[ORCHESTRATOR_CONTRACT.md](../../docs/orchestrator/ORCHESTRATOR_CONTRACT.md)**: Orchestrator integration

### Guardrails
- **[AGENTS.md](../../AGENTS.md)**: Canonical guardrails (root)
- **[docs/AGENTS.md](../../docs/AGENTS.md)**: Canonical guardrails (docs)

## Examples

See `examples/` for complete examples:
- `examples/multi_agent_dispatch.py`: Multi-agent coordination with lifecycle
- `examples/run_langgraph_demo.py`: LangGraph integration

## FAQ

### Q: When should I call `startup()`?

**A**: Before any work. Orchestrators typically call it, or use context managers.

### Q: Must all agents implement AgentLifecycleProtocol?

**A**: Yes, this is a canonical requirement per `AGENTS.md`.

### Q: What if startup fails?

**A**: Set `cleanup_on_error=True` to automatically rollback partial initialization.

### Q: Can agents be reused after shutdown?

**A**: No, `TERMINATED` is final. Create a new instance.

## Contributing

When adding lifecycle features:

1. Update this README
2. Add tests to `tests/test_agent_lifecycle.py`
3. Update `docs/agents/AGENT_LIFECYCLE.md`
4. Update `AGENTS.md` guardrails
5. Update `CHANGELOG.md`

See `CONTRIBUTING.md` for full guidelines.

---

**Related**:
- Orchestrator Protocol: `src/cuga/orchestrator/`
- Modular Agents: `src/cuga/modular/agents.py`
- Backend Agents: `src/cuga/backend/cuga_graph/`

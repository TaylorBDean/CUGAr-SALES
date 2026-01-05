# Agent I/O Contract - Implementation Summary

> **Date**: 2025-12-31  
> **Priority**: P1 Critical  
> **Status**: Complete (Protocol Definition & Documentation)

## Problem Statement

**Original Issue**: Priority 1 "Standardize Agent Input / Output Contracts"

Agents accept and return different structures, preventing clean integration:

1. **Inconsistent inputs**: 
   - PlannerAgent: `plan(goal, metadata)`
   - WorkerAgent: `execute(steps, metadata)`
   - BackendAgents: `run(input_variables: AgentState)`
   - CoordinatorAgent: `dispatch(goal, trace_id)`

2. **No standard metadata**: trace_id, profile, priority handled inconsistently

3. **Implicit error handling**: Some agents raise exceptions, others return error strings

4. **Special-casing in orchestration**: Routing logic must handle each agent type differently

**Impact**: Prevents clean routing/orchestration, limits composability, blocks integration.

---

## Solution Overview

Created **canonical I/O contracts** that all agents MUST implement:

### 1. AgentRequest (Canonical Input)

**Location**: `src/cuga/agents/contracts.py`

Standardized input structure accepted by ALL agents:

```python
@dataclass
class AgentRequest:
    # Required
    goal: str                           # High-level objective
    task: str                           # Specific task
    metadata: RequestMetadata           # trace_id, profile, priority, timeout
    
    # Optional
    inputs: Optional[Dict[str, Any]]    # Agent-specific inputs
    context: Optional[Dict[str, Any]]   # Previous step context
    constraints: Optional[Dict[str, Any]]  # Execution constraints
    expected_output: Optional[str]      # Expected output description
```

**Key Features**:
- Required: goal, task, metadata (with trace_id)
- Optional: inputs, context, constraints, expected_output
- Validation: `validate()` checks required fields
- Serialization: `to_dict()` / `from_dict()` for persistence

### 2. AgentResponse (Canonical Output)

**Location**: `src/cuga/agents/contracts.py`

Standardized output structure returned by ALL agents:

```python
@dataclass
class AgentResponse:
    # Required
    status: ResponseStatus  # SUCCESS, ERROR, PARTIAL, PENDING, CANCELLED
    
    # Optional (based on status)
    result: Optional[Any]              # Success result
    error: Optional[AgentError]        # Error details (if ERROR)
    trace: List[Dict[str, Any]]        # Execution trace
    metadata: Dict[str, Any]           # Response metadata
    timestamp: str                     # Response timestamp
```

**Key Features**:
- Status: SUCCESS/ERROR/PARTIAL/PENDING/CANCELLED
- Result: Required for SUCCESS status
- Error: Structured AgentError for ERROR status
- Trace: Execution events with trace_id propagation
- Metadata: Performance metrics (duration_ms, cost, etc.)

### 3. AgentError (Structured Errors)

**Location**: `src/cuga/agents/contracts.py`

Structured error information instead of exceptions:

```python
@dataclass(frozen=True)
class AgentError:
    type: ErrorType               # VALIDATION, EXECUTION, TIMEOUT, etc.
    message: str                  # Human-readable error
    details: Optional[Dict]       # Additional details
    recoverable: bool = False     # Whether error is recoverable
    retry_after: Optional[float]  # Seconds to wait before retry
    trace_context: Optional[Dict] # Error context for debugging
```

**Error Types**:
- VALIDATION: Input validation failed
- EXECUTION: Execution error
- TIMEOUT: Task timeout
- RESOURCE: Resource unavailable
- PERMISSION: Permission denied
- NETWORK: Network error
- UNKNOWN: Unknown error

### 4. AgentProtocol (Canonical Interface)

**Location**: `src/cuga/agents/contracts.py`

All agents MUST implement:

```python
class AgentProtocol(Protocol):
    async def process(self, request: AgentRequest) -> AgentResponse:
        """Process request and return response. MUST NOT raise."""
        ...
```

**Rules**:
- Accepts AgentRequest
- Returns AgentResponse
- MUST NOT raise exceptions (errors in response.error)
- Propagates trace_id from request to response

---

## Files Created/Modified

### Created Files

1. **`src/cuga/agents/contracts.py`** (600 lines)
   - AgentRequest, AgentResponse, AgentError, RequestMetadata
   - ResponseStatus, ErrorType enums
   - AgentProtocol interface
   - Convenience constructors: success_response, error_response, partial_response
   - Validation: validate_request, validate_response

2. **`docs/agents/AGENT_IO_CONTRACT.md`** (1000+ lines)
   - Request structure (required/optional fields)
   - Response structure (success/error/partial)
   - Error handling (structured errors, no exceptions)
   - Metadata propagation (trace_id, profile, priority)
   - Usage examples (planning, execution, orchestration)
   - Migration guide (backward compatibility)
   - Testing requirements
   - FAQ

3. **`tests/test_agent_contracts.py`** (600 lines)
   - Request structure tests (validation, serialization)
   - Response structure tests (success, error, partial)
   - Protocol compliance tests (accepts request, returns response)
   - Error handling tests (no exceptions, structured errors)
   - Trace propagation tests
   - Metadata tests
   - Canonical compliance test suite: `test_agent_io_compliance()`

### Modified Files

1. **`src/cuga/agents/__init__.py`**
   - Added I/O contract exports

2. **`AGENTS.md`** (root)
   - Added "AgentProtocol (I/O Contract)" section

3. **`docs/AGENTS.md`** (canonical)
   - Mirrored root file changes

4. **`CHANGELOG.md`**
   - Documented I/O contract under "## vNext"

---

## Architecture

### Before (Inconsistent I/O)

```
┌─────────────┐   plan(goal, metadata)         ┌──────────────┐
│ Orchestrator├────────────────────────────────>│ PlannerAgent │
└─────────────┘   ← AgentPlan                  └──────────────┘

┌─────────────┐   execute(steps, metadata)     ┌──────────────┐
│ Orchestrator├────────────────────────────────>│ WorkerAgent  │
└─────────────┘   ← AgentResult                └──────────────┘

┌─────────────┐   run(input_variables)         ┌──────────────┐
│ Orchestrator├────────────────────────────────>│ BackendAgent │
└─────────────┘   ← AIMessage                  └──────────────┘

Problem: Each agent has different signature, orchestrator must special-case
```

### After (Standardized I/O)

```
┌─────────────┐   process(AgentRequest)        ┌──────────────┐
│ Orchestrator├────────────────────────────────>│ PlannerAgent │
└─────────────┘   ← AgentResponse              └──────────────┘

┌─────────────┐   process(AgentRequest)        ┌──────────────┐
│ Orchestrator├────────────────────────────────>│ WorkerAgent  │
└─────────────┘   ← AgentResponse              └──────────────┘

┌─────────────┐   process(AgentRequest)        ┌──────────────┐
│ Orchestrator├────────────────────────────────>│ BackendAgent │
└─────────────┘   ← AgentResponse              └──────────────┘

Solution: Uniform interface, no special-casing required
```

### Request Flow

```
1. User Request
   ↓
2. Orchestrator creates AgentRequest
   {
     goal: "Find cheap flights",
     task: "Search API",
     metadata: {trace_id, profile, timeout},
     inputs: {origin, destination},
   }
   ↓
3. Route to Agent via process()
   ↓
4. Agent processes request
   ↓
5. Agent returns AgentResponse
   {
     status: SUCCESS,
     result: {flights: [...]},
     trace: [{event, duration}],
     metadata: {duration_ms, cost},
   }
   ↓
6. Orchestrator handles response
   - If SUCCESS: use result in next step
   - If ERROR: retry if recoverable, else fail
   - If PARTIAL: continue with partial result
```

---

## Benefits

### 1. Eliminates Special-Casing

**Before**:
```python
# Orchestrator must know each agent type
if isinstance(agent, PlannerAgent):
    result = agent.plan(goal, {"trace_id": trace_id})
elif isinstance(agent, WorkerAgent):
    result = agent.execute(steps, {"trace_id": trace_id})
elif isinstance(agent, BackendAgent):
    state = AgentState(input=goal, ...)
    result = await agent.run(state)
```

**After**:
```python
# Uniform interface for all agents
request = AgentRequest(
    goal=goal,
    task=task,
    metadata=RequestMetadata(trace_id=trace_id),
    inputs=inputs,
)
response = await agent.process(request)

if response.is_success():
    result = response.result
else:
    handle_error(response.error)
```

### 2. Structured Error Handling

**Before** (inconsistent):
```python
try:
    result = agent.plan(goal)  # May raise exception
except Exception as e:
    # What type of error? Recoverable?
    logger.error(f"Error: {e}")
```

**After** (structured):
```python
response = await agent.process(request)

if response.is_error():
    error = response.error
    if error.recoverable:
        await asyncio.sleep(error.retry_after or 1.0)
        response = await agent.process(request)  # Retry
    else:
        logger.error(f"{error.type}: {error.message}")
        raise OrchestrationError(error.message)
```

### 3. Metadata Propagation

**Before** (manual):
```python
# Manually pass trace_id to each agent
result1 = planner.plan(goal, {"trace_id": trace_id})
result2 = worker.execute(steps, {"trace_id": trace_id})
```

**After** (automatic):
```python
# trace_id in RequestMetadata, propagated automatically
request = AgentRequest(..., metadata=RequestMetadata(trace_id=trace_id))
response = await agent.process(request)

# trace_id in response.trace events
assert any(event["trace_id"] == trace_id for event in response.trace)
```

### 4. Clean Orchestration

**Before** (brittle):
```python
class Orchestrator:
    async def route(self, agent_type, goal):
        if agent_type == "planner":
            agent = self.planner
            result = agent.plan(goal, self._get_metadata())
        elif agent_type == "worker":
            agent = self.worker
            result = agent.execute(self._get_steps(), self._get_metadata())
        # ... special case for each agent type
```

**After** (clean):
```python
class Orchestrator:
    async def route(self, agent_name, goal, task):
        agent = self._get_agent(agent_name)
        
        request = AgentRequest(
            goal=goal,
            task=task,
            metadata=self._get_metadata(),
        )
        
        response = await agent.process(request)
        return response
```

---

## Testing Strategy

### 1. Compliance Tests

Every agent MUST pass:

```python
@pytest.mark.asyncio
async def test_agent_io_compliance(agent: AgentProtocol):
    # Create request
    request = AgentRequest(
        goal="Test",
        task="Test",
        metadata=RequestMetadata(trace_id="test"),
    )
    
    # Process
    response = await agent.process(request)
    
    # Verify structure
    assert isinstance(response, AgentResponse)
    assert response.status in ResponseStatus
    
    # Verify status-dependent fields
    if response.status == ResponseStatus.SUCCESS:
        assert response.result is not None
    elif response.status == ResponseStatus.ERROR:
        assert response.error is not None
    
    # Verify trace propagation
    assert any("test" in str(event) for event in response.trace)
```

### 2. Error Handling Tests

```python
@pytest.mark.asyncio
async def test_agent_errors_no_exceptions(agent):
    """Verify agent returns errors instead of raising."""
    request = AgentRequest(
        goal="Test",
        task="Invalid task that will fail",
        metadata=RequestMetadata(trace_id="test"),
    )
    
    # Should NOT raise
    response = await agent.process(request)
    
    assert response.status == ResponseStatus.ERROR
    assert response.error is not None
```

### 3. Serialization Tests

```python
def test_request_roundtrip():
    """Verify AgentRequest can be serialized/deserialized."""
    original = AgentRequest(
        goal="Test",
        task="Test",
        metadata=RequestMetadata(trace_id="test"),
        inputs={"key": "value"},
    )
    
    data = original.to_dict()
    restored = AgentRequest.from_dict(data)
    
    assert restored.goal == original.goal
    assert restored.inputs == original.inputs
```

---

## Migration Path

### Phase 1: Protocol Definition (COMPLETE ✅)

- [x] Define AgentRequest, AgentResponse, AgentError
- [x] Define AgentProtocol interface
- [x] Create convenience constructors
- [x] Create validation utilities
- [x] Document I/O contract
- [x] Create compliance test suite
- [x] Update AGENTS.md guardrails

### Phase 2: Modular Agent Implementation (TODO)

- [ ] Add `process()` to PlannerAgent
- [ ] Add `process()` to WorkerAgent
- [ ] Add `process()` to CoordinatorAgent
- [ ] Keep legacy methods for backward compatibility
- [ ] Add compliance tests

### Phase 3: Backend Agent Migration (TODO)

- [ ] Add `process()` to BackendAgents
- [ ] Adapt AgentState to AgentRequest/AgentResponse
- [ ] Update orchestration logic
- [ ] Add compliance tests

### Phase 4: Orchestrator Integration (TODO)

- [ ] Update orchestrators to use AgentRequest/AgentResponse
- [ ] Remove agent type special-casing
- [ ] Implement structured error handling
- [ ] Add retry logic for recoverable errors

---

## Integration Points

### With OrchestratorProtocol

```python
class MyOrchestrator(OrchestratorProtocol):
    async def orchestrate(self, context: ExecutionContext):
        # Create request
        request = AgentRequest(
            goal=context.metadata.get("user_goal"),
            task="Plan execution",
            metadata=RequestMetadata(
                trace_id=context.trace_id,
                profile=context.profile,
            ),
        )
        
        # Route to agent
        decision = await self.make_routing_decision(context)
        agent = self._get_agent(decision.target)
        
        response = await agent.process(request)
        
        # Handle response
        if response.is_error():
            return await self.handle_error(response.error, context)
        
        return response.result
```

### With AgentLifecycleProtocol

```python
class MyAgent(ManagedAgent, AgentProtocol):
    async def _do_startup(self, config):
        """Initialize resources."""
        self.connection = await create_connection()
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """Process request per I/O contract."""
        # Agent must be READY
        if self.get_state() != AgentState.READY:
            return error_response(
                ErrorType.RESOURCE,
                "Agent not ready",
                recoverable=False,
            )
        
        # Process
        try:
            result = await self._do_work(request)
            return success_response(result)
        except Exception as e:
            return error_response(ErrorType.EXECUTION, str(e))
    
    async def _do_shutdown(self, timeout_seconds):
        """Release resources."""
        await self.connection.close()
```

---

## Success Criteria

### Protocol Definition (COMPLETE ✅)

- [x] AgentRequest defines canonical input structure
- [x] AgentResponse defines canonical output structure
- [x] AgentError provides structured error information
- [x] AgentProtocol defines uniform interface
- [x] Convenience constructors simplify response creation
- [x] Validation utilities ensure correctness
- [x] Comprehensive documentation (1000+ lines)
- [x] Complete test suite (600+ lines)
- [x] AGENTS.md updated with I/O contract requirements
- [x] CHANGELOG.md documents changes

### Implementation (TODO)

- [ ] PlannerAgent, WorkerAgent, CoordinatorAgent implement AgentProtocol
- [ ] BackendAgents implement AgentProtocol
- [ ] All agents pass compliance tests
- [ ] Orchestrators use uniform interface (no special-casing)
- [ ] Structured error handling throughout
- [ ] Migration complete with no regressions

---

## References

### Documentation

- **I/O Contract**: `docs/agents/AGENT_IO_CONTRACT.md`
- **Lifecycle Contract**: `docs/agents/AGENT_LIFECYCLE.md`
- **State Ownership**: `docs/agents/STATE_OWNERSHIP.md`
- **Orchestrator Contract**: `docs/orchestrator/ORCHESTRATOR_CONTRACT.md`
- **Guardrails**: `AGENTS.md`, `docs/AGENTS.md`

### Code

- **Protocol**: `src/cuga/agents/contracts.py`
- **Tests**: `tests/test_agent_contracts.py`
- **Existing Agents**: `src/cuga/modular/agents.py`, `src/cuga/backend/cuga_graph/`

### Related Work

- **OrchestratorProtocol**: Defines orchestration lifecycle
- **AgentLifecycleProtocol**: Defines startup/shutdown contracts
- **AGENTS.md Guardrails**: Root canonical source

---

## Next Steps

1. **Implement I/O Contract in Modular Agents** (Task 3)
   - Add `process()` to PlannerAgent, WorkerAgent, CoordinatorAgent
   - Keep legacy methods for backward compatibility
   - Pass compliance tests

2. **Update Orchestration Logic**
   - Remove agent type special-casing
   - Use uniform `process(AgentRequest)` interface
   - Implement structured error handling

3. **Migrate Backend Agents**
   - Add `process()` to all BackendAgents
   - Adapt AgentState to AgentRequest/AgentResponse
   - Pass compliance tests

4. **Documentation Updates**
   - Add examples showing before/after migration
   - Create video/tutorial for developers

---

**Status**: ✅ **Protocol Definition Complete**  
**Remaining**: Implementation in existing agents (incremental migration)  
**Priority**: P1 Critical (blocks clean integration)  
**Impact**: Eliminates special-casing, enables clean routing/orchestration

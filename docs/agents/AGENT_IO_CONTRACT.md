# Agent Input/Output Contract

> **Status**: Canonical  
> **Last Updated**: 2025-12-31  
> **Related**: `AGENT_LIFECYCLE.md`, `STATE_OWNERSHIP.md`, `docs/orchestrator/ORCHESTRATOR_CONTRACT.md`

## Problem Statement

Agents currently accept and return different structures, causing:

1. **Inconsistent inputs**: PlannerAgent takes `(goal, metadata)`, WorkerAgent takes `(steps, metadata)`, BackendAgents take `AgentState`
2. **No standard metadata**: trace_id, profile, priority handled inconsistently
3. **Implicit error handling**: Some agents raise exceptions, others return error strings
4. **Special-casing in orchestration**: Routing logic must handle each agent type differently

This prevents clean integration and makes orchestration brittle.

---

## Solution: Canonical I/O Contracts

All agents MUST accept **`AgentRequest`** and return **`AgentResponse`** to enable clean routing without special-casing.

### AgentRequest (Canonical Input)

```python
@dataclass
class AgentRequest:
    """Canonical agent input structure."""
    
    # Required fields
    goal: str                           # High-level objective
    task: str                           # Specific task description
    metadata: RequestMetadata           # trace_id, profile, priority, timeout
    
    # Optional fields
    inputs: Optional[Dict[str, Any]]    # Agent-specific inputs
    context: Optional[Dict[str, Any]]   # Previous step context
    constraints: Optional[Dict[str, Any]]  # Execution constraints
    expected_output: Optional[str]      # Expected output description
```

### AgentResponse (Canonical Output)

```python
@dataclass
class AgentResponse:
    """Canonical agent output structure."""
    
    # Required fields
    status: ResponseStatus  # SUCCESS, ERROR, PARTIAL, PENDING, CANCELLED
    
    # Optional fields (based on status)
    result: Optional[Any]              # Success result
    error: Optional[AgentError]        # Error details (if ERROR status)
    trace: List[Dict[str, Any]]        # Execution trace events
    metadata: Dict[str, Any]           # Response metadata
    timestamp: str                     # Response timestamp
```

---

## Request Structure

### Required Fields

#### 1. goal (string)

High-level objective describing what the user wants to achieve.

**Examples**:
- `"Find cheap flights from NY to LA"`
- `"Book hotel for 3 nights in Paris"`
- `"Analyze user sentiment from tweets"`

**Rules**:
- MUST be present and non-empty
- Should be concise, user-facing description
- Same goal can be decomposed into multiple tasks

#### 2. task (string)

Specific task description for this agent invocation.

**Examples**:
- `"Search flights API with origin=NY, destination=LA"`
- `"Execute plan step 1: Call searchFlights API"`
- `"Generate SQL query from natural language"`

**Rules**:
- MUST be present and non-empty
- More specific than goal (action-oriented)
- Should start with action verb (Search, Execute, Generate, etc.)

#### 3. metadata (RequestMetadata)

Standard metadata for trace propagation and execution control.

```python
@dataclass(frozen=True)
class RequestMetadata:
    trace_id: str                      # Unique trace ID (REQUIRED)
    profile: str = "default"           # Execution profile
    priority: int = 5                  # 0-10, higher = more urgent
    timeout_seconds: Optional[float]   # Max execution time
    parent_context: Optional[Dict]     # Parent trace context
    tags: Optional[Dict[str, str]]     # Custom tags
```

**Rules**:
- `trace_id` MUST be present and unique
- `profile` determines tool allowlist, budget, sandbox
- `priority` affects scheduling (0=lowest, 10=highest)
- `timeout_seconds` enforces deadline

### Optional Fields

#### 1. inputs (Dict[str, Any])

Agent-specific input data.

**Examples**:
```python
# Planning agent
inputs = {"max_tools": 5, "prefer_tools": ["searchFlights"]}

# Execution agent
inputs = {"origin": "NY", "destination": "LA", "date": "2025-01-15"}

# Code generation agent
inputs = {"language": "python", "framework": "fastapi"}
```

**Rules**:
- Schema depends on agent type
- Should be validated by agent implementation
- Defaults to empty dict if not provided

#### 2. context (Dict[str, Any])

Context from previous steps in multi-step workflows.

**Examples**:
```python
# Context from planning step
context = {
    "plan": {...},
    "selected_tools": ["searchFlights", "bookFlight"],
    "step_index": 1,
}

# Context from previous agent
context = {
    "previous_result": {"flights": [...]},
    "previous_agent": "FlightSearchAgent",
}
```

**Rules**:
- Enables chaining agents without global state
- Should contain serializable data only
- Defaults to empty dict if not provided

#### 3. constraints (Dict[str, Any])

Execution constraints (budget, resource limits, policies).

**Examples**:
```python
constraints = {
    "max_api_calls": 10,
    "max_cost_usd": 0.50,
    "allowed_tools": ["searchFlights"],
    "blocked_domains": ["evil.com"],
}
```

**Rules**:
- Enforced by PolicyEnforcer before execution
- Overrides profile defaults if more restrictive
- Defaults to empty dict if not provided

#### 4. expected_output (string)

Description of expected output format/structure.

**Examples**:
- `"List of flight objects with price, airline, departure time"`
- `"Single JSON object with booking confirmation ID"`
- `"Boolean indicating success/failure"`

**Rules**:
- Helps agents validate their output
- Used for documentation/logging
- Optional but recommended for clarity

---

## Response Structure

### Required Fields

#### 1. status (ResponseStatus)

Response status enum.

```python
class ResponseStatus(str, Enum):
    SUCCESS = "success"        # Task completed successfully
    ERROR = "error"            # Task failed unrecoverably
    PARTIAL = "partial"        # Task partially completed
    PENDING = "pending"        # Task pending (async/background)
    CANCELLED = "cancelled"    # Task cancelled
```

**Rules**:
- MUST be present
- Determines which optional fields are required
- SUCCESS requires `result`, ERROR requires `error`

### Optional Fields (Required Based on Status)

#### 1. result (Any) - Required if SUCCESS

Agent result data.

**Examples**:
```python
# Planning agent result
result = {
    "steps": [
        {"tool": "searchFlights", "inputs": {...}},
        {"tool": "bookFlight", "inputs": {...}},
    ]
}

# Execution agent result
result = {
    "flights": [
        {"price": 299, "airline": "Delta", "departure": "08:00"},
        {"price": 350, "airline": "United", "departure": "10:30"},
    ]
}

# Simple result
result = "Task completed successfully"
```

**Rules**:
- MUST be present if `status == SUCCESS`
- Schema depends on agent type
- Should match `expected_output` if provided in request

#### 2. error (AgentError) - Required if ERROR

Structured error information.

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
```python
class ErrorType(str, Enum):
    VALIDATION = "validation"      # Input validation failed
    EXECUTION = "execution"        # Execution error
    TIMEOUT = "timeout"           # Task timeout
    RESOURCE = "resource"         # Resource unavailable
    PERMISSION = "permission"     # Permission denied
    NETWORK = "network"           # Network error
    UNKNOWN = "unknown"           # Unknown error
```

**Rules**:
- MUST be present if `status == ERROR`
- `message` should be human-readable
- `recoverable=True` enables automatic retry
- `retry_after` suggests backoff delay

#### 3. trace (List[Dict[str, Any]])

Execution trace events for observability.

**Examples**:
```python
trace = [
    {"event": "plan:start", "timestamp": "2025-01-01T10:00:00Z"},
    {"event": "tool:selected", "tool": "searchFlights", "score": 0.95},
    {"event": "api:call", "url": "https://...", "duration_ms": 150},
    {"event": "plan:complete", "step_count": 3},
]
```

**Rules**:
- Each event should have `"event"` field
- Include timestamps for timing analysis
- Propagate `trace_id` from request metadata
- Emit to observability backend (OTEL, LangFuse)

#### 4. metadata (Dict[str, Any])

Response metadata (timing, cost, resource usage).

**Examples**:
```python
metadata = {
    "duration_ms": 250,
    "api_calls": 2,
    "cost_usd": 0.003,
    "tool_count": 3,
    "cache_hit": True,
}
```

**Rules**:
- Should include performance metrics
- Useful for cost tracking and optimization
- Defaults to empty dict

#### 5. timestamp (string)

Response timestamp (ISO 8601 format).

**Example**: `"2025-01-01T10:00:00.123Z"`

**Rules**:
- Auto-generated if not provided
- Use UTC timezone
- ISO 8601 format

---

## Usage Examples

### Planning Agent

```python
from cuga.agents import AgentRequest, AgentResponse, RequestMetadata, success_response

class PlannerAgent:
    async def process(self, request: AgentRequest) -> AgentResponse:
        # Validate request
        validate_request(request)
        
        # Extract inputs
        goal = request.goal
        max_tools = request.inputs.get("max_tools", 5) if request.inputs else 5
        
        # Generate plan
        steps = self._create_plan(goal, max_tools)
        
        # Build trace
        trace = [
            {"event": "plan:start", "goal": goal, "trace_id": request.metadata.trace_id},
            {"event": "plan:complete", "step_count": len(steps), "trace_id": request.metadata.trace_id},
        ]
        
        # Return success response
        return success_response(
            result={"steps": steps},
            trace=trace,
            metadata={"duration_ms": 100, "tool_count": len(steps)},
        )
```

### Execution Agent with Error Handling

```python
from cuga.agents import AgentRequest, AgentResponse, error_response, ErrorType

class WorkerAgent:
    async def process(self, request: AgentRequest) -> AgentResponse:
        try:
            # Execute steps
            result = await self._execute_steps(request.inputs["steps"])
            
            return success_response(
                result=result,
                trace=[{"event": "execute:complete"}],
            )
        
        except TimeoutError as e:
            # Return structured error
            return error_response(
                error_type=ErrorType.TIMEOUT,
                message=f"Execution timeout after {request.metadata.timeout_seconds}s",
                details={"partial_result": e.partial_result},
                recoverable=True,
                retry_after=5.0,
            )
        
        except Exception as e:
            # Unexpected error
            return error_response(
                error_type=ErrorType.EXECUTION,
                message=str(e),
                recoverable=False,
            )
```

### Orchestrator Integration

```python
from cuga.orchestrator import OrchestratorProtocol, ExecutionContext
from cuga.agents import AgentRequest, RequestMetadata

class MyOrchestrator(OrchestratorProtocol):
    async def orchestrate(self, context: ExecutionContext):
        # Create standardized request
        request = AgentRequest(
            goal=context.metadata.get("user_goal", ""),
            task="Generate execution plan",
            metadata=RequestMetadata(
                trace_id=context.trace_id,
                profile=context.profile,
                timeout_seconds=30.0,
            ),
        )
        
        # Route to planner
        planner = self._get_agent("planner")
        response = await planner.process(request)
        
        if response.is_error():
            # Handle error
            if response.error.recoverable:
                await asyncio.sleep(response.error.retry_after or 1.0)
                response = await planner.process(request)  # Retry
            else:
                raise OrchestrationError(response.error.message)
        
        # Use result in next step
        plan = response.result
        # ...
```

---

## Migration Guide

### Step 1: Identify Current Signatures

**Before (inconsistent)**:
```python
# PlannerAgent
def plan(self, goal: str, metadata: Optional[dict] = None) -> AgentPlan:
    ...

# WorkerAgent
def execute(self, steps: Iterable[dict], metadata: Optional[dict] = None) -> AgentResult:
    ...

# BackendAgent
async def run(self, input_variables: AgentState) -> AIMessage:
    ...
```

### Step 2: Add `process()` Method

**After (standardized)**:
```python
from cuga.agents import AgentRequest, AgentResponse, AgentProtocol

class PlannerAgent(AgentProtocol):
    async def process(self, request: AgentRequest) -> AgentResponse:
        """New canonical interface."""
        # Extract fields from request
        goal = request.goal
        metadata = request.metadata
        
        # Call existing plan() logic
        plan = self.plan(goal, metadata.to_dict())
        
        # Convert to AgentResponse
        return success_response(
            result={"steps": plan.steps},
            trace=plan.trace,
        )
    
    def plan(self, goal: str, metadata: Optional[dict] = None) -> AgentPlan:
        """Legacy method (keep for backward compatibility)."""
        ...
```

### Step 3: Update Callers

**Before**:
```python
# Special-casing required
if isinstance(agent, PlannerAgent):
    result = agent.plan(goal, {"trace_id": trace_id})
elif isinstance(agent, WorkerAgent):
    result = agent.execute(steps, {"trace_id": trace_id})
```

**After**:
```python
# Uniform interface
request = AgentRequest(
    goal=goal,
    task="Execute task",
    metadata=RequestMetadata(trace_id=trace_id),
    inputs={"steps": steps} if steps else None,
)
response = await agent.process(request)

if response.is_success():
    result = response.result
else:
    logger.error(f"Agent error: {response.error.message}")
```

### Step 4: Add Validation

```python
from cuga.agents import validate_request, validate_response

class MyAgent(AgentProtocol):
    async def process(self, request: AgentRequest) -> AgentResponse:
        # Validate input
        validate_request(request)
        
        # Process
        response = await self._do_process(request)
        
        # Validate output
        validate_response(response)
        
        return response
```

---

## Testing Requirements

All agents MUST pass I/O contract compliance tests:

```python
import pytest
from cuga.agents import AgentRequest, RequestMetadata, ResponseStatus

@pytest.mark.asyncio
async def test_agent_io_compliance(agent):
    """Canonical compliance test for AgentProtocol."""
    
    # Create request
    request = AgentRequest(
        goal="Test goal",
        task="Test task",
        metadata=RequestMetadata(trace_id="test-123"),
    )
    
    # Process request
    response = await agent.process(request)
    
    # Verify response structure
    assert response.status in ResponseStatus
    
    if response.status == ResponseStatus.SUCCESS:
        assert response.result is not None
    elif response.status == ResponseStatus.ERROR:
        assert response.error is not None
        assert response.error.message
    
    # Verify trace propagation
    assert any("trace_id" in event or request.metadata.trace_id in str(event) 
               for event in response.trace)
```

---

## FAQ

### Q: Can agents still use their own input/output formats internally?

**A**: Yes, the `process()` method is a facade. Internal logic can remain unchanged:

```python
async def process(self, request: AgentRequest) -> AgentResponse:
    # Adapt request to internal format
    internal_input = self._adapt_request(request)
    
    # Call internal logic
    internal_output = await self._internal_process(internal_input)
    
    # Adapt output to AgentResponse
    return self._adapt_response(internal_output)
```

### Q: What about backward compatibility?

**A**: Keep legacy methods for backward compatibility, add new `process()` method:

```python
class MyAgent:
    async def process(self, request: AgentRequest) -> AgentResponse:
        """New canonical interface."""
        return self._adapt_response(self.legacy_method(request.goal))
    
    def legacy_method(self, goal: str):
        """Legacy method (backward compatible)."""
        ...
```

### Q: How do I handle agent-specific inputs?

**A**: Use `request.inputs` dict:

```python
async def process(self, request: AgentRequest) -> AgentResponse:
    # Extract agent-specific inputs
    max_retries = request.inputs.get("max_retries", 3) if request.inputs else 3
    prefer_cached = request.inputs.get("prefer_cached", True) if request.inputs else True
    
    # Process with agent-specific logic
    ...
```

### Q: Should errors raise exceptions or return error responses?

**A**: **Return error responses** (don't raise). This enables orchestrators to handle errors gracefully:

```python
# ✅ Correct - return error response
async def process(self, request: AgentRequest) -> AgentResponse:
    try:
        result = await self._do_work()
        return success_response(result)
    except Exception as e:
        return error_response(ErrorType.EXECUTION, str(e))

# ❌ Wrong - raising exception
async def process(self, request: AgentRequest) -> AgentResponse:
    result = await self._do_work()  # May raise
    return success_response(result)
```

---

## References

- **Protocol Definition**: `src/cuga/agents/contracts.py`
- **Lifecycle Contract**: `docs/agents/AGENT_LIFECYCLE.md`
- **State Ownership**: `docs/agents/STATE_OWNERSHIP.md`
- **Orchestrator Contract**: `docs/orchestrator/ORCHESTRATOR_CONTRACT.md`
- **Guardrails**: `AGENTS.md`, `docs/AGENTS.md`

---

## Changelog

- **2025-12-31**: Initial agent I/O contract defining AgentRequest/AgentResponse structures

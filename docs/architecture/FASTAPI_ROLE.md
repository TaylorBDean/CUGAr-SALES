# FastAPI's Role in the Architecture

**Status**: Canonical  
**Last Updated**: 2025-12-31  
**Purpose**: Clarify FastAPI's architectural role to prevent mixing transport and orchestration concerns

---

## 🎯 Executive Summary

**FastAPI is a TRANSPORT LAYER ONLY, not an orchestrator.**

FastAPI serves HTTP requests and delegates to existing orchestration components (Planner, Coordinator, Workers). It provides:
- ✅ HTTP/SSE transport (endpoints, middleware, streaming)
- ✅ Authentication and budget enforcement (cross-cutting concerns)
- ✅ Request/response serialization (JSON ↔ Python objects)
- ❌ **NOT** planning logic
- ❌ **NOT** coordination decisions
- ❌ **NOT** tool execution

---

## 🏗️ Architectural Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                            │
│  (CLI, Web UI, External Services)                          │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ HTTP/SSE
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  TRANSPORT LAYER (FastAPI)                  │
│  Role: HTTP endpoints, auth, budget, serialization         │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  FastAPI App (src/cuga/backend/app.py)              │  │
│  │  - GET  /health         (health check)              │  │
│  │  - POST /plan           (synchronous planning)       │  │
│  │  - POST /execute        (streaming execution)        │  │
│  │                                                       │  │
│  │  Middleware:                                         │  │
│  │  - budget_guard()       (auth + budget enforcement)  │  │
│  │                                                       │  │
│  │  Responsibilities:                                   │  │
│  │  ✅ Parse HTTP request → extract goal/trace_id      │  │
│  │  ✅ Authenticate X-Token header                      │  │
│  │  ✅ Enforce AGENT_BUDGET_CEILING                     │  │
│  │  ✅ Propagate trace_id to observability             │  │
│  │  ✅ Call orchestration layer (Planner/Coordinator)  │  │
│  │  ✅ Serialize response → JSON/SSE                    │  │
│  │  ❌ NO planning logic                                │  │
│  │  ❌ NO coordination decisions                        │  │
│  │  ❌ NO tool execution                                │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Delegate to orchestration
                         ▼
┌─────────────────────────────────────────────────────────────┐
│               ORCHESTRATION LAYER                           │
│  Role: Planning, coordination, execution                    │
│                                                              │
│  Planner        → Create execution plan                     │
│  Coordinator    → Select workers, dispatch                  │
│  Workers        → Execute tools, manage memory              │
└────────────────────────────────────────────────────────────┘
```

---

## 📋 FastAPI Instances in CUGAR

### 1. Simple Backend (`src/cuga/backend/app.py`)

**Purpose**: Minimal production-ready API for plan/execute operations

```python
from cuga.planner.core import Planner
from cuga.coordinator.core import Coordinator
from cuga.workers.base import Worker

app = FastAPI(title="Cuga Backend")
planner = Planner()
coordinator = Coordinator([Worker("w1"), Worker("w2")])

@app.post("/plan")
async def plan(payload: dict, x_trace_id: str | None = Header(default=None)):
    # 1. Transport: Extract trace_id from header
    propagate_trace(x_trace_id or "api")
    
    # 2. Delegation: Call orchestration layer (Planner)
    steps = await planner.plan(payload.get("goal", ""), 
                               metadata={"trace_id": x_trace_id or "api"})
    
    # 3. Transport: Serialize and return
    return {"steps": [s.tool for s in steps]}

@app.post("/execute")
async def execute(payload: dict, x_trace_id: str | None = Header(default=None)):
    # 1. Transport: Extract and propagate trace_id
    trace = x_trace_id or "api"
    
    # 2. Delegation: Call Planner
    steps = await planner.plan(payload.get("goal", ""), metadata={"trace_id": trace})
    
    # 3. Delegation: Call Coordinator for execution
    async def iterator():
        async for item in coordinator.run(steps, trace_id=trace):
            yield (f"data: {item}\n\n").encode()  # 4. Transport: SSE format
    
    # 5. Transport: Streaming response
    return StreamingResponse(iterator(), media_type="text/event-stream")
```

**Key Points**:
- ✅ FastAPI handles HTTP/SSE transport
- ✅ Delegates planning to `Planner`
- ✅ Delegates coordination to `Coordinator`
- ✅ No planning/coordination logic in FastAPI layer

---

### 2. Full Backend (`src/cuga/backend/server/main.py`)

**Purpose**: Complete web application with LangGraph integration, browser automation, MCP tools

```python
app = FastAPI(lifespan=lifespan)

@app.post("/stream")
async def stream_endpoint(request: StreamRequest):
    # 1. Transport: Parse request, validate
    # 2. Delegation: AgentRunner orchestrates LangGraph execution
    async for event in agent_runner.stream_events(...):
        yield event  # 3. Transport: SSE streaming
    
    # FastAPI does NOT contain orchestration logic
    # AgentRunner/LangGraph handles planning and coordination
```

**Orchestration Components**:
- `AgentRunner` (from `cuga.backend.cuga_graph.utils.controller`)
- `DynamicAgentGraph` (LangGraph-based orchestration)
- `PlanControllerNode`, `BrowserPlannerAgent`, `APIPlannerAgent` (planning)
- FastAPI just exposes `/stream`, `/reset`, `/stop` endpoints

**Key Points**:
- ✅ FastAPI provides HTTP transport for LangGraph
- ✅ AgentRunner orchestrates graph execution
- ✅ Browser/API planners handle domain-specific planning
- ❌ FastAPI does NOT make routing/planning decisions

---

### 3. MCP Registry Server (`src/cuga/backend/tools_env/registry/registry/api_registry_server.py`)

**Purpose**: Tool registry HTTP API for MCP tool invocation

```python
app = FastAPI(lifespan=lifespan)

@app.post("/functions/call")
async def call_mcp_function(request: FunctionCallRequest):
    # 1. Transport: Parse function call request
    # 2. Delegation: ApiRegistry resolves and invokes tool
    result = await registry.call_function(
        app_name=request.app_name,
        function_name=request.function_name,
        arguments=request.args
    )
    # 3. Transport: Return TextContent or JSONResponse
    return result
```

**Key Points**:
- ✅ FastAPI exposes registry over HTTP
- ✅ `ApiRegistry` + `MCPManager` handle tool resolution/invocation
- ✅ No orchestration logic in FastAPI endpoints

---

## 🚫 Anti-Patterns (What FastAPI Should NOT Do)

### ❌ Anti-Pattern 1: Planning Logic in Endpoints

```python
# BAD: Planning logic mixed with transport
@app.post("/plan")
async def plan(payload: dict):
    goal = payload.get("goal")
    
    # ❌ BAD: Tool ranking in endpoint
    tools = registry.list_tools()
    ranked = []
    for tool in tools:
        score = calculate_similarity(goal, tool.description)  # ❌ NO!
        ranked.append((tool, score))
    ranked.sort(key=lambda x: x[1], reverse=True)
    
    return {"steps": [{"tool": t.name} for t, _ in ranked[:3]]}
```

**Why Bad**: Violates separation of concerns. Planning logic belongs in `PlannerAgent`, not transport layer.

**Good Alternative**:
```python
# GOOD: Delegate to Planner
@app.post("/plan")
async def plan(payload: dict):
    steps = await planner.plan(payload.get("goal", ""))  # ✅ Delegation
    return {"steps": [s.tool for s in steps]}
```

---

### ❌ Anti-Pattern 2: Coordination Logic in Endpoints

```python
# BAD: Worker selection in endpoint
@app.post("/execute")
async def execute(payload: dict):
    steps = await planner.plan(payload.get("goal"))
    
    # ❌ BAD: Round-robin worker selection in FastAPI
    worker_idx = 0
    results = []
    for step in steps:
        worker = workers[worker_idx % len(workers)]  # ❌ NO!
        result = await worker.execute(step)
        results.append(result)
        worker_idx += 1
    
    return {"results": results}
```

**Why Bad**: Coordination logic (worker selection, dispatch) belongs in `CoordinatorAgent`.

**Good Alternative**:
```python
# GOOD: Delegate to Coordinator
@app.post("/execute")
async def execute(payload: dict):
    steps = await planner.plan(payload.get("goal"))
    
    # ✅ Coordinator handles worker selection and dispatch
    async def iterator():
        async for item in coordinator.run(steps, trace_id=trace_id):
            yield (f"data: {item}\n\n").encode()
    
    return StreamingResponse(iterator(), media_type="text/event-stream")
```

---

### ❌ Anti-Pattern 3: Tool Execution in Endpoints

```python
# BAD: Direct tool execution in endpoint
@app.post("/execute_tool")
async def execute_tool(payload: dict):
    tool_name = payload.get("tool")
    
    # ❌ BAD: Tool resolution and execution in FastAPI
    tool = registry.get(tool_name)  # ❌ NO!
    result = tool.handler(payload.get("input"), {})  # ❌ NO!
    
    return {"result": result}
```

**Why Bad**: Tool execution belongs in `WorkerAgent` with sandboxing, budget enforcement, and trace propagation.

**Good Alternative**:
```python
# GOOD: Delegate to Worker
@app.post("/execute_tool")
async def execute_tool(payload: dict):
    # ✅ Worker handles tool resolution, sandboxing, execution
    result = await worker.execute(
        [{"tool": payload.get("tool"), "input": payload.get("input")}],
        metadata={"trace_id": trace_id}
    )
    return {"result": result.output}
```

---

## ✅ FastAPI Responsibilities (Canonical)

### 1. HTTP/SSE Transport

**What FastAPI Does**:
- Parse HTTP requests (JSON payloads, headers, query params)
- Extract metadata (trace_id from `X-Trace-Id`, token from `X-Token`)
- Stream responses via SSE (`text/event-stream`)
- Serialize responses to JSON

**Code Pattern**:
```python
@app.post("/endpoint")
async def endpoint(payload: dict, x_trace_id: str | None = Header(default=None)):
    # Extract from HTTP
    goal = payload.get("goal")
    trace_id = x_trace_id or "default"
    
    # Delegate to orchestration
    result = await orchestrator.run(goal, trace_id)
    
    # Serialize to HTTP
    return {"output": result}
```

---

### 2. Authentication & Authorization

**What FastAPI Does**:
- Validate `X-Token` header against `AGENT_TOKEN` environment variable
- Return `401 Unauthorized` if token invalid
- Middleware applies to all endpoints

**Code Pattern**:
```python
@app.middleware("http")
async def budget_guard(request, call_next):
    # Authentication
    expected_token_hash = get_expected_token_hash()
    token = request.headers.get("X-Token")
    token_hash = hashlib.sha256((token or "").encode()).digest()
    if not secrets.compare_digest(token_hash, expected_token_hash):
        raise HTTPException(status_code=401, detail="unauthorized")
    
    # Proceed to endpoint
    response = await call_next(request)
    return response
```

---

### 3. Budget Enforcement (Cross-Cutting Concern)

**What FastAPI Does**:
- Read `AGENT_BUDGET_CEILING` from environment
- Check `X-Budget-Spent` header from client
- Return `429 Too Many Requests` if budget exceeded
- Add `X-Budget-Ceiling` to response headers

**Code Pattern**:
```python
@app.middleware("http")
async def budget_guard(request, call_next):
    # Budget check
    ceiling = int(os.environ.get("AGENT_BUDGET_CEILING", "100"))
    spent = int(request.headers.get("X-Budget-Spent", "0"))
    if spent > ceiling:
        return JSONResponse(status_code=429, content={"detail": "budget exceeded"})
    
    response = await call_next(request)
    response.headers["X-Budget-Ceiling"] = str(ceiling)
    return response
```

**Why in FastAPI**: Budget enforcement is a cross-cutting concern applied uniformly to all endpoints before orchestration begins.

---

### 4. Trace Propagation (Observability Hook)

**What FastAPI Does**:
- Extract `X-Trace-Id` from request headers
- Call `propagate_trace(trace_id)` to set context var
- Pass trace_id to orchestration layer via metadata

**Code Pattern**:
```python
from cuga.observability import propagate_trace

@app.post("/plan")
async def plan(payload: dict, x_trace_id: str | None = Header(default=None)):
    # Propagate trace to context
    trace_id = x_trace_id or "api"
    propagate_trace(trace_id)
    
    # Pass to orchestration
    steps = await planner.plan(goal, metadata={"trace_id": trace_id})
    return {"steps": steps}
```

---

## 🔀 Orchestration Delegation Patterns

### Pattern 1: Synchronous Planning

```python
@app.post("/plan")
async def plan(payload: dict, x_trace_id: str | None = Header(default=None)):
    # 1. Extract (Transport)
    goal = payload.get("goal", "")
    trace_id = x_trace_id or "api"
    propagate_trace(trace_id)
    
    # 2. Delegate (Orchestration)
    steps = await planner.plan(goal, metadata={"trace_id": trace_id})
    
    # 3. Serialize (Transport)
    return {"steps": [s.tool for s in steps]}
```

**Layers**:
- **Transport**: Extract goal, trace_id; serialize steps
- **Orchestration**: `planner.plan()` (tool ranking, memory search)

---

### Pattern 2: Streaming Execution

```python
@app.post("/execute")
async def execute(payload: dict, x_trace_id: str | None = Header(default=None)):
    # 1. Extract (Transport)
    goal = payload.get("goal", "")
    trace_id = x_trace_id or "api"
    
    # 2. Delegate to Planner (Orchestration)
    steps = await planner.plan(goal, metadata={"trace_id": trace_id})
    
    # 3. Delegate to Coordinator (Orchestration)
    async def iterator():
        async for item in coordinator.run(steps, trace_id=trace_id):
            # 4. Format for SSE (Transport)
            yield (f"data: {json.dumps(item)}\n\n").encode()
    
    # 5. Stream (Transport)
    return StreamingResponse(iterator(), media_type="text/event-stream")
```

**Layers**:
- **Transport**: Extract goal, format SSE, return streaming response
- **Orchestration**: `planner.plan()` + `coordinator.run()` (planning + worker dispatch)

---

### Pattern 3: LangGraph Integration

```python
@app.post("/stream")
async def stream_endpoint(request: StreamRequest):
    # 1. Extract (Transport)
    config = create_runnable_config(request.session_id, request.user_id)
    
    # 2. Delegate to AgentRunner (Orchestration)
    agent_runner = AgentRunner(config)
    
    # 3. Stream events (Transport)
    async for event in agent_runner.stream_events(request.goal):
        if event.type == "node":
            yield f"data: {json.dumps(event.data)}\n\n"
    
    return StreamingResponse(iterator(), media_type="text/event-stream")
```

**Layers**:
- **Transport**: Parse request, format SSE stream
- **Orchestration**: `AgentRunner` wraps LangGraph (PlanControllerNode → BrowserPlanner/APIPlanner)

---

## 📊 Comparison: Transport vs Orchestration

| Concern                     | FastAPI (Transport) | Planner/Coordinator (Orchestration) |
|-----------------------------|---------------------|-------------------------------------|
| Parse HTTP requests         | ✅ Yes              | ❌ No                               |
| Extract headers/payload     | ✅ Yes              | ❌ No                               |
| Authenticate X-Token        | ✅ Yes              | ❌ No                               |
| Enforce budget ceiling      | ✅ Yes              | ❌ No                               |
| Propagate trace_id          | ✅ Yes (to context) | ✅ Yes (across agents)              |
| Serialize to JSON/SSE       | ✅ Yes              | ❌ No                               |
| Rank tools by goal          | ❌ No               | ✅ Yes (PlannerAgent)               |
| Select workers              | ❌ No               | ✅ Yes (CoordinatorAgent)           |
| Execute tools               | ❌ No               | ✅ Yes (WorkerAgent)                |
| Search memory               | ❌ No               | ✅ Yes (VectorMemory)               |
| Apply profile isolation     | ❌ No               | ✅ Yes (ToolRegistry sandboxing)    |

---

## 🛡️ Security & Isolation Boundaries

### FastAPI's Role in Security

**Cross-Cutting Security (FastAPI)**:
- ✅ Authentication (X-Token validation)
- ✅ Budget enforcement (AGENT_BUDGET_CEILING)
- ✅ Rate limiting (429 responses)
- ✅ CORS middleware (for web clients)

**Domain Security (Orchestration)**:
- ✅ Profile isolation (VectorMemory, ToolRegistry)
- ✅ Tool allowlisting (only `cuga.modular.tools.*`)
- ✅ Sandbox profiles (py/node slim/full, read-only mounts)
- ✅ Budget tracking (per tool execution)

**Boundary**:
- FastAPI enforces **who can call** (auth) and **how much** (budget ceiling)
- Orchestration enforces **what can run** (tool allowlist) and **where** (sandbox profiles)

---

## 🧪 Testing Implications

### Test FastAPI Layer Separately

```python
# Test transport concerns (FastAPI endpoints)
def test_plan_endpoint_authentication():
    response = client.post("/plan", json={"goal": "test"})
    assert response.status_code == 401  # No token

def test_plan_endpoint_budget_exceeded():
    response = client.post("/plan", 
                           json={"goal": "test"},
                           headers={"X-Token": token, "X-Budget-Spent": "200"})
    assert response.status_code == 429

def test_plan_endpoint_delegates_to_planner():
    with patch("cuga.planner.core.Planner.plan") as mock_plan:
        mock_plan.return_value = [PlanStep(tool="echo", params={})]
        response = client.post("/plan", json={"goal": "test"}, 
                               headers={"X-Token": token})
        assert response.status_code == 200
        mock_plan.assert_called_once()
```

### Test Orchestration Layer Separately

```python
# Test orchestration logic (Planner, Coordinator, Workers)
def test_planner_ranks_tools_by_similarity():
    planner = PlannerAgent(registry, memory, config)
    plan = planner.plan("search flights")
    assert plan.steps[0].tool == "search_flights"  # Highest score

def test_coordinator_round_robin_worker_selection():
    coordinator = CoordinatorAgent(planner, [worker1, worker2], memory)
    result1 = coordinator.dispatch("goal1")
    result2 = coordinator.dispatch("goal2")
    # Verify worker1 then worker2 selected
```

**Key Point**: FastAPI tests focus on **transport concerns** (auth, budget, serialization); orchestration tests focus on **planning/coordination logic** (tool ranking, worker selection).

---

## 📚 Related Documentation

- [System Execution Narrative](../SYSTEM_EXECUTION_NARRATIVE.md) - Complete request → response flow
- [Architecture Overview](../../ARCHITECTURE.md) - High-level system design
- [Orchestrator Contract](../orchestrator/ORCHESTRATOR_CONTRACT.md) - Orchestration lifecycle
- [Deployment Guide](../deployment.md) - FastAPI deployment configuration
- [Environment Modes](../configuration/ENVIRONMENT_MODES.md) - Service mode environment requirements

---

## ✅ Summary: FastAPI's Canonical Role

### FastAPI IS:
- ✅ HTTP/SSE transport layer
- ✅ Authentication and budget enforcement (middleware)
- ✅ Request/response serialization
- ✅ Trace propagation hook (context vars)
- ✅ Thin adapter between HTTP and orchestration

### FastAPI IS NOT:
- ❌ Orchestrator (does not plan or coordinate)
- ❌ Planner (does not rank tools or search memory)
- ❌ Worker (does not execute tools)
- ❌ Registry (does not resolve tools)
- ❌ Memory (does not store/search context)

### Golden Rule:
**If it's not about HTTP transport, auth, or budget enforcement, it doesn't belong in FastAPI.**

All planning, coordination, execution, memory, and tool resolution logic MUST live in dedicated orchestration components (`Planner`, `Coordinator`, `Worker`, `ToolRegistry`, `VectorMemory`).

---

**For questions or architectural clarifications, see [CONTRIBUTING.md](../../CONTRIBUTING.md).**

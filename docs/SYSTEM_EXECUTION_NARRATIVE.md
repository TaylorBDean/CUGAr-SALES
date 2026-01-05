# System Execution Narrative: Request → Response

> **Status**: Canonical  
> **Last Updated**: 2025-12-31  
> **Purpose**: End-to-end execution flow for contributor onboarding and orchestrator understanding

---

## 📋 Overview

This document traces the complete execution flow of the CUGAR agent system from **request entry → routing → agent processing → memory → tool execution → response**. It unifies scattered documentation into a single narrative for contributor onboarding.

### Key Questions Answered

1. **Where do requests enter the system?** (CLI, FastAPI, MCP)
2. **How does routing work?** (RoutingAuthority → OrchestratorProtocol)
3. **What happens during agent execution?** (PlannerAgent → CoordinatorAgent → WorkerAgent)
4. **How is memory used?** (VectorMemory → search → remember)
5. **How do tools execute?** (ToolRegistry → sandboxed execution)
6. **How do responses flow back?** (AgentResult → trace propagation)

---

## 🚀 Entry Points: Three Execution Modes

### 1. CLI Mode (Local Development)

**Entry**: `python -m cuga.modular.cli plan "search for flights"`

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI Entry Point                          │
│              src/cuga/modular/cli.py                        │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ├─ Parse args (goal, backend, profile, trace_id)
                            ├─ Load state from .cuga_modular_state.json
                            ├─ Initialize VectorMemory (profile-scoped)
                            │
                            ▼
                    handle_plan(args)
                            │
                            ├─ Build ToolRegistry (allowlist: cuga.modular.tools.*)
                            ├─ Create PlannerAgent(registry, memory, config)
                            ├─ Create WorkerAgent(registry, memory)
                            ├─ Create CoordinatorAgent(planner, workers, memory)
                            │
                            ▼
                coordinator.dispatch(goal, trace_id)
                            │
                            └─ Persist memory → .cuga_modular_state.json
```

**Key Files**:
- `src/cuga/modular/cli.py` - CLI commands (ingest, query, plan)
- `src/cuga/modular/agents.py` - Agent implementations
- `src/cuga/modular/memory.py` - VectorMemory with local/backend storage
- `src/cuga/modular/config.py` - AgentConfig (from env)

**Environment Requirements** (see `docs/configuration/ENVIRONMENT_MODES.md`):
- **Required**: Model API key (OPENAI_API_KEY or provider-specific)
- **Optional**: CUGA_PROFILE (default: "default"), AGENT_BACKEND (default: "local")

---

### 2. FastAPI Service Mode (Production)

**Entry**: `POST /plan` or `POST /execute` with JSON payload

> **Important**: FastAPI is a **transport layer only**, not an orchestrator. It handles HTTP/SSE transport, authentication, and budget enforcement, then delegates to Planner/Coordinator. See [`docs/architecture/FASTAPI_ROLE.md`](architecture/FASTAPI_ROLE.md) for complete role clarification.

```
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI Entry Point                        │
│               src/cuga/backend/app.py                       │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ├─ Middleware: budget_guard (AGENT_BUDGET_CEILING)
                            ├─ Auth: AGENT_TOKEN validation
                            ├─ Extract trace_id from X-Trace-Id header
                            │
                            ▼
                  POST /plan (payload: {goal})
                            │
                            ├─ propagate_trace(trace_id)
                            ├─ planner.plan(goal, metadata={trace_id})
                            └─ Return: {steps: [tool names]}
                            
                  POST /execute (payload: {goal})
                            │
                            ├─ planner.plan(goal, metadata={trace_id})
                            ├─ coordinator.run(steps, trace_id)
                            └─ StreamingResponse (SSE: "data: {event}\n\n")
```

**Key Files**:
- `src/cuga/backend/app.py` - FastAPI endpoints
- `src/cuga/planner/core.py` - Async planner
- `src/cuga/coordinator/core.py` - Async coordinator
- `src/cuga/workers/base.py` - Worker protocol
- `src/cuga/registry/loader.py` - Registry from YAML

**Environment Requirements** (see `docs/configuration/ENVIRONMENT_MODES.md`):
- **Required**: AGENT_TOKEN, AGENT_BUDGET_CEILING, model API key
- **Recommended**: OTEL_*, LANGFUSE_*, TRACELOOP_* (observability)

---

### 3. MCP Mode (Agent Orchestration)

**Entry**: MCP server receives tool invocation request

```
┌─────────────────────────────────────────────────────────────┐
│                   MCP Entry Point                           │
│     src/cuga/backend/tools_env/registry/                    │
│            api_registry_server.py                           │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ├─ Load MCP_SERVERS_FILE (YAML config)
                            ├─ Initialize MCPManager (FastMCP clients)
                            ├─ Create ApiRegistry (tool router)
                            │
                            ▼
          POST /functions/call
                 {app_name, function_name, args}
                            │
                            ├─ registry.call_function(app_name, function_name, args)
                            ├─ MCPManager resolves transport (SSE/stdio)
                            ├─ Authenticate if secure (auth headers/query params)
                            ├─ FastMCP client.call_tool(tool_name, args)
                            │
                            ▼
          Return: TextContent (result.text or result.structured_content)
```

**Key Files**:
- `src/cuga/backend/tools_env/registry/registry/api_registry_server.py` - FastAPI registry
- `src/cuga/backend/tools_env/registry/mcp_manager/mcp_manager.py` - MCP client manager
- `src/cuga/mcp/lifecycle.py` - LifecycleManager (call/ensure_runner/stop)
- `src/cuga/mcp/adapters/langchain_adapter.py` - LangChain integration

**Environment Requirements** (see `docs/configuration/ENVIRONMENT_MODES.md`):
- **Required**: MCP_SERVERS_FILE, CUGA_PROFILE_SANDBOX, model API key
- **Optional**: Auth tokens per service (in MCP_SERVERS_FILE)

---

## 🎯 Core Execution Flow: From Goal to Result

### Phase 1: Request Entry & Context Creation

```
User Goal: "Find cheap flights from NY to LA"
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  1. Create ExecutionContext (Canonical)                     │
│     docs/orchestrator/EXECUTION_CONTEXT.md                  │
│                                                              │
│  ExecutionContext(                                           │
│    trace_id="trace-abc123",        # Unique trace (required)│
│    request_id="req-456",           # Request tracking       │
│    user_intent="Find flight...",   # Explicit intent        │
│    user_id="user-alice",           # User identification    │
│    memory_scope="user:alice",      # Memory isolation       │
│    conversation_id="conv-101",     # Multi-turn context     │
│    session_id="sess-789",          # Session tracking       │
│    profile="production",           # Config profile         │
│    metadata={"priority": "high"}   # Additional context     │
│  )                                                           │
│                                                              │
│  Properties:                                                 │
│  ✅ Immutable (frozen dataclass)                            │
│  ✅ Trace continuity (trace_id propagates)                  │
│  ✅ Memory isolation (per user/session)                     │
│  ✅ Nested orchestration (with_* methods)                   │
└──────────────────────────────────────────────────────────────┘
```

**Code Path**:
```python
# CLI mode
trace_id = str(uuid.uuid4())
metadata = {"profile": profile, "trace_id": trace_id}

# FastAPI mode
trace_id = x_trace_id or "api"
propagate_trace(trace_id)
metadata = {"trace_id": trace_id}

# MCP mode
# trace_id from ActivityTracker or request headers
```

---

### Phase 2: Routing Decision

```
┌──────────────────────────────────────────────────────────────┐
│  2. RoutingAuthority (Canonical)                            │
│     docs/orchestrator/ROUTING_AUTHORITY.md                  │
│                                                              │
│     ┌────────────────────────────┐                          │
│     │   RoutingAuthority         │ Single Source of Truth   │
│     │  (Pluggable Policies)      │                          │
│     └────────────┬───────────────┘                          │
│                  │                                           │
│     ┌────────────┴───────────────┐                          │
│     │                            │                           │
│     ▼                            ▼                           │
│  Agent Routing              Worker Routing                  │
│  - RoundRobin               - Capability-based              │
│  - Load-balanced            - Profile-aware                 │
│  - Capability-matched       - Availability check            │
│                                                              │
│  Decision: RoutingDecision(                                 │
│    target="worker-1",                                        │
│    reason="round-robin selection",                          │
│    metadata={"worker_idx": 0, "total_workers": 3}           │
│  )                                                           │
└──────────────────────────────────────────────────────────────┘
```

**Code Path**:
```python
# CoordinatorAgent.dispatch()
def _select_worker(self) -> WorkerAgent:
    with self._lock:  # Thread-safe round-robin
        if not self.workers:
            raise ValueError("No workers available")
        worker = self.workers[self._next_worker_idx]
        self._next_worker_idx = (self._next_worker_idx + 1) % len(self.workers)
    return worker
```

**Related**:
- `docs/orchestrator/ORCHESTRATOR_CONTRACT.md` - make_routing_decision() contract
- `src/cuga/modular/agents.py` - CoordinatorAgent._select_worker()

---

### Phase 3: Planning (PlannerAgent)

```
┌──────────────────────────────────────────────────────────────┐
│  3. PlannerAgent.plan(goal, metadata)                       │
│     src/cuga/modular/agents.py                              │
│                                                              │
│  Goal: "Find cheap flights from NY to LA"                   │
│                                                              │
│  Step 1: Memory Search (VectorMemory)                       │
│    ├─ Query: "find cheap flights NY LA"                     │
│    ├─ Normalize: {"find", "cheap", "flights", "ny", "la"}  │
│    ├─ Search: memory.search(query, top_k=3)                 │
│    └─ Hits: [                                               │
│         SearchHit(text="flight booking workflow...",        │
│                   score=0.75),                              │
│         SearchHit(text="price comparison logic...",         │
│                   score=0.60)                               │
│       ]                                                      │
│                                                              │
│  Step 2: Tool Ranking (_rank_tools)                         │
│    ├─ Extract terms: {"find", "cheap", "flights"}          │
│    ├─ Score each tool:                                      │
│    │   ToolSpec(name="search_flights", desc="Search...")    │
│    │     → overlap=3, score=3/3=1.0                         │
│    │   ToolSpec(name="compare_prices", desc="Compare...")   │
│    │     → overlap=2, score=2/3=0.67                        │
│    │   ToolSpec(name="echo", desc="Echo text")              │
│    │     → overlap=0, score=0                               │
│    └─ Ranked: [(search_flights, 1.0), (compare_prices, 0.67)]│
│                                                              │
│  Step 3: Select Top K Steps (config.max_steps)              │
│    ├─ Clamp: max(1, min(config.max_steps, len(scored)))    │
│    ├─ Create steps:                                         │
│    └─ [                                                      │
│         {"tool": "search_flights", "input": {goal},         │
│          "reason": "matched with score 1.00",               │
│          "trace_id": trace_id, "index": 0},                 │
│         {"tool": "compare_prices", "input": {goal},         │
│          "reason": "matched with score 0.67",               │
│          "trace_id": trace_id, "index": 1}                  │
│       ]                                                      │
│                                                              │
│  Step 4: Remember Goal (memory persistence)                 │
│    └─ memory.remember(goal, metadata={profile, trace_id})   │
│                                                              │
│  Return: AgentPlan(                                          │
│    steps=[...],                                             │
│    trace=[                                                   │
│      {"event": "plan:start", "goal": goal, "trace_id": ...},│
│      {"event": "plan:steps", "count": 2, "trace_id": ...},  │
│      {"event": "plan:complete", "trace_id": ...}            │
│    ]                                                         │
│  )                                                           │
└──────────────────────────────────────────────────────────────┘
```

**Key Features**:
- ✅ **Vector-based tool ranking** (not LLM-based by default)
- ✅ **Memory-augmented**: Past executions influence tool selection
- ✅ **Deterministic**: Same goal + same memory → same plan
- ✅ **Trace propagation**: All events include trace_id

**Related**:
- `docs/agents/AGENT_IO_CONTRACT.md` - AgentRequest/AgentResponse contracts
- `src/cuga/modular/memory.py` - VectorMemory.search() and .remember()

---

### Phase 4: Coordination (CoordinatorAgent)

```
┌──────────────────────────────────────────────────────────────┐
│  4. CoordinatorAgent.dispatch(goal, trace_id)               │
│     src/cuga/modular/agents.py                              │
│                                                              │
│  Input: goal, trace_id                                       │
│                                                              │
│  Step 1: Planning                                            │
│    plan = planner.plan(goal, metadata={profile, trace_id})  │
│    traces = list(plan.trace)  # Collect planning traces     │
│                                                              │
│  Step 2: Worker Selection (Thread-Safe Round-Robin)         │
│    worker = self._select_worker()                           │
│      ├─ Lock acquisition (threading.Lock)                   │
│      ├─ Select: workers[_next_worker_idx]                   │
│      ├─ Increment: _next_worker_idx = (idx + 1) % len(workers)│
│      └─ Release lock                                         │
│                                                              │
│  Step 3: Execution Delegation                                │
│    result = worker.execute(plan.steps, metadata={...})      │
│    traces.extend(result.trace)  # Merge execution traces    │
│                                                              │
│  Return: AgentResult(                                        │
│    output=result.output,                                     │
│    trace=traces  # Complete trace: plan + execution         │
│  )                                                           │
└──────────────────────────────────────────────────────────────┘
```

**Concurrency Safety**:
```python
# Thread-safe worker selection
_lock: threading.Lock = field(default_factory=threading.Lock)

def _select_worker(self):
    with self._lock:
        # Atomic read-modify-write
        worker = self.workers[self._next_worker_idx]
        self._next_worker_idx = (self._next_worker_idx + 1) % len(self.workers)
    return worker
```

**Related**:
- `docs/orchestrator/ORCHESTRATOR_CONTRACT.md` - Orchestration lifecycle
- `tests/scenario/test_agent_composition.py` - Multi-worker coordination tests

---

### Phase 5: Execution (WorkerAgent)

```
┌──────────────────────────────────────────────────────────────┐
│  5. WorkerAgent.execute(steps, metadata)                    │
│     src/cuga/modular/agents.py                              │
│                                                              │
│  Input: steps = [                                            │
│    {"tool": "search_flights", "input": {...}, "trace_id": ...},│
│    {"tool": "compare_prices", "input": {...}, "trace_id": ...} │
│  ]                                                           │
│                                                              │
│  For each step:                                              │
│    Step 1: Tool Resolution                                   │
│      tool = registry.get(step["tool"])                      │
│        ├─ Validate: tool in allowlist (cuga.modular.tools.*) │
│        ├─ Profile filter: tool.profile matches context      │
│        └─ Return: ToolSpec(name, description, handler)      │
│                                                              │
│    Step 2: Context Assembly                                  │
│      context = {                                             │
│        "profile": profile,  # From metadata or memory        │
│        "trace_id": trace_id # Propagate trace                │
│      }                                                       │
│                                                              │
│    Step 3: Tool Execution (Sandboxed)                        │
│      result = tool.handler(step["input"], context)          │
│        ├─ Security: No eval/exec, restricted imports        │
│        ├─ Isolation: Read-only mounts by default            │
│        ├─ Budget: Respects AGENT_BUDGET_CEILING             │
│        └─ Timeout: Configurable per tool                    │
│                                                              │
│    Step 4: Observability Emission (Optional)                 │
│      if self.observability:                                  │
│        emitter.emit({                                        │
│          "event": "tool",                                    │
│          "name": tool.name,                                  │
│          "profile": profile,                                 │
│          "trace_id": trace_id                                │
│        })                                                    │
│                                                              │
│    Step 5: Trace Collection                                  │
│      trace.append({                                          │
│        "event": "execute:step",                             │
│        "tool": tool.name,                                    │
│        "index": idx,                                         │
│        "trace_id": trace_id                                  │
│      })                                                      │
│                                                              │
│    Step 6: Memory Update                                     │
│      memory.remember(str(result), metadata={profile, trace_id})│
│                                                              │
│  Return: AgentResult(                                        │
│    output=result,  # Last tool's output                      │
│    trace=trace     # All execution events                    │
│  )                                                           │
└──────────────────────────────────────────────────────────────┘
```

**Security Guardrails** (see `AGENTS.md`):
- ✅ **Import allowlist**: Only `cuga.modular.tools.*` allowed
- ✅ **No eval/exec**: Dynamic code execution forbidden
- ✅ **Budget enforcement**: AGENT_BUDGET_CEILING blocks overruns
- ✅ **Profile isolation**: No cross-profile memory leakage
- ✅ **Read-only mounts**: Sandbox prevents writes outside /workdir

**Related**:
- `docs/sandboxing.md` - Sandbox profiles (py/node slim/full, orchestrator)
- `AGENTS.md` - Tool contract, sandbox expectations, budget policies

---

### Phase 6: Tool Execution (Deep Dive)

```
┌──────────────────────────────────────────────────────────────┐
│  6. Tool Handler Execution                                   │
│     src/cuga/modular/tools/*.py                             │
│                                                              │
│  Tool Signature (Canonical):                                 │
│    def handler(inputs: Dict[str, Any],                      │
│                context: Dict[str, Any]) -> Any:             │
│                                                              │
│  Example: Echo Tool                                          │
│    def echo_handler(inputs, context):                       │
│      trace_id = context.get("trace_id")                     │
│      profile = context.get("profile")                       │
│      text = inputs.get("text", "")                          │
│      return text  # Simple pass-through                     │
│                                                              │
│  Example: File Reader Tool                                   │
│    def read_file_handler(inputs, context):                  │
│      path = inputs.get("path")                              │
│      profile = context.get("profile")                       │
│      sandbox = get_sandbox_for_profile(profile)             │
│      # Validate path within sandbox                         │
│      if not is_safe_path(path, sandbox):                    │
│        raise ValueError("Path outside sandbox")             │
│      return Path(path).read_text()                          │
│                                                              │
│  Registry Loading (ToolRegistry):                            │
│    registry = ToolRegistry([                                 │
│      ToolSpec(name="echo",                                  │
│               description="Echo text",                      │
│               handler=echo_handler),                        │
│      ToolSpec(name="read_file",                             │
│               description="Read file content",              │
│               handler=read_file_handler,                    │
│               sandbox_profile="py-slim")                    │
│    ])                                                        │
│                                                              │
│  Dynamic Import Restriction:                                 │
│    ✅ Allowed: from cuga.modular.tools import my_tool       │
│    ❌ Denied:  from external_lib import dangerous_tool      │
│    ❌ Denied:  __import__("os").system("rm -rf /")          │
└──────────────────────────────────────────────────────────────┘
```

**MCP Tool Execution** (for external services):
```
Tool Call: mcp_tool("weather_api_get_forecast", {"city": "NYC"})
                            │
                            ▼
┌──────────────────────────────────────────────────────────────┐
│  MCP Lifecycle (src/cuga/mcp/lifecycle.py)                  │
│                                                              │
│  1. Circuit Breaker Check                                    │
│     if not circuit.allow():                                  │
│       return ToolResponse(ok=False, error="circuit open")    │
│                                                              │
│  2. Ensure Runner (Pooled/Reused)                            │
│     runner = await lifecycle.ensure_runner(spec)            │
│       ├─ Check existing pool                                │
│       ├─ Spawn if needed (stdio/sse transport)              │
│       └─ Health check (optional)                            │
│                                                              │
│  3. Call with Resilience                                     │
│     - Timeout: 30s default (configurable)                   │
│     - Retry: Exponential backoff (3 attempts)               │
│     - Circuit breaker: Half-open after failures             │
│                                                              │
│  4. Response Handling                                        │
│     result = await runner.call_tool(tool_name, args)        │
│     return ToolResponse(ok=True, result=result.text)        │
│                                                              │
│  5. Observability                                            │
│     metrics.counter("mcp.calls").inc()                      │
│     metrics.histogram("mcp.latency_ms").observe(duration)   │
└──────────────────────────────────────────────────────────────┘
```

**Related**:
- `docs/MCP_INTEGRATION.md` - MCP tool lifecycle
- `docs/mcp/registry.yaml` - Tool registry with sandbox profiles
- `src/cuga/mcp/lifecycle.py` - LifecycleManager (call/retry/circuit)

---

### Phase 7: Memory Operations

```
┌──────────────────────────────────────────────────────────────┐
│  7. VectorMemory (src/cuga/modular/memory.py)               │
│                                                              │
│  Architecture:                                               │
│    VectorMemory                                              │
│      ├─ Embedder (HashingEmbedder or model-based)          │
│      ├─ Backend (local/faiss/chroma/qdrant)                 │
│      └─ Store (List[MemoryRecord])                          │
│                                                              │
│  Operation 1: Remember                                       │
│    memory.remember(text, metadata={profile, trace_id})      │
│      ├─ Create: MemoryRecord(text, metadata)                │
│      ├─ Store locally: self.store.append(record)            │
│      └─ If backend != "local":                              │
│          ├─ Embed: embedding = embedder.embed(text)         │
│          └─ Upsert: backend.upsert([EmbeddedRecord(...)])   │
│                                                              │
│  Operation 2: Search                                         │
│    hits = memory.search(query, top_k=3)                     │
│      ├─ If backend:                                          │
│      │   ├─ Embed query: query_vec = embedder.embed(query)  │
│      │   └─ Vector search: backend.search(query_vec, top_k) │
│      └─ If local:                                            │
│          ├─ Normalize: query_terms = _normalize_words(query)│
│          ├─ Score: overlap / max(len(query_terms), 1)       │
│          └─ Rank: sorted by score, return top_k             │
│                                                              │
│  Profile Isolation:                                          │
│    memory = VectorMemory(profile="user:alice")              │
│    memory.remember("secret", metadata={                     │
│      "profile": "user:alice",  # Stored with profile tag    │
│      "trace_id": trace_id                                    │
│    })                                                        │
│    # Only queries with profile="user:alice" can access      │
│                                                              │
│  Persistence (CLI mode):                                     │
│    _persist_memory(memory, Path(".cuga_modular_state.json"))│
│      ├─ Serialize: {                                         │
│      │     "records": [record.__dict__ for record in store] │
│      │   }                                                   │
│      └─ Write: state_path.write_text(json.dumps(state))     │
└──────────────────────────────────────────────────────────────┘
```

**Backend Options**:
- **local**: In-memory keyword matching (offline-first)
- **faiss**: CPU/GPU vector similarity search
- **chroma**: Persistent embeddings with metadata filtering
- **qdrant**: Cloud/local vector DB with full-text + vector hybrid

**Related**:
- `src/cuga/modular/memory.py` - VectorMemory implementation
- `src/cuga/modular/embeddings/` - Embedder implementations
- `src/cuga/modular/vector_backends/` - Backend protocols

---

### Phase 8: Response Assembly

```
┌──────────────────────────────────────────────────────────────┐
│  8. Response Flow                                            │
│                                                              │
│  CLI Mode:                                                   │
│    result = coordinator.dispatch(goal, trace_id)            │
│    output = {                                                │
│      "event": "plan",                                        │
│      "output": result.output,  # Last tool's result          │
│      "trace": result.trace,    # Complete trace chain        │
│      "trace_id": trace_id                                    │
│    }                                                         │
│    LOGGER.info(json.dumps(output))  # JSON log to stdout    │
│    _persist_memory(memory, state_path)                       │
│                                                              │
│  FastAPI Mode (Streaming):                                   │
│    async def iterator():                                     │
│      async for item in coordinator.run(steps, trace_id):    │
│        # item = {"event": "tool:start", "tool": "...", ...} │
│        yield (f"data: {json.dumps(item)}\n\n").encode()     │
│    return StreamingResponse(iterator(),                      │
│                             media_type="text/event-stream")  │
│                                                              │
│  FastAPI Mode (Plan Only):                                   │
│    steps = await planner.plan(goal, metadata={trace_id})    │
│    return {"steps": [s.tool for s in steps]}                │
│                                                              │
│  MCP Mode:                                                   │
│    result = await mcp_manager.call_tool(tool_name, args)    │
│    if isinstance(result, dict):                             │
│      return JSONResponse(status_code=result.get("status_code", 500),│
│                          content=result)                     │
│    return [TextContent(text=result[0].text, type='text')]   │
│                                                              │
│  Trace Structure (Canonical):                                │
│    [                                                         │
│      {"event": "plan:start", "goal": "...", "trace_id": "..."},│
│      {"event": "plan:steps", "count": 2, "trace_id": "..."},│
│      {"event": "plan:complete", "trace_id": "..."},         │
│      {"event": "execute:step", "tool": "search_flights",    │
│       "index": 0, "trace_id": "..."},                        │
│      {"event": "execute:step", "tool": "compare_prices",    │
│       "index": 1, "trace_id": "..."}                         │
│    ]                                                         │
└──────────────────────────────────────────────────────────────┘
```

**Observability Integration** (see `docs/observability.md`):
```python
# OTEL tracing
from cuga.observability import propagate_trace, Span, InMemoryTracer

propagate_trace(trace_id)  # Sets context var
span = Span(name="plan", trace_id=trace_id, start=time.time())
# ... execution ...
span.end = time.time()
tracer.spans.append(span)

# LangFuse/LangSmith hooks (env-driven)
if os.getenv("LANGFUSE_PUBLIC_KEY"):
    langfuse.trace(name="plan", id=trace_id, metadata={...})
```

**Related**:
- `src/cuga/observability.py` - Trace propagation, span tracking
- `docs/observability.md` - OTEL/LangFuse/LangSmith integration

---

## 🔄 Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Request Entry                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐                      │
│  │   CLI    │    │  FastAPI │    │   MCP    │                      │
│  │  plan    │    │  /execute│    │ /call_fn │                      │
│  └────┬─────┘    └────┬─────┘    └────┬─────┘                      │
│       │               │               │                              │
│       └───────────────┴───────────────┘                              │
│                       │                                              │
│                       ▼                                              │
│       ┌──────────────────────────────────────┐                      │
│       │   ExecutionContext Creation          │                      │
│       │   (trace_id, profile, metadata)      │                      │
│       └────────────────┬─────────────────────┘                      │
│                        │                                             │
│                        ▼                                             │
│       ┌──────────────────────────────────────┐                      │
│       │   RoutingAuthority                   │                      │
│       │   (Select orchestrator/worker)       │                      │
│       └────────────────┬─────────────────────┘                      │
│                        │                                             │
│                        ▼                                             │
│       ┌──────────────────────────────────────┐                      │
│       │  CoordinatorAgent.dispatch()         │                      │
│       │  ┌────────────────────────────────┐  │                      │
│       │  │  PlannerAgent.plan(goal)       │  │                      │
│       │  │  ┌──────────────────────────┐  │  │                      │
│       │  │  │ VectorMemory.search()    │  │  │                      │
│       │  │  │ (retrieve past context)  │  │  │                      │
│       │  │  └────────┬─────────────────┘  │  │                      │
│       │  │           │                     │  │                      │
│       │  │  ┌────────▼─────────────────┐  │  │                      │
│       │  │  │ _rank_tools()            │  │  │                      │
│       │  │  │ (score by overlap)       │  │  │                      │
│       │  │  └────────┬─────────────────┘  │  │                      │
│       │  │           │                     │  │                      │
│       │  │  ┌────────▼─────────────────┐  │  │                      │
│       │  │  │ Select top K steps       │  │  │                      │
│       │  │  └────────┬─────────────────┘  │  │                      │
│       │  │           │                     │  │                      │
│       │  │  ┌────────▼─────────────────┐  │  │                      │
│       │  │  │ memory.remember(goal)    │  │  │                      │
│       │  │  └──────────────────────────┘  │  │                      │
│       │  │                                 │  │                      │
│       │  │  Return: AgentPlan(steps, trace)│  │                      │
│       │  └─────────────┬───────────────────┘  │                      │
│       │                │                       │                      │
│       │  ┌─────────────▼─────────────────┐    │                      │
│       │  │ _select_worker()              │    │                      │
│       │  │ (thread-safe round-robin)     │    │                      │
│       │  └─────────────┬─────────────────┘    │                      │
│       │                │                       │                      │
│       │  ┌─────────────▼─────────────────┐    │                      │
│       │  │  WorkerAgent.execute(steps)   │    │                      │
│       │  │  For each step:               │    │                      │
│       │  │  ┌──────────────────────────┐ │    │                      │
│       │  │  │ registry.get(tool_name)  │ │    │                      │
│       │  │  │ (validate allowlist)     │ │    │                      │
│       │  │  └────────┬─────────────────┘ │    │                      │
│       │  │           │                    │    │                      │
│       │  │  ┌────────▼─────────────────┐ │    │                      │
│       │  │  │ tool.handler(input, ctx) │ │    │                      │
│       │  │  │ (sandboxed execution)    │ │    │                      │
│       │  │  └────────┬─────────────────┘ │    │                      │
│       │  │           │                    │    │                      │
│       │  │  ┌────────▼─────────────────┐ │    │                      │
│       │  │  │ observability.emit()     │ │    │                      │
│       │  │  │ (optional trace)         │ │    │                      │
│       │  │  └────────┬─────────────────┘ │    │                      │
│       │  │           │                    │    │                      │
│       │  │  ┌────────▼─────────────────┐ │    │                      │
│       │  │  │ memory.remember(result)  │ │    │                      │
│       │  │  └──────────────────────────┘ │    │                      │
│       │  │                                │    │                      │
│       │  │  Return: AgentResult(output, trace)│                      │
│       │  └────────────────────────────────┘    │                      │
│       │                                         │                      │
│       │  Return: AgentResult(output, merged_trace)                   │
│       └────────────────┬────────────────────────┘                     │
│                        │                                              │
│                        ▼                                              │
│       ┌──────────────────────────────────────┐                       │
│       │   Response Assembly                  │                       │
│       │   - CLI: JSON log + persist state    │                       │
│       │   - FastAPI: SSE stream or JSON      │                       │
│       │   - MCP: TextContent or JSONResponse │                       │
│       └──────────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🛡️ Security & Isolation

### Profile-Based Isolation

```
┌──────────────────────────────────────────────────────────────┐
│  Profile Isolation (Canonical)                              │
│                                                              │
│  profile="user:alice"                                        │
│    ├─ Memory: Only access records with profile="user:alice" │
│    ├─ Tools: Filter registry by profile allowlist           │
│    ├─ Sandbox: Mount user-specific /workdir                 │
│    └─ Budget: Independent ceiling per profile               │
│                                                              │
│  profile="production"                                        │
│    ├─ Memory: Shared knowledge base (optional)              │
│    ├─ Tools: Full registry access                           │
│    ├─ Sandbox: Read-only mounts by default                  │
│    └─ Budget: Strict ceiling (AGENT_BUDGET_CEILING)         │
│                                                              │
│  No Cross-Profile Leakage:                                   │
│    ✅ memory.search(query) filters by profile automatically  │
│    ✅ registry.get(tool) checks profile match                │
│    ✅ sandbox enforces per-profile mount isolation           │
└──────────────────────────────────────────────────────────────┘
```

### Sandbox Profiles

From `docs/mcp/registry.yaml` and `docs/sandboxing.md`:

| Profile        | Use Case              | Mounts                          | Network |
|----------------|-----------------------|---------------------------------|---------|
| `py-slim`      | Python tools (safe)   | `/workdir` RW, rest read-only   | ❌      |
| `py-full`      | Python tools (rich)   | `/workdir` RW, `/tmp` RW        | ✅ (opt)|
| `node-slim`    | Node.js tools (safe)  | `/workdir` RW, rest read-only   | ❌      |
| `node-full`    | Node.js tools (rich)  | `/workdir` RW, `/tmp` RW        | ✅ (opt)|
| `orchestrator` | Coordinator processes | Full filesystem (trusted)       | ✅      |

**Related**:
- `AGENTS.md` - Sandbox expectations, registry hygiene
- `docs/sandboxing.md` - Sandbox profile specifications
- `docs/security/SECURITY_CONTROLS.md` - Security boundaries

---

## 📊 Observability & Tracing

### Trace Propagation

```
Request Entry (trace_id="trace-abc123")
      │
      ├─ CLI: --trace-id flag or auto-generated UUID
      ├─ FastAPI: X-Trace-Id header or "api" default
      └─ MCP: Request headers or ActivityTracker
      │
      ▼
ExecutionContext(trace_id="trace-abc123")
      │
      ├─ PlannerAgent.plan(metadata={"trace_id": ...})
      │   └─ trace = [{"event": "plan:start", "trace_id": ...}, ...]
      │
      ├─ WorkerAgent.execute(metadata={"trace_id": ...})
      │   └─ trace = [{"event": "execute:step", "trace_id": ...}, ...]
      │
      ├─ tool.handler(context={"trace_id": ...})
      │   └─ Logs include trace_id for correlation
      │
      └─ observability.emit({"trace_id": ...})
          └─ OTEL span, LangFuse trace, LangSmith run
```

### Observability Backends (Env-Driven)

```python
# OTEL (OpenTelemetry)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
OTEL_SERVICE_NAME=cuga-agent
→ Automatic span export to Jaeger/Zipkin/Datadog

# LangFuse
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...
LANGFUSE_HOST=https://cloud.langfuse.com
→ Trace LLM calls, tool executions, costs

# LangSmith
LANGSMITH_API_KEY=ls-...
LANGSMITH_PROJECT=cuga-prod
→ Trace LangChain/LangGraph runs

# Traceloop (OpenLLMetry)
TRACELOOP_API_KEY=tl-...
→ Unified observability for LLM apps
```

**Related**:
- `src/cuga/observability.py` - Trace context vars, span tracking
- `docs/observability.md` - Backend integrations
- `docs/observability/` - Advanced patterns

---

## 🧪 Testing the Flow

### Unit Tests (Components)

```bash
# Test planner ranking
pytest tests/test_planner.py::test_planner_ranks_tools_by_goal -v

# Test worker execution
pytest tests/test_worker.py::test_worker_executes_steps -v

# Test coordinator dispatch
pytest tests/test_coordinator.py::test_coordinator_dispatch -v

# Test memory search
pytest tests/test_memory.py::test_vector_memory_search -v
```

### Scenario Tests (End-to-End)

```bash
# Multi-agent dispatch (round-robin coordination)
pytest tests/scenario/test_agent_composition.py::TestMultiAgentDispatch -v

# Memory-augmented planning (learning from past)
pytest tests/scenario/test_agent_composition.py::TestMemoryAugmentedPlanning -v

# Profile isolation (security boundaries)
pytest tests/scenario/test_agent_composition.py::TestProfileBasedIsolation -v

# Error recovery (partial results)
pytest tests/scenario/test_agent_composition.py::TestErrorRecoveryScenarios -v
```

**Related**:
- `docs/testing/SCENARIO_TESTING.md` - Scenario test guide
- `docs/testing/COVERAGE_MATRIX.md` - Test coverage by layer

---

## 📚 Related Documentation

### Architecture & Contracts
- [`ARCHITECTURE.md`](../ARCHITECTURE.md) - High-level system design
- [`docs/orchestrator/ORCHESTRATOR_CONTRACT.md`](orchestrator/ORCHESTRATOR_CONTRACT.md) - Orchestration lifecycle
- [`docs/orchestrator/ROUTING_AUTHORITY.md`](orchestrator/ROUTING_AUTHORITY.md) - Routing decisions
- [`docs/orchestrator/EXECUTION_CONTEXT.md`](orchestrator/EXECUTION_CONTEXT.md) - Context propagation
- [`docs/agents/AGENT_IO_CONTRACT.md`](agents/AGENT_IO_CONTRACT.md) - AgentRequest/AgentResponse
- [`docs/agents/AGENT_LIFECYCLE.md`](agents/AGENT_LIFECYCLE.md) - Startup/shutdown contracts

### Configuration & Environment
- [`docs/configuration/ENVIRONMENT_MODES.md`](configuration/ENVIRONMENT_MODES.md) - Env vars per mode
- [`AGENTS.md`](../AGENTS.md) - Guardrails, policies, registry hygiene
- [`docs/configuration/CONFIG_RESOLUTION.md`](configuration/CONFIG_RESOLUTION.md) - Config precedence

### Tools & Security
- [`docs/TOOLS.md`](TOOLS.md) - Tool development guide
- [`docs/sandboxing.md`](sandboxing.md) - Sandbox profiles
- [`docs/security/SECURITY_CONTROLS.md`](security/SECURITY_CONTROLS.md) - Security boundaries
- [`docs/mcp/registry.yaml`](mcp/registry.yaml) - Tool registry

### Memory & RAG
- [`docs/memory/`](memory/) - Memory backends, embeddings
- [`configs/rag.yaml`](../configs/rag.yaml) - RAG configuration
- [`src/cuga/modular/memory.py`](../src/cuga/modular/memory.py) - VectorMemory implementation

### MCP Integration
- [`docs/MCP_INTEGRATION.md`](MCP_INTEGRATION.md) - MCP tool lifecycle
- [`docs/mcp/`](mcp/) - MCP server specs, adapters
- [`src/cuga/mcp/lifecycle.py`](../src/cuga/mcp/lifecycle.py) - LifecycleManager

### Observability
- [`docs/observability.md`](observability.md) - Tracing setup
- [`docs/observability/`](observability/) - OTEL/LangFuse patterns
- [`src/cuga/observability.py`](../src/cuga/observability.py) - Trace propagation

### Testing
- [`docs/testing/SCENARIO_TESTING.md`](testing/SCENARIO_TESTING.md) - E2E test guide
- [`docs/testing/COVERAGE_MATRIX.md`](testing/COVERAGE_MATRIX.md) - Coverage analysis
- [`tests/scenario/test_agent_composition.py`](../tests/scenario/test_agent_composition.py) - Scenario tests

---

## 🎓 Contributor Quick Start

### For New Contributors

1. **Read this document first** to understand the complete flow
2. **Pick an entry point** (CLI, FastAPI, or MCP) for your use case
3. **Review guardrails** in [`AGENTS.md`](../AGENTS.md) before making changes
4. **Check test coverage** in [`docs/testing/COVERAGE_MATRIX.md`](testing/COVERAGE_MATRIX.md)
5. **Run scenario tests** to validate your changes don't break orchestration

### For Orchestrator Work

1. **Understand ExecutionContext** ([`docs/orchestrator/EXECUTION_CONTEXT.md`](orchestrator/EXECUTION_CONTEXT.md))
2. **Review OrchestratorProtocol** ([`docs/orchestrator/ORCHESTRATOR_CONTRACT.md`](orchestrator/ORCHESTRATOR_CONTRACT.md))
3. **Check RoutingAuthority** ([`docs/orchestrator/ROUTING_AUTHORITY.md`](orchestrator/ROUTING_AUTHORITY.md))
4. **Validate with scenario tests** ([`tests/scenario/test_agent_composition.py`](../tests/scenario/test_agent_composition.py))

### For Tool Development

1. **Review tool contract** in [`AGENTS.md`](../AGENTS.md) (signature, allowlist, sandbox)
2. **Check sandbox profiles** in [`docs/sandboxing.md`](sandboxing.md)
3. **Implement handler** following `def handler(inputs, context) -> Any` pattern
4. **Register in ToolRegistry** with sandbox profile and profile filter
5. **Add tests** for tool execution and error handling

---

## 🔍 Debugging Tips

### Trace a Request End-to-End

```bash
# 1. CLI mode with trace_id
python -m cuga.modular.cli plan "find flights" --trace-id "debug-123" 2>&1 | jq '.trace_id'

# 2. FastAPI mode with header
curl -X POST http://localhost:8000/execute \
  -H "X-Trace-Id: debug-456" \
  -H "Content-Type: application/json" \
  -d '{"goal": "find flights"}'

# 3. Check logs for trace_id correlation
grep "debug-456" logs/cuga.log | jq -s '.'
```

### Inspect Memory State

```bash
# CLI mode persists to .cuga_modular_state.json
cat .cuga_modular_state.json | jq '.records[] | {text, metadata}'

# Check profile isolation
cat .cuga_modular_state.json | jq '.records[] | select(.metadata.profile == "user:alice")'
```

### Verify Tool Execution

```bash
# List registered tools
python -c "from cuga.modular.tools import ToolRegistry; print(ToolRegistry().tools)"

# Test tool handler directly
python -c "
from cuga.modular.tools import ToolSpec
tool = ToolSpec(name='echo', description='Echo', handler=lambda i, c: i.get('text'))
print(tool.handler({'text': 'hello'}, {}))
"
```

### Check Routing Decisions

```python
# In orchestrator code, log routing decisions
from cuga.orchestrator import RoutingDecision

decision = RoutingDecision(
    target="worker-1",
    reason="round-robin selection",
    metadata={"worker_idx": 0, "total_workers": 3}
)
LOGGER.info(f"Routing decision: {decision}")
```

---

## 📈 Performance Considerations

### Concurrency

- **Thread-safe coordinator**: `threading.Lock` for round-robin selection
- **Async workers**: Use `async def execute()` for I/O-bound tools
- **Connection pooling**: MCP runners reused across calls

### Memory Management

- **Local mode**: In-memory store, no persistence overhead
- **Backend mode**: Lazy connection (`connect_backend()` on first use)
- **Embeddings**: Deterministic hashing embedder by default (no model calls)

### Observability Overhead

- **Conditional emission**: Only emit if `observability` is configured
- **Batch spans**: Collect locally, flush periodically to OTEL
- **Sampling**: Use trace sampling for high-throughput scenarios

---

## ✅ Summary Checklist

### Request Entry
- [ ] ExecutionContext created with trace_id, profile, metadata
- [ ] Environment validated per mode (local/service/MCP)
- [ ] Auth token verified (service/MCP modes)

### Routing
- [ ] RoutingAuthority consulted for orchestrator/worker selection
- [ ] Routing decision logged with reason and metadata

### Planning
- [ ] Memory searched for context (top_k hits)
- [ ] Tools ranked by goal similarity (not blindly all tools)
- [ ] Steps created with trace_id propagation
- [ ] Goal remembered in memory (metadata: profile, trace_id)

### Execution
- [ ] Worker selected (round-robin, thread-safe)
- [ ] Tools resolved from registry (allowlist validated)
- [ ] Tool handlers executed (sandboxed, budget-enforced)
- [ ] Results remembered in memory (metadata: profile, trace_id)
- [ ] Observability events emitted (optional)

### Response
- [ ] AgentResult assembled (output + merged traces)
- [ ] Response formatted per mode (JSON log / SSE stream / TextContent)
- [ ] Memory persisted (CLI mode only)
- [ ] Trace correlation verified (all events have same trace_id)

---

## 📚 Related Documentation

### Architecture
- **[Orchestrator Interface and Semantics](orchestrator/README.md)** - Formal specification for orchestrator API with lifecycle callbacks, failure modes, retry semantics, execution context, routing authority, and implementation patterns
- **[FastAPI Role Clarification](architecture/FASTAPI_ROLE.md)** - Defines FastAPI as transport layer only (vs orchestration) to prevent mixing concerns
- **[Architecture Overview](../ARCHITECTURE.md)** - High-level system design with modular stack, scheduling, and tooling

### Agent Contracts
- **[Agent I/O Contract](agents/AGENT_IO_CONTRACT.md)** - AgentRequest/AgentResponse standardization
- **[Agent Lifecycle](agents/AGENT_LIFECYCLE.md)** - Agent startup/shutdown/health contracts
- **[State Ownership](agents/STATE_OWNERSHIP.md)** - AGENT vs MEMORY vs ORCHESTRATOR state boundaries

### Configuration
- **[Environment Modes](configuration/ENVIRONMENT_MODES.md)** - Environment requirements per execution mode (local/service/MCP/test)
- **[Config Resolution](configuration/CONFIG_RESOLUTION.md)** - Configuration precedence layers (CLI → env → .env → YAML → TOML → defaults)

### Testing
- **[Scenario Testing](testing/SCENARIO_TESTING.md)** - End-to-end orchestration scenario tests
- **[Coverage Matrix](testing/COVERAGE_MATRIX.md)** - Test coverage by architectural layer

---

**For questions or improvements to this narrative, see [`CONTRIBUTING.md`](../CONTRIBUTING.md).**


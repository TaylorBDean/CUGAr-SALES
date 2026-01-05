<div align="center">
  <img src="docs/image/CUGAr.png" alt="CUGAr Logo" width="400"/>
</div>

# Architecture Overview

> **For a narrative walkthrough of the complete execution flow**, see [`docs/SYSTEM_EXECUTION_NARRATIVE.md`](docs/SYSTEM_EXECUTION_NARRATIVE.md) - traces request → response with CLI/FastAPI/MCP examples, routing decisions, agent lifecycle, memory operations, and tool execution.
>
> **For FastAPI's specific role**, see [`docs/architecture/FASTAPI_ROLE.md`](docs/architecture/FASTAPI_ROLE.md) - clarifies FastAPI as transport layer only (not orchestrator) to prevent mixing transport and orchestration concerns.
>
> **For the orchestrator interface and semantics**, see [`docs/orchestrator/README.md`](docs/orchestrator/README.md) - formal specification for orchestrator API, lifecycle callbacks, failure modes, retry semantics, and implementation patterns.

## Modular Stack
- Planner → Coordinator → Workers with profile-scoped VectorMemory.
- Embeddings: deterministic hashing embedder; vector backends (FAISS/Chroma/Qdrant) behind `VectorBackend` protocol.
- RAG: RagLoader validates backends at init and persists `path`/`profile` metadata; RagRetriever surfaces scored hits.

## Scheduling & Execution
- PlannerAgent ranks tools by goal similarity (ReAct/Plan-and-Execute hybrid) respecting config max steps.
- CoordinatorAgent dispatches workers via thread-safe round-robin to guarantee fairness.
- WorkerAgent defaults profile to memory profile, propagates `trace_id`, and logs structured traces.

## Orchestrator Architecture (v1.3.2)

### Overview
The orchestrator layer provides production-ready coordination with retry policies, audit trails, approval gates, and partial result recovery. All orchestration follows the canonical **OrchestratorProtocol** with explicit lifecycle stages and immutable execution context.

### Core Components

#### 1. OrchestratorProtocol
Defines the orchestrator lifecycle contract:
- **Lifecycle Stages**: `initialize` → `plan` → `route` → `execute` → `aggregate` → `complete`
- **ExecutionContext**: Immutable context with `trace_id`, `request_id`, `user_intent`, and optional fields (`user_id`, `memory_scope`, `conversation_id`, `session_id`, `parent_context`)
- **Failure Modes**: Structured error propagation with `FailureMode` taxonomy (AGENT/SYSTEM/RESOURCE/POLICY/USER)
- **Context Updates**: Immutable with `with_*` methods for safe updates across stages

See [`docs/orchestrator/ORCHESTRATOR_CONTRACT.md`](docs/orchestrator/ORCHESTRATOR_CONTRACT.md) for full specification.

#### 2. RoutingAuthority
All routing decisions MUST go through `RoutingAuthority` interface:
- **PolicyBasedRoutingAuthority**: Pluggable routing policies (round-robin, capability-based, load-balanced)
- **RoundRobinPolicy**: Ensures fair worker selection with thread-safe state management
- **CapabilityBasedPolicy**: Routes based on worker capabilities and tool requirements
- **LoadBalancedPolicy**: Distributes work based on worker load metrics

No routing bypass allowed—agents/FastAPI/LangGraph nodes MUST NOT contain internal routing logic.

See [`docs/orchestrator/ROUTING_AUTHORITY.md`](docs/orchestrator/ROUTING_AUTHORITY.md) for routing patterns.

#### 3. PlanningAuthority
All planning decisions MUST go through `PlanningAuthority` interface:
- **Plan State Machine**: `CREATED` → `VALIDATED` → `EXECUTING` → `COMPLETED`/`FAILED`
- **ToolBudget Tracking**: Enforces `cost_ceiling`, `call_ceiling`, `token_ceiling` with warnings before blocking
- **State Transitions**: Idempotent and validated (can't skip stages, terminal states are final)
- **AuditTrail Integration**: All plans automatically recorded with trace_id for debugging

See [`docs/orchestrator/PLANNING_AUTHORITY.md`](docs/orchestrator/PLANNING_AUTHORITY.md) for planning patterns.

#### 4. RetryPolicy
Intelligent retry with failure mode categorization:
- **Strategies**: Exponential backoff (default), linear backoff, no-retry
- **Transient Failures**: Automatic retry for `ConnectionError`, `TimeoutError`, `HTTPStatusError` (5xx)
- **Terminal Failures**: No retry for `ValidationError`, `AuthenticationError`, `PermissionError`
- **Backoff Configuration**: Configurable `max_attempts`, `base_delay`, `max_delay`, `multiplier`

RetryPolicy implementations (ExponentialBackoff/Linear/NoRetry) are pluggable via factory function.

See [`docs/orchestrator/FAILURE_MODES.md`](docs/orchestrator/FAILURE_MODES.md) for failure taxonomy.

#### 5. AuditTrail
Persistent decision recording for compliance and debugging:
- **Backends**: SQLite (production), JSON (development)
- **DecisionRecord**: Records planning, routing, execution decisions with trace_id
- **Trace Queries**: `get_trace_history(trace_id)` retrieves all decisions for a trace
- **Decision Types**: `"planning"`, `"routing"`, `"execution"` with type-specific metadata

All routing and planning decisions MUST be recorded to audit trail with decision reasoning.

#### 6. ApprovalGate
Human-in-the-loop approval for sensitive operations:
- **ApprovalPolicy**: Configurable approval requirements (manual, auto-approve, timeout-based)
- **Manual Approval**: Async approval workflow with `request_approval()` and `resolve_approval()`
- **Auto-Approve**: Automatic approval after timeout (configurable, default 30s)
- **Timeout Handling**: Graceful degradation with configurable fallback behavior

Approval gates integrate with observability (emit `approval_requested`, `approval_received` events).

#### 7. PartialResult
Recovery from partial execution failures:
- **Checkpoint Tracking**: Records completed steps and last successful output
- **Recovery Strategies**: Automatic recovery strategy suggestions based on failure mode
- **Resume Capability**: `WorkerAgent.execute_from_partial()` resumes from last checkpoint
- **Failure Detection**: Distinguishes recoverable vs terminal failures

PartialResult attached to exceptions for automatic recovery by orchestrators.

### Integration Patterns

#### Basic Orchestration Flow
```python
# 1. Create execution context
context = ExecutionContext(trace_id="trace-001", user_intent="Calculate 10 + 5")

# 2. Create plan with budget
plan = Plan(
    plan_id="plan-001",
    goal="Calculate 10 + 5",
    steps=[PlanStep(tool="add", input={"a": 10, "b": 5}, index=0)],
    stage=PlanningStage.CREATED,
    budget=ToolBudget(cost_ceiling=100.0, call_ceiling=50, token_ceiling=10000),
    trace_id=context.trace_id,
)

# 3. Record to audit trail
audit_trail.record_plan(plan)

# 4. Route to worker
worker = routing_authority.select_worker(plan.steps[0])

# 5. Execute with retry policy
result = worker.execute(
    steps=[{"tool": step.tool, "input": step.input} for step in plan.steps],
    metadata={"trace_id": context.trace_id}
)
```

#### Retry with Transient Failure
```python
# Create retry policy
retry_policy = create_retry_policy(
    strategy="exponential",
    max_attempts=3,
    base_delay=0.1,
    max_delay=5.0,
)

# Execute with automatic retry
try:
    result = worker.execute(steps, metadata={"trace_id": trace_id})
except Exception as exc:
    if retry_policy.should_retry(exc, attempt=1):
        # Retry with backoff
        time.sleep(retry_policy.get_delay(attempt=1))
        result = worker.execute(steps, metadata={"trace_id": trace_id})
    else:
        raise
```

#### Partial Result Recovery
```python
try:
    result = worker.execute(steps, metadata={"trace_id": trace_id})
except Exception as exc:
    # Extract partial result from exception
    partial = worker.get_partial_result_from_exception(exc)
    
    if partial and partial.is_recoverable:
        # Get recovery strategy suggestions
        strategies = partial.get_recovery_strategies()
        print(f"Recovery strategies: {strategies}")
        
        # Resume from checkpoint
        result = worker.execute_from_partial(steps, partial)
```

#### Approval Gate Integration
```python
# Create approval policy
approval_policy = ApprovalPolicy(
    require_approval=True,
    auto_approve_timeout=30.0,
)

# Request approval for sensitive operation
approval_id = approval_gate.request_approval(
    operation="delete_database",
    context={"database": "production", "user": "admin"},
)

# Wait for approval (with timeout)
approved = await approval_gate.wait_for_approval(approval_id, timeout=30.0)

if approved:
    # Execute sensitive operation
    result = worker.execute(steps, metadata={"trace_id": trace_id})
```

### Observability Integration

The orchestrator emits structured events for all operations:
- **Planning Events**: `plan_created` with step_count, tool_list, budget
- **Routing Events**: `route_decision` with worker_id, policy, reasoning
- **Execution Events**: `tool_call_start`, `tool_call_complete`, `tool_call_error`
- **Budget Events**: `budget_warning`, `budget_exceeded`
- **Approval Events**: `approval_requested`, `approval_received`, `approval_timeout`

Events include `trace_id`, `timestamp`, `duration_ms`, and component-specific metadata.

See [`docs/observability/OBSERVABILITY_SLOS.md`](docs/observability/OBSERVABILITY_SLOS.md) for golden signals and metrics.

### Testing Strategy

The orchestrator test suite (168 tests) covers:
1. **Unit Tests** (152 tests): Individual component behavior
   - OrchestratorProtocol (31 tests)
   - RoutingAuthority (20 tests)
   - PlanningAuthority (18 tests)
   - RetryPolicy (18 tests)
   - AuditTrail (17 tests)
   - ApprovalGate (26 tests)
   - PartialResult (22 tests)

2. **Integration Tests** (16 tests): End-to-end orchestration
   - Retry + approval + audit combined
   - Partial result recovery workflows
   - Concurrent execution with trace isolation
   - Complex multi-stage workflows

See [`tests/test_orchestrator_integration.py`](tests/test_orchestrator_integration.py) for integration test examples.

### Configuration

Orchestrator components are configured via environment variables and YAML:

```yaml
# configs/orchestrator.yaml
retry:
  strategy: exponential  # exponential, linear, none
  max_attempts: 3
  base_delay: 0.1
  max_delay: 5.0
  multiplier: 2.0

approval:
  require_approval: true
  auto_approve_timeout: 30.0
  approval_backend: sqlite  # sqlite, redis

audit:
  backend: sqlite  # sqlite, json
  db_path: data/audit.db
  retention_days: 90

routing:
  policy: round_robin  # round_robin, capability_based, load_balanced
  worker_pool_size: 4

budget:
  cost_ceiling: 100.0
  call_ceiling: 50
  token_ceiling: 10000
  warn_threshold: 0.8  # Warn at 80% of ceiling
```

### Deployment Considerations

1. **Audit Trail**: Use SQLite backend for production (persistent, queryable)
2. **Approval Gates**: Configure timeouts based on SLA requirements
3. **Retry Policy**: Tune backoff parameters for your failure patterns
4. **Budget Tracking**: Set realistic ceilings based on workload analysis
5. **Observability**: Wire OTEL_EXPORTER_OTLP_ENDPOINT for centralized tracing

See [`docs/orchestrator/README.md`](docs/orchestrator/README.md) for complete API reference and deployment guide.

## Tooling & CLI
- ToolRegistry restricts dynamic imports to `cuga.modular.tools.*`.
- CLI (`python -m cuga.modular.cli`) provides `ingest`, `query`, `plan` with JSON logs and shared state file for demos.

For a mode-aware, controller → planner → executor narrative (including MCP pack assembly and configuration keys), see [docs/agents/architecture.md](docs/agents/architecture.md).

# Agent Integration Guide (v1.1.0)

> **Status**: Production-ready as of v1.1.0 (January 2, 2026)  
> **Test Coverage**: 26/26 tests passing (100%) - 15 unit + 11 integration tests

## Overview

The v1.1.0 release integrates modular agents (`PlannerAgent`, `WorkerAgent`, `CoordinatorAgent`) with the observability and guardrails infrastructure introduced in v1.0.0. All agent operations now emit structured events, enforce budget constraints, and provide comprehensive metrics for monitoring.

## Architecture

```
┌─────────────────┐
│ PlannerAgent    │──► plan_created events
│  - Tool ranking │    (trace_id, steps_count, duration_ms)
│  - LLM planning │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│ CoordinatorAgent│──► route_decision events
│  - Round-robin  │    (agent_selected, alternatives, reason)
│  - Dispatch     │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│ WorkerAgent     │──► tool_call_start/complete/error events
│  - Tool exec    │    (tool_name, inputs, result, duration_ms)
│  - Budget guard │──► budget_exceeded events
│  - Memory store │    (profile, current_value, limit, utilization_pct)
└─────────────────┘
```

## PlannerAgent Observability

### Event Emission

**PlannerAgent.plan()** emits `plan_created` events after generating execution plans:

```python
from cuga.modular.agents import PlannerAgent
from cuga.modular.config import AgentConfig
from cuga.modular.memory import VectorMemory

# Create planner
config = AgentConfig(profile="production", max_steps=10)
memory = VectorMemory(profile="production")
planner = PlannerAgent(config=config, registry=registry, memory=memory)

# Plan emits plan_created event automatically
plan = planner.plan(
    goal="Analyze sales data and create report",
    metadata={"trace_id": "sales-analysis-001"}
)
```

### Event Structure

```python
{
    "event_type": "plan_created",
    "trace_id": "sales-analysis-001",
    "timestamp": 1735862400.123,
    "status": "success",
    "attributes": {
        "goal": "Analyze sales data and create report",
        "steps_count": 5,
        "tools_selected": ["read_csv", "aggregate", "chart", "write_report"],
        "profile": "production",
        "max_steps": 10
    },
    "duration_ms": 245.67
}
```

### Key Metadata

- **`steps_count`**: Number of steps in generated plan
- **`tools_selected`**: List of tool names ranked by similarity
- **`profile`**: Agent profile (e.g., "production", "dev")
- **`max_steps`**: Maximum steps configured for this planner
- **`duration_ms`**: Time spent planning (milliseconds)

### Trace Propagation

PlannerAgent generates a `trace_id` if not provided:

```python
# Automatic trace_id generation
plan = planner.plan(goal="Do something")  
# trace_id: "plan-<id>-<timestamp>"

# Explicit trace_id (recommended for correlation)
plan = planner.plan(
    goal="Do something",
    metadata={"trace_id": "my-custom-trace-001"}
)
```

## WorkerAgent Observability & Guardrails

### Event Emission

**WorkerAgent.execute()** emits three types of events:

1. **`tool_call_start`** - Before tool execution
2. **`tool_call_complete`** - After successful execution
3. **`tool_call_error`** - On execution failure
4. **`budget_exceeded`** - When budget guard blocks execution

```python
from cuga.modular.agents import WorkerAgent
from cuga.backend.guardrails.policy import GuardrailPolicy, ToolBudget

# Create worker with budget enforcement
policy = GuardrailPolicy(
    profile="production",
    tool_allowlist=["read_csv", "write_file", "http_get"],
    budget=ToolBudget(
        max_cost=10.0,      # Maximum cost units
        max_calls=50,       # Maximum tool calls
        max_tokens=100_000  # Maximum tokens
    )
)

worker = WorkerAgent(
    registry=registry,
    memory=memory,
    guardrail_policy=policy  # Optional - enables budget enforcement
)

# Execute emits tool_call_start, then complete/error
steps = [
    {"tool": "read_csv", "input": {"path": "data.csv"}},
    {"tool": "http_get", "input": {"url": "https://api.example.com/data"}}
]

result = worker.execute(steps, metadata={"trace_id": "data-pipeline-001"})
```

### Event Structures

#### tool_call_start

```python
{
    "event_type": "tool_call_start",
    "trace_id": "data-pipeline-001",
    "timestamp": 1735862400.456,
    "status": "success",
    "attributes": {
        "tool_name": "read_csv",
        "inputs": {"path": "data.csv"},
        "profile": "production",
        "step_index": 0
    }
}
```

#### tool_call_complete

```python
{
    "event_type": "tool_call_complete",
    "trace_id": "data-pipeline-001",
    "timestamp": 1735862400.789,
    "status": "success",
    "attributes": {
        "tool_name": "read_csv",
        "inputs": {"path": "data.csv"},
        "result": {"rows": 1000, "columns": 10}
    },
    "duration_ms": 333.12
}
```

#### tool_call_error

```python
{
    "event_type": "tool_call_error",
    "trace_id": "data-pipeline-001",
    "timestamp": 1735862401.123,
    "status": "error",
    "attributes": {
        "tool_name": "http_get",
        "inputs": {"url": "https://api.example.com/data"},
        "error_type": "ConnectionError"
    },
    "error_message": "Connection timeout after 30s",
    "duration_ms": 30012.45
}
```

#### budget_exceeded

```python
{
    "event_type": "budget_exceeded",
    "trace_id": "data-pipeline-001",
    "timestamp": 1735862401.456,
    "status": "error",
    "attributes": {
        "profile": "production",
        "budget_type": "cost",
        "current_value": 10.05,
        "limit": 10.0,
        "utilization_pct": 100.5,
        "overage": 0.05
    }
}
```

### Budget Enforcement

WorkerAgent enforces budgets using `budget_guard()`:

```python
# Budget guard checks before EACH tool call
# Raises ValueError if budget exhausted

try:
    result = worker.execute(steps, metadata={"trace_id": "test-001"})
except ValueError as e:
    # Budget exhausted - budget_exceeded event emitted
    print(f"Budget error: {e}")
    # "Budget exhausted for profile 'production': 
    #  cost=10.05/10.0, calls=51/50, tokens=95000/100000"
```

**Cost Estimation**: Currently uses `0.01` cost per tool call. In production, this should be tool-specific (e.g., LLM calls cost more than file reads).

### Budget State Tracking

```python
# Check budget state
policy = worker.guardrail_policy
budget = policy.budget

print(f"Cost: {budget.current_cost}/{budget.max_cost}")
print(f"Calls: {budget.current_calls}/{budget.max_calls}")
print(f"Tokens: {budget.current_tokens}/{budget.max_tokens}")

# Calculate utilization percentage
cost_pct = (budget.current_cost / budget.max_cost * 100) if budget.max_cost > 0 else 0
calls_pct = (budget.current_calls / budget.max_calls * 100) if budget.max_calls > 0 else 0
tokens_pct = (budget.current_tokens / budget.max_tokens * 100) if budget.max_tokens > 0 else 0

utilization_pct = max(cost_pct, calls_pct, tokens_pct)
print(f"Overall utilization: {utilization_pct:.1f}%")
```

## CoordinatorAgent Observability

### Event Emission

**CoordinatorAgent.dispatch()** emits `route_decision` events after selecting workers:

```python
from cuga.modular.agents import CoordinatorAgent

# Create coordinator with worker pool
coordinator = CoordinatorAgent(workers=[worker1, worker2, worker3])

# Dispatch emits route_decision event automatically
result = coordinator.dispatch(
    plan=plan,
    metadata={"trace_id": "orchestration-001"}
)
```

### Event Structure

```python
{
    "event_type": "route_decision",
    "trace_id": "orchestration-001",
    "timestamp": 1735862402.123,
    "status": "success",
    "attributes": {
        "agent_selected": "WorkerAgent-2",
        "alternatives_considered": 3,
        "reason": "round_robin",
        "worker_idx": 1,  # 0-indexed position in worker pool
        "total_workers": 3
    },
    "duration_ms": 0.45
}
```

### Routing Metadata

- **`agent_selected`**: Name of selected worker (e.g., "WorkerAgent-2")
- **`alternatives_considered`**: Number of workers in pool
- **`reason`**: Routing algorithm used ("round_robin")
- **`worker_idx`**: Index of selected worker (0-based)
- **`duration_ms`**: Time spent routing (typically <1ms)

## End-to-End Example

### Complete Flow with All Events

```python
from cuga.modular.agents import PlannerAgent, WorkerAgent, CoordinatorAgent
from cuga.modular.config import AgentConfig
from cuga.modular.memory import VectorMemory
from cuga.backend.guardrails.policy import GuardrailPolicy, ToolBudget
from cuga.observability import get_collector

# Setup
registry = build_default_registry()
memory = VectorMemory(profile="production")
config = AgentConfig(profile="production", max_steps=5)

# Create agents with observability
policy = GuardrailPolicy(
    profile="production",
    tool_allowlist=["calculator", "write_file"],
    budget=ToolBudget(max_cost=5.0, max_calls=10, max_tokens=50_000)
)

planner = PlannerAgent(config=config, registry=registry, memory=memory)
worker = WorkerAgent(registry=registry, memory=memory, guardrail_policy=policy)
coordinator = CoordinatorAgent(workers=[worker])

# Execute with trace correlation
trace_id = "calculation-workflow-001"

# Step 1: Plan (emits plan_created)
plan = planner.plan(
    goal="Calculate 2+2 and save to file",
    metadata={"trace_id": trace_id}
)

# Step 2: Route (emits route_decision)
result = coordinator.dispatch(plan, metadata={"trace_id": trace_id})

# All events correlated by trace_id
collector = get_collector()
events = [e for e in collector.events if e.trace_id == trace_id]

print(f"Total events for trace {trace_id}: {len(events)}")
for event in events:
    print(f"  - {event.event_type.value} at {event.timestamp}")

# Example output:
#   Total events for trace calculation-workflow-001: 5
#   - plan_created at 1735862400.123
#   - route_decision at 1735862400.456
#   - tool_call_start at 1735862400.789 (calculator)
#   - tool_call_complete at 1735862401.012 (calculator)
#   - tool_call_start at 1735862401.234 (write_file)
#   - tool_call_complete at 1735862401.567 (write_file)
```

## Golden Signals & Metrics

### Automatic Metrics Updates

All agent operations automatically update golden signals:

```python
from cuga.observability import get_collector

collector = get_collector()
signals = collector.signals

# Success rate (% successful tool calls)
print(f"Success rate: {signals.success_rate():.1f}%")

# Latency percentiles
print(f"P50 latency: {signals.latency_p50():.1f}ms")
print(f"P95 latency: {signals.latency_p95():.1f}ms")
print(f"P99 latency: {signals.latency_p99():.1f}ms")

# Error rates
print(f"Tool error rate: {signals.tool_error_rate():.1f}%")

# Plan efficiency
print(f"Mean steps per task: {signals.mean_steps_per_task():.1f}")
```

### Prometheus Export

Agent events are included in `/metrics` endpoint:

```bash
curl http://localhost:8000/metrics

# Example output:
# HELP cuga_requests_total Total agent requests
# TYPE cuga_requests_total counter
cuga_requests_total 42

# HELP cuga_success_rate Success rate percentage
# TYPE cuga_success_rate gauge
cuga_success_rate 95.2

# HELP cuga_tool_calls_total Total tool calls
# TYPE cuga_tool_calls_total counter
cuga_tool_calls_total 127

# HELP cuga_tool_errors_total Tool execution errors
# TYPE cuga_tool_errors_total counter
cuga_tool_errors_total 6

# HELP cuga_budget_exceeded_total Budget exceeded events
# TYPE cuga_budget_exceeded_total counter
cuga_budget_exceeded_total 2
```

## Testing Patterns

### Integration Test Structure

```python
import pytest
from cuga.observability import get_collector, set_collector, ObservabilityCollector

@pytest.fixture
def test_collector():
    """Create test collector with console exporter."""
    collector = ObservabilityCollector(
        exporters=[ConsoleExporter(pretty=False)],
        auto_export=False,  # Don't print during tests
        buffer_size=100,
    )
    set_collector(collector)
    yield collector
    collector.reset_metrics()

def test_planner_emits_event(test_collector, registry, memory, config):
    """Test PlannerAgent emits plan_created event."""
    planner = PlannerAgent(config=config, registry=registry, memory=memory)
    test_collector.reset_metrics()
    
    # Execute
    plan = planner.plan(goal="Test goal", metadata={"trace_id": "test-001"})
    
    # Verify event
    events = [e for e in test_collector.events if e.event_type.value == "plan_created"]
    assert len(events) == 1
    
    event = events[0]
    assert event.trace_id == "test-001"
    assert event.attributes["goal"] == "Test goal"
    assert event.attributes["steps_count"] > 0
    assert event.duration_ms is not None
```

### Budget Test Pattern

```python
def test_budget_enforcement(test_collector, registry, memory):
    """Test WorkerAgent enforces budget limits."""
    policy = GuardrailPolicy(
        profile="test",
        tool_allowlist=["echo"],
        budget=ToolBudget(max_cost=0.05, max_calls=1, max_tokens=100),
        emit_events=False,  # Disable legacy events
    )
    
    worker = WorkerAgent(registry=registry, memory=memory, guardrail_policy=policy)
    test_collector.reset_metrics()
    
    # First call succeeds
    steps = [{"tool": "echo", "input": {"text": "first"}}]
    result = worker.execute(steps, metadata={"trace_id": "test-001"})
    assert result.output == "first"
    
    # Second call fails (budget exhausted)
    with pytest.raises(ValueError, match="Budget exhausted"):
        worker.execute(steps, metadata={"trace_id": "test-002"})
    
    # Verify budget_exceeded event
    budget_events = [e for e in test_collector.events if e.event_type.value == "budget_exceeded"]
    assert len(budget_events) == 1
```

## Migration from v1.0.0

### Backward Compatibility

v1.1.0 maintains backward compatibility with v1.0.0:

- **Legacy observability**: BaseEmitter still supported (deprecated)
- **Trace lists**: Old trace lists maintained alongside new events
- **Optional guardrails**: WorkerAgent works without guardrail_policy

### Deprecation Warnings

```python
# Legacy BaseEmitter (deprecated - still works)
worker = WorkerAgent(
    registry=registry,
    memory=memory,
    observability=InMemoryTracer()  # Deprecated but functional
)

# Recommended v1.1.0 approach
worker = WorkerAgent(
    registry=registry,
    memory=memory,
    guardrail_policy=policy  # New guardrails integration
)
```

## Configuration

### Environment Variables

```bash
# Observability backend (optional)
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export LANGFUSE_PUBLIC_KEY=pk-...
export LANGFUSE_SECRET_KEY=sk-...

# Budget enforcement (required for service mode)
export AGENT_BUDGET_CEILING=100
export AGENT_ESCALATION_MAX=2
export AGENT_BUDGET_POLICY=warn  # or "block"

# Agent configuration
export AGENT_PROFILE=production
export AGENT_MAX_STEPS=10
```

### Profile-Based Configuration

```yaml
# configs/agent.production.yaml
profile: production
max_steps: 10
budget:
  max_cost: 100.0
  max_calls: 500
  max_tokens: 1_000_000
observability:
  auto_export: true
  buffer_size: 1000
  exporters:
    - type: otlp
      endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT}
    - type: console
      pretty: true
```

## Troubleshooting

### No Events Emitted

**Problem**: Events not appearing in collector.

**Solutions**:
1. Verify collector is set: `set_collector(collector)`
2. Check auto_export setting: `auto_export=False` for testing
3. Verify trace_id propagation in metadata
4. Check for silent exceptions in try/except blocks

### Budget Not Enforcing

**Problem**: Tools execute beyond budget limits.

**Solutions**:
1. Verify guardrail_policy is set on WorkerAgent
2. Check budget limits are configured (max_cost, max_calls, max_tokens)
3. Verify budget_guard() is called before tool execution
4. Check for budget.charge() after successful execution

### Missing Trace Correlation

**Problem**: Events not correlated by trace_id.

**Solutions**:
1. Pass consistent trace_id in metadata across all agent calls
2. Use same trace_id for plan/route/execute chain
3. Check trace_id propagation through coordinator
4. Verify trace_id is in event attributes

## Best Practices

### 1. Always Use Trace IDs

```python
# Good: Explicit trace_id for correlation
trace_id = f"user-{user_id}-request-{request_id}"
plan = planner.plan(goal=goal, metadata={"trace_id": trace_id})
result = coordinator.dispatch(plan, metadata={"trace_id": trace_id})

# Avoid: Implicit trace_id generation
plan = planner.plan(goal=goal)  # Auto-generates unique ID each call
```

### 2. Set Appropriate Budget Limits

```python
# Production: Conservative limits with monitoring
policy = GuardrailPolicy(
    profile="production",
    budget=ToolBudget(
        max_cost=50.0,      # Enough for typical workflows
        max_calls=100,      # Prevents runaway loops
        max_tokens=500_000  # Covers most LLM operations
    )
)

# Development: Higher limits for testing
policy = GuardrailPolicy(
    profile="dev",
    budget=ToolBudget(
        max_cost=1000.0,    # Generous for experimentation
        max_calls=1000,
        max_tokens=5_000_000
    )
)
```

### 3. Monitor Golden Signals

```python
# Check metrics after workflows
collector = get_collector()
signals = collector.signals

# Alert if success rate drops
if signals.success_rate() < 95.0:
    logger.warning(f"Low success rate: {signals.success_rate():.1f}%")

# Alert if P95 latency too high
if signals.latency_p95() > 5000.0:  # 5 seconds
    logger.warning(f"High P95 latency: {signals.latency_p95():.1f}ms")

# Alert on high error rates
if signals.tool_error_rate() > 5.0:
    logger.error(f"High error rate: {signals.tool_error_rate():.1f}%")
```

### 4. Use Profile-Based Isolation

```python
# Separate budgets per profile
prod_policy = GuardrailPolicy(profile="production", budget=prod_budget)
dev_policy = GuardrailPolicy(profile="dev", budget=dev_budget)

prod_worker = WorkerAgent(registry=registry, memory=prod_memory, guardrail_policy=prod_policy)
dev_worker = WorkerAgent(registry=registry, memory=dev_memory, guardrail_policy=dev_policy)
```

## See Also

- [Observability SLOs](./OBSERVABILITY_SLOS.md) - Service level objectives and metrics
- [Integration Checklist](./INTEGRATION_CHECKLIST.md) - Component integration guide
- [AGENTS.md](../../AGENTS.md) - Canonical agent guardrails
- [Testing Guide](../testing/SCENARIO_TESTING.md) - End-to-end scenario tests

## Version History

- **v1.1.0** (2026-01-02): Initial agent integration with 26/26 tests passing
- **v1.0.0** (2026-01-01): Observability infrastructure foundation

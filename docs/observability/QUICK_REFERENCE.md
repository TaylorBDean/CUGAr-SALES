# Observability Quick Reference

## Event Emission Patterns

### Planning
```python
from cuga.observability import PlanEvent, emit_event
import time

start = time.time()
# ... planning logic ...
duration_ms = (time.time() - start) * 1000

emit_event(PlanEvent.create(
    trace_id=trace_id,
    goal=user_goal,
    steps_count=len(steps),
    tools_selected=[s.tool for s in steps],
    duration_ms=duration_ms,
))
```

### Routing
```python
from cuga.observability import RouteEvent, emit_event

emit_event(RouteEvent.create(
    trace_id=trace_id,
    agent_selected=selected_agent,
    routing_policy="capability_based",
    alternatives_considered=other_agents,
    reasoning="Agent has required capabilities",
))
```

### Tool Execution
```python
from cuga.observability import ToolCallEvent, emit_event

# Start
emit_event(ToolCallEvent.start(
    trace_id=trace_id,
    tool_name=tool,
    tool_params=params,
))

start = time.time()
try:
    result = execute(tool, params)
    duration_ms = (time.time() - start) * 1000
    
    # Complete
    emit_event(ToolCallEvent.complete(
        trace_id=trace_id,
        tool_name=tool,
        duration_ms=duration_ms,
        result_size=len(str(result)),
    ))
except Exception as e:
    duration_ms = (time.time() - start) * 1000
    
    # Error
    emit_event(ToolCallEvent.error(
        trace_id=trace_id,
        tool_name=tool,
        error_type=type(e).__name__,
        error_message=str(e),
        duration_ms=duration_ms,
    ))
    raise
```

### Budget Tracking
```python
from cuga.observability import BudgetEvent, emit_event

# Warning at 80% threshold
if spent > ceiling * 0.8:
    emit_event(BudgetEvent.warning(
        trace_id=trace_id,
        budget_type="cost",
        spent=spent,
        ceiling=ceiling,
        threshold=ceiling * 0.8,
    ))

# Exceeded
if spent > ceiling:
    emit_event(BudgetEvent.exceeded(
        trace_id=trace_id,
        budget_type="cost",
        spent=spent,
        ceiling=ceiling,
        policy="block",
    ))
```

### Approval Workflow
```python
from cuga.observability import ApprovalEvent, emit_event

# Request
emit_event(ApprovalEvent.requested(
    trace_id=trace_id,
    action_description="Delete database",
    risk_level="high",
    timeout_seconds=300,
))

# Wait for approval
start = time.time()
approved = await wait_for_approval(timeout=300)
wait_ms = (time.time() - start) * 1000

if approved is not None:
    # Received
    emit_event(ApprovalEvent.received(
        trace_id=trace_id,
        approved=approved,
        wait_time_ms=wait_ms,
        reason="User decision",
    ))
else:
    # Timeout
    emit_event(ApprovalEvent.timeout(
        trace_id=trace_id,
        wait_time_ms=wait_ms,
        default_action="deny",
    ))
```

## Metrics Access

### Get Current Metrics
```python
from cuga.observability import get_collector

metrics = get_collector().get_metrics()
```

### Key Metrics
```python
# Success & Error Rates
success_rate = metrics['success_rate']  # 0-100
error_rate = metrics['error_rate']      # 0-100
tool_error_rate = metrics['tool_error_rate']  # 0-100

# Latency
latency = metrics['latency']['end_to_end']
p50 = latency['p50']  # milliseconds
p95 = latency['p95']
p99 = latency['p99']
mean = latency['mean']

# Traffic
total_requests = metrics['total_requests']
successful = metrics['successful_requests']
failed = metrics['failed_requests']
rps = metrics['requests_per_second']

# Tools
tool_calls = metrics['tool_calls']
tool_errors = metrics['tool_errors']
steps_per_task = metrics['mean_steps_per_task']

# Approval
approval_requests = metrics['approval']['requests']
approval_wait_p95 = metrics['approval']['wait_time']['p95']
```

### Prometheus Export
```python
prometheus_text = get_collector().get_prometheus_metrics()
# Returns Prometheus text format
```

## Configuration

### Environment Variables
```bash
# OTEL Endpoint
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"

# Service Name
export OTEL_SERVICE_NAME="cuga-agent"

# Exporter Type (otlp|console|none)
export OTEL_TRACES_EXPORTER="otlp"

# Custom Headers
export OTEL_EXPORTER_OTLP_HEADERS="x-api-key=secret"
```

### Initialization
```python
from cuga.observability import ObservabilityCollector, OTELExporter, set_collector

collector = ObservabilityCollector(
    exporters=[
        OTELExporter(
            endpoint="http://localhost:4318",
            service_name="cuga-agent",
        )
    ],
    auto_export=True,
)
set_collector(collector)
```

## Common Patterns

### Trace Lifecycle
```python
from cuga.observability import get_collector

collector = get_collector()

# Start
collector.start_trace(trace_id, metadata={"user": "alice"})

try:
    # ... execution ...
    collector.end_trace(trace_id, success=True)
except Exception:
    collector.end_trace(trace_id, success=False)
    raise
```

### Flush & Shutdown
```python
# Force flush events
collector.flush()

# Export current metrics
collector.export_metrics()

# Shutdown (flush + export + close exporters)
collector.shutdown()
```

### Reset for Testing
```python
collector.reset_metrics()
```

## Dashboard Panels

When using `observability/grafana_dashboard.json`:

1. **Success Rate** - Gauge with red/yellow/green thresholds
2. **Tool Error Rate** - Error tracking gauge
3. **Mean Steps Per Task** - Planning complexity
4. **Budget Utilization** - Warnings and exceeded events
5. **Request Rate** - Traffic over time
6. **End-to-End Latency** - P50/P95/P99 percentiles
7. **Tool Call Latency** - Per-tool timing
8. **Approval Wait Time** - Human-in-the-loop latency
9. **Tool Errors by Type** - Error distribution
10. **Tool Errors by Tool** - Per-tool errors
11. **Active Traces** - Current trace count
12. **Event Timeline** - Structured log stream

## Troubleshooting

### Events not appearing
```python
# Check collector initialized
from cuga.observability import get_collector
collector = get_collector()  # Should not raise

# Verify auto-export enabled
assert collector.auto_export == True

# Check buffer
print(f"Buffer size: {len(collector._event_buffer)}")

# Force flush
collector.flush()
```

### OTEL connection issues
```bash
# Test endpoint
curl http://localhost:4318/v1/traces

# Check exporter enabled
echo $OTEL_TRACES_EXPORTER  # Should be "otlp"

# Use console exporter for debugging
export OTEL_TRACES_EXPORTER=console
```

### High memory usage
```python
# Reduce buffer size
collector = ObservabilityCollector(
    buffer_size=100,  # Default: 1000
    auto_export=True,  # Flush immediately
)

# Periodic flush
import atexit
atexit.register(collector.shutdown)
```

## See Also

- [OBSERVABILITY_SLOS.md](../docs/observability/OBSERVABILITY_SLOS.md) - Full documentation
- [observability_example.py](../examples/observability_example.py) - Integration example
- [test_observability.py](../tests/observability/test_observability.py) - Test suite
- [configs/observability.yaml](../configs/observability.yaml) - Configuration

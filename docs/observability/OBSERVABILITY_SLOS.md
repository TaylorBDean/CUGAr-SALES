# Observability & SLOs

Comprehensive observability for CUGAR agent system with structured events, golden signals tracking, OpenTelemetry integration, and pre-built Grafana dashboards.

## Overview

The observability system provides:

1. **Structured Events**: Per-step event emission (plan, route, tool_call, budget, approval)
2. **Golden Signals**: Success rate, latency, traffic, and error tracking
3. **Agent-Specific Metrics**: Steps per task, tool error rates, approval wait times
4. **OTEL Export**: Native OpenTelemetry integration with OTLP, Jaeger, Zipkin
5. **Grafana Dashboard**: Pre-built dashboard for real-time monitoring

## Architecture

```
┌─────────────────┐
│ Agent Execution │
└────────┬────────┘
         │ emit events
         ▼
┌─────────────────────┐
│ Event System        │
│ - PlanEvent         │
│ - RouteEvent        │
│ - ToolCallEvent     │
│ - BudgetEvent       │
│ - ApprovalEvent     │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│ Observability       │
│ Collector           │
│ - Event buffering   │
│ - Signal tracking   │
│ - Trace correlation │
└────────┬────────────┘
         │
         ├─────────────┬──────────────┐
         ▼             ▼              ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │   OTEL   │  │ Console  │  │ Custom   │
  │ Exporter │  │ Exporter │  │ Exporter │
  └──────────┘  └──────────┘  └──────────┘
         │             │              │
         ▼             ▼              ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │  Jaeger  │  │  Stdout  │  │   HTTP   │
  │  Zipkin  │  │   Logs   │  │ Endpoint │
  │  OTLP    │  └──────────┘  └──────────┘
  └──────────┘
         │
         ▼
  ┌──────────┐
  │ Grafana  │
  │Dashboard │
  └──────────┘
```

## Event Types

### 1. Plan Events
Emitted when planning completes:

```python
from cuga.observability import PlanEvent, get_collector

event = PlanEvent.create(
    trace_id="trace-123",
    goal="Find flights to NYC",
    steps_count=3,
    tools_selected=["search", "filter", "book"],
    duration_ms=150.0,
)
get_collector().emit_event(event)
```

### 2. Route Events
Emitted when routing decision is made:

```python
from cuga.observability import RouteEvent

event = RouteEvent.create(
    trace_id="trace-123",
    agent_selected="travel_agent",
    routing_policy="capability_based",
    alternatives_considered=["general_agent", "booking_agent"],
    reasoning="Travel agent has flight booking capability",
)
get_collector().emit_event(event)
```

### 3. Tool Call Events
Emitted for tool execution lifecycle:

```python
from cuga.observability import ToolCallEvent

# Start
start_event = ToolCallEvent.start(
    trace_id="trace-123",
    tool_name="search_flights",
    tool_params={"origin": "SFO", "destination": "NYC"},
)
get_collector().emit_event(start_event)

# Complete
complete_event = ToolCallEvent.complete(
    trace_id="trace-123",
    tool_name="search_flights",
    duration_ms=450.0,
    result_size=1024,
)
get_collector().emit_event(complete_event)

# Error
error_event = ToolCallEvent.error(
    trace_id="trace-123",
    tool_name="search_flights",
    error_type="timeout",
    error_message="API timeout after 30s",
    duration_ms=30000.0,
)
get_collector().emit_event(error_event)
```

### 4. Budget Events
Emitted for budget tracking:

```python
from cuga.observability import BudgetEvent

# Warning
warning_event = BudgetEvent.warning(
    trace_id="trace-123",
    budget_type="cost",
    spent=85.0,
    ceiling=100.0,
    threshold=80.0,
)

# Exceeded
exceeded_event = BudgetEvent.exceeded(
    trace_id="trace-123",
    budget_type="cost",
    spent=105.0,
    ceiling=100.0,
    policy="warn",
)
```

### 5. Approval Events
Emitted for human-in-the-loop workflow:

```python
from cuga.observability import ApprovalEvent

# Requested
request_event = ApprovalEvent.requested(
    trace_id="trace-123",
    action_description="Book flight for $450",
    risk_level="medium",
    timeout_seconds=300,
)

# Received
received_event = ApprovalEvent.received(
    trace_id="trace-123",
    approved=True,
    wait_time_ms=15000.0,
    reason="Approved by user",
)
```

## Golden Signals

### Success Rate
Percentage of successful requests:

```python
from cuga.observability import get_collector

metrics = get_collector().get_metrics()
print(f"Success rate: {metrics['success_rate']:.2f}%")
```

### Latency
Percentile latency tracking:

```python
metrics = get_collector().get_metrics()
latency = metrics['latency']['end_to_end']
print(f"P50: {latency['p50']:.2f}ms")
print(f"P95: {latency['p95']:.2f}ms")
print(f"P99: {latency['p99']:.2f}ms")
```

### Error Rate
Tool and request error rates:

```python
metrics = get_collector().get_metrics()
print(f"Tool error rate: {metrics['tool_error_rate']:.2f}%")
print(f"Request error rate: {metrics['error_rate']:.2f}%")
```

### Traffic
Request rate and throughput:

```python
metrics = get_collector().get_metrics()
print(f"Requests per second: {metrics['requests_per_second']:.2f}")
print(f"Total requests: {metrics['total_requests']}")
```

### Agent-Specific Metrics

**Mean Steps Per Task:**
```python
print(f"Avg steps: {metrics['mean_steps_per_task']:.1f}")
```

**Approval Wait Time:**
```python
approval = metrics['approval']
print(f"Approval wait P95: {approval['wait_time']['p95']:.2f}ms")
```

## Configuration

### Environment Variables

```bash
# OTEL Exporter Configuration
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_EXPORTER_OTLP_HEADERS="x-api-key=secret123"
export OTEL_SERVICE_NAME="cuga-agent"

# Exporter Type (otlp, jaeger, zipkin, console, none)
export OTEL_TRACES_EXPORTER="otlp"
export OTEL_METRICS_EXPORTER="otlp"

# Sampling (optional)
export OTEL_TRACES_SAMPLER="always_on"
export OTEL_TRACES_SAMPLER_ARG="1.0"
```

### Config File (configs/observability.yaml)

```yaml
observability:
  enabled: true
  auto_export: true
  buffer_size: 1000
  
  exporters:
    - type: otlp
      endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT:-http://localhost:4318}
      service_name: ${OTEL_SERVICE_NAME:-cuga-agent}
    
    - type: console
      pretty: false
  
  sampling:
    rate: 1.0  # 100% sampling
  
  redaction:
    enabled: true
    keys:
      - secret
      - token
      - password
      - api_key
```

## Integration

### Initialize in Agent

```python
from cuga.observability import ObservabilityCollector, OTELExporter

# Create collector with OTEL exporter
collector = ObservabilityCollector(
    exporters=[
        OTELExporter(
            endpoint="http://localhost:4318",
            service_name="cuga-agent",
        )
    ],
    auto_export=True,
)

# Set as global collector
from cuga.observability import set_collector
set_collector(collector)
```

### Emit Events in Planner

```python
from cuga.observability import PlanEvent, get_collector
import time

class PlannerAgent:
    def plan(self, goal: str, trace_id: str):
        start_time = time.time()
        
        # ... planning logic ...
        
        duration_ms = (time.time() - start_time) * 1000
        event = PlanEvent.create(
            trace_id=trace_id,
            goal=goal,
            steps_count=len(steps),
            tools_selected=[s.tool for s in steps],
            duration_ms=duration_ms,
        )
        get_collector().emit_event(event)
        
        return steps
```

### Emit Events in Tool Execution

```python
from cuga.observability import ToolCallEvent, get_collector
import time

def execute_tool(tool_name: str, params: dict, trace_id: str):
    # Start event
    start_event = ToolCallEvent.start(
        trace_id=trace_id,
        tool_name=tool_name,
        tool_params=params,
    )
    get_collector().emit_event(start_event)
    
    start_time = time.time()
    try:
        result = _call_tool(tool_name, params)
        duration_ms = (time.time() - start_time) * 1000
        
        # Complete event
        complete_event = ToolCallEvent.complete(
            trace_id=trace_id,
            tool_name=tool_name,
            duration_ms=duration_ms,
            result_size=len(str(result)),
        )
        get_collector().emit_event(complete_event)
        
        return result
    
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        
        # Error event
        error_event = ToolCallEvent.error(
            trace_id=trace_id,
            tool_name=tool_name,
            error_type=type(e).__name__,
            error_message=str(e),
            duration_ms=duration_ms,
        )
        get_collector().emit_event(error_event)
        raise
```

## Prometheus Metrics Endpoint

Expose metrics for Prometheus scraping:

```python
from fastapi import FastAPI
from cuga.observability import get_collector

app = FastAPI()

@app.get("/metrics")
def metrics():
    """Prometheus metrics endpoint."""
    return get_collector().get_prometheus_metrics()
```

Example output:
```
# HELP cuga_requests_total Total number of requests
# TYPE cuga_requests_total counter
cuga_requests_total 1250

# HELP cuga_success_rate Request success rate percentage
# TYPE cuga_success_rate gauge
cuga_success_rate 98.40

# HELP cuga_latency_ms End-to-end latency in milliseconds
# TYPE cuga_latency_ms summary
cuga_latency_ms{quantile="0.5"} 145.23
cuga_latency_ms{quantile="0.95"} 387.56
cuga_latency_ms{quantile="0.99"} 892.34
```

## Grafana Dashboard

### Import Dashboard

1. Copy `observability/grafana_dashboard.json`
2. In Grafana: **Dashboards** → **Import** → **Upload JSON file**
3. Select Prometheus datasource
4. Click **Import**

### Dashboard Panels

The dashboard includes:

1. **Success Rate Gauge** - Real-time success rate with thresholds
2. **Tool Error Rate Gauge** - Tool-specific error tracking
3. **Mean Steps Per Task** - Planning efficiency metric
4. **Budget Utilization** - Budget warnings and exceeded events
5. **Request Rate Graph** - Total, success, and failed requests over time
6. **End-to-End Latency** - P50, P95, P99 latency percentiles
7. **Tool Call Latency by Tool** - Per-tool latency tracking
8. **Approval Wait Time** - Human-in-the-loop latency
9. **Tool Errors by Type** - Error distribution pie chart
10. **Tool Errors by Tool** - Tool-specific error distribution
11. **Active Traces** - Current trace count
12. **Recent Events Timeline** - Structured event log stream

### Dashboard Screenshot

```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│ Success     │ Tool Error  │ Mean Steps  │ Budget      │
│ Rate: 98.4% │ Rate: 2.1%  │ Per Task: 4 │ Warnings: 5 │
│ 🟢 Gauge    │ 🟢 Gauge    │ 📊 Stat     │ 📊 Bar      │
└─────────────┴─────────────┴─────────────┴─────────────┘

┌─────────────────────────────┬─────────────────────────────┐
│ Request Rate                │ End-to-End Latency          │
│ 📈 Total, Success, Failed   │ 📈 P50, P95, P99            │
└─────────────────────────────┴─────────────────────────────┘

┌─────────────────────────────┬─────────────────────────────┐
│ Tool Call Latency by Tool   │ Approval Wait Time          │
│ 📈 P95 per tool             │ 📈 P50, P95, P99            │
└─────────────────────────────┴─────────────────────────────┘

┌────────────┬────────────┬────────────────────────────────┐
│ Errors by  │ Errors by  │ Active Traces                  │
│ Type       │ Tool       │ Count: 15                      │
│ 🥧 Pie     │ 🥧 Pie     │ 📊 Stat                        │
└────────────┴────────────┴────────────────────────────────┘

┌───────────────────────────────────────────────────────────┐
│ Recent Events Timeline                                    │
│ 📋 Structured event log stream with filtering            │
└───────────────────────────────────────────────────────────┘
```

## Testing

### Unit Tests

```python
import pytest
from cuga.observability import (
    ObservabilityCollector,
    PlanEvent,
    ToolCallEvent,
    ConsoleExporter,
)

def test_event_emission():
    collector = ObservabilityCollector(
        exporters=[ConsoleExporter(pretty=False)],
        auto_export=False,
    )
    
    event = PlanEvent.create(
        trace_id="test-123",
        goal="Test goal",
        steps_count=3,
        tools_selected=["tool1", "tool2"],
        duration_ms=100.0,
    )
    
    collector.emit_event(event)
    
    metrics = collector.get_metrics()
    assert metrics['mean_steps_per_task'] == 3.0
    assert len(collector._event_buffer) == 1

def test_golden_signals():
    collector = ObservabilityCollector()
    
    # Emit success event
    collector.signals.record_request_start()
    collector.signals.record_request_success(100.0)
    
    # Emit tool events
    collector.signals.record_tool_call_start("tool1")
    collector.signals.record_tool_call_complete("tool1", 50.0)
    
    metrics = collector.get_metrics()
    assert metrics['success_rate'] == 100.0
    assert metrics['tool_calls'] == 1
    assert metrics['total_requests'] == 1
```

### Integration Tests

```python
def test_otel_export():
    """Test OTEL export integration."""
    from cuga.observability import OTELExporter
    
    exporter = OTELExporter(
        endpoint="http://localhost:4318",
        enabled=True,
    )
    
    event = ToolCallEvent.start(
        trace_id="test-123",
        tool_name="test_tool",
        tool_params={"key": "value"},
    )
    
    exporter.export_event(event)
    # Verify span created in OTEL backend
```

## Best Practices

1. **Always emit events**: Don't skip event emission to maintain complete observability
2. **Use trace_id consistently**: Propagate trace_id through entire execution
3. **Redact sensitive data**: Events automatically redact secrets, but review params
4. **Set appropriate thresholds**: Configure Grafana alert thresholds for your SLOs
5. **Monitor golden signals**: Focus on success rate, latency, and error rate first
6. **Export to persistent storage**: Use OTEL with persistent backend (Jaeger, Zipkin)
7. **Flush on shutdown**: Always call `collector.shutdown()` to flush buffers

## Troubleshooting

### Events Not Appearing in OTEL Backend

1. Check exporter enabled: `OTEL_TRACES_EXPORTER=otlp`
2. Verify endpoint reachable: `curl http://localhost:4318/v1/traces`
3. Check exporter logs: Look for connection errors
4. Test with console exporter: `OTEL_TRACES_EXPORTER=console`

### Metrics Not Updating

1. Verify collector initialized: `get_collector()` should not fail
2. Check event emission: Events should trigger signal updates
3. Call `collector.export_metrics()` to force export
4. Verify Prometheus scraping `/metrics` endpoint

### High Memory Usage

1. Reduce buffer size: `buffer_size=100` in collector config
2. Enable auto-export: `auto_export=True` to flush immediately
3. Increase flush frequency: Call `collector.flush()` periodically
4. Check for event accumulation: Monitor `len(collector._event_buffer)`

## See Also

- [AGENTS.md](../AGENTS.md) - Agent guardrails and contracts
- [docs/orchestrator/ORCHESTRATOR_CONTRACT.md](../docs/orchestrator/ORCHESTRATOR_CONTRACT.md) - Orchestrator protocol
- [docs/orchestrator/EXECUTION_CONTEXT.md](../docs/orchestrator/EXECUTION_CONTEXT.md) - Execution context
- [configs/observability.yaml](../configs/observability.yaml) - Configuration file

# Observability

Comprehensive observability for CUGAR agent system with structured events, golden signals, and OTEL integration.

## Quick Start

```python
from cuga.observability import ObservabilityCollector, OTELExporter, PlanEvent

# Initialize with OTEL exporter
collector = ObservabilityCollector(
    exporters=[OTELExporter(endpoint="http://localhost:4318")]
)

# Emit events
event = PlanEvent.create(
    trace_id="trace-123",
    goal="Find flights",
    steps_count=3,
    tools_selected=["search", "filter"],
    duration_ms=150.0,
)
collector.emit_event(event)

# Get metrics
metrics = collector.get_metrics()
print(f"Success rate: {metrics['success_rate']:.2f}%")
```

## Features

- **Structured Events**: Per-step emission (plan, route, tool_call, budget, approval)
- **Golden Signals**: Success rate, latency, traffic, errors
- **Agent Metrics**: Steps/task, tool errors, approval wait times
- **OTEL Export**: Native OpenTelemetry with OTLP, Jaeger, Zipkin
- **Grafana Dashboard**: Pre-built monitoring dashboard

## Event Types

### Plan Events
Emitted when planning completes with step count and selected tools.

### Route Events
Emitted when routing decision is made with alternatives and reasoning.

### Tool Call Events
Emitted for tool start, complete, and error with timing and results.

### Budget Events
Emitted for budget warnings and exceeded thresholds.

### Approval Events
Emitted for human-in-the-loop approval requests and decisions.

## Golden Signals

- **Success Rate**: % of successful executions
- **Latency**: P50/P95/P99 end-to-end and per-tool
- **Tool Error Rate**: % of failed tool calls
- **Mean Steps Per Task**: Average planning complexity
- **Approval Wait Time**: Human decision latency

## Configuration

Environment variables:
```bash
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_SERVICE_NAME="cuga-agent"
export OTEL_TRACES_EXPORTER="otlp"
```

Config file (`configs/observability.yaml`):
```yaml
observability:
  enabled: true
  auto_export: true
  exporters:
    otlp:
      enabled: true
      endpoint: http://localhost:4318
```

## Grafana Dashboard

Import `observability/grafana_dashboard.json` to Grafana for instant monitoring with:
- Success rate gauge
- Latency percentiles
- Tool error tracking
- Budget utilization
- Event timeline

## Documentation

See [docs/observability/OBSERVABILITY_SLOS.md](../docs/observability/OBSERVABILITY_SLOS.md) for:
- Complete API reference
- Integration examples
- Best practices
- Troubleshooting guide

## Examples

Run the example:
```bash
python examples/observability_example.py
```

See [examples/observability_example.py](../examples/observability_example.py) for complete integration demo.

## Testing

Run tests:
```bash
pytest tests/observability/test_observability.py -v
```

## Prometheus Metrics

Expose metrics endpoint:
```python
from fastapi import FastAPI
from cuga.observability import get_collector

app = FastAPI()

@app.get("/metrics")
def metrics():
    return get_collector().get_prometheus_metrics()
```

Metrics include:
- `cuga_requests_total`: Total requests
- `cuga_success_rate`: Success rate percentage
- `cuga_latency_ms`: Latency histogram
- `cuga_tool_error_rate`: Tool error percentage
- `cuga_approval_wait_ms`: Approval wait time

## Architecture

```
Agent → Events → Collector → Golden Signals → Exporters → Backends
                     ↓                              ↓
                  Buffer                      OTEL/Console
```

All events are PII-safe with automatic redaction of secrets, tokens, and credentials.


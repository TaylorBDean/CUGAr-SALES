# Observability Integration Checklist

Quick checklist for integrating observability into CUGAR agent components.

## Prerequisites

✅ All observability modules in `src/cuga/observability/`  
✅ Configuration file `configs/observability.yaml`  
✅ OTEL collector running (optional, use console exporter for dev)

## Step 1: Initialize Collector (One-time Setup)

### In Main Entry Point (e.g., `src/cuga/cli.py` or `main.py`)

```python
from cuga.observability import ObservabilityCollector, OTELExporter, set_collector
import os

# Initialize collector at startup
def init_observability():
    collector = ObservabilityCollector(
        exporters=[
            OTELExporter(
                endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"),
                service_name=os.getenv("OTEL_SERVICE_NAME", "cuga-agent"),
            )
        ],
        auto_export=True,
    )
    set_collector(collector)
    return collector

# At startup
collector = init_observability()

# At shutdown
import atexit
atexit.register(collector.shutdown)
```

**Status**: [ ] Done

---

## Step 2: Emit Plan Events

### In `src/cuga/planner/core.py` (PlannerAgent.plan)

```python
from cuga.observability import PlanEvent, emit_event
import time

class PlannerAgent:
    def plan(self, goal: str, metadata: dict) -> List[Step]:
        trace_id = metadata.get("trace_id") or str(uuid.uuid4())
        
        # Start timing
        start_time = time.time()
        
        # ... existing planning logic ...
        steps = self._create_plan(goal)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Emit plan event
        event = PlanEvent.create(
            trace_id=trace_id,
            goal=goal[:200],  # Truncate for safety
            steps_count=len(steps),
            tools_selected=[step.tool for step in steps],
            duration_ms=duration_ms,
        )
        emit_event(event)
        
        return steps
```

**Files to modify**:
- [ ] `src/cuga/planner/core.py`

**Verification**:
```python
# Check event emitted
from cuga.observability import get_collector
metrics = get_collector().get_metrics()
assert metrics['mean_steps_per_task'] > 0
```

---

## Step 3: Emit Route Events

### In `src/cuga/orchestrator/routing.py` (RoutingAuthority)

```python
from cuga.observability import RouteEvent, emit_event
import time

class RoutingAuthority:
    def route(self, context: ExecutionContext, ...) -> Agent:
        start_time = time.time()
        
        # ... existing routing logic ...
        selected_agent = self._select_agent(...)
        alternatives = self._get_alternatives(...)
        
        duration_ms = (time.time() - start_time) * 1000
        
        # Emit route event
        event = RouteEvent.create(
            trace_id=context.trace_id,
            agent_selected=selected_agent.name,
            routing_policy=self.policy.name,
            alternatives_considered=[a.name for a in alternatives],
            reasoning=self._get_reasoning(),
        )
        emit_event(event)
        
        return selected_agent
```

**Files to modify**:
- [ ] `src/cuga/orchestrator/routing.py`

**Verification**:
```python
# Check routing latency tracked
metrics = get_collector().get_metrics()
assert 'routing' in metrics['latency']
```

---

## Step 4: Emit Tool Call Events

### In `src/cuga/workers/core.py` (WorkerAgent.execute_step)

```python
from cuga.observability import ToolCallEvent, emit_event
import time

class WorkerAgent:
    def execute_step(self, step: Step, context: dict) -> Any:
        trace_id = context.get("trace_id", "")
        
        # Emit start event
        start_event = ToolCallEvent.start(
            trace_id=trace_id,
            tool_name=step.tool,
            tool_params=step.params,
        )
        emit_event(start_event)
        
        start_time = time.time()
        
        try:
            # Execute tool
            result = self._execute_tool(step.tool, step.params)
            
            duration_ms = (time.time() - start_time) * 1000
            
            # Emit complete event
            complete_event = ToolCallEvent.complete(
                trace_id=trace_id,
                tool_name=step.tool,
                duration_ms=duration_ms,
                result_size=len(str(result)),
            )
            emit_event(complete_event)
            
            return result
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            
            # Emit error event
            error_event = ToolCallEvent.error(
                trace_id=trace_id,
                tool_name=step.tool,
                error_type=type(e).__name__,
                error_message=str(e)[:500],
                duration_ms=duration_ms,
            )
            emit_event(error_event)
            
            raise
```

**Files to modify**:
- [ ] `src/cuga/workers/core.py`

**Verification**:
```python
# Check tool metrics
metrics = get_collector().get_metrics()
assert metrics['tool_calls'] > 0
assert 'tools' in metrics['latency']
```

---

## Step 5: Emit Budget Events

### In Budget Enforcer (e.g., `src/cuga/backend/app.py`)

```python
from cuga.observability import BudgetEvent, emit_event

async def budget_guard(request, call_next):
    trace_id = request.headers.get("X-Trace-ID", "")
    ceiling = int(os.environ.get("AGENT_BUDGET_CEILING", "100"))
    spent = int(request.headers.get("X-Budget-Spent", "0"))
    
    # Check if approaching limit (80% threshold)
    if spent > ceiling * 0.8 and spent <= ceiling:
        event = BudgetEvent.warning(
            trace_id=trace_id,
            budget_type="cost",
            spent=float(spent),
            ceiling=float(ceiling),
            threshold=ceiling * 0.8,
        )
        emit_event(event)
    
    # Check if exceeded
    if spent > ceiling:
        event = BudgetEvent.exceeded(
            trace_id=trace_id,
            budget_type="cost",
            spent=float(spent),
            ceiling=float(ceiling),
            policy="block",
        )
        emit_event(event)
        
        return JSONResponse(
            status_code=429,
            content={"detail": "budget exceeded"}
        )
    
    return await call_next(request)
```

**Files to modify**:
- [ ] `src/cuga/backend/app.py` (or wherever budget enforcement lives)

**Verification**:
```python
# Check budget tracking
metrics = get_collector().get_metrics()
assert 'budget' in metrics
```

---

## Step 6: Emit Approval Events (If Applicable)

### In Approval Workflow Handler

```python
from cuga.observability import ApprovalEvent, emit_event
import time
import asyncio

async def request_approval(action: str, risk_level: str, trace_id: str) -> bool:
    # Emit request event
    request_event = ApprovalEvent.requested(
        trace_id=trace_id,
        action_description=action,
        risk_level=risk_level,
        timeout_seconds=300,
    )
    emit_event(request_event)
    
    start_time = time.time()
    
    try:
        # Wait for approval
        approved = await asyncio.wait_for(
            wait_for_human_approval(),
            timeout=300.0
        )
        
        wait_time_ms = (time.time() - start_time) * 1000
        
        # Emit received event
        received_event = ApprovalEvent.received(
            trace_id=trace_id,
            approved=approved,
            wait_time_ms=wait_time_ms,
            reason="User decision",
        )
        emit_event(received_event)
        
        return approved
        
    except asyncio.TimeoutError:
        wait_time_ms = (time.time() - start_time) * 1000
        
        # Emit timeout event
        timeout_event = ApprovalEvent.timeout(
            trace_id=trace_id,
            wait_time_ms=wait_time_ms,
            default_action="deny",
        )
        emit_event(timeout_event)
        
        return False
```

**Files to modify**:
- [ ] Approval workflow handler (if exists)

**Verification**:
```python
# Check approval metrics
metrics = get_collector().get_metrics()
if metrics['approval']['requests'] > 0:
    print(f"Approval wait P95: {metrics['approval']['wait_time']['p95']:.2f}ms")
```

---

## Step 7: Add Prometheus Metrics Endpoint

### In FastAPI App (e.g., `src/cuga/backend/server/main.py`)

```python
from fastapi import FastAPI
from cuga.observability import get_collector

app = FastAPI()

@app.get("/metrics", response_class=PlainTextResponse)
def prometheus_metrics():
    """Prometheus metrics endpoint."""
    return get_collector().get_prometheus_metrics()

@app.get("/health/observability")
def observability_health():
    """Observability health check."""
    metrics = get_collector().get_metrics()
    return {
        "status": "healthy",
        "total_events": metrics['total_requests'],
        "success_rate": metrics['success_rate'],
        "buffer_size": len(get_collector()._event_buffer),
    }
```

**Files to modify**:
- [ ] `src/cuga/backend/server/main.py`

**Verification**:
```bash
curl http://localhost:8000/metrics
curl http://localhost:8000/health/observability
```

---

## Step 8: Configure OTEL Backend (Optional)

### Docker Compose for OTEL Collector + Jaeger

Create `docker-compose.observability.yml`:

```yaml
version: '3.8'

services:
  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # Jaeger UI
      - "4317:4317"    # OTLP gRPC
      - "4318:4318"    # OTLP HTTP
    environment:
      - COLLECTOR_OTLP_ENABLED=true

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
    volumes:
      - ./observability/grafana_dashboard.json:/var/lib/grafana/dashboards/cuga.json
```

**Start services**:
```bash
docker-compose -f docker-compose.observability.yml up -d
```

**Access**:
- Jaeger UI: http://localhost:16686
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000

**Status**: [ ] Done

---

## Step 9: Import Grafana Dashboard

1. Open Grafana: http://localhost:3000
2. Go to **Dashboards** → **Import**
3. Upload `observability/grafana_dashboard.json`
4. Select Prometheus datasource
5. Click **Import**

**Status**: [ ] Done

---

## Step 10: Verify Integration

### Run Example
```bash
python examples/observability_example.py
```

### Check Metrics
```python
from cuga.observability import get_collector

metrics = get_collector().get_metrics()
print(f"Success rate: {metrics['success_rate']:.2f}%")
print(f"Total requests: {metrics['total_requests']}")
print(f"Tool calls: {metrics['tool_calls']}")
print(f"Mean steps: {metrics['mean_steps_per_task']:.1f}")
```

### Check Prometheus Endpoint
```bash
curl http://localhost:8000/metrics | grep cuga_
```

### Check Jaeger Traces
- Open http://localhost:16686
- Search for service: `cuga-agent`
- Verify traces appearing

### Check Grafana Dashboard
- Open http://localhost:3000
- Navigate to imported dashboard
- Verify panels populating with data

**Status**: [ ] Done

---

## Troubleshooting

### Events not appearing
```python
# Check collector initialized
from cuga.observability import get_collector
collector = get_collector()
print(f"Exporters: {len(collector.exporters)}")
print(f"Auto-export: {collector.auto_export}")
```

### OTEL connection issues
```bash
# Test OTEL endpoint
curl http://localhost:4318/v1/traces

# Use console exporter for debugging
export OTEL_TRACES_EXPORTER=console
```

### No metrics in Prometheus
```bash
# Check metrics endpoint
curl http://localhost:8000/metrics

# Verify Prometheus scraping config
docker logs prometheus | grep cuga
```

---

## Final Checklist

- [ ] Collector initialized at startup
- [ ] Plan events emitting from planner
- [ ] Route events emitting from routing
- [ ] Tool call events (start/complete/error)
- [ ] Budget events (warning/exceeded)
- [ ] Approval events (if applicable)
- [ ] Prometheus `/metrics` endpoint exposed
- [ ] OTEL backend configured (optional)
- [ ] Grafana dashboard imported
- [ ] Example script runs successfully
- [ ] Metrics visible in Grafana
- [ ] Traces visible in Jaeger (if configured)

---

## Environment Setup

Required environment variables:

```bash
# Observability
export OBSERVABILITY_ENABLED=true

# OTEL Configuration
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_SERVICE_NAME="cuga-agent"
export OTEL_TRACES_EXPORTER="otlp"  # or "console" for debugging

# Optional: Custom headers
export OTEL_EXPORTER_OTLP_HEADERS="x-api-key=your-key"
```

---

## Quick Reference

**Emit event**: `from cuga.observability import emit_event; emit_event(event)`  
**Get metrics**: `from cuga.observability import get_collector; get_collector().get_metrics()`  
**Prometheus export**: `get_collector().get_prometheus_metrics()`  
**Flush events**: `get_collector().flush()`  
**Shutdown**: `get_collector().shutdown()`

---

## Documentation

- Full reference: `docs/observability/OBSERVABILITY_SLOS.md`
- Quick reference: `docs/observability/QUICK_REFERENCE.md`
- Implementation summary: `docs/observability/IMPLEMENTATION_SUMMARY.md`
- Example: `examples/observability_example.py`
- Tests: `tests/observability/test_observability.py`

---

**Next**: Start with Step 1 (Initialize Collector), then progressively add event emission to each component. Test each step before moving to the next.

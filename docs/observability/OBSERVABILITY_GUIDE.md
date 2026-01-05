# Observability and Debugging Guide

**Status**: Canonical Reference  
**Last Updated**: 2025-12-31  
**Audience**: DevOps engineers, SREs, enterprise integrators, troubleshooters

---

## 📋 Overview

This guide provides comprehensive observability and debugging patterns for CUGAR agent systems. Learn how to instrument, monitor, and troubleshoot agent execution with structured logging, distributed tracing, metrics, and error introspection.

### What This Guide Covers

✅ **Structured Logging** - JSON logs with trace context, PII redaction, log levels  
✅ **Distributed Tracing** - OpenTelemetry, LangFuse, LangSmith integration  
✅ **Metrics Collection** - Performance metrics, error rates, resource usage  
✅ **Error Introspection** - Failure taxonomy, stack traces, recovery suggestions  
✅ **Replayable Traces** - Capture and replay execution for debugging  
✅ **Dashboard Setup** - Pre-built Grafana/LangFuse dashboards  
✅ **Troubleshooting Playbooks** - Common issues and solutions

---

## 🎯 Quick Start

### Minimal Observability Setup

```python
# Enable structured logging
import logging
from cuga.observability import configure_logging

configure_logging(
    level=logging.INFO,
    format="json",
    output="stdout",
    redact_secrets=True
)

# Enable OpenTelemetry tracing
from cuga.observability import configure_tracing

configure_tracing(
    service_name="cuga-agent",
    exporter="otlp",
    endpoint="http://localhost:4317",
    sample_rate=1.0  # 100% sampling for development
)

# Run agent with trace context
from cuga.orchestrator import ExecutionContext

context = ExecutionContext(
    trace_id="customer-onboard-001",
    user_id="sales-rep-123",
    profile="production"
)

async for event in orchestrator.orchestrate(goal, context):
    # Events automatically include trace context
    print(event)
```

### Environment Variables

```bash
# Structured Logging
export CUGA_LOG_LEVEL=INFO                  # DEBUG, INFO, WARNING, ERROR, CRITICAL
export CUGA_LOG_FORMAT=json                 # json, text, structured
export CUGA_LOG_OUTPUT=stdout               # stdout, file, both
export CUGA_LOG_FILE=/var/log/cuga/app.log # Log file path
export CUGA_LOG_REDACT_SECRETS=true         # Redact sensitive data

# OpenTelemetry
export OTEL_SERVICE_NAME=cuga-agent
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_TRACES_SAMPLER=parentbased_traceidratio
export OTEL_TRACES_SAMPLER_ARG=1.0          # Sample rate (0.0-1.0)

# LangFuse (LLM observability)
export LANGFUSE_PUBLIC_KEY=pk-xxx
export LANGFUSE_SECRET_KEY=sk-xxx
export LANGFUSE_HOST=https://cloud.langfuse.com

# LangSmith (alternative)
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=ls_xxx
export LANGCHAIN_PROJECT=cuga-production

# OpenInference (Phoenix)
export PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006
```

---

## 📝 Structured Logging

### Log Format

All logs follow a structured JSON format with required fields:

```json
{
  "timestamp": "2025-12-31T12:00:00.123Z",
  "level": "INFO",
  "service": "cuga-agent",
  "trace_id": "customer-onboard-001",
  "span_id": "span-abc123",
  "user_id": "sales-rep-123",
  "profile": "production",
  "component": "CoordinatorAgent",
  "event": "step_execution",
  "message": "Executing step: create_crm_account",
  "duration_ms": 1234,
  "metadata": {
    "step_index": 2,
    "worker": "worker-1",
    "tool": "create_crm_account"
  },
  "error": null
}
```

### Required Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `timestamp` | ISO 8601 | Event timestamp (UTC) | `2025-12-31T12:00:00.123Z` |
| `level` | string | Log level | `INFO`, `WARNING`, `ERROR` |
| `service` | string | Service name | `cuga-agent` |
| `trace_id` | string | Distributed trace ID | `customer-onboard-001` |
| `span_id` | string | Current span ID | `span-abc123` |
| `user_id` | string | User/actor ID | `sales-rep-123` |
| `profile` | string | Execution profile | `production` |
| `component` | string | Component emitting log | `CoordinatorAgent` |
| `event` | string | Event type | `step_execution` |
| `message` | string | Human-readable message | `Executing step: ...` |

### Optional Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `duration_ms` | number | Operation duration | `1234` |
| `metadata` | object | Additional context | `{"step_index": 2}` |
| `error` | object | Error details | `{"type": "TimeoutError"}` |
| `request_id` | string | Request identifier | `req-456` |
| `conversation_id` | string | Conversation thread | `conv-789` |
| `session_id` | string | User session | `sess-012` |

### Implementation

```python
# src/cuga/observability/logging.py
import logging
import json
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar

# Context variables for trace propagation
trace_context: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
span_context: ContextVar[Optional[str]] = ContextVar("span_id", default=None)
user_context: ContextVar[Optional[str]] = ContextVar("user_id", default=None)

class StructuredLogger:
    """
    Structured JSON logger with trace context and PII redaction.
    
    Features:
    - Automatic trace_id/span_id propagation from context vars
    - PII redaction (secrets, tokens, passwords)
    - Standardized field names across all components
    - Configurable output (stdout, file, both)
    """
    
    def __init__(
        self,
        component: str,
        level: int = logging.INFO,
        redact_secrets: bool = True,
        output: str = "stdout",
        log_file: Optional[str] = None,
    ):
        self.component = component
        self.logger = logging.getLogger(component)
        self.logger.setLevel(level)
        self.redact_secrets = redact_secrets
        
        # Configure handlers
        if output in ["stdout", "both"]:
            self._add_stdout_handler()
        if output in ["file", "both"] and log_file:
            self._add_file_handler(log_file)
    
    def _add_stdout_handler(self):
        """Add stdout handler with JSON formatting."""
        handler = logging.StreamHandler()
        handler.setFormatter(self._json_formatter())
        self.logger.addHandler(handler)
    
    def _add_file_handler(self, log_file: str):
        """Add file handler with JSON formatting."""
        handler = logging.FileHandler(log_file)
        handler.setFormatter(self._json_formatter())
        self.logger.addHandler(handler)
    
    def _json_formatter(self):
        """Create JSON formatter."""
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_data = {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "level": record.levelname,
                    "service": "cuga-agent",
                    "component": record.name,
                    "message": record.getMessage(),
                }
                
                # Add trace context if available
                if trace_id := trace_context.get():
                    log_data["trace_id"] = trace_id
                if span_id := span_context.get():
                    log_data["span_id"] = span_id
                if user_id := user_context.get():
                    log_data["user_id"] = user_id
                
                # Add extra fields from record
                for key in ["event", "duration_ms", "metadata", "error", 
                           "profile", "request_id", "conversation_id", "session_id"]:
                    if hasattr(record, key):
                        log_data[key] = getattr(record, key)
                
                return json.dumps(log_data)
        
        return JSONFormatter()
    
    def info(self, message: str, **kwargs):
        """Log info message with structured fields."""
        extra = self._prepare_extra(kwargs)
        self.logger.info(message, extra=extra)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with structured fields."""
        extra = self._prepare_extra(kwargs)
        self.logger.warning(message, extra=extra)
    
    def error(self, message: str, **kwargs):
        """Log error message with structured fields."""
        extra = self._prepare_extra(kwargs)
        self.logger.error(message, extra=extra)
    
    def _prepare_extra(self, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare extra fields with PII redaction."""
        if self.redact_secrets:
            kwargs = self._redact_sensitive_data(kwargs)
        return kwargs
    
    def _redact_sensitive_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive data from logs."""
        sensitive_keys = {"secret", "token", "password", "api_key", "credential"}
        
        def redact_dict(d):
            if not isinstance(d, dict):
                return d
            
            return {
                k: "[REDACTED]" if k.lower() in sensitive_keys else redact_dict(v)
                for k, v in d.items()
            }
        
        return redact_dict(data)


# Usage in components
logger = StructuredLogger(component="CoordinatorAgent")

logger.info(
    "Executing step",
    event="step_execution",
    metadata={
        "step_index": 2,
        "worker": "worker-1",
        "tool": "create_crm_account"
    }
)
```

### Log Levels

| Level | When to Use | Examples |
|-------|-------------|----------|
| **DEBUG** | Detailed diagnostic info | Variable values, function entry/exit, internal state |
| **INFO** | Normal operations | Step execution, routing decisions, successful operations |
| **WARNING** | Potentially harmful situations | Retry attempts, fallback routing, non-critical failures |
| **ERROR** | Error events | Failed operations, exceptions, validation errors |
| **CRITICAL** | Severe errors causing failure | System crashes, data corruption, security breaches |

### Examples by Component

#### PlannerAgent Logs

```json
// Planning started
{
  "level": "INFO",
  "component": "PlannerAgent",
  "event": "planning_started",
  "message": "Starting plan creation",
  "trace_id": "trace-001",
  "metadata": {
    "goal": "Onboard customer: Acme Corp",
    "tools_available": 15
  }
}

// Tool selection
{
  "level": "INFO",
  "component": "PlannerAgent",
  "event": "tool_selected",
  "message": "Selected tool: create_crm_account",
  "trace_id": "trace-001",
  "metadata": {
    "tool": "create_crm_account",
    "score": 0.95,
    "rank": 1,
    "reason": "High similarity to goal"
  }
}

// Planning complete
{
  "level": "INFO",
  "component": "PlannerAgent",
  "event": "planning_complete",
  "message": "Plan created with 5 steps",
  "trace_id": "trace-001",
  "duration_ms": 234,
  "metadata": {
    "steps": ["validate_data", "create_crm", "create_billing", "approval", "send_email"],
    "estimated_duration_ms": 5000
  }
}
```

#### CoordinatorAgent Logs

```json
// Routing decision
{
  "level": "INFO",
  "component": "CoordinatorAgent",
  "event": "routing_decision",
  "message": "Routing task to worker-1",
  "trace_id": "trace-001",
  "metadata": {
    "task": "create_crm_account",
    "target": "worker-1",
    "reason": "round-robin selection",
    "fallback": "worker-2"
  }
}

// Step execution
{
  "level": "INFO",
  "component": "CoordinatorAgent",
  "event": "step_execution_started",
  "message": "Executing step: create_crm_account",
  "trace_id": "trace-001",
  "metadata": {
    "step_index": 2,
    "total_steps": 5,
    "worker": "worker-1"
  }
}

// Step complete
{
  "level": "INFO",
  "component": "CoordinatorAgent",
  "event": "step_execution_complete",
  "message": "Step completed: create_crm_account",
  "trace_id": "trace-001",
  "duration_ms": 1234,
  "metadata": {
    "step_index": 2,
    "result": {"account_id": "crm-123"}
  }
}
```

#### WorkerAgent Logs

```json
// Tool execution
{
  "level": "INFO",
  "component": "WorkerAgent",
  "event": "tool_execution",
  "message": "Executing tool: create_crm_account",
  "trace_id": "trace-001",
  "metadata": {
    "tool": "create_crm_account",
    "inputs": {"company": "Acme Corp"},
    "sandbox": "py-slim",
    "budget_remaining": 95
  }
}

// Tool success
{
  "level": "INFO",
  "component": "WorkerAgent",
  "event": "tool_success",
  "message": "Tool execution successful",
  "trace_id": "trace-001",
  "duration_ms": 1100,
  "metadata": {
    "tool": "create_crm_account",
    "result": {"account_id": "crm-123"}
  }
}

// Tool failure
{
  "level": "ERROR",
  "component": "WorkerAgent",
  "event": "tool_failure",
  "message": "Tool execution failed",
  "trace_id": "trace-001",
  "error": {
    "type": "TimeoutError",
    "message": "CRM API timeout after 30s",
    "retryable": true,
    "failure_mode": "SYSTEM_TIMEOUT"
  },
  "metadata": {
    "tool": "create_crm_account",
    "attempt": 1,
    "max_attempts": 3
  }
}
```

---

## 🔍 Distributed Tracing

### Trace Architecture

```
User Request
    │
    ├─ trace_id: "customer-onboard-001"
    │
    ▼
┌────────────────────────────────────────────────┐
│ Span: orchestrate                              │
│ ├─ duration: 5234ms                            │
│ ├─ status: success                             │
│ └─ attributes: {goal, profile}                 │
│     │                                           │
│     ├─ Span: planning                          │
│     │  ├─ duration: 234ms                      │
│     │  └─ attributes: {tools_selected: 5}      │
│     │                                           │
│     ├─ Span: routing                           │
│     │  ├─ duration: 5ms                        │
│     │  └─ attributes: {target: "worker-1"}     │
│     │                                           │
│     ├─ Span: step_execution (create_crm)       │
│     │  ├─ duration: 1234ms                     │
│     │  ├─ attributes: {tool, worker, result}   │
│     │  │                                        │
│     │  └─ Span: external_api_call (CRM)        │
│     │     ├─ duration: 1100ms                  │
│     │     └─ attributes: {endpoint, status}    │
│     │                                           │
│     ├─ Span: step_execution (create_billing)   │
│     │  └─ ...                                  │
│     │                                           │
│     └─ Span: aggregation                       │
│        ├─ duration: 10ms                       │
│        └─ attributes: {steps_completed: 5}     │
└────────────────────────────────────────────────┘
```

### OpenTelemetry Integration

```python
# src/cuga/observability/tracing.py
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from typing import Optional, Dict, Any

def configure_tracing(
    service_name: str = "cuga-agent",
    exporter: str = "otlp",
    endpoint: str = "http://localhost:4317",
    sample_rate: float = 1.0,
) -> trace.Tracer:
    """
    Configure OpenTelemetry distributed tracing.
    
    Args:
        service_name: Service name for traces
        exporter: Exporter type (otlp, jaeger, zipkin)
        endpoint: Exporter endpoint
        sample_rate: Sampling rate (0.0-1.0)
    
    Returns:
        Configured tracer instance
    """
    # Create resource
    resource = Resource.create({
        "service.name": service_name,
        "service.version": "1.0.0",
    })
    
    # Create tracer provider
    provider = TracerProvider(resource=resource)
    
    # Configure exporter
    if exporter == "otlp":
        span_exporter = OTLPSpanExporter(endpoint=endpoint)
    else:
        raise ValueError(f"Unsupported exporter: {exporter}")
    
    # Add span processor
    processor = BatchSpanProcessor(span_exporter)
    provider.add_span_processor(processor)
    
    # Set global tracer provider
    trace.set_tracer_provider(provider)
    
    return trace.get_tracer(__name__)


# Usage in orchestrator
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

class TracedOrchestrator(OrchestratorProtocol):
    async def orchestrate(self, goal, context, *, error_strategy):
        with tracer.start_as_current_span(
            "orchestrate",
            attributes={
                "goal": goal,
                "trace_id": context.trace_id,
                "profile": context.profile,
            }
        ) as span:
            try:
                # PLANNING
                with tracer.start_as_current_span("planning") as plan_span:
                    plan = await self.planner.plan(goal, context)
                    plan_span.set_attribute("tools_selected", len(plan.steps))
                
                # EXECUTION
                for step in plan.steps:
                    with tracer.start_as_current_span(
                        f"step_execution",
                        attributes={
                            "tool": step.tool,
                            "step_index": step.index,
                        }
                    ) as step_span:
                        result = await self.worker.execute(step, context)
                        step_span.set_attribute("result", str(result))
                
                span.set_status(trace.Status(trace.StatusCode.OK))
                
            except Exception as err:
                span.set_status(trace.Status(
                    trace.StatusCode.ERROR,
                    description=str(err)
                ))
                span.record_exception(err)
                raise
```

### Trace Context Propagation

```python
# Propagate trace context across components
from contextvars import ContextVar
from cuga.observability.logging import trace_context, span_context

def propagate_trace(context: ExecutionContext):
    """Set trace context for current execution."""
    trace_context.set(context.trace_id)
    if context.request_id:
        # Store request_id in context var if needed
        pass

# In orchestrator
async def orchestrate(self, goal, context, **kwargs):
    propagate_trace(context)
    
    # All subsequent logs and spans will include trace_id
    logger.info("Starting orchestration")
    
    # ... orchestration logic ...
```

### LangFuse Integration

```python
# src/cuga/observability/langfuse_integration.py
from langfuse import Langfuse
from typing import Optional

class LangFuseTracer:
    """
    LangFuse integration for LLM observability.
    
    Tracks:
    - LLM calls (model, prompt, completion, tokens, cost)
    - Agent spans (planning, execution, tools)
    - User feedback and evaluations
    """
    
    def __init__(self, public_key: str, secret_key: str, host: str):
        self.client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host
        )
    
    def trace_orchestration(self, context: ExecutionContext):
        """Create top-level trace for orchestration."""
        return self.client.trace(
            name="orchestration",
            id=context.trace_id,
            user_id=context.user_id,
            session_id=context.session_id,
            metadata={
                "profile": context.profile,
                "request_id": context.request_id,
            }
        )
    
    def trace_llm_call(
        self,
        trace_id: str,
        model: str,
        prompt: str,
        completion: str,
        tokens: int,
        duration_ms: int,
    ):
        """Track LLM call."""
        self.client.generation(
            trace_id=trace_id,
            name="llm_call",
            model=model,
            input=prompt,
            output=completion,
            usage={
                "input_tokens": tokens,
                "output_tokens": len(completion.split()),
                "total_tokens": tokens + len(completion.split()),
            },
            metadata={
                "duration_ms": duration_ms,
            }
        )


# Usage
langfuse = LangFuseTracer(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=os.getenv("LANGFUSE_HOST")
)

trace = langfuse.trace_orchestration(context)

# Track LLM call
langfuse.trace_llm_call(
    trace_id=context.trace_id,
    model="gpt-4",
    prompt="Plan steps for: onboard customer",
    completion="1. Validate data\n2. Create CRM account\n...",
    tokens=100,
    duration_ms=500
)
```

---

## 📊 Metrics Collection

### Key Metrics

#### Orchestration Metrics

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `orchestration_duration_ms` | Histogram | Total orchestration duration | `profile`, `status` |
| `orchestration_total` | Counter | Total orchestrations | `profile`, `status` |
| `orchestration_errors` | Counter | Orchestration errors | `profile`, `error_type` |
| `steps_executed` | Counter | Steps executed | `profile`, `tool` |
| `step_duration_ms` | Histogram | Step execution duration | `profile`, `tool` |

#### Agent Metrics

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `planning_duration_ms` | Histogram | Planning duration | `profile` |
| `tools_selected` | Histogram | Tools selected per plan | `profile` |
| `routing_duration_ms` | Histogram | Routing decision duration | `profile`, `policy` |
| `worker_utilization` | Gauge | Worker utilization % | `worker_id` |

#### Tool Metrics

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `tool_execution_duration_ms` | Histogram | Tool execution duration | `tool`, `status` |
| `tool_execution_total` | Counter | Total tool executions | `tool`, `status` |
| `tool_errors` | Counter | Tool errors | `tool`, `error_type` |
| `tool_retries` | Counter | Tool retry attempts | `tool` |

#### Resource Metrics

| Metric | Type | Description | Labels |
|--------|------|-------------|--------|
| `memory_usage_bytes` | Gauge | Memory usage | `profile` |
| `budget_spent` | Counter | Budget spent | `profile`, `user_id` |
| `budget_remaining` | Gauge | Budget remaining | `profile`, `user_id` |

### Prometheus Integration

```python
# src/cuga/observability/metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server
from typing import Dict, Any

# Define metrics
orchestration_duration = Histogram(
    "orchestration_duration_ms",
    "Orchestration duration in milliseconds",
    ["profile", "status"]
)

orchestration_total = Counter(
    "orchestration_total",
    "Total orchestrations",
    ["profile", "status"]
)

step_duration = Histogram(
    "step_duration_ms",
    "Step execution duration in milliseconds",
    ["profile", "tool"]
)

tool_errors = Counter(
    "tool_errors",
    "Tool execution errors",
    ["tool", "error_type"]
)

budget_spent = Counter(
    "budget_spent",
    "Budget spent",
    ["profile", "user_id"]
)

# Usage in orchestrator
class MetricsOrchestrator(OrchestratorProtocol):
    async def orchestrate(self, goal, context, **kwargs):
        start_time = time.time()
        status = "success"
        
        try:
            # ... orchestration logic ...
            
            for step in plan.steps:
                step_start = time.time()
                
                try:
                    result = await self.worker.execute(step, context)
                    step_duration.labels(
                        profile=context.profile,
                        tool=step.tool
                    ).observe((time.time() - step_start) * 1000)
                    
                except Exception as err:
                    tool_errors.labels(
                        tool=step.tool,
                        error_type=type(err).__name__
                    ).inc()
                    raise
            
        except Exception:
            status = "failed"
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            orchestration_duration.labels(
                profile=context.profile,
                status=status
            ).observe(duration_ms)
            
            orchestration_total.labels(
                profile=context.profile,
                status=status
            ).inc()


# Start Prometheus metrics server
start_http_server(8000)  # Metrics at http://localhost:8000/metrics
```

### Grafana Dashboard

```json
{
  "dashboard": {
    "title": "CUGAR Agent Observability",
    "panels": [
      {
        "title": "Orchestration Duration (p50, p95, p99)",
        "targets": [
          {
            "expr": "histogram_quantile(0.50, orchestration_duration_ms_bucket)",
            "legendFormat": "p50"
          },
          {
            "expr": "histogram_quantile(0.95, orchestration_duration_ms_bucket)",
            "legendFormat": "p95"
          },
          {
            "expr": "histogram_quantile(0.99, orchestration_duration_ms_bucket)",
            "legendFormat": "p99"
          }
        ]
      },
      {
        "title": "Orchestration Success Rate",
        "targets": [
          {
            "expr": "rate(orchestration_total{status=\"success\"}[5m]) / rate(orchestration_total[5m])"
          }
        ]
      },
      {
        "title": "Tool Error Rate by Type",
        "targets": [
          {
            "expr": "rate(tool_errors[5m])",
            "legendFormat": "{{tool}} - {{error_type}}"
          }
        ]
      },
      {
        "title": "Budget Utilization",
        "targets": [
          {
            "expr": "budget_spent / (budget_spent + budget_remaining)"
          }
        ]
      }
    ]
  }
}
```

---

## 🔧 Error Introspection

### Error Context Capture

```python
# src/cuga/observability/error_introspection.py
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List
import traceback
from cuga.orchestrator import FailureMode, OrchestrationError

@dataclass
class ErrorContext:
    """
    Comprehensive error context for debugging.
    
    Captures everything needed to understand and reproduce an error.
    """
    # Error identification
    error_id: str
    trace_id: str
    timestamp: str
    
    # Error details
    error_type: str
    error_message: str
    failure_mode: FailureMode
    recoverable: bool
    
    # Execution context
    stage: str
    component: str
    profile: str
    user_id: Optional[str]
    
    # Stack trace
    stack_trace: List[str]
    cause_chain: List[str]
    
    # State at failure
    execution_state: Dict[str, Any]
    inputs: Dict[str, Any]
    partial_results: Optional[Dict[str, Any]]
    
    # Retry context
    attempt_number: int
    max_attempts: int
    retry_delay_ms: Optional[int]
    
    # Recovery suggestions
    suggested_action: str
    runbook_url: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for logging."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON for storage."""
        import json
        return json.dumps(self.to_dict(), indent=2)


def capture_error_context(
    error: OrchestrationError,
    attempt: int = 1,
    max_attempts: int = 3,
) -> ErrorContext:
    """
    Capture comprehensive error context.
    
    Args:
        error: OrchestrationError instance
        attempt: Current attempt number
        max_attempts: Maximum retry attempts
    
    Returns:
        ErrorContext with full debugging information
    """
    # Capture stack trace
    stack_trace = traceback.format_exception(
        type(error.cause) if error.cause else type(error),
        error.cause if error.cause else error,
        error.__traceback__
    )
    
    # Capture cause chain
    cause_chain = []
    current_cause = error.cause
    while current_cause:
        cause_chain.append(f"{type(current_cause).__name__}: {current_cause}")
        current_cause = getattr(current_cause, "__cause__", None)
    
    # Classify failure mode
    failure_mode = classify_error(error)
    
    # Generate recovery suggestion
    suggested_action = get_recovery_suggestion(failure_mode, error)
    runbook_url = get_runbook_url(failure_mode)
    
    return ErrorContext(
        error_id=f"err-{error.context.trace_id[:8]}",
        trace_id=error.context.trace_id,
        timestamp=datetime.utcnow().isoformat() + "Z",
        error_type=type(error).__name__,
        error_message=error.message,
        failure_mode=failure_mode,
        recoverable=error.recoverable,
        stage=error.stage.value,
        component="orchestrator",
        profile=error.context.profile,
        user_id=error.context.user_id,
        stack_trace=stack_trace,
        cause_chain=cause_chain,
        execution_state=error.context.to_dict(),
        inputs=error.metadata.get("inputs", {}),
        partial_results=error.metadata.get("partial_result"),
        attempt_number=attempt,
        max_attempts=max_attempts,
        retry_delay_ms=calculate_retry_delay(attempt) if error.recoverable else None,
        suggested_action=suggested_action,
        runbook_url=runbook_url,
    )


def get_recovery_suggestion(mode: FailureMode, error: OrchestrationError) -> str:
    """Get recovery suggestion based on failure mode."""
    suggestions = {
        FailureMode.SYSTEM_TIMEOUT: "Retry with exponential backoff. Check external service health.",
        FailureMode.SYSTEM_NETWORK: "Check network connectivity. Verify firewall rules. Retry after delay.",
        FailureMode.AGENT_VALIDATION: "Fix input validation errors. Check input schema.",
        FailureMode.POLICY_BUDGET: "Increase budget ceiling or optimize tool usage.",
        FailureMode.RESOURCE_TOOL_UNAVAILABLE: "Check tool registration. Verify allowlist. Use fallback tool.",
        FailureMode.USER_INVALID_INPUT: "Validate user input. Return error to user with correction guidance.",
    }
    
    return suggestions.get(
        mode,
        "Review error context and stack trace. Check runbook for details."
    )


def get_runbook_url(mode: FailureMode) -> Optional[str]:
    """Get runbook URL for failure mode."""
    base_url = "https://docs.example.com/runbooks"
    
    runbooks = {
        FailureMode.SYSTEM_TIMEOUT: f"{base_url}/timeout-errors",
        FailureMode.SYSTEM_NETWORK: f"{base_url}/network-errors",
        FailureMode.POLICY_BUDGET: f"{base_url}/budget-exceeded",
    }
    
    return runbooks.get(mode)


# Usage in error handler
async def handle_error(self, error, strategy):
    """Enhanced error handling with introspection."""
    # Capture error context
    error_ctx = capture_error_context(error, attempt=1, max_attempts=3)
    
    # Log with full context
    logger.error(
        f"Orchestration error: {error.message}",
        event="orchestration_error",
        error=error_ctx.to_dict()
    )
    
    # Store for analysis
    await self.error_store.save(error_ctx)
    
    # Emit alert if critical
    if error_ctx.failure_mode.severity == FailureSeverity.CRITICAL:
        await self.alerting.send_alert(error_ctx)
    
    # Return suggested action
    return {
        "recoverable": error_ctx.recoverable,
        "suggested_action": error_ctx.suggested_action,
        "runbook_url": error_ctx.runbook_url,
        "partial_results": error_ctx.partial_results,
    }
```

### Error Storage and Analysis

```python
# src/cuga/observability/error_store.py
from typing import List, Optional
import asyncpg

class ErrorStore:
    """
    Persistent storage for error contexts.
    
    Enables:
    - Historical error analysis
    - Pattern detection
    - Trend analysis
    - Debugging assistance
    """
    
    def __init__(self, db_url: str):
        self.db_url = db_url
    
    async def save(self, error_ctx: ErrorContext):
        """Save error context to database."""
        conn = await asyncpg.connect(self.db_url)
        
        await conn.execute("""
            INSERT INTO error_contexts (
                error_id, trace_id, timestamp, error_type, error_message,
                failure_mode, recoverable, stage, component, profile,
                stack_trace, execution_state, partial_results,
                suggested_action, runbook_url
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15)
        """, error_ctx.error_id, error_ctx.trace_id, error_ctx.timestamp,
            error_ctx.error_type, error_ctx.error_message, error_ctx.failure_mode.value,
            error_ctx.recoverable, error_ctx.stage, error_ctx.component,
            error_ctx.profile, error_ctx.stack_trace, error_ctx.execution_state,
            error_ctx.partial_results, error_ctx.suggested_action, error_ctx.runbook_url
        )
        
        await conn.close()
    
    async def query_by_trace(self, trace_id: str) -> List[ErrorContext]:
        """Query errors by trace ID."""
        conn = await asyncpg.connect(self.db_url)
        
        rows = await conn.fetch("""
            SELECT * FROM error_contexts WHERE trace_id = $1 ORDER BY timestamp
        """, trace_id)
        
        await conn.close()
        
        return [ErrorContext(**dict(row)) for row in rows]
    
    async def query_by_failure_mode(
        self,
        mode: FailureMode,
        limit: int = 100
    ) -> List[ErrorContext]:
        """Query errors by failure mode."""
        conn = await asyncpg.connect(self.db_url)
        
        rows = await conn.fetch("""
            SELECT * FROM error_contexts 
            WHERE failure_mode = $1 
            ORDER BY timestamp DESC 
            LIMIT $2
        """, mode.value, limit)
        
        await conn.close()
        
        return [ErrorContext(**dict(row)) for row in rows]
```

---

## 🎬 Replayable Traces

### Trace Capture

```python
# src/cuga/observability/trace_replay.py
from dataclasses import dataclass
from typing import List, Dict, Any
import json

@dataclass
class ReplayableTrace:
    """
    Complete trace capture for replay.
    
    Captures:
    - Initial request (goal, context, config)
    - All events (planning, routing, execution)
    - Final result or error
    - Timing information
    """
    trace_id: str
    timestamp_start: str
    timestamp_end: str
    duration_ms: int
    
    # Initial request
    goal: str
    context: Dict[str, Any]
    config: Dict[str, Any]
    
    # Events
    events: List[Dict[str, Any]]
    
    # Result
    status: str  # "success", "failed", "cancelled"
    result: Optional[Dict[str, Any]]
    error: Optional[Dict[str, Any]]
    
    def to_json(self) -> str:
        """Serialize to JSON for storage."""
        return json.dumps({
            "trace_id": self.trace_id,
            "timestamp_start": self.timestamp_start,
            "timestamp_end": self.timestamp_end,
            "duration_ms": self.duration_ms,
            "goal": self.goal,
            "context": self.context,
            "config": self.config,
            "events": self.events,
            "status": self.status,
            "result": self.result,
            "error": self.error,
        }, indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "ReplayableTrace":
        """Deserialize from JSON."""
        data = json.loads(json_str)
        return cls(**data)


class TraceRecorder:
    """
    Record complete traces for replay.
    
    Usage:
        recorder = TraceRecorder()
        
        async for event in orchestrator.orchestrate(goal, context):
            recorder.record_event(event)
        
        trace = recorder.finalize()
        await trace_store.save(trace)
    """
    
    def __init__(self, trace_id: str, goal: str, context: ExecutionContext):
        self.trace_id = trace_id
        self.goal = goal
        self.context = context.to_dict()
        self.events = []
        self.start_time = time.time()
        self.end_time = None
        self.status = None
        self.result = None
        self.error = None
    
    def record_event(self, event: Dict[str, Any]):
        """Record an event."""
        self.events.append({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "stage": event["stage"],
            "data": event["data"],
        })
    
    def finalize(
        self,
        status: str,
        result: Optional[Dict[str, Any]] = None,
        error: Optional[Dict[str, Any]] = None
    ) -> ReplayableTrace:
        """Finalize trace recording."""
        self.end_time = time.time()
        self.status = status
        self.result = result
        self.error = error
        
        return ReplayableTrace(
            trace_id=self.trace_id,
            timestamp_start=datetime.fromtimestamp(self.start_time).isoformat() + "Z",
            timestamp_end=datetime.fromtimestamp(self.end_time).isoformat() + "Z",
            duration_ms=int((self.end_time - self.start_time) * 1000),
            goal=self.goal,
            context=self.context,
            config={},  # Add config if needed
            events=self.events,
            status=self.status,
            result=self.result,
            error=self.error,
        )


# Usage
async def orchestrate_with_recording(orchestrator, goal, context):
    """Orchestrate with trace recording."""
    recorder = TraceRecorder(context.trace_id, goal, context)
    
    try:
        async for event in orchestrator.orchestrate(goal, context):
            recorder.record_event(event)
            yield event
        
        trace = recorder.finalize(status="success", result={"completed": True})
    
    except OrchestrationError as err:
        trace = recorder.finalize(
            status="failed",
            error={"message": err.message, "stage": err.stage.value}
        )
        raise
    
    finally:
        await trace_store.save(trace)
```

### Trace Replay

```python
class TraceReplayer:
    """
    Replay captured traces for debugging.
    
    Features:
    - Step-by-step replay
    - Breakpoint support
    - State inspection
    - Diff comparison
    """
    
    def __init__(self, trace: ReplayableTrace):
        self.trace = trace
        self.current_event_idx = 0
    
    async def replay(self, speed: float = 1.0):
        """Replay trace at specified speed (1.0 = real-time)."""
        print(f"Replaying trace: {self.trace.trace_id}")
        print(f"Goal: {self.trace.goal}")
        print(f"Duration: {self.trace.duration_ms}ms")
        print()
        
        for i, event in enumerate(self.trace.events):
            print(f"[{i+1}/{len(self.trace.events)}] {event['stage']}")
            print(f"  Data: {json.dumps(event['data'], indent=2)}")
            print()
            
            # Calculate delay
            if i < len(self.trace.events) - 1:
                current_time = datetime.fromisoformat(event['timestamp'].replace('Z', '+00:00'))
                next_time = datetime.fromisoformat(self.trace.events[i+1]['timestamp'].replace('Z', '+00:00'))
                delay = (next_time - current_time).total_seconds() / speed
                await asyncio.sleep(delay)
        
        print(f"Replay complete. Status: {self.trace.status}")
        if self.trace.error:
            print(f"Error: {self.trace.error}")
    
    def step(self) -> Dict[str, Any]:
        """Step to next event."""
        if self.current_event_idx >= len(self.trace.events):
            raise StopIteration("End of trace")
        
        event = self.trace.events[self.current_event_idx]
        self.current_event_idx += 1
        return event
    
    def reset(self):
        """Reset replay to beginning."""
        self.current_event_idx = 0
    
    def inspect_state(self, event_idx: int) -> Dict[str, Any]:
        """Inspect state at specific event."""
        if event_idx >= len(self.trace.events):
            raise ValueError(f"Invalid event index: {event_idx}")
        
        event = self.trace.events[event_idx]
        return {
            "event_index": event_idx,
            "stage": event["stage"],
            "timestamp": event["timestamp"],
            "data": event["data"],
        }


# Usage
trace_json = await trace_store.load(trace_id="customer-onboard-001")
trace = ReplayableTrace.from_json(trace_json)

replayer = TraceReplayer(trace)
await replayer.replay(speed=2.0)  # 2x speed

# Step-by-step replay
replayer.reset()
event1 = replayer.step()
event2 = replayer.step()

# Inspect state
state = replayer.inspect_state(event_idx=3)
```

---

## 🚨 Troubleshooting Playbooks

### Common Issues

#### 1. Missing Trace IDs in Logs

**Symptoms**:
- Logs don't include `trace_id` field
- Cannot correlate logs across components

**Diagnosis**:
```bash
# Check if trace context is set
grep -c '"trace_id"' /var/log/cuga/app.log
```

**Solution**:
```python
# Ensure propagate_trace() is called
from cuga.observability.logging import propagate_trace

async def orchestrate(self, goal, context, **kwargs):
    propagate_trace(context)  # ← Must call this first
    logger.info("Starting orchestration")
```

**Prevention**:
- Add assertion in orchestrator: `assert context.trace_id`
- Configure CI to fail if logs missing trace_id

---

#### 2. High Cardinality Metrics

**Symptoms**:
- Prometheus OOM
- Slow dashboard queries
- Metrics explosion

**Diagnosis**:
```bash
# Check metric cardinality
curl http://localhost:8000/metrics | grep -c "tool_execution_duration"
```

**Solution**:
```python
# Limit label cardinality
step_duration.labels(
    profile=context.profile,
    tool=normalize_tool_name(step.tool)  # Normalize to reduce cardinality
)

def normalize_tool_name(tool: str) -> str:
    """Normalize tool names to reduce cardinality."""
    # Group similar tools: create_crm_123 → create_crm
    return tool.split('_')[0] + '_' + tool.split('_')[1]
```

**Prevention**:
- Document label cardinality limits in metrics guide
- Add cardinality alerts in Prometheus

---

#### 3. Trace Context Lost in Async Calls

**Symptoms**:
- Child spans missing parent context
- Broken trace hierarchy

**Diagnosis**:
```python
# Check if context propagates
with tracer.start_as_current_span("parent") as parent_span:
    print(f"Parent span: {parent_span.get_span_context().span_id}")
    
    async def child_fn():
        current_span = trace.get_current_span()
        print(f"Child span: {current_span.get_span_context().span_id}")
        print(f"Parent: {current_span.parent}")
    
    await child_fn()
```

**Solution**:
```python
# Use run_in_executor with context
import contextvars

async def async_fn_with_context():
    # Context automatically propagates in async/await
    with tracer.start_as_current_span("child"):
        await some_async_call()

# For thread pools, copy context explicitly
context = contextvars.copy_context()
await loop.run_in_executor(executor, context.run, sync_fn)
```

---

#### 4. PII in Logs

**Symptoms**:
- Sensitive data in logs
- Compliance violations

**Diagnosis**:
```bash
# Search for patterns
grep -E '"password"|"token"|"api_key"' /var/log/cuga/app.log
```

**Solution**:
```python
# Enable redaction
logger = StructuredLogger(
    component="MyAgent",
    redact_secrets=True  # ← Enable redaction
)

# Add custom redaction rules
def _redact_sensitive_data(self, data):
    sensitive_patterns = [
        r'password.*',
        r'.*token.*',
        r'.*key.*',
        r'.*secret.*',
        r'credit_card',
        r'ssn',
    ]
    # ... redaction logic ...
```

**Prevention**:
- Add PII detection tests
- Configure log scanning alerts

---

## 📚 Related Documentation

- **[System Execution Narrative](../SYSTEM_EXECUTION_NARRATIVE.md)** - Complete request → response flow
- **[Orchestrator Interface](../orchestrator/README.md)** - Lifecycle stages and error handling
- **[Failure Modes](../orchestrator/FAILURE_MODES.md)** - Error taxonomy and recovery
- **[Enterprise Workflows](../examples/ENTERPRISE_WORKFLOWS.md)** - End-to-end examples with observability
- **[Testing Guide](../testing/SCENARIO_TESTING.md)** - Testing observability integration

---

**For questions or contributions, see [CONTRIBUTING.md](../../CONTRIBUTING.md).**

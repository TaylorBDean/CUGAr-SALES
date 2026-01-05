# Observability Deprecation Notice (v1.1.0 → v1.3.0)

**Effective Date:** 2026-01-02 (v1.1.0)  
**Removal Date:** TBD (v1.3.0, estimated Q2 2026)

## Overview

As part of the v1.1.0 agent integration release, several legacy observability patterns have been deprecated in favor of the new structured observability system. This document outlines what's deprecated, migration paths, and timelines.

## Deprecated Components

### 1. `cuga.modular.observability.BaseEmitter`

**Status:** ⚠️ Deprecated in v1.1.0, will be removed in v1.3.0

**Reason:** Replaced by structured event emission via `cuga.observability.emit_event()`.

**Migration:**

```python
# ❌ Old (deprecated):
from cuga.modular.observability import BaseEmitter

class MyEmitter(BaseEmitter):
    def emit(self, payload):
        # Custom emission logic
        pass

worker = WorkerAgent(registry=..., memory=..., observability=MyEmitter())

# ✅ New (v1.1.0+):
from cuga.observability import emit_event, ToolCallEvent

# Events automatically emitted by agents
worker = WorkerAgent(registry=..., memory=...)

# If you need custom observability, use exporters:
from cuga.observability import ObservabilityCollector, set_collector
from cuga.observability.exporters import ConsoleExporter, OTELExporter

collector = ObservabilityCollector(
    exporters=[ConsoleExporter(), OTELExporter()]
)
set_collector(collector)
```

**Deprecation Warning:**
```
DeprecationWarning: BaseEmitter is deprecated as of v1.1.0 and will be removed in v1.3.0. 
Use cuga.observability.emit_event() instead. Events are now automatically emitted by agents.
```

---

### 2. `cuga.observability_legacy.InMemoryTracer`

**Status:** ⚠️ Deprecated in v1.1.0, will be removed in v1.3.0

**Reason:** Replaced by `cuga.observability.ObservabilityCollector` with structured events.

**Migration:**

```python
# ❌ Old (deprecated):
from cuga.observability_legacy import InMemoryTracer

tracer = InMemoryTracer()
span = tracer.start_span("tool_execution", tool="calculator")
# ... do work ...
span.end(result="42")

# ✅ New (v1.1.0+):
from cuga.observability import emit_event, ToolCallEvent, get_collector
import time

# Emit start event
start_time = time.perf_counter()
start_event = ToolCallEvent.create_start(
    trace_id="my-trace-001",
    tool_name="calculator",
    inputs={"operation": "add"}
)
emit_event(start_event)

# ... do work ...

# Emit complete event
duration_ms = (time.perf_counter() - start_time) * 1000
complete_event = ToolCallEvent.create_complete(
    trace_id="my-trace-001",
    tool_name="calculator",
    inputs={"operation": "add"},
    result="42",
    duration_ms=duration_ms
)
emit_event(complete_event)

# Access events via collector
collector = get_collector()
all_events = collector.events
```

**Deprecation Warning:**
```
DeprecationWarning: InMemoryTracer is deprecated as of v1.1.0 and will be removed in v1.3.0. 
Use cuga.observability.ObservabilityCollector via get_collector() instead. 
See docs/observability/AGENT_INTEGRATION.md for migration guide.
```

---

### 3. `WorkerAgent.observability` Parameter

**Status:** ⚠️ Deprecated in v1.1.0, will be removed in v1.3.0

**Reason:** Events are now automatically emitted; explicit observability parameter is redundant.

**Migration:**

```python
# ❌ Old (deprecated):
from cuga.modular.observability import BaseEmitter

worker = WorkerAgent(
    registry=registry,
    memory=memory,
    observability=BaseEmitter()  # Deprecated parameter
)

# ✅ New (v1.1.0+):
worker = WorkerAgent(
    registry=registry,
    memory=memory
    # No observability parameter needed - events automatically emitted
)

# Configure observability globally:
from cuga.observability import set_collector, ObservabilityCollector
collector = ObservabilityCollector(exporters=[...])
set_collector(collector)
```

**Deprecation Warning:**
```
DeprecationWarning: WorkerAgent.observability (BaseEmitter) is deprecated as of v1.1.0 and 
will be removed in v1.3.0. All events are now automatically emitted via 
cuga.observability.emit_event(). Remove the 'observability' parameter.
```

---

### 4. `cuga.modular.observability.LangfuseEmitter`

**Status:** ⚠️ Deprecated in v1.1.0, will be removed in v1.3.0

**Reason:** Replaced by OTEL-based exporters with LangFuse integration.

**Migration:**

```python
# ❌ Old (deprecated):
from cuga.modular.observability import LangfuseEmitter

worker = WorkerAgent(
    registry=...,
    memory=...,
    observability=LangfuseEmitter()
)

# ✅ New (v1.1.0+):
# Configure LangFuse via environment variables
import os
os.environ["LANGFUSE_PUBLIC_KEY"] = "pk-..."
os.environ["LANGFUSE_SECRET_KEY"] = "sk-..."

# Use OTEL exporter (automatically integrates with LangFuse)
from cuga.observability import ObservabilityCollector, set_collector
from cuga.observability.exporters import OTELExporter

collector = ObservabilityCollector(
    exporters=[OTELExporter()]
)
set_collector(collector)

worker = WorkerAgent(registry=..., memory=...)
```

**Deprecation Warning:**
```
DeprecationWarning: LangfuseEmitter is deprecated as of v1.1.0 and will be removed in v1.3.0. 
Use cuga.observability.exporters with OTEL/LangFuse integration instead.
```

---

### 5. `cuga.modular.observability.OpenInferenceEmitter`

**Status:** ⚠️ Deprecated in v1.1.0, will be removed in v1.3.0

**Reason:** Replaced by OTEL-based exporters with OpenInference integration.

**Migration:**

```python
# ❌ Old (deprecated):
from cuga.modular.observability import OpenInferenceEmitter

worker = WorkerAgent(
    registry=...,
    memory=...,
    observability=OpenInferenceEmitter()
)

# ✅ New (v1.1.0+):
# Configure OpenInference via environment variables
import os
os.environ["OPENINFERENCE_ENDPOINT"] = "http://localhost:6006"

# Use OTEL exporter (automatically integrates with OpenInference)
from cuga.observability import ObservabilityCollector, set_collector
from cuga.observability.exporters import OTELExporter

collector = ObservabilityCollector(
    exporters=[OTELExporter()]
)
set_collector(collector)

worker = WorkerAgent(registry=..., memory=...)
```

**Deprecation Warning:**
```
DeprecationWarning: OpenInferenceEmitter is deprecated as of v1.1.0 and will be removed in v1.3.0. 
Use cuga.observability.exporters with OTEL integration instead.
```

---

## Timeline

| Version | Date | Status |
|---------|------|--------|
| v1.1.0 | 2026-01-02 | ✅ Deprecation warnings added, backward compatible |
| v1.2.0 | TBD (Q1 2026) | ⚠️ Deprecation warnings remain, features still functional |
| v1.3.0 | TBD (Q2 2026) | ❌ Legacy components removed (breaking change) |

## Backward Compatibility

**v1.1.0 - v1.2.x:** All deprecated components remain functional with deprecation warnings. Existing code will continue to work without modifications.

**v1.3.0+:** Deprecated components will be removed. Code using legacy patterns will break and must be migrated.

## Migration Checklist

- [ ] Replace `BaseEmitter` with `ObservabilityCollector` and exporters
- [ ] Replace `InMemoryTracer` with `get_collector()` and structured events
- [ ] Remove `observability` parameter from `WorkerAgent` instantiation
- [ ] Replace `LangfuseEmitter` with OTEL exporters + environment config
- [ ] Replace `OpenInferenceEmitter` with OTEL exporters + environment config
- [ ] Update tests to verify events via `collector.events` instead of `tracer.spans`
- [ ] Verify deprecation warnings are resolved (run with `-W error::DeprecationWarning`)

## Testing Migration

```bash
# Check for deprecation warnings
python -m pytest tests/ -W error::DeprecationWarning

# Should fail if any deprecated patterns are used
# Fix warnings before v1.3.0 removal
```

## Resources

- **Migration Guide**: `docs/observability/AGENT_INTEGRATION.md`
- **New Event System**: `docs/observability/OBSERVABILITY_SLOS.md`
- **Exporter Configuration**: `src/cuga/observability/exporters/`
- **Integration Examples**: `examples/observability_example.py`
- **Changelog**: `CHANGELOG.md` (v1.1.0 section)

## Support

For migration questions or issues:
1. Check `docs/observability/AGENT_INTEGRATION.md` for code examples
2. Review integration tests: `tests/integration/test_agent_observability.py`
3. File an issue on GitHub with "migration" label

---

**Last Updated:** 2026-01-02 (v1.1.0 release)

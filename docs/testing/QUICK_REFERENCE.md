# Test Coverage Quick Reference

**Last Updated**: 2025-12-31

## At-a-Glance Coverage Status

### ✅ Well-Tested Layers (>75% coverage)

| Layer | Coverage | Tests | Status |
|-------|----------|-------|--------|
| **Orchestrator** | 80% | 35+ | ✅ Good |
| **Failure Modes** | 85% | 60+ | ✅ Good |
| **Routing** | 80% | 50+ | ✅ Good |

### ⚠️ Partially Tested Layers (25-75% coverage)

| Layer | Coverage | Tests | Gaps |
|-------|----------|-------|------|
| **Agents** | 60% | 30+ | Planner/Worker/Coordinator integration |

### ❌ Untested Layers (<25% coverage)

| Layer | Coverage | Tests | Risk |
|-------|----------|-------|------|
| **Tools** | 10% | 5 | **CRITICAL** - Security boundaries |
| **Memory** | 0% | 0 | **HIGH** - Data integrity |
| **Config** | 0% | 0 | **MEDIUM** - Operational |
| **Observability** | 0% | 0 | **MEDIUM** - Debugging |

---

## Critical Path Status

| # | Path | Status | Risk | Priority |
|---|------|--------|------|----------|
| 1 | **Planning → Execution** | ❌ Untested | **HIGH** | 🔥 P0 |
| 2 | **Multi-Worker Coordination** | ⚠️ Partial | **MEDIUM** | P1 |
| 3 | **Nested Orchestration** | ❌ Untested | **MEDIUM** | P2 |
| 4 | **Error Recovery** | ⚠️ Partial | **MEDIUM** | P1 |
| 5 | **Memory-Augmented Planning** | ❌ Untested | **HIGH** | 🔥 P0 |
| 6 | **Profile-Based Isolation** | ❌ Untested | **CRITICAL** | 🔥 P0 |

---

## Priority Actions (Next Sprint)

### 🔥 Critical (This Week)

1. **Test Path 6**: Profile-based tool isolation
   - File: `tests/integration/test_profile_based_isolation.py`
   - Effort: 6 hours
   - Validates: Security boundaries per profile
   
2. **Test Path 1**: Planning → execution flow
   - File: `tests/integration/test_planning_execution_flow.py`
   - Effort: 4 hours
   - Validates: End-to-end user flow
   
3. **Test Path 5**: Memory-augmented planning
   - File: `tests/integration/test_memory_augmented_planning.py`
   - Effort: 6 hours
   - Validates: Memory layer integration

**Total Effort**: ~16 hours (2 developer-days)

### ⚠️ Important (This Month)

4. **Test Tools Layer**: Registry resolution, validation
   - File: `tests/unit/test_tool_registry.py`
   - Effort: 8 hours
   
5. **Test Memory Layer**: Vector storage, similarity search
   - File: `tests/unit/test_vector_memory.py`
   - Effort: 8 hours
   
6. **Test Config Layer**: Precedence, merge strategies
   - File: `tests/unit/test_config_resolver.py`
   - Effort: 8 hours

**Total Effort**: ~24 hours (3 developer-days)

---

## Test File Locations

### Existing Tests (DO NOT DELETE)

```
tests/
├── test_orchestrator_protocol.py      # Orchestrator lifecycle, routing, errors
├── test_agent_lifecycle.py            # Startup/shutdown, state ownership
├── test_agent_contracts.py            # AgentRequest/Response, validation
├── test_failure_modes.py              # Failure taxonomy, retry policies
├── test_routing_authority.py          # Routing context, decisions, policies
├── unit/
│   └── test_registry_sandboxing.py    # Registry loading, tool execution
└── scenario/
    └── test_stateful_agent.py         # Multi-turn conversation E2E
```

### Tests to Create (PRIORITY)

```
tests/
└── integration/
    ├── test_profile_based_isolation.py       # 🔥 P0 - Security
    ├── test_planning_execution_flow.py       # 🔥 P0 - User flow
    ├── test_memory_augmented_planning.py     # 🔥 P0 - Memory
    ├── test_multi_worker_coordination.py     # P1 - Scalability
    ├── test_error_recovery_flow.py           # P1 - Resilience
    ├── test_nested_orchestration.py          # P2 - Advanced
    └── test_observability_chain.py           # P2 - Debugging

tests/
└── unit/
    ├── test_tool_registry.py                 # P0 - Tools layer
    ├── test_vector_memory.py                 # P0 - Memory layer
    └── test_config_resolver.py               # P1 - Config layer
```

---

## Running Tests

### Run All Tests

```bash
# Root tests (fast)
pytest tests/ -v

# Include unit tests
pytest tests/unit/ -v

# Include scenario tests (slower)
pytest tests/scenario/ -v

# Run specific layer
pytest tests/test_orchestrator_protocol.py -v
pytest tests/test_agent_lifecycle.py -v
pytest tests/test_failure_modes.py -v
```

### Run with Coverage

```bash
# Coverage report
pytest tests/ --cov=src/cuga --cov-report=term-missing

# Fail if coverage <80%
pytest tests/ --cov=src/cuga --cov-fail-under=80
```

### Run Integration Tests (when created)

```bash
# All integration tests
pytest tests/integration/ -v

# Specific critical path
pytest tests/integration/test_profile_based_isolation.py -v
```

---

## Test Ownership

| Layer | Primary Owner | Test Files |
|-------|---------------|------------|
| **Orchestrator** | Platform Team | `test_orchestrator_protocol.py` |
| **Agents** | Agent Team | `test_agent_lifecycle.py`, `test_agent_contracts.py` |
| **Failure Modes** | Platform Team | `test_failure_modes.py` |
| **Routing** | Orchestration Team | `test_routing_authority.py` |
| **Tools** | ⚠️ **UNASSIGNED** | `test_registry_sandboxing.py` (minimal) |
| **Memory** | ⚠️ **UNASSIGNED** | ❌ None |
| **Config** | ⚠️ **UNASSIGNED** | ❌ None |
| **Observability** | ⚠️ **UNASSIGNED** | ❌ None |

**Action Required**: Assign ownership for untested layers.

---

## Common Test Patterns

### Orchestrator Test Pattern

```python
import pytest
from cuga.orchestrator import ExecutionContext, OrchestratorProtocol

@pytest.fixture
def context():
    return ExecutionContext(trace_id="test-123", profile="test")

@pytest.mark.asyncio
async def test_orchestration_flow(orchestrator, context):
    """Test full orchestration lifecycle."""
    stages = []
    async for event in orchestrator.orchestrate("goal", context):
        stages.append(event["stage"])
    
    assert "initialize" in stages
    assert "execute" in stages
    assert "complete" in stages
```

### Agent Test Pattern

```python
import pytest
from cuga.agents.lifecycle import ManagedAgent

@pytest.mark.asyncio
async def test_agent_lifecycle():
    """Test agent startup/shutdown."""
    agent = TestAgent()
    
    await agent.startup()
    assert agent.state == "READY"
    
    await agent.shutdown()
    assert agent.state == "TERMINATED"
```

### Integration Test Pattern

```python
import pytest
from cuga.planner import Planner
from cuga.coordinator import Coordinator
from cuga.workers import Worker

@pytest.mark.asyncio
async def test_planning_execution_flow():
    """Test end-to-end planning and execution."""
    planner = Planner()
    workers = [Worker("w1"), Worker("w2")]
    coordinator = Coordinator(workers)
    
    # Plan
    plan = await planner.plan("test goal")
    
    # Execute
    results = []
    async for result in coordinator.run(plan, trace_id="test"):
        results.append(result)
    
    assert len(results) > 0
    assert all(r["status"] == "ok" for r in results)
```

---

## Risk Assessment Summary

### Production Deployment Blockers

1. 🚨 **Tools Layer Untested** (10% coverage)
   - Security boundaries untested
   - Registry resolution untested
   - Sandbox isolation untested
   - **Impact**: Security vulnerabilities, tool resolution failures
   - **Blocker**: YES

2. 🚨 **Memory Layer Untested** (0% coverage)
   - Data persistence untested
   - Profile isolation untested
   - Vector search untested
   - **Impact**: Data loss, cross-profile leakage, query failures
   - **Blocker**: YES

3. ⚠️ **Critical Paths Untested**
   - Planning → execution flow untested
   - Profile-based isolation untested
   - Memory-augmented planning untested
   - **Impact**: User-facing failures, security breaches
   - **Blocker**: YES

### Non-Blocking Gaps

4. ℹ️ **Config Layer Untested** (0% coverage)
   - Operational risk (misconfigurations)
   - Not user-facing
   - **Blocker**: NO (but should be tested)

5. ℹ️ **Observability Untested** (0% coverage)
   - Debugging risk (trace gaps)
   - Can add post-deployment
   - **Blocker**: NO (but highly recommended)

---

## Next Steps Checklist

- [ ] Assign test ownership for untested layers (Tools, Memory, Config, Observability)
- [ ] Create `tests/integration/` directory
- [ ] Implement Path 6: Profile-based isolation test (6 hours)
- [ ] Implement Path 1: Planning → execution flow test (4 hours)
- [ ] Implement Path 5: Memory-augmented planning test (6 hours)
- [ ] Implement Tools layer unit tests (8 hours)
- [ ] Implement Memory layer unit tests (8 hours)
- [ ] Implement Config layer unit tests (8 hours)
- [ ] Set up CI/CD coverage gating (>80% required)
- [ ] Schedule quarterly coverage audits

---

**See Full Analysis**: `docs/testing/COVERAGE_MATRIX.md`

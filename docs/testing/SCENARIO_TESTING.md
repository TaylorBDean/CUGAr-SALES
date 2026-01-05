# Scenario Testing Guide

**Last Updated**: 2025-12-31  
**Status**: Canonical

## Overview

Scenario tests validate end-to-end agent composition workflows under real conditions. Unlike unit tests (single component) or integration tests (component pairs), scenario tests exercise **complete orchestration flows** with real components, memory persistence, and complex multi-step interactions.

---

## What Are Scenario Tests?

### Definition

**Scenario tests** simulate real-world agent workflows from start to finish, validating:
- Multi-agent coordination (planner → coordinator → workers)
- Memory-augmented decision making
- Profile-based security boundaries
- Error recovery and resilience
- Stateful multi-turn conversations
- Complex workflow orchestration

### Scenario vs. Unit vs. Integration

| Aspect | Unit Test | Integration Test | Scenario Test |
|--------|-----------|------------------|---------------|
| **Scope** | Single component | 2-3 components | Full workflow (5+ components) |
| **Mocking** | Heavy (isolate component) | Moderate (mock externals) | Minimal (real components) |
| **Duration** | Fast (<100ms) | Medium (100ms-1s) | Slow (1s-10s+) |
| **Focus** | Correctness | Integration | Real-world behavior |
| **Example** | `test_planner_ranks_tools()` | `test_planner_executor_flow()` | `test_multi_agent_dispatch()` |

---

## Scenario Test Catalog

### Scenario 1: Multi-Agent Dispatch (CrewAI/AutoGen Style)

**Purpose**: Validate coordinator distributes work across multiple workers

**Components**:
- PlannerAgent (goal → plan)
- CoordinatorAgent (dispatch logic)
- WorkerAgent × N (round-robin execution)
- VectorMemory (shared context)

**Flow**:
```
User Goal
  ↓
Planner generates multi-step plan
  ↓
Coordinator selects worker (round-robin)
  ↓
Worker 1 executes step 1
  ↓
Coordinator selects worker (round-robin)
  ↓
Worker 2 executes step 2
  ↓
...
  ↓
Coordinator aggregates results
  ↓
Result returned to user
```

**Validates**:
- ✅ Round-robin worker selection under concurrent dispatch
- ✅ Shared memory context across workers
- ✅ Trace propagation through all layers
- ✅ Result aggregation from multiple workers

**Test File**: `tests/scenario/test_agent_composition.py::TestMultiAgentDispatch`

**Example**:
```python
def test_multi_worker_round_robin(self):
    registry = ToolRegistry([...])
    memory = VectorMemory(profile="test")
    
    planner = PlannerAgent(registry=registry, memory=memory)
    workers = [WorkerAgent(...) for _ in range(3)]
    coordinator = CoordinatorAgent(planner=planner, workers=workers, memory=memory)
    
    # Execute 6 tasks - each worker should get 2
    for i in range(6):
        result = coordinator.dispatch(f"Task {i}")
        assert result.output is not None
```

---

### Scenario 2: Memory-Augmented Planning

**Purpose**: Validate planner learns from past executions

**Components**:
- VectorMemory (storage + similarity search)
- PlannerAgent (memory-informed ranking)
- WorkerAgent (execution trace capture)

**Flow**:
```
First Execution:
  Goal → Planner → Tool selection (no memory)
  → Execution → Store result in memory
  
Second Execution:
  Goal → Planner queries memory → Tool ranking influenced
  → Execution benefits from learned patterns
```

**Validates**:
- ✅ Planner queries memory for similar past tasks
- ✅ Tool ranking influenced by memory scores
- ✅ Execution traces stored in memory
- ✅ Future planning benefits from learned patterns

**Test File**: `tests/scenario/test_agent_composition.py::TestMemoryAugmentedPlanning`

**Example**:
```python
def test_memory_influences_tool_selection(self):
    memory = VectorMemory(profile="learning-test")
    
    # Pre-populate with learned preferences
    memory.store(
        content="Tool: financial_analyzer. Success: True",
        metadata={"tool": "financial_analyzer", "success": True}
    )
    
    planner = PlannerAgent(registry=registry, memory=memory)
    
    # Should prefer financial_analyzer based on memory
    plan = planner.plan("Analyze quarterly financial reports")
    
    assert plan.steps is not None
```

---

### Scenario 3: Profile-Based Tool Isolation

**Purpose**: Validate security boundaries per execution profile

**Components**:
- ExecutionContext (profile field)
- ToolRegistry (profile-aware filtering)
- PolicyEnforcer (allowlist/denylist)
- Sandbox (profile constraints)

**Flow**:
```
Goal + Profile "restricted"
  ↓
ToolRegistry filters tools (only safe tools)
  ↓
PolicyEnforcer validates tool access
  ↓
Sandbox executes with restricted permissions
  
Goal + Profile "demo_power"
  ↓
ToolRegistry allows more tools
  ↓
Sandbox executes with relaxed permissions
```

**Validates**:
- ✅ Tools filtered by profile allowlist
- ✅ Restricted profile blocks dangerous tools
- ✅ Production profile enforces stricter policies
- ✅ No cross-profile memory contamination

**Test File**: `tests/scenario/test_agent_composition.py::TestProfileBasedIsolation`

**Example**:
```python
def test_restricted_profile_blocks_tools(self):
    registry = ToolRegistry([
        ToolSpec(name="safe_echo", ...),
        ToolSpec(name="exec_code", ...)  # Dangerous
    ])
    
    planner_restricted = PlannerAgent(
        registry=registry,
        config=AgentConfig(profile="restricted")
    )
    
    # Should only allow safe tools
    plan = planner_restricted.plan("Echo hello")
    assert "exec_code" not in [s.tool for s in plan.steps]
```

---

### Scenario 4: Error Recovery and Partial Results

**Purpose**: Validate graceful failure handling

**Components**:
- WorkerAgent (execution)
- FailureMode taxonomy
- RetryPolicy (exponential backoff)
- PartialResult (preservation)

**Flow**:
```
Execute multi-step plan
  ↓
Step 1: Success
  ↓
Step 2: Failure (network timeout)
  ↓
Categorize failure (SYSTEM_NETWORK)
  ↓
RetryPolicy: Wait + Retry
  ↓
Step 2: Retry success
  ↓
Step 3: Success
  ↓
Aggregate results (include retry info)
```

**Validates**:
- ✅ Tool failures captured (no uncaught exceptions)
- ✅ Retry policies applied (exponential backoff)
- ✅ Partial results preserved
- ✅ Coordinator continues with available workers

**Test File**: `tests/scenario/test_agent_composition.py::TestErrorRecoveryScenarios`

---

### Scenario 5: Streaming Execution

**Purpose**: Validate event emission during execution

**Components**:
- PlannerAgent (streaming plan generation)
- WorkerAgent (streaming execution updates)
- Observability emitters (event capture)

**Flow**:
```
Goal → Planner (emit: plan_start)
  ↓
Generate step 1 (emit: plan_step_1)
  ↓
Generate step 2 (emit: plan_step_2)
  ↓
Plan complete (emit: plan_complete)
  ↓
Execute step 1 (emit: exec_start_1, exec_complete_1)
  ↓
Execute step 2 (emit: exec_start_2, exec_complete_2)
  ↓
Aggregate (emit: complete)
```

**Validates**:
- ✅ Planning emits step-by-step events
- ✅ Execution emits progress updates
- ✅ Events include trace IDs
- ✅ Events are ordered correctly

**Test File**: `tests/scenario/test_agent_composition.py::TestStreamingExecution`

---

### Scenario 6: Stateful Multi-Turn Conversation

**Purpose**: Validate session persistence and context carryover

**Components**:
- VectorMemory (session storage)
- MemoryStore (session state)
- PlannerAgent (context-aware planning)

**Flow**:
```
Turn 1: User provides context
  → Store in memory (session_id)
  
Turn 2: User asks question
  → Query memory (session_id)
  → Answer uses stored context
  
Turn 3: Follow-up question
  → Memory provides full conversation history
  → Answer maintains session continuity
```

**Validates**:
- ✅ Session state persists across turns
- ✅ Memory provides context to later turns
- ✅ Conversation history influences planning
- ✅ Session cleanup works correctly

**Test File**: `tests/scenario/test_agent_composition.py::TestStatefulConversation`

**Example**:
```python
def test_multi_turn_conversation(self):
    session_id = str(uuid.uuid4())
    memory = VectorMemory(profile=session_id)
    coordinator = CoordinatorAgent(planner=..., workers=..., memory=memory)
    
    # Turn 1: Store information
    result1 = coordinator.dispatch("Remember my name is Alice")
    memory.store("User's name is Alice", metadata={"session_id": session_id})
    
    # Turn 2: Recall information
    result2 = coordinator.dispatch("What is my name?")
    recalled = memory.query("user name", filter_metadata={"session_id": session_id})
    assert "Alice" in recalled[0]["content"]
```

---

### Scenario 7: Complex Multi-Step Workflow

**Purpose**: Validate orchestration of 5+ step workflows

**Components**:
- PlannerAgent (multi-step planning)
- WorkerAgent (sequential execution)
- CoordinatorAgent (result aggregation)

**Flow**:
```
Goal: "Load data, clean, transform, analyze, report"
  ↓
Planner generates 5-step plan
  ↓
Worker executes: Load → Clean → Transform → Analyze → Report
  ↓
Each step passes output to next step
  ↓
Final result aggregates all steps
```

**Validates**:
- ✅ Multi-step plans generated correctly
- ✅ Steps execute in order
- ✅ Intermediate results passed between steps
- ✅ Final result aggregates all steps

**Test File**: `tests/scenario/test_agent_composition.py::TestComplexWorkflow`

---

### Scenario 8: Nested Coordination

**Purpose**: Validate hierarchical orchestration (parent → child coordinators)

**Components**:
- Parent CoordinatorAgent
- Child CoordinatorAgents
- Shared VectorMemory
- ExecutionContext (parent_context chaining)

**Flow**:
```
Parent Goal: "Complete project"
  ↓
Parent decomposes into sub-goals
  → Sub-goal 1: "Design database"
  → Sub-goal 2: "Implement API"
  → Sub-goal 3: "Write tests"
  ↓
Child coordinators execute sub-goals
  ↓
Parent aggregates child results
  ↓
Final result returned
```

**Validates**:
- ✅ Parent context propagates to children
- ✅ Child results aggregate to parent
- ✅ Trace continuity across nesting levels
- ✅ Memory shared across coordinator hierarchy

**Test File**: `tests/scenario/test_agent_composition.py::TestNestedCoordination`

---

## Running Scenario Tests

### Run All Scenarios

```bash
# Run all scenario tests
pytest tests/scenario/ -v

# Run with output
pytest tests/scenario/ -v -s

# Run specific scenario class
pytest tests/scenario/test_agent_composition.py::TestMultiAgentDispatch -v

# Run specific test
pytest tests/scenario/test_agent_composition.py::TestMultiAgentDispatch::test_multi_worker_round_robin -v
```

### Run with Coverage

```bash
# Scenario coverage only
pytest tests/scenario/ --cov=src/cuga --cov-report=term-missing

# All tests with scenario emphasis
pytest tests/ --cov=src/cuga --cov-report=html
open htmlcov/index.html
```

### Performance Profiling

```bash
# Time each scenario
pytest tests/scenario/ --durations=10

# Profile slow scenarios
pytest tests/scenario/ --profile

# Fail if scenario takes >30s
pytest tests/scenario/ --timeout=30
```

---

## Writing New Scenario Tests

### Scenario Test Template

```python
class TestMyScenario:
    """
    Test Scenario: [Brief description]
    
    Flow:
        [Component 1] → [Component 2] → ... → [Result]
    
    Validates:
        - ✅ [Expected behavior 1]
        - ✅ [Expected behavior 2]
        - ✅ [Expected behavior 3]
    """
    
    def test_scenario_happy_path(self):
        """Test scenario succeeds under normal conditions."""
        # Setup
        registry = ToolRegistry([...])
        memory = VectorMemory(profile="test")
        agents = setup_agents(registry, memory)
        
        # Execute
        result = agents.coordinator.dispatch("User goal")
        
        # Validate
        assert result.output is not None
        assert len(result.trace) > 0
        assert "expected" in result.output
    
    def test_scenario_edge_case(self):
        """Test scenario handles edge cases."""
        # ...
    
    def test_scenario_failure_mode(self):
        """Test scenario recovers from failures."""
        # ...
```

### Best Practices

**DO**:
- ✅ Use real components (minimal mocks)
- ✅ Test end-to-end flows (5+ components)
- ✅ Validate trace propagation
- ✅ Check memory persistence
- ✅ Use descriptive test names
- ✅ Document flow in docstring
- ✅ Include edge cases and failure modes

**DON'T**:
- ❌ Mock core components (defeats purpose)
- ❌ Test single components (use unit tests)
- ❌ Skip validation (check all invariants)
- ❌ Ignore failures (scenarios must be stable)
- ❌ Hard-code values (use fixtures)
- ❌ Test too many things in one scenario

---

## Scenario Test Fixtures

### Common Fixtures

```python
@pytest.fixture
def test_registry():
    """Standard tool registry for scenarios."""
    return ToolRegistry([
        ToolSpec(name="echo", ...),
        ToolSpec(name="calculate", ...),
        ToolSpec(name="store", ...),
        ToolSpec(name="retrieve", ...)
    ])

@pytest.fixture
def test_memory():
    """Isolated memory instance per test."""
    return VectorMemory(profile=f"test-{uuid.uuid4().hex[:8]}")

@pytest.fixture
def test_config():
    """Standard agent configuration."""
    return AgentConfig(
        profile="test",
        strategy="react",
        max_steps=6,
        temperature=0.3
    )
```

### Fixture Patterns

**Isolated State** (default):
```python
@pytest.fixture
def isolated_memory():
    """New memory instance per test (no sharing)."""
    return VectorMemory(profile=f"test-{uuid.uuid4().hex[:8]}")
```

**Shared State** (multi-turn scenarios):
```python
@pytest.fixture(scope="class")
def shared_memory():
    """Shared memory across test class."""
    return VectorMemory(profile="shared-test")
```

**Session State** (full test suite):
```python
@pytest.fixture(scope="session")
def session_registry():
    """Shared registry for entire test session."""
    return ToolRegistry([...])
```

---

## Troubleshooting Scenario Tests

### Problem: Scenario test is slow (>10s)

**Solutions**:
1. Reduce max_steps in config (default: 6 → 3)
2. Use simpler tools (avoid network calls)
3. Mock external dependencies (databases, APIs)
4. Use in-memory backends (vector storage)

### Problem: Scenario test is flaky

**Causes**:
- Race conditions (concurrent workers)
- Non-deterministic behavior (random tool selection)
- Shared state between tests
- External dependencies (network, filesystem)

**Solutions**:
1. Use deterministic tool ranking
2. Isolate state per test (fresh memory/registry)
3. Add explicit synchronization (locks, barriers)
4. Mock external dependencies

### Problem: Scenario test fails in CI but passes locally

**Causes**:
- Timing differences (CI slower)
- Environment differences (missing dependencies)
- State leakage from other tests

**Solutions**:
1. Increase timeouts in CI
2. Explicitly set environment in test
3. Use isolated fixtures (no shared state)
4. Add CI-specific configuration

---

## Scenario Coverage Goals

### Current Status

| Scenario | Status | Coverage |
|----------|--------|----------|
| Multi-Agent Dispatch | ✅ Implemented | 3 tests |
| Memory-Augmented Planning | ✅ Implemented | 2 tests |
| Profile-Based Isolation | ✅ Implemented | 2 tests |
| Error Recovery | ✅ Implemented | 2 tests |
| Streaming Execution | ✅ Implemented | 1 test |
| Stateful Conversation | ✅ Implemented | 1 test |
| Complex Workflow | ✅ Implemented | 1 test |
| Nested Coordination | ✅ Implemented | 1 test |

**Total**: 13 scenario tests covering 8 real-world patterns

### Target Coverage (Q1 2026)

- [ ] Budget enforcement scenarios
- [ ] MCP server integration scenarios
- [ ] FastAPI endpoint scenarios
- [ ] LangGraph node routing scenarios
- [ ] Observability chain scenarios
- [ ] RAG query flow scenarios

---

## See Also

- `TESTING.md` - General testing guide
- `docs/testing/COVERAGE_MATRIX.md` - Coverage analysis
- `AGENTS.md` - Agent guardrails and protocols
- `examples/multi_agent_dispatch.py` - Multi-agent example

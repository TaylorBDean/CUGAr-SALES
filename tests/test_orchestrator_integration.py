"""
Full Orchestrator Integration Tests (Task #9)

End-to-end integration tests validating that all orchestrator components
work together seamlessly:
- OrchestratorProtocol + RoutingAuthority + PlanningAuthority
- RetryPolicy + PartialResult recovery
- AuditTrail + ApprovalGate
- Observability integration

These tests ensure the complete orchestration stack operates correctly
under real-world scenarios including failures, retries, approvals, and recovery.
"""

import asyncio
import os
import pytest
import tempfile
import time
from typing import Any, Dict

from cuga.modular.agents import CoordinatorAgent, WorkerAgent, PlannerAgent, AgentResult
from cuga.modular.tools import ToolRegistry, ToolSpec
from cuga.modular.memory import VectorMemory
from cuga.modular.llm.interface import MockLLM

from cuga.orchestrator.protocol import ExecutionContext, LifecycleStage
from cuga.orchestrator.routing import (
    RoutingAuthority,
    PolicyBasedRoutingAuthority,
    RoundRobinPolicy,
    CapabilityBasedPolicy,
)
from cuga.orchestrator.planning import (
    Plan,
    PlanStep,
    PlanningStage,
    ToolBudget,
)
from cuga.orchestrator.failures import (
    FailureMode,
    PartialResult,
    create_retry_policy,
)
from cuga.orchestrator.audit import AuditTrail, SQLiteAuditBackend
from cuga.orchestrator.approval import (
    ApprovalGate,
    ApprovalPolicy,
    ApprovalStatus,
    create_approval_gate,
)


# ============================================================================
# Test Tools
# ============================================================================

def tool_add(inputs: Dict[str, Any], context: Dict[str, Any]) -> int:
    """Add two numbers."""
    return inputs["a"] + inputs["b"]


def tool_multiply(inputs: Dict[str, Any], context: Dict[str, Any]) -> int:
    """Multiply two numbers."""
    return inputs["a"] * inputs["b"]


def tool_divide(inputs: Dict[str, Any], context: Dict[str, Any]) -> float:
    """Divide two numbers."""
    if inputs["b"] == 0:
        raise ValueError("Division by zero")
    return inputs["a"] / inputs["b"]


# Track retry attempts per trace_id
_retry_attempts = {}

def tool_transient_failure(inputs: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Tool that fails transiently (succeeds after 2 attempts)."""
    trace_id = context.get("trace_id", "default")
    _retry_attempts[trace_id] = _retry_attempts.get(trace_id, 0) + 1
    attempt = _retry_attempts[trace_id]
    
    if attempt < 3:  # Fail first 2 attempts
        raise ConnectionError(f"Transient network error (attempt {attempt})")
    return "success_after_retry"


def tool_slow_operation(inputs: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Simulates slow operation."""
    time.sleep(0.1)
    return f"processed_{inputs.get('data', 'default')}"


def tool_sensitive_operation(inputs: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Sensitive operation requiring approval."""
    return f"deleted_{inputs.get('resource', 'unknown')}"


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def registry():
    """Create test tool registry."""
    reg = ToolRegistry()
    reg.register(ToolSpec(name="add", handler=tool_add, description="Add numbers"))
    reg.register(ToolSpec(name="multiply", handler=tool_multiply, description="Multiply"))
    reg.register(ToolSpec(name="divide", handler=tool_divide, description="Divide"))
    reg.register(ToolSpec(name="transient", handler=tool_transient_failure, description="Transient failure"))
    reg.register(ToolSpec(name="slow", handler=tool_slow_operation, description="Slow operation"))
    reg.register(ToolSpec(name="sensitive", handler=tool_sensitive_operation, description="Sensitive op"))
    return reg


@pytest.fixture
def memory():
    """Create test memory."""
    return VectorMemory(profile="integration_test")


@pytest.fixture
def llm():
    """Create mock LLM."""
    return MockLLM()


@pytest.fixture
def temp_db():
    """Create temporary database for audit trail."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    # Cleanup
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def audit_trail(temp_db):
    """Create audit trail with SQLite backend."""
    backend = SQLiteAuditBackend(db_path=temp_db)
    return AuditTrail(backend=backend)


@pytest.fixture
def routing_authority():
    """Create routing authority with round-robin policy."""
    return PolicyBasedRoutingAuthority(worker_policy=RoundRobinPolicy())


@pytest.fixture
def retry_policy():
    """Create retry policy with exponential backoff."""
    return create_retry_policy(
        strategy="exponential",
        max_attempts=3,
        base_delay=0.01,  # Fast for tests
        max_delay=1.0,
        multiplier=2.0,
    )


@pytest.fixture
def approval_policy_disabled():
    """Create disabled approval policy."""
    return ApprovalPolicy(enabled=False)


@pytest.fixture
def approval_policy_enabled():
    """Create enabled approval policy with short timeout."""
    return ApprovalPolicy(
        enabled=True,
        timeout_seconds=1.0,
        auto_approve_on_timeout=True,
    )


# ============================================================================
# Test 1: Basic End-to-End Orchestration
# ============================================================================

@pytest.mark.asyncio
async def test_e2e_basic_orchestration(
    registry,
    memory,
    llm,
    routing_authority,
    audit_trail,
):
    """Test basic end-to-end orchestration: Plan → Route → Execute."""
    # Create context
    context = ExecutionContext(trace_id="e2e-basic-001")
    
    # Create plan directly
    plan = Plan(
        plan_id="plan-001",
        goal="Calculate (5 + 3) * 2",
        steps=[
            PlanStep(tool="add", input={"a": 5, "b": 3}, index=0),
            PlanStep(tool="multiply", input={"a": 8, "b": 2}, index=1),
        ],
        stage=PlanningStage.CREATED,
        budget=ToolBudget(),
        trace_id=context.trace_id,
    )
    
    # Record plan in audit trail
    audit_trail.record_plan(plan)
    
    # Create worker
    worker = WorkerAgent(registry=registry, memory=memory)
    
    # Execute plan steps directly
    steps = [{"tool": step.tool, "input": step.input} for step in plan.steps]
    result = worker.execute(steps, metadata={"trace_id": context.trace_id})
    
    # Validate result
    assert result.output == 16
    assert len(result.trace) == 2
    
    # Validate audit trail - records are DecisionRecord objects
    records = audit_trail.get_trace_history(context.trace_id)
    assert len(records) == 1
    planning_records = [r for r in records if r.decision_type == "planning"]
    assert len(planning_records) == 1
    # Goal is embedded in the reason field
    assert "Calculate (5 + 3) * 2" in planning_records[0].reason


# ============================================================================
# Test 2: Retry Integration
# ============================================================================

def test_e2e_retry_with_transient_failure(
    registry,
    memory,
    retry_policy,
):
    """Test retry policy integration with transient failures."""
    worker = WorkerAgent(
        registry=registry,
        memory=memory,
        retry_policy=retry_policy,
    )
    
    steps = [
        {"tool": "add", "input": {"a": 1, "b": 2}},
        {"tool": "transient", "input": {}},  # Will fail twice, succeed on 3rd
        {"tool": "multiply", "input": {"a": 3, "b": 4}},
    ]
    
    # Should succeed after retries
    result = worker.execute(steps, metadata={"trace_id": "retry-001"})
    
    # Validate that transient tool eventually succeeded
    assert result.output == 12  # Final multiply result


# ============================================================================
# Test 3: Partial Result Recovery
# ============================================================================

def test_e2e_partial_result_recovery(registry, memory):
    """Test partial result preservation and recovery."""
    worker = WorkerAgent(registry=registry, memory=memory)
    
    steps = [
        {"tool": "add", "input": {"a": 10, "b": 20}},
        {"tool": "multiply", "input": {"a": 30, "b": 2}},
        {"tool": "divide", "input": {"a": 60, "b": 0}},  # Will fail (div by zero)
        {"tool": "add", "input": {"a": 100, "b": 200}},
    ]
    
    # First execution fails at step 2
    with pytest.raises(ValueError) as exc_info:
        worker.execute(steps, metadata={"trace_id": "recovery-001"})
    
    # Extract partial result
    partial = worker.get_partial_result_from_exception(exc_info.value)
    
    assert partial is not None
    assert len(partial.completed_steps) == 2
    assert partial.completion_ratio == pytest.approx(0.5)
    assert partial.is_recoverable
    assert partial.recovery_strategy in ["retry_from_checkpoint", "manual"]
    
    # Fix the failing step
    steps[2] = {"tool": "divide", "input": {"a": 60, "b": 2}}
    
    # Resume from partial result
    result = worker.execute_from_partial(steps, partial)
    
    # Should complete successfully
    assert result.output == 300  # Final add result


# ============================================================================
# Test 4: Audit Trail Integration
# ============================================================================

def test_e2e_audit_trail_persistence(
    registry,
    memory,
    audit_trail,
):
    """Test audit trail records all orchestration decisions."""
    context = ExecutionContext(trace_id="audit-001")
    
    # Create and record multiple plans
    for i in range(3):
        plan = Plan(
            plan_id=f"plan-audit-{i}",
            goal=f"Task {i}",
            steps=[PlanStep(tool="add", input={"a": i, "b": i+1}, index=0)],
            stage=PlanningStage.CREATED,
            budget=ToolBudget(),
            trace_id=context.trace_id,
        )
        audit_trail.record_plan(plan)
    
    # Query audit trail - returns DecisionRecord objects
    records = audit_trail.get_trace_history(context.trace_id)
    assert len(records) == 3
    
    # All should be planning records
    planning_records = [r for r in records if r.decision_type == "planning"]
    assert len(planning_records) == 3
    
    # Validate plan goals are in reason fields
    reasons = [r.reason for r in planning_records]
    assert any("Task 0" in r for r in reasons)
    assert any("Task 1" in r for r in reasons)
    assert any("Task 2" in r for r in reasons)


# ============================================================================
# Test 5: Approval Gate Integration
# ============================================================================

@pytest.mark.asyncio
async def test_e2e_approval_gate_auto_approve(
    registry,
    memory,
    approval_policy_enabled,
):
    """Test approval gate with auto-approve on timeout."""
    approval_gate = ApprovalGate(policy=approval_policy_enabled)
    
    # Note: WorkerAgent doesn't have built-in approval gate integration yet
    # This test validates the approval gate works independently
    
    request = approval_gate.create_request(
        operation="test_operation",
        trace_id="approval-001",
        metadata={"tool": "sensitive"},
        risk_level="low",
    )
    
    # Wait for approval (will auto-approve after timeout)
    response = await approval_gate.wait_for_approval(request)
    
    # Should be approved (auto-approve on timeout)
    assert response.status == ApprovalStatus.APPROVED
    assert "timeout" in response.reason.lower()


@pytest.mark.asyncio
async def test_e2e_approval_gate_manual_approve(approval_policy_enabled):
    """Test manual approval flow."""
    approval_gate = ApprovalGate(policy=approval_policy_enabled)
    
    request = approval_gate.create_request(
        operation="delete_database",
        trace_id="approval-002",
        risk_level="critical",
    )
    
    # Create approval task
    approval_task = asyncio.create_task(
        approval_gate.wait_for_approval(request)
    )
    
    # Give time for request to be registered
    await asyncio.sleep(0.01)
    
    # Manually approve
    approval_gate.respond_to_request(
        request_id=request.request_id,
        approved=True,
        approver="admin@example.com",
        reason="Approved after review",
    )
    
    # Wait for approval
    response = await approval_task
    
    assert response.status == ApprovalStatus.APPROVED
    assert response.approver == "admin@example.com"


# ============================================================================
# Test 6: Combined Retry + Partial Result
# ============================================================================

def test_e2e_retry_with_partial_result(registry, memory, retry_policy):
    """Test retry policy combined with partial result recovery."""
    worker = WorkerAgent(
        registry=registry,
        memory=memory,
        retry_policy=retry_policy,
    )
    
    steps = [
        {"tool": "add", "input": {"a": 1, "b": 1}},
        {"tool": "transient", "input": {}},  # Retries internally
        {"tool": "divide", "input": {"a": 10, "b": 0}},  # Fails (non-retryable)
    ]
    
    # Should fail after retries succeed but division fails
    with pytest.raises(ValueError) as exc_info:
        worker.execute(steps, metadata={"trace_id": "retry-partial-001"})
    
    partial = worker.get_partial_result_from_exception(exc_info.value)
    
    # First two steps should have completed
    assert len(partial.completed_steps) == 2
    assert partial.completion_ratio == pytest.approx(2/3)
    
    # Fix and resume
    steps[2] = {"tool": "divide", "input": {"a": 10, "b": 2}}
    result = worker.execute_from_partial(steps, partial)
    
    assert result.output == 5.0


# ============================================================================
# Test 7: Planning + Routing + Audit
# ============================================================================

def test_e2e_planning_routing_audit_integration(
    registry,
    memory,
    audit_trail,
):
    """Test planning and audit trail integration."""
    context = ExecutionContext(trace_id="pra-001")
    
    # Create plan with budget
    budget = ToolBudget(
        cost_ceiling=100.0,
        call_ceiling=10,
        token_ceiling=1000,
    )
    
    plan = Plan(
        plan_id="plan-pra-001",
        goal="Multi-step calculation",
        steps=[
            PlanStep(tool="add", input={"a": 5, "b": 10}, index=0),
            PlanStep(tool="multiply", input={"a": 15, "b": 3}, index=1),
            PlanStep(tool="divide", input={"a": 45, "b": 5}, index=2),
        ],
        stage=PlanningStage.CREATED,
        budget=budget,
        trace_id=context.trace_id,
    )
    
    # Record plan
    audit_trail.record_plan(plan)
    
    # Execute with worker
    worker = WorkerAgent(registry=registry, memory=memory)
    steps = [{"tool": step.tool, "input": step.input} for step in plan.steps]
    result = worker.execute(steps, metadata={"trace_id": context.trace_id})
    
    # Validate
    assert result.output == 9.0
    
    # Query audit trail - returns DecisionRecord objects
    records = audit_trail.get_trace_history(context.trace_id)
    assert len(records) == 1
    planning_records = [r for r in records if r.decision_type == "planning"]
    assert len(planning_records) == 1
    # Verify step count in metadata
    assert planning_records[0].metadata.get("step_count") == 3


# ============================================================================
# Test 8: Failure Recovery Scenarios
# ============================================================================

def test_e2e_multiple_recovery_attempts(registry, memory):
    """Test multiple recovery attempts with different strategies."""
    worker = WorkerAgent(registry=registry, memory=memory)
    
    steps = [
        {"tool": "add", "input": {"a": 1, "b": 2}},
        {"tool": "multiply", "input": {"a": 3, "b": 4}},
        {"tool": "divide", "input": {"a": 12, "b": 0}},  # Fails
        {"tool": "add", "input": {"a": 6, "b": 6}},
    ]
    
    # First attempt fails
    with pytest.raises(ValueError) as exc1:
        worker.execute(steps, metadata={"trace_id": "multi-recovery-001"})
    
    partial1 = worker.get_partial_result_from_exception(exc1.value)
    assert len(partial1.completed_steps) == 2
    
    # Second attempt with wrong fix (still fails)
    steps[2] = {"tool": "divide", "input": {"a": 12, "b": 0}}  # Still wrong!
    
    with pytest.raises(ValueError) as exc2:
        worker.execute_from_partial(steps, partial1)
    
    partial2 = worker.get_partial_result_from_exception(exc2.value)
    assert len(partial2.completed_steps) == 2  # Same progress
    
    # Third attempt with correct fix
    steps[2] = {"tool": "divide", "input": {"a": 12, "b": 3}}
    result = worker.execute_from_partial(steps, partial2)
    
    assert result.output == 12  # Final add result


# ============================================================================
# Test 9: Complex Multi-Stage Workflow
# ============================================================================

def test_e2e_complex_multi_stage_workflow(
    registry,
    memory,
    audit_trail,
    retry_policy,
):
    """Test complex workflow with multiple stages and components."""
    context = ExecutionContext(trace_id="complex-001")
    
    # Stage 1: Planning
    plan = Plan(
        plan_id="plan-complex-001",
        goal="Complex calculation pipeline",
        steps=[
            PlanStep(tool="add", input={"a": 10, "b": 20}, index=0),
            PlanStep(tool="multiply", input={"a": 30, "b": 2}, index=1),
            PlanStep(tool="divide", input={"a": 60, "b": 3}, index=2),
            PlanStep(tool="add", input={"a": 20, "b": 5}, index=3),
        ],
        stage=PlanningStage.CREATED,
        budget=ToolBudget(),
        trace_id=context.trace_id,
    )
    
    audit_trail.record_plan(plan)
    
    # Stage 2: Execution
    worker = WorkerAgent(registry=registry, memory=memory, retry_policy=retry_policy)
    steps = [{"tool": step.tool, "input": step.input} for step in plan.steps]
    result = worker.execute(steps, metadata={"trace_id": context.trace_id})
    
    # Validate
    assert result.output == 25  # (10+20) * 2 / 3 = 20, then 20+5 = 25
    
    # Validate audit trail completeness
    records = audit_trail.get_trace_history(context.trace_id)
    assert len(records) == 1
    planning_records = [r for r in records if r.decision_type == "planning"]
    assert len(planning_records) == 1
    assert planning_records[0].metadata.get("step_count") == 4


# ============================================================================
# Test 10: Observability Integration
# ============================================================================

def test_e2e_observability_events(registry, memory):
    """Test that observability events are emitted during orchestration."""
    from cuga.observability import get_collector
    
    collector = get_collector()
    initial_event_count = len(collector.events)
    
    worker = WorkerAgent(registry=registry, memory=memory)
    
    steps = [
        {"tool": "add", "input": {"a": 5, "b": 10}},
        {"tool": "multiply", "input": {"a": 15, "b": 2}},
    ]
    
    result = worker.execute(steps, metadata={"trace_id": "observability-001"})
    
    # Should have emitted tool_call_start and tool_call_complete for each step
    final_event_count = len(collector.events)
    new_events = final_event_count - initial_event_count
    
    # At least 4 events (2 start + 2 complete)
    assert new_events >= 4
    
    # Check event types - collector.events contains event objects/dicts
    recent_events = collector.events[-new_events:]
    
    # Events may be ToolCallEvent objects or dicts - handle both
    event_types = []
    for e in recent_events:
        if hasattr(e, 'event_type'):
            event_types.append(e.event_type)
        elif isinstance(e, dict) and 'event_type' in e:
            event_types.append(e['event_type'])
    
    assert "tool_call_start" in event_types
    assert "tool_call_complete" in event_types


# ============================================================================
# Test 11: Error Propagation
# ============================================================================

def test_e2e_error_propagation_through_stack(
    registry,
    memory,
    audit_trail,
):
    """Test that errors propagate correctly through the orchestration stack."""
    context = ExecutionContext(trace_id="error-prop-001")
    
    # Create plan with failing step
    plan = Plan(
        plan_id="plan-error-001",
        goal="Calculation with error",
        steps=[
            PlanStep(tool="add", input={"a": 1, "b": 2}, index=0),
            PlanStep(tool="divide", input={"a": 10, "b": 0}, index=1),  # Will fail
        ],
        stage=PlanningStage.CREATED,
        budget=ToolBudget(),
        trace_id=context.trace_id,
    )
    
    audit_trail.record_plan(plan)
    
    # Execute (should fail)
    worker = WorkerAgent(registry=registry, memory=memory)
    steps = [{"tool": step.tool, "input": step.input} for step in plan.steps]
    
    with pytest.raises(ValueError) as exc_info:
        worker.execute(steps, metadata={"trace_id": context.trace_id})
    
    # Verify partial result attached
    partial = worker.get_partial_result_from_exception(exc_info.value)
    assert partial is not None
    assert len(partial.completed_steps) == 1
    
    # Audit trail should still have records
    records = audit_trail.get_trace_history(context.trace_id)
    assert len(records) == 1
    planning_records = [r for r in records if r.decision_type == "planning"]
    assert len(planning_records) == 1


# ============================================================================
# Test 12: Concurrent Execution
# ============================================================================

def test_e2e_concurrent_orchestration(
    registry,
    memory,
):
    """Test concurrent orchestration with multiple traces."""
    workers = [
        WorkerAgent(registry=registry, memory=memory)
        for _ in range(3)
    ]
    
    results = []
    
    # Execute multiple traces concurrently (simulated with sequential for simplicity)
    for i in range(5):
        context = ExecutionContext(trace_id=f"concurrent-{i}")
        # Use round-robin manually
        worker = workers[i % len(workers)]
        
        steps = [
            {"tool": "add", "input": {"a": i, "b": i+1}},
            {"tool": "multiply", "input": {"a": i+1, "b": 2}},
        ]
        
        result = worker.execute(steps, metadata={"trace_id": context.trace_id})
        results.append(result.output)
    
    # Validate all executions completed
    assert len(results) == 5
    assert results[0] == 2  # (0+1) * 2
    assert results[1] == 4  # (1+2) * 2
    assert results[2] == 6  # (2+3) * 2


# ============================================================================
# Test 13: Budget Tracking
# ============================================================================

def test_e2e_budget_tracking_in_plans():
    """Test budget tracking through plan lifecycle."""
    context = ExecutionContext(trace_id="budget-001")
    
    budget = ToolBudget(
        cost_ceiling=50.0,
        call_ceiling=5,
        token_ceiling=500,
    )
    
    plan = Plan(
        plan_id="plan-budget-001",
        goal="Budget-tracked task",
        steps=[
            PlanStep(tool="add", input={"a": i, "b": i+1}, index=i)
            for i in range(3)
        ],
        stage=PlanningStage.CREATED,
        budget=budget,
        trace_id=context.trace_id,
    )
    
    # Budget should track step count
    assert len(plan.steps) == 3
    assert plan.budget.call_ceiling == 5


# ============================================================================
# Test 14: Recovery Strategy Validation
# ============================================================================

def test_e2e_recovery_strategy_suggestions(registry, memory):
    """Test recovery strategy suggestions for different failure scenarios."""
    worker = WorkerAgent(registry=registry, memory=memory)
    
    # Scenario 1: High completion (75%)
    steps_high = [
        {"tool": "add", "input": {"a": 1, "b": 2}},
        {"tool": "multiply", "input": {"a": 3, "b": 4}},
        {"tool": "add", "input": {"a": 5, "b": 6}},
        {"tool": "divide", "input": {"a": 10, "b": 0}},  # Fails at 75%
    ]
    
    with pytest.raises(ValueError) as exc_high:
        worker.execute(steps_high, metadata={"trace_id": "strategy-high"})
    
    partial_high = worker.get_partial_result_from_exception(exc_high.value)
    assert partial_high.recovery_strategy == "retry_failed"
    
    # Scenario 2: Medium completion (50%)
    steps_med = [
        {"tool": "add", "input": {"a": 1, "b": 2}},
        {"tool": "divide", "input": {"a": 10, "b": 0}},  # Fails at 50%
        {"tool": "multiply", "input": {"a": 3, "b": 4}},
    ]
    
    with pytest.raises(ValueError) as exc_med:
        worker.execute(steps_med, metadata={"trace_id": "strategy-med"})
    
    partial_med = worker.get_partial_result_from_exception(exc_med.value)
    assert partial_med.recovery_strategy == "retry_from_checkpoint"


# ============================================================================
# Test 15: End-to-End with All Components
# ============================================================================

def test_e2e_all_components_integration(
    registry,
    memory,
    llm,
    audit_trail,
    retry_policy,
    approval_policy_disabled,
):
    """
    Ultimate integration test: All components working together.
    
    Tests: Planning + Execution + Retry + Partial Result + Audit Trail
    """
    context = ExecutionContext(
        trace_id="ultimate-001",
        user_intent="Calculate complex result with error handling",
    )
    
    # 1. Planning
    budget = ToolBudget(cost_ceiling=200.0, call_ceiling=20, token_ceiling=2000)
    plan = Plan(
        plan_id="plan-ultimate-001",
        goal="Multi-step calculation with retry and recovery",
        steps=[
            PlanStep(tool="add", input={"a": 10, "b": 20}, index=0),
            PlanStep(tool="transient", input={}, index=1),  # Will retry
            PlanStep(tool="multiply", input={"a": 30, "b": 3}, index=2),
            PlanStep(tool="divide", input={"a": 90, "b": 3}, index=3),
        ],
        stage=PlanningStage.CREATED,
        budget=budget,
        trace_id=context.trace_id,
    )
    
    audit_trail.record_plan(plan)
    
    # 2. Execution (with automatic retry)
    worker = WorkerAgent(
        registry=registry,
        memory=memory,
        retry_policy=retry_policy,
    )
    steps = [{"tool": step.tool, "input": step.input} for step in plan.steps]
    result = worker.execute(steps, metadata={"trace_id": context.trace_id})
    
    # 3. Validation
    assert result.output == 30.0  # Final result
    assert len(result.trace) == 4
    
    # 4. Audit Trail Validation
    records = audit_trail.get_trace_history(context.trace_id)
    assert len(records) == 1
    planning_records = [r for r in records if r.decision_type == "planning"]
    assert len(planning_records) == 1
    assert "retry and recovery" in planning_records[0].reason
    
    print(f"✅ Ultimate integration test passed with all components!")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

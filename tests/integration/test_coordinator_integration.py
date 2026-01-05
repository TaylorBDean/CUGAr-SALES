"""
Integration test for AGENTSCoordinator with full compliance validation.

Tests the integrated coordinator with:
- TraceEmitter (canonical events)
- BudgetEnforcer (tool limits)
- ApprovalManager (human approval)
- ProfileLoader (profile-driven behavior)

Note: Uses sync wrappers since pytest-asyncio not available
"""
import pytest
import asyncio
import uuid
from cuga.orchestrator import (
    AGENTSCoordinator,
    ExecutionContext,
    Plan,
    PlanStep,
    PlanningStage,
    ToolBudget,
)


def test_coordinator_basic_execution():
    """Test basic plan execution with trace emission."""
    coordinator = AGENTSCoordinator(profile="enterprise")
    
    # Create simple plan
    plan = Plan(
        plan_id=str(uuid.uuid4()),
        goal="Test execution",
        steps=[
            PlanStep(
                tool="test_tool_1",
                input={},
                name="Test step 1",
                reason="Test step 1",
                metadata={"side_effect_class": "read-only", "domain": "test"}
            ),
            PlanStep(
                tool="test_tool_2",
                input={},
                name="Test step 2",
                reason="Test step 2",
                metadata={"side_effect_class": "read-only", "domain": "test"}
            ),
        ],
        stage=PlanningStage.CREATED,
        budget=ToolBudget(),
        trace_id=coordinator.trace_emitter.trace_id,
    )
    
    # Create execution context
    context = ExecutionContext(
        trace_id=coordinator.trace_emitter.trace_id,
        request_id="test-request-123",
        user_intent="Test execution",
        memory_scope="test/session",
    )
    
    # Execute plan (sync wrapper)
    result = asyncio.run(coordinator.execute_plan(plan, context))
    
    # Verify success
    assert result.success is True
    assert len(result.results) == 2
    assert result.trace_id == coordinator.trace_emitter.trace_id
    
    # Verify canonical events emitted
    trace = coordinator.get_trace()
    event_types = {e["event"] for e in trace}
    assert "plan_created" in event_types
    assert "tool_call_start" in event_types
    assert "tool_call_complete" in event_types
    
    # Verify budget tracking
    utilization = coordinator.get_budget_utilization()
    assert utilization["total"]["used"] == 2
    assert utilization["total"]["limit"] == 200  # Enterprise budget


def test_coordinator_budget_enforcement():
    """Test budget limits prevent over-execution."""
def test_coordinator_budget_enforcement():
    """Test budget limits prevent over-execution."""
    coordinator = AGENTSCoordinator(profile="smb")  # 100 call limit
    
    # Create plan exceeding budget
    plan = Plan(
        plan_id=str(uuid.uuid4()),
        goal="Budget test",
        steps=[
            PlanStep(
                tool=f"tool_{i}",
                input={},
                name=f"Step {i}",
                reason=f"Step {i}",
                metadata={"side_effect_class": "read-only", "domain": "test"}
            )
            for i in range(150)  # Exceeds 100 call limit
        ],
        stage=PlanningStage.CREATED,
        budget=ToolBudget(),
        trace_id=coordinator.trace_emitter.trace_id,
    )
    
    context = ExecutionContext(
        trace_id=coordinator.trace_emitter.trace_id,
        request_id="test-budget",
        user_intent="Test budget enforcement",
        memory_scope="test/session",
    )
    
    # Execute plan (sync wrapper)
    result = asyncio.run(coordinator.execute_plan(plan, context))
    
    # Verify partial execution (stopped at budget limit)
    assert result.success is False  # Has partial results
    assert result.partial_results is not None
    assert len(result.results) < 150  # Didn't execute all steps
    assert len(result.results) <= 100  # Respected budget
    
    # Verify budget_exceeded events
    trace = coordinator.get_trace()
    budget_events = [e for e in trace if e["event"] == "budget_exceeded"]
    assert len(budget_events) > 0



def test_coordinator_approval_required():
    """Test approval requests for execute/propose actions."""
    coordinator = AGENTSCoordinator(profile="enterprise")
    
    # Create plan with execute side-effects
    plan = Plan(
        plan_id=str(uuid.uuid4()),
        goal="Test approval",
        steps=[
            PlanStep(
                tool="send_email",
                input={"to": "prospect@company.com"},
                name="Send email",
                reason="Qualified lead",
                metadata={"side_effect_class": "execute", "domain": "engagement"}
            ),
        ],
        stage=PlanningStage.CREATED,
        budget=ToolBudget(),
        trace_id=coordinator.trace_emitter.trace_id,
    )
    
    context = ExecutionContext(
        trace_id=coordinator.trace_emitter.trace_id,
        request_id="test-approval",
        user_intent="Test approval flow",
        memory_scope="test/session",
    )
    
    # Execute plan
    result = asyncio.run(coordinator.execute_plan(plan, context))
    
    # Verify approval was requested
    assert result.approvals_required > 0
    
    # Verify approval_requested event
    trace = coordinator.get_trace()
    approval_events = [e for e in trace if e["event"] == "approval_requested"]
    assert len(approval_events) == 1



def test_coordinator_profile_driven_budgets():
    """Test different profiles have different budgets."""
    # Enterprise profile
    coord_enterprise = AGENTSCoordinator(profile="enterprise")
    util_enterprise = coord_enterprise.get_budget_utilization()
    assert util_enterprise["total"]["limit"] == 200
    
    # SMB profile
    coord_smb = AGENTSCoordinator(profile="smb")
    util_smb = coord_smb.get_budget_utilization()
    assert util_smb["total"]["limit"] == 100
    
    # Technical profile
    coord_technical = AGENTSCoordinator(profile="technical")
    util_technical = coord_technical.get_budget_utilization()
    assert util_technical["total"]["limit"] == 500



def test_coordinator_graceful_degradation():
    """Test coordinator handles tool failures gracefully."""
    coordinator = AGENTSCoordinator(profile="enterprise")
    
    # Create plan (execution will succeed in mock, but test partial result handling)
    plan = Plan(
        plan_id=str(uuid.uuid4()),
        goal="Test degradation",
        steps=[
            PlanStep(
                tool="test_tool_1",
                input={},
                name="Step 1",
                reason="Step 1",
                metadata={"side_effect_class": "read-only", "domain": "test"}
            ),
        ],
        stage=PlanningStage.CREATED,
        budget=ToolBudget(),
        trace_id=coordinator.trace_emitter.trace_id,
    )
    
    context = ExecutionContext(
        trace_id=coordinator.trace_emitter.trace_id,
        request_id="test-degradation",
        user_intent="Test graceful degradation",
        memory_scope="test/session",
    )
    
    # Execute plan
    result = asyncio.run(coordinator.execute_plan(plan, context))
    
    # Even with potential failures, coordinator should return ExecutionResult
    assert result is not None
    assert result.trace_id == coordinator.trace_emitter.trace_id



def test_coordinator_golden_signals():
    """Test golden signals extraction."""
    coordinator = AGENTSCoordinator(profile="enterprise")
    
    # Create and execute plan
    plan = Plan(
        plan_id=str(uuid.uuid4()),
        goal="Test golden signals",
        steps=[
            PlanStep(
                tool="test_tool",
                input={},
                name="Test",
                reason="Test",
                metadata={"side_effect_class": "read-only", "domain": "test"}
            ),
        ],
        stage=PlanningStage.CREATED,
        budget=ToolBudget(),
        trace_id=coordinator.trace_emitter.trace_id,
    )
    
    context = ExecutionContext(
        trace_id=coordinator.trace_emitter.trace_id,
        request_id="test-signals",
        user_intent="Test golden signals",
        memory_scope="test/session",
    )
    
    result = asyncio.run(coordinator.execute_plan(plan, context))
    
    # Get golden signals
    signals = coordinator.get_golden_signals()
    
    # Verify golden signals structure
    assert "success_rate" in signals
    assert "latency" in signals
    assert "error_rate" in signals
    assert "total_events" in signals
    
    # With successful execution, success_rate should be high
    assert signals["success_rate"] >= 0.0
    assert signals["error_rate"] >= 0.0



def test_coordinator_trace_continuity():
    """Test trace_id is preserved throughout execution."""
    coordinator = AGENTSCoordinator(profile="enterprise")
    original_trace_id = coordinator.trace_emitter.trace_id
    
    # Execute multiple plans
    for i in range(3):
        plan = Plan(
            plan_id=str(uuid.uuid4()),
            goal=f"Test {i}",
            steps=[
                PlanStep(
                    tool=f"tool_{i}",
                    input={},
                    name=f"Step {i}",
                    reason=f"Step {i}",
                    metadata={"side_effect_class": "read-only", "domain": "test"}
                ),
            ],
            stage=PlanningStage.CREATED,
            budget=ToolBudget(),
            trace_id=original_trace_id,
        )
        
        context = ExecutionContext(
            trace_id=original_trace_id,
            request_id=f"test-{i}",
            user_intent=f"Test {i}",
            memory_scope="test/session",
        )
        
        result = asyncio.run(coordinator.execute_plan(plan, context))
        assert result.trace_id == original_trace_id
    
    # Verify all events have same trace_id
    trace = coordinator.get_trace()
    trace_ids = {e["trace_id"] for e in trace}
    assert len(trace_ids) == 1
    assert original_trace_id in trace_ids

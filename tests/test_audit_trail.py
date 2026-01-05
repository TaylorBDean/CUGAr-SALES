"""
Tests for AuditTrail integration with CoordinatorAgent.

This test suite validates:
- AuditTrail field and initialization in CoordinatorAgent
- Recording routing decisions during orchestrate()
- Recording plans during orchestrate()
- Query and retrieval of audit records
- Different backend implementations (JSON, SQLite)
- Trace ID continuity across audit records
- Audit trail persistence across process restarts

Version: 1.3.2
Author: Orchestration Team
"""

import asyncio
import os
import shutil
import tempfile
from pathlib import Path
from typing import List

import pytest

from cuga.modular.agents import CoordinatorAgent, PlannerAgent, WorkerAgent
from cuga.modular.tools import ToolRegistry, ToolSpec
from cuga.memory.vector import VectorMemory
from cuga.orchestrator.audit import (
    AuditTrail,
    DecisionRecord,
    create_audit_trail,
    JSONAuditBackend,
    SQLiteAuditBackend,
)
from cuga.orchestrator.protocol import ExecutionContext


@pytest.fixture
def temp_audit_dir():
    """Create temporary directory for audit trail storage."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_tool_registry():
    """Create mock tool registry with test tools."""
    def mock_search(inputs, ctx):
        query = inputs.get("query", "")
        return {"results": [f"Result for: {query}"]}
    
    def mock_calculator(inputs, ctx):
        operation = inputs.get("operation", "")
        return {"result": 42}
    
    search_tool = ToolSpec(name="search", description="Search for information", handler=mock_search)
    calculator_tool = ToolSpec(name="calculator", description="Perform calculations", handler=mock_calculator)
    
    return ToolRegistry(tools=[search_tool, calculator_tool])


@pytest.fixture
def mock_memory():
    """Create mock VectorMemory."""
    return VectorMemory()


@pytest.fixture
def mock_planner(mock_tool_registry):
    """Create mock PlannerAgent."""
    class MockPlanResult:
        def __init__(self):
            # Return 2 steps to match test expectations
            self.steps = [
                {"tool": "search", "name": "Search step", "input": {"query": "test"}},
                {"tool": "calculator", "name": "Calculate step", "input": {"operation": "2+2"}},
            ]
    
    class MockPlanner:
        def plan(self, goal, metadata=None):
            return MockPlanResult()
    
    planner = MockPlanner()
    planner.tool_registry = mock_tool_registry
    return planner


@pytest.fixture
def mock_workers(mock_tool_registry):
    """Create mock WorkerAgent list."""
    class MockWorker:
        def __init__(self, worker_id: int):
            self.worker_id = worker_id
            self.tool_registry = mock_tool_registry
        
        def execute(self, steps, metadata=None):
            worker_id = self.worker_id  # Capture worker_id in closure
            
            class MockResult:
                def __init__(self):
                    self.status = "success"
                    self.result = {"output": f"Worker {worker_id} executed"}
                    self.output = f"Worker {worker_id} executed"  # Add output attribute
                    self.trace = []
            
            return MockResult()
    
    return [MockWorker(i) for i in range(3)]


@pytest.fixture
def coordinator_with_default_audit(mock_planner, mock_workers, mock_memory):
    """Create CoordinatorAgent with default audit trail."""
    return CoordinatorAgent(
        planner=mock_planner,
        workers=mock_workers,
        memory=mock_memory,
    )


@pytest.fixture
def coordinator_with_json_audit(mock_planner, mock_workers, mock_memory, temp_audit_dir):
    """Create CoordinatorAgent with JSON audit trail."""
    audit_path = Path(temp_audit_dir) / "decisions.jsonl"
    audit_trail = create_audit_trail(backend_type="json", storage_path=audit_path)
    
    return CoordinatorAgent(
        planner=mock_planner,
        workers=mock_workers,
        memory=mock_memory,
        audit_trail=audit_trail,
    )


@pytest.fixture
def coordinator_with_sqlite_audit(mock_planner, mock_workers, mock_memory, temp_audit_dir):
    """Create CoordinatorAgent with SQLite audit trail."""
    audit_path = Path(temp_audit_dir) / "decisions.db"
    audit_trail = create_audit_trail(backend_type="sqlite", storage_path=audit_path)
    
    return CoordinatorAgent(
        planner=mock_planner,
        workers=mock_workers,
        memory=mock_memory,
        audit_trail=audit_trail,
    )


# ========================================
# Test: AuditTrail Field & Initialization
# ========================================

def test_coordinator_has_audit_trail_field(coordinator_with_default_audit):
    """Test that CoordinatorAgent has audit_trail field."""
    assert hasattr(coordinator_with_default_audit, "audit_trail")
    assert coordinator_with_default_audit.audit_trail is not None


def test_default_audit_trail_initialization(coordinator_with_default_audit):
    """Test that default audit trail is SQLite backend."""
    audit_trail = coordinator_with_default_audit.audit_trail
    assert isinstance(audit_trail, AuditTrail)
    assert isinstance(audit_trail.backend, SQLiteAuditBackend)


def test_custom_json_audit_trail(coordinator_with_json_audit):
    """Test that custom JSON audit trail is used."""
    audit_trail = coordinator_with_json_audit.audit_trail
    assert isinstance(audit_trail, AuditTrail)
    assert isinstance(audit_trail.backend, JSONAuditBackend)


def test_custom_sqlite_audit_trail(coordinator_with_sqlite_audit):
    """Test that custom SQLite audit trail is used."""
    audit_trail = coordinator_with_sqlite_audit.audit_trail
    assert isinstance(audit_trail, AuditTrail)
    assert isinstance(audit_trail.backend, SQLiteAuditBackend)


# ========================================
# Test: Plan Recording
# ========================================

@pytest.mark.asyncio
async def test_orchestrate_records_plan(coordinator_with_sqlite_audit):
    """Test that orchestrate() records plan to audit trail."""
    context = ExecutionContext(trace_id="test-trace-plan")
    
    # Run orchestration
    results = []
    async for stage_result in coordinator_with_sqlite_audit.orchestrate(
        goal="Test goal",
        context=context,
    ):
        results.append(stage_result)
    
    # Query audit trail for plan records
    audit_trail = coordinator_with_sqlite_audit.audit_trail
    planning_records = audit_trail.get_planning_history(limit=10)
    
    assert len(planning_records) > 0, "No planning records found"
    
    # Check that plan record has correct fields
    plan_record = planning_records[0]
    assert plan_record.trace_id == "test-trace-plan"
    assert plan_record.decision_type == "planning"
    assert plan_record.stage == "plan"
    assert "step_count" in plan_record.metadata
    assert plan_record.metadata["step_count"] >= 1  # At least 1 step


@pytest.mark.asyncio
async def test_plan_record_contains_budget_info(coordinator_with_sqlite_audit):
    """Test that plan record contains budget information."""
    context = ExecutionContext(trace_id="test-trace-budget")
    
    # Run orchestration
    results = []
    async for stage_result in coordinator_with_sqlite_audit.orchestrate(
        goal="Test budget tracking",
        context=context,
    ):
        results.append(stage_result)
    
    # Query audit trail
    audit_trail = coordinator_with_sqlite_audit.audit_trail
    trace_records = audit_trail.get_trace_history("test-trace-budget")
    
    # Find plan record
    plan_records = [r for r in trace_records if r.decision_type == "planning"]
    assert len(plan_records) > 0
    
    plan_record = plan_records[0]
    assert "cost_ceiling" in plan_record.metadata or "budget_ceiling" in plan_record.metadata
    assert "estimated_total_cost" in plan_record.metadata or "estimated_cost" in plan_record.metadata


# ========================================
# Test: Routing Decision Recording
# ========================================

@pytest.mark.asyncio
async def test_orchestrate_records_routing_decision(coordinator_with_sqlite_audit):
    """Test that orchestrate() records routing decision to audit trail."""
    context = ExecutionContext(trace_id="test-trace-routing")
    
    # Run orchestration
    results = []
    async for stage_result in coordinator_with_sqlite_audit.orchestrate(
        goal="Test routing",
        context=context,
    ):
        results.append(stage_result)
    
    # Query audit trail for routing records
    audit_trail = coordinator_with_sqlite_audit.audit_trail
    routing_records = audit_trail.get_routing_history(limit=10)
    
    assert len(routing_records) > 0, "No routing records found"
    
    # Check routing record fields
    routing_record = routing_records[0]
    assert routing_record.trace_id == "test-trace-routing"
    assert routing_record.decision_type == "routing"
    assert routing_record.stage == "route"
    assert routing_record.target.startswith("worker-")  # e.g., "worker-0"
    assert len(routing_record.alternatives) >= 2  # At least 2 other workers


@pytest.mark.asyncio
async def test_routing_record_contains_strategy_info(coordinator_with_sqlite_audit):
    """Test that routing record contains strategy metadata."""
    context = ExecutionContext(trace_id="test-trace-strategy")
    
    # Run orchestration
    results = []
    async for stage_result in coordinator_with_sqlite_audit.orchestrate(
        goal="Test strategy",
        context=context,
    ):
        results.append(stage_result)
    
    # Query audit trail
    audit_trail = coordinator_with_sqlite_audit.audit_trail
    trace_records = audit_trail.get_trace_history("test-trace-strategy")
    
    # Find routing record
    routing_records = [r for r in trace_records if r.decision_type == "routing"]
    assert len(routing_records) > 0
    
    routing_record = routing_records[0]
    assert "strategy" in routing_record.metadata


# ========================================
# Test: Trace Queries
# ========================================

@pytest.mark.asyncio
async def test_get_trace_history_returns_both_plan_and_routing(coordinator_with_sqlite_audit):
    """Test that trace history includes both planning and routing records."""
    context = ExecutionContext(trace_id="test-trace-combined")
    
    # Run orchestration
    results = []
    async for stage_result in coordinator_with_sqlite_audit.orchestrate(
        goal="Test combined trace",
        context=context,
    ):
        results.append(stage_result)
    
    # Query trace history
    audit_trail = coordinator_with_sqlite_audit.audit_trail
    trace_records = audit_trail.get_trace_history("test-trace-combined")
    
    assert len(trace_records) >= 2, "Expected at least plan + routing records"
    
    # Check that we have both types
    decision_types = {r.decision_type for r in trace_records}
    assert "planning" in decision_types
    assert "routing" in decision_types


@pytest.mark.asyncio
async def test_trace_records_chronological_order(coordinator_with_sqlite_audit):
    """Test that trace records are returned in chronological order."""
    context = ExecutionContext(trace_id="test-trace-order")
    
    # Run orchestration
    results = []
    async for stage_result in coordinator_with_sqlite_audit.orchestrate(
        goal="Test chronological order",
        context=context,
    ):
        results.append(stage_result)
    
    # Query trace history
    audit_trail = coordinator_with_sqlite_audit.audit_trail
    trace_records = audit_trail.get_trace_history("test-trace-order")
    
    # Plan should come before routing
    timestamps = [r.timestamp for r in trace_records]
    assert timestamps == sorted(timestamps), "Records not in chronological order"
    
    # Find plan and routing records
    plan_record = next((r for r in trace_records if r.decision_type == "planning"), None)
    routing_record = next((r for r in trace_records if r.decision_type == "routing"), None)
    
    assert plan_record is not None
    assert routing_record is not None
    assert plan_record.timestamp < routing_record.timestamp


# ========================================
# Test: Backend Switching
# ========================================

def test_json_backend_stores_records(coordinator_with_json_audit, temp_audit_dir):
    """Test that JSON backend persists records to file."""
    audit_trail = coordinator_with_json_audit.audit_trail
    json_path = Path(temp_audit_dir) / "decisions.jsonl"
    
    # Manually record a decision (bypass orchestrate for simplicity)
    from cuga.orchestrator.routing import (
        RoutingDecision,
        RoutingCandidate,
        RoutingStrategy,
        RoutingDecisionType,
    )
    
    decision = RoutingDecision(
        strategy=RoutingStrategy.ROUND_ROBIN,
        decision_type=RoutingDecisionType.WORKER_SELECTION,
        selected=RoutingCandidate(id="worker-0", name="Worker 0", type="worker", available=True),
        alternatives=[
            RoutingCandidate(id="worker-1", name="Worker 1", type="worker", available=True),
        ],
        reason="Test routing",
        confidence=1.0,
        metadata={},
    )
    
    audit_trail.record_routing_decision(decision, trace_id="test-json", stage="route")
    
    # Check file exists and has content
    assert json_path.exists()
    with open(json_path, "r") as f:
        lines = f.readlines()
        assert len(lines) >= 1


def test_sqlite_backend_stores_records(coordinator_with_sqlite_audit, temp_audit_dir):
    """Test that SQLite backend persists records to database."""
    audit_trail = coordinator_with_sqlite_audit.audit_trail
    db_path = Path(temp_audit_dir) / "decisions.db"
    
    # Manually record a decision
    from cuga.orchestrator.routing import (
        RoutingDecision,
        RoutingCandidate,
        RoutingStrategy,
        RoutingDecisionType,
    )
    
    decision = RoutingDecision(
        strategy=RoutingStrategy.ROUND_ROBIN,
        decision_type=RoutingDecisionType.WORKER_SELECTION,
        selected=RoutingCandidate(id="worker-0", name="Worker 0", type="worker", available=True),
        alternatives=[],
        reason="Test SQLite",
        confidence=1.0,
        metadata={},
    )
    
    audit_trail.record_routing_decision(decision, trace_id="test-sqlite", stage="route")
    
    # Check database file exists
    assert db_path.exists()
    
    # Verify record can be queried
    records = audit_trail.get_trace_history("test-sqlite")
    assert len(records) >= 1


# ========================================
# Test: Persistence Across Instances
# ========================================

def test_audit_trail_persists_across_coordinator_instances(
    mock_planner, mock_workers, mock_memory, temp_audit_dir
):
    """Test that audit trail persists across multiple CoordinatorAgent instances."""
    db_path = Path(temp_audit_dir) / "shared_decisions.db"
    
    # First coordinator instance
    audit_trail_1 = create_audit_trail(backend_type="sqlite", storage_path=db_path)
    coordinator_1 = CoordinatorAgent(
        planner=mock_planner,
        workers=mock_workers,
        memory=mock_memory,
        audit_trail=audit_trail_1,
    )
    
    # Manually record decision with first coordinator
    from cuga.orchestrator.routing import (
        RoutingDecision,
        RoutingCandidate,
        RoutingStrategy,
        RoutingDecisionType,
    )
    
    decision = RoutingDecision(
        strategy=RoutingStrategy.ROUND_ROBIN,
        decision_type=RoutingDecisionType.WORKER_SELECTION,
        selected=RoutingCandidate(id="worker-0", name="Worker 0", type="worker", available=True),
        alternatives=[],
        reason="First instance",
        confidence=1.0,
        metadata={},
    )
    
    coordinator_1.audit_trail.record_routing_decision(
        decision, trace_id="shared-trace", stage="route"
    )
    
    # Second coordinator instance with same database
    audit_trail_2 = create_audit_trail(backend_type="sqlite", storage_path=db_path)
    coordinator_2 = CoordinatorAgent(
        planner=mock_planner,
        workers=mock_workers,
        memory=mock_memory,
        audit_trail=audit_trail_2,
    )
    
    # Query from second instance
    records = coordinator_2.audit_trail.get_trace_history("shared-trace")
    assert len(records) >= 1
    assert records[0].reason == "First instance"


# ========================================
# Test: Error Handling
# ========================================

@pytest.mark.asyncio
async def test_orchestrate_continues_on_audit_trail_error(coordinator_with_sqlite_audit, monkeypatch):
    """Test that orchestrate() continues if audit trail recording fails."""
    # Monkeypatch audit trail to raise error
    def failing_record_plan(*args, **kwargs):
        raise RuntimeError("Simulated audit failure")
    
    monkeypatch.setattr(
        coordinator_with_sqlite_audit.audit_trail,
        "record_plan",
        failing_record_plan,
    )
    
    context = ExecutionContext(trace_id="test-trace-error")
    
    # Run orchestration - should complete despite audit error
    results = []
    async for stage_result in coordinator_with_sqlite_audit.orchestrate(
        goal="Test error handling",
        context=context,
    ):
        results.append(stage_result)
    
    # Check that orchestration completed
    stages = [r["stage"] for r in results]
    stage_values = [s.value if hasattr(s, 'value') else s for s in stages]
    assert "complete" in stage_values or "COMPLETE" in stage_values


# ========================================
# Test: Query Methods
# ========================================

def test_get_recent_returns_latest_records(coordinator_with_sqlite_audit):
    """Test that get_recent() returns latest records."""
    from cuga.orchestrator.routing import (
        RoutingDecision,
        RoutingCandidate,
        RoutingStrategy,
        RoutingDecisionType,
    )
    
    audit_trail = coordinator_with_sqlite_audit.audit_trail
    
    # Record multiple decisions
    for i in range(5):
        decision = RoutingDecision(
            strategy=RoutingStrategy.ROUND_ROBIN,
            decision_type=RoutingDecisionType.WORKER_SELECTION,
            selected=RoutingCandidate(
                id=f"worker-{i}", name=f"Worker {i}", type="worker", available=True
            ),
            alternatives=[],
            reason=f"Decision {i}",
            confidence=1.0,
            metadata={},
        )
        audit_trail.record_routing_decision(
            decision, trace_id=f"trace-{i}", stage="route"
        )
    
    # Get recent records
    recent = audit_trail.get_recent(limit=3)
    assert len(recent) == 3
    
    # Should be in reverse chronological order (newest first)
    assert recent[0].reason == "Decision 4"
    assert recent[1].reason == "Decision 3"
    assert recent[2].reason == "Decision 2"


def test_get_routing_history_filters_by_type(coordinator_with_sqlite_audit):
    """Test that get_routing_history() only returns routing records."""
    from cuga.orchestrator.routing import (
        RoutingDecision,
        RoutingCandidate,
        RoutingStrategy,
        RoutingDecisionType,
    )
    from cuga.orchestrator.planning import Plan, PlanStep, ToolBudget, PlanningStage
    
    audit_trail = coordinator_with_sqlite_audit.audit_trail
    
    # Record routing decision
    routing_decision = RoutingDecision(
        strategy=RoutingStrategy.ROUND_ROBIN,
        decision_type=RoutingDecisionType.WORKER_SELECTION,
        selected=RoutingCandidate(id="worker-0", name="Worker 0", type="worker", available=True),
        alternatives=[],
        reason="Routing test",
        confidence=1.0,
        metadata={},
    )
    audit_trail.record_routing_decision(routing_decision, trace_id="test-filter", stage="route")
    
    # Record plan
    plan = Plan(
        plan_id="plan-123",
        trace_id="test-filter",
        goal="Test goal",
        steps=[
            PlanStep(
                tool="search",
                input={"query": "test"},
                reason="Search test",
                estimated_cost=0.1,
                estimated_tokens=10,
            )
        ],
        budget=ToolBudget(cost_ceiling=100.0),
        stage=PlanningStage.CREATED,
    )
    audit_trail.record_plan(plan, stage="plan")
    
    # Get routing history
    routing_records = audit_trail.get_routing_history(limit=10)
    
    # Should only contain routing decisions
    assert all(r.decision_type == "routing" for r in routing_records)
    assert len([r for r in routing_records if r.reason == "Routing test"]) >= 1


def test_get_planning_history_filters_by_type(coordinator_with_sqlite_audit):
    """Test that get_planning_history() only returns planning records."""
    from cuga.orchestrator.routing import (
        RoutingDecision,
        RoutingCandidate,
        RoutingStrategy,
        RoutingDecisionType,
    )
    from cuga.orchestrator.planning import Plan, PlanStep, ToolBudget, PlanningStage
    
    audit_trail = coordinator_with_sqlite_audit.audit_trail
    
    # Record routing decision
    routing_decision = RoutingDecision(
        strategy=RoutingStrategy.ROUND_ROBIN,
        decision_type=RoutingDecisionType.WORKER_SELECTION,
        selected=RoutingCandidate(id="worker-0", name="Worker 0", type="worker", available=True),
        alternatives=[],
        reason="Routing test",
        confidence=1.0,
        metadata={},
    )
    audit_trail.record_routing_decision(routing_decision, trace_id="test-filter-2", stage="route")
    
    # Record plan
    plan = Plan(
        plan_id="plan-456",
        trace_id="test-filter-2",
        goal="Test goal",
        steps=[
            PlanStep(
                tool="calculator",
                input={"operation": "2+2"},
                reason="Calculate test",
                estimated_cost=0.1,
                estimated_tokens=10,
            )
        ],
        budget=ToolBudget(cost_ceiling=100.0),
        stage=PlanningStage.CREATED,
    )
    audit_trail.record_plan(plan, stage="plan")
    
    # Get planning history
    planning_records = audit_trail.get_planning_history(limit=10)
    
    # Should only contain planning decisions
    assert all(r.decision_type == "planning" for r in planning_records)
    assert len([r for r in planning_records if "plan-456" in r.target]) >= 1

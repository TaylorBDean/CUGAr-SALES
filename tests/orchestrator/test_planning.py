"""
Tests for deterministic routing and planning with audit trails.

Validates:
1. Determinism: Same inputs → same plan/routing decisions
2. Idempotency: Repeated transitions are safe
3. Budget enforcement: Plans respect budget constraints
4. Audit persistence: Decisions are recorded and queryable
"""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

import pytest

from cuga.orchestrator import (
    # Planning
    PlanningAuthority,
    ToolRankingPlanner,
    Plan,
    PlanStep,
    PlanningStage,
    ToolBudget,
    BudgetError,
    # Routing
    RoutingAuthority,
    PolicyBasedRoutingAuthority,
    RoundRobinPolicy,
    CapabilityBasedPolicy,
    RoutingContext,
    RoutingCandidate,
    RoutingStrategy,
    # Audit
    AuditTrail,
    DecisionRecord,
    JSONAuditBackend,
    SQLiteAuditBackend,
)


class TestToolBudget:
    """Test tool budget tracking and enforcement."""
    
    def test_budget_initialization(self):
        """Test budget initializes with defaults."""
        budget = ToolBudget()
        assert budget.cost_ceiling == 100.0
        assert budget.cost_spent == 0.0
        assert budget.within_limits()
    
    def test_budget_cost_tracking(self):
        """Test cost tracking updates correctly."""
        budget = ToolBudget(cost_ceiling=10.0)
        budget = budget.with_cost(5.0)
        assert budget.cost_spent == 5.0
        assert budget.remaining_cost() == 5.0
        assert budget.within_limits()
        
        budget = budget.with_cost(6.0)
        assert budget.cost_spent == 11.0
        assert not budget.within_limits()
    
    def test_budget_call_tracking(self):
        """Test call tracking updates correctly."""
        budget = ToolBudget(call_ceiling=5)
        budget = budget.with_call()
        assert budget.call_spent == 1
        assert budget.remaining_calls() == 4
        assert budget.within_limits()
    
    def test_budget_token_tracking(self):
        """Test token tracking updates correctly."""
        budget = ToolBudget(token_ceiling=100)
        budget = budget.with_tokens(50)
        assert budget.token_spent == 50
        assert budget.remaining_tokens() == 50
        assert budget.within_limits()


class TestPlanningStageTransitions:
    """Test plan state machine transitions."""
    
    def test_valid_transition_created_to_routed(self):
        """Test valid transition from CREATED to ROUTED."""
        plan = Plan(
            plan_id="test",
            goal="test goal",
            steps=[],
            stage=PlanningStage.CREATED,
            budget=ToolBudget(),
            trace_id="trace-1",
        )
        
        routed_plan = plan.transition_to(PlanningStage.ROUTED)
        assert routed_plan.stage == PlanningStage.ROUTED
        assert routed_plan.routed_at is not None
        assert routed_plan.plan_id == plan.plan_id
    
    def test_invalid_transition_created_to_executing(self):
        """Test invalid transition raises error."""
        plan = Plan(
            plan_id="test",
            goal="test goal",
            steps=[],
            stage=PlanningStage.CREATED,
            budget=ToolBudget(),
            trace_id="trace-1",
        )
        
        with pytest.raises(ValueError, match="Invalid transition"):
            plan.transition_to(PlanningStage.EXECUTING)
    
    def test_full_lifecycle_transition(self):
        """Test full plan lifecycle transitions."""
        plan = Plan(
            plan_id="test",
            goal="test goal",
            steps=[],
            stage=PlanningStage.CREATED,
            budget=ToolBudget(),
            trace_id="trace-1",
        )
        
        plan = plan.transition_to(PlanningStage.ROUTED)
        assert plan.stage == PlanningStage.ROUTED
        
        plan = plan.transition_to(PlanningStage.EXECUTING)
        assert plan.stage == PlanningStage.EXECUTING
        assert plan.started_at is not None
        
        plan = plan.transition_to(PlanningStage.COMPLETED)
        assert plan.stage == PlanningStage.COMPLETED
        assert plan.completed_at is not None
    
    def test_terminal_stage_no_transitions(self):
        """Test terminal stages cannot transition."""
        plan = Plan(
            plan_id="test",
            goal="test goal",
            steps=[],
            stage=PlanningStage.COMPLETED,
            budget=ToolBudget(),
            trace_id="trace-1",
        )
        
        with pytest.raises(ValueError, match="Invalid transition"):
            plan.transition_to(PlanningStage.CREATED)


class TestToolRankingPlanner:
    """Test tool ranking planner determinism."""
    
    def test_deterministic_planning_same_inputs(self):
        """Test same inputs produce same plan."""
        planner = ToolRankingPlanner(max_steps=3)
        
        tools = [
            {"name": "tool1", "description": "search web", "cost": 1.0, "tokens": 100},
            {"name": "tool2", "description": "query database", "cost": 0.5, "tokens": 50},
            {"name": "tool3", "description": "web scraper", "cost": 2.0, "tokens": 200},
        ]
        
        constraints = {"available_tools": tools}
        
        plan1 = planner.create_plan(
            "search web for python docs",
            trace_id="trace-1",
            constraints=constraints,
        )
        
        plan2 = planner.create_plan(
            "search web for python docs",
            trace_id="trace-2",
            constraints=constraints,
        )
        
        # Plans should have same tool selection and order
        assert len(plan1.steps) == len(plan2.steps)
        for step1, step2 in zip(plan1.steps, plan2.steps):
            assert step1.tool == step2.tool
            assert step1.reason == step2.reason
    
    def test_budget_enforcement(self):
        """Test planner respects budget constraints."""
        planner = ToolRankingPlanner(max_steps=5)
        
        tools = [
            {"name": "tool1", "description": "expensive", "cost": 60.0, "tokens": 5000},
            {"name": "tool2", "description": "cheap", "cost": 0.1, "tokens": 10},
        ]
        
        budget = ToolBudget(cost_ceiling=10.0, call_ceiling=10, token_ceiling=1000)
        constraints = {"available_tools": tools}
        
        plan = planner.create_plan(
            "test goal",
            trace_id="trace-1",
            budget=budget,
            constraints=constraints,
        )
        
        # Should only include cheap tool
        assert len(plan.steps) == 1
        assert plan.steps[0].tool == "tool2"
        assert plan.estimated_total_cost() <= budget.cost_ceiling
    
    def test_insufficient_budget_raises_error(self):
        """Test insufficient budget raises BudgetError."""
        planner = ToolRankingPlanner()
        
        tools = [
            {"name": "tool1", "description": "expensive", "cost": 200.0, "tokens": 10000},
        ]
        
        budget = ToolBudget(cost_ceiling=10.0)
        constraints = {"available_tools": tools}
        
        with pytest.raises(BudgetError) as exc_info:
            planner.create_plan(
                "test goal",
                trace_id="trace-1",
                budget=budget,
                constraints=constraints,
            )
        
        assert exc_info.value.required_cost == 200.0
        assert exc_info.value.available_cost == 10.0
    
    def test_plan_validation(self):
        """Test plan validation checks budget sufficiency."""
        planner = ToolRankingPlanner()
        
        # Create plan with insufficient budget
        plan = Plan(
            plan_id="test",
            goal="test",
            steps=[
                PlanStep(
                    tool="tool1",
                    input={},
                    estimated_cost=100.0,
                )
            ],
            stage=PlanningStage.CREATED,
            budget=ToolBudget(cost_ceiling=10.0),
            trace_id="trace-1",
        )
        
        with pytest.raises(ValueError, match="Insufficient budget"):
            planner.validate_plan(plan)


class TestRoutingDeterminism:
    """Test routing decision determinism."""
    
    def test_round_robin_deterministic_order(self):
        """Test round-robin maintains deterministic order."""
        policy = RoundRobinPolicy()
        
        candidates = [
            RoutingCandidate(id="w1", name="worker-1", type="worker"),
            RoutingCandidate(id="w2", name="worker-2", type="worker"),
            RoutingCandidate(id="w3", name="worker-3", type="worker"),
        ]
        
        context = RoutingContext(trace_id="trace-1", profile="test")
        
        # First three decisions should cycle through all workers
        decisions = []
        for _ in range(6):
            decision = policy.evaluate(context, candidates)
            decisions.append(decision.selected.id)
        
        # Should cycle: w1, w2, w3, w1, w2, w3
        assert decisions == ["w1", "w2", "w3", "w1", "w2", "w3"]
    
    def test_capability_based_deterministic(self):
        """Test capability-based routing is deterministic."""
        policy = CapabilityBasedPolicy()
        
        candidates = [
            RoutingCandidate(
                id="a1",
                name="agent-1",
                type="agent",
                capabilities=["search", "web"],
            ),
            RoutingCandidate(
                id="a2",
                name="agent-2",
                type="agent",
                capabilities=["database", "query"],
            ),
        ]
        
        context = RoutingContext(
            trace_id="trace-1",
            profile="test",
            constraints={"required_capabilities": ["search", "web"]},
        )
        
        decision1 = policy.evaluate(context, candidates)
        decision2 = policy.evaluate(context, candidates)
        
        # Same capabilities → same selection
        assert decision1.selected.id == decision2.selected.id
        assert decision1.selected.id == "a1"


class TestAuditTrailPersistence:
    """Test audit trail persistence and querying."""
    
    def test_json_backend_store_and_query(self):
        """Test JSON backend stores and retrieves records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = JSONAuditBackend(Path(tmpdir) / "audit.jsonl")
            
            record = DecisionRecord(
                record_id=str(uuid.uuid4()),
                timestamp="2025-01-01T00:00:00Z",
                trace_id="trace-1",
                decision_type="routing",
                stage="route",
                target="worker-1",
                reason="round-robin selection",
            )
            
            backend.store_record(record)
            
            # Query by trace
            records = backend.query_by_trace("trace-1")
            assert len(records) == 1
            assert records[0].target == "worker-1"
    
    def test_sqlite_backend_store_and_query(self):
        """Test SQLite backend stores and retrieves records."""
        with tempfile.TemporaryDirectory() as tmpdir:
            backend = SQLiteAuditBackend(Path(tmpdir) / "audit.db")
            
            record = DecisionRecord(
                record_id=str(uuid.uuid4()),
                timestamp="2025-01-01T00:00:00Z",
                trace_id="trace-1",
                decision_type="planning",
                stage="plan",
                target="plan-123",
                reason="created plan with 3 steps",
            )
            
            backend.store_record(record)
            
            # Query by trace
            records = backend.query_by_trace("trace-1")
            assert len(records) == 1
            assert records[0].decision_type == "planning"
            
            # Query by type
            planning_records = backend.query_by_type("planning")
            assert len(planning_records) == 1
    
    def test_audit_trail_integration(self):
        """Test AuditTrail high-level interface."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit = AuditTrail(
                backend_type="sqlite",
                storage_path=Path(tmpdir) / "audit.db",
            )
            
            # Create plan and record
            plan = Plan(
                plan_id="plan-123",
                goal="test goal",
                steps=[],
                stage=PlanningStage.CREATED,
                budget=ToolBudget(),
                trace_id="trace-1",
            )
            
            audit.record_plan(plan)
            
            # Query trace history
            history = audit.get_trace_history("trace-1")
            assert len(history) == 1
            assert history[0].target == "plan-123"
    
    def test_audit_trail_multiple_traces(self):
        """Test audit trail handles multiple traces."""
        with tempfile.TemporaryDirectory() as tmpdir:
            audit = AuditTrail(
                backend_type="json",
                storage_path=Path(tmpdir) / "audit.jsonl",
            )
            
            # Record multiple traces
            for i in range(3):
                plan = Plan(
                    plan_id=f"plan-{i}",
                    goal=f"goal {i}",
                    steps=[],
                    stage=PlanningStage.CREATED,
                    budget=ToolBudget(),
                    trace_id=f"trace-{i}",
                )
                audit.record_plan(plan)
            
            # Query specific trace
            trace_1_history = audit.get_trace_history("trace-1")
            assert len(trace_1_history) == 1
            assert trace_1_history[0].trace_id == "trace-1"
            
            # Query all recent
            recent = audit.get_recent(limit=10)
            assert len(recent) == 3


class TestIntegratedWorkflow:
    """Test integrated plan → route → execute workflow."""
    
    def test_complete_workflow_with_audit(self):
        """Test complete workflow with planning, routing, and audit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup
            planner = ToolRankingPlanner(max_steps=3)
            routing = PolicyBasedRoutingAuthority(
                worker_policy=RoundRobinPolicy()
            )
            audit = AuditTrail(
                backend_type="sqlite",
                storage_path=Path(tmpdir) / "audit.db",
            )
            
            tools = [
                {"name": "tool1", "description": "search", "cost": 1.0, "tokens": 100},
                {"name": "tool2", "description": "query", "cost": 0.5, "tokens": 50},
            ]
            
            trace_id = "trace-integration"
            
            # 1. Create plan
            plan = planner.create_plan(
                "search for data",
                trace_id=trace_id,
                constraints={"available_tools": tools},
            )
            
            assert plan.stage == PlanningStage.CREATED
            audit.record_plan(plan, stage="plan_created")
            
            # 2. Route workers to steps
            workers = [
                RoutingCandidate(id="w1", name="worker-1", type="worker"),
                RoutingCandidate(id="w2", name="worker-2", type="worker"),
            ]
            
            routed_steps = []
            for step in plan.steps:
                context = RoutingContext(
                    trace_id=trace_id,
                    profile=plan.profile,
                    task=step.tool,
                )
                
                decision = routing.route_to_worker(context, workers)
                audit.record_routing_decision(decision, trace_id, stage="worker_routing")
                
                # Assign worker to step
                routed_step = PlanStep(
                    tool=step.tool,
                    input=step.input,
                    name=step.name,
                    reason=step.reason,
                    estimated_cost=step.estimated_cost,
                    estimated_tokens=step.estimated_tokens,
                    worker=decision.selected.id,
                    index=step.index,
                )
                routed_steps.append(routed_step)
            
            plan = plan.with_routed_steps(routed_steps)
            plan = plan.transition_to(PlanningStage.ROUTED)
            
            # 3. Verify audit trail
            history = audit.get_trace_history(trace_id)
            
            # Should have plan creation + routing decisions
            assert len(history) >= 3  # 1 plan + 2 tool steps
            
            plan_records = [r for r in history if r.decision_type == "planning"]
            routing_records = [r for r in history if r.decision_type == "routing"]
            
            assert len(plan_records) >= 1
            assert len(routing_records) >= 2
            
            # Verify workers assigned in round-robin
            workers_assigned = [s.worker for s in plan.steps]
            assert workers_assigned == ["w1", "w2"]

"""
Tests for PlanningAuthority integration in CoordinatorAgent.

Validates that:
1. CoordinatorAgent has planning_authority field
2. Default PlanningAuthority is initialized
3. Custom PlanningAuthority can be provided
4. orchestrate() uses PlanningAuthority to create plans
5. Plans include ToolBudget tracking
6. Plan state transitions work (CREATED → ROUTED → EXECUTING → COMPLETED)
7. Budget validation works
8. create_coordinator() factory supports planning parameters
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from dataclasses import dataclass

from cuga.modular.agents import (
    CoordinatorAgent,
    PlannerAgent,
    WorkerAgent,
    AgentResult,
    create_coordinator,
)
from cuga.modular.memory import VectorMemory
from cuga.modular.tools import ToolRegistry, ToolSpec
from cuga.modular.config import AgentConfig
from cuga.orchestrator.protocol import ExecutionContext, LifecycleStage
from cuga.orchestrator.planning import (
    PlanningAuthority,
    ToolRankingPlanner,
    Plan,
    PlanStep,
    PlanningStage,
    ToolBudget,
    BudgetError,
    create_planning_authority,
)
from cuga.orchestrator.routing import RoutingStrategy


# --- Fixtures ---

@pytest.fixture
def memory():
    """Mock VectorMemory for testing."""
    return MagicMock(spec=VectorMemory)


@pytest.fixture
def tool_registry():
    """Create tool registry with test tools."""
    def echo_handler(inputs, ctx):
        return inputs.get("text", "hello")
    
    def add_handler(inputs, ctx):
        return str(inputs.get("a", 0) + inputs.get("b", 0))
    
    return ToolRegistry(
        tools=[
            ToolSpec(name="echo", description="Echo text", handler=echo_handler),
            ToolSpec(name="add", description="Add numbers", handler=add_handler),
        ]
    )


@pytest.fixture
def planner(tool_registry, memory):
    """Create mock planner."""
    planner = MagicMock(spec=PlannerAgent)
    planner.config = AgentConfig(profile="test")
    
    # Mock plan() to return a simple plan
    mock_plan = AgentResult(
        output="plan",
        trace=[{"event": "plan_created"}],
    )
    mock_plan.steps = [
        {"tool": "echo", "input": {"text": "hello"}},
    ]
    planner.plan.return_value = mock_plan
    
    # Mock startup/shutdown
    planner.startup = AsyncMock()
    planner.shutdown = AsyncMock()
    
    return planner


@pytest.fixture
def worker(tool_registry):
    """Create mock worker."""
    worker = MagicMock(spec=WorkerAgent)
    worker.execute = MagicMock(return_value=AgentResult(
        output="hello",
        trace=[{"event": "tool_executed", "tool": "echo"}],
    ))
    
    # Mock startup/shutdown
    worker.startup = AsyncMock()
    worker.shutdown = AsyncMock()
    
    return worker


@pytest.fixture
def coordinator(planner, worker, memory):
    """Create coordinator with default authorities."""
    return CoordinatorAgent(
        planner=planner,
        workers=[worker],
        memory=memory,
    )


@pytest.fixture
def custom_planning_authority():
    """Create custom planning authority with tight budget."""
    return create_planning_authority(
        max_steps=5,
        budget=ToolBudget(cost_ceiling=10.0, call_ceiling=5, token_ceiling=1000),
    )


# --- Tests ---

class TestPlanningAuthorityIntegration:
    """Test PlanningAuthority integration in CoordinatorAgent."""
    
    def test_coordinator_has_planning_authority(self, coordinator):
        """CoordinatorAgent has planning_authority field."""
        assert hasattr(coordinator, "planning_authority")
        assert coordinator.planning_authority is not None
    
    def test_coordinator_default_planning_authority(self, coordinator):
        """CoordinatorAgent initializes default planning authority."""
        assert isinstance(coordinator.planning_authority, PlanningAuthority)
        assert isinstance(coordinator.planning_authority, ToolRankingPlanner)
    
    def test_coordinator_custom_planning_authority(
        self, planner, worker, memory, custom_planning_authority
    ):
        """CoordinatorAgent accepts custom planning authority."""
        coordinator = CoordinatorAgent(
            planner=planner,
            workers=[worker],
            memory=memory,
            planning_authority=custom_planning_authority,
        )
        
        assert coordinator.planning_authority is custom_planning_authority
        assert coordinator.planning_authority.max_steps == 5
    
    @pytest.mark.asyncio
    async def test_orchestrate_uses_planning_authority(self, coordinator):
        """orchestrate() delegates to planning_authority.create_plan()."""
        context = ExecutionContext(trace_id="test", profile="test")
        
        plans = []
        async for event in coordinator.orchestrate("test goal", context):
            if event["stage"] == LifecycleStage.PLAN:
                plans.append(event["data"]["plan"])
        
        assert len(plans) == 1
        plan = plans[0]
        
        # Validate plan is from PlanningAuthority (has Plan attributes)
        assert isinstance(plan, Plan)
        assert plan.goal == "test goal"
        assert plan.trace_id == "test"
        assert plan.profile == "test"
        assert hasattr(plan, "plan_id")
        assert hasattr(plan, "stage")
        assert hasattr(plan, "budget")
    
    @pytest.mark.asyncio
    async def test_plan_includes_budget(self, coordinator):
        """Plans include ToolBudget tracking."""
        context = ExecutionContext(trace_id="test", profile="test")
        
        async for event in coordinator.orchestrate("test goal", context):
            if event["stage"] == LifecycleStage.PLAN:
                plan = event["data"]["plan"]
                budget = event["data"]["budget"]
                
                assert isinstance(budget, ToolBudget)
                assert budget.cost_ceiling > 0
                assert budget.call_ceiling > 0
                assert budget.token_ceiling > 0
                break


class TestPlanStateTransitions:
    """Test plan state machine transitions."""
    
    @pytest.mark.asyncio
    async def test_plan_stage_transitions(self, coordinator):
        """Plans transition through lifecycle stages."""
        context = ExecutionContext(trace_id="test", profile="test")
        
        stages_seen = []
        plans_seen = {}
        
        async for event in coordinator.orchestrate("test goal", context):
            stage = event["stage"]
            stages_seen.append(stage)
            
            if stage == LifecycleStage.PLAN:
                plan = event["data"]["plan"]
                plans_seen["plan"] = plan
                # After create_plan() and transition_to(ROUTED)
                assert plan.stage == PlanningStage.ROUTED
            
            elif stage == LifecycleStage.EXECUTE:
                # Plan should have transitioned to COMPLETED by end of execute
                planning_stage = event["data"].get("plan_stage")
                assert planning_stage == PlanningStage.COMPLETED.value
        
        # Verify stages occurred in order
        assert LifecycleStage.PLAN in stages_seen
        assert LifecycleStage.EXECUTE in stages_seen
    
    @pytest.mark.asyncio
    async def test_plan_metadata_includes_stage(self, coordinator):
        """Plan events include planning_stage metadata."""
        context = ExecutionContext(trace_id="test", profile="test")
        
        async for event in coordinator.orchestrate("test goal", context):
            if event["stage"] == LifecycleStage.PLAN:
                assert "planning_stage" in event["data"]
                assert event["data"]["planning_stage"] == PlanningStage.ROUTED.value
                break


class TestBudgetTracking:
    """Test ToolBudget tracking and enforcement."""
    
    @pytest.mark.asyncio
    async def test_plan_includes_estimated_cost(self, coordinator):
        """Plans include estimated cost in metadata."""
        context = ExecutionContext(trace_id="test", profile="test")
        
        async for event in coordinator.orchestrate("test goal", context):
            if event["stage"] == LifecycleStage.PLAN:
                plan = event["data"]["plan"]
                assert plan.estimated_total_cost() >= 0
                break
    
    @pytest.mark.asyncio
    async def test_plan_budget_is_sufficient(self, coordinator):
        """Plans are validated for budget sufficiency."""
        context = ExecutionContext(trace_id="test", profile="test")
        
        async for event in coordinator.orchestrate("test goal", context):
            if event["stage"] == LifecycleStage.PLAN:
                plan = event["data"]["plan"]
                # Plan should be valid (budget_sufficient)
                assert plan.budget_sufficient()
                break
    
    def test_custom_budget_enforced(
        self, planner, worker, memory, custom_planning_authority
    ):
        """Custom budget limits are enforced."""
        coordinator = CoordinatorAgent(
            planner=planner,
            workers=[worker],
            memory=memory,
            planning_authority=custom_planning_authority,
        )
        
        # Verify budget limits
        budget = coordinator.planning_authority.default_budget
        assert budget.cost_ceiling == 10.0
        assert budget.call_ceiling == 5


class TestCreateCoordinatorFactory:
    """Test create_coordinator() factory with planning parameters."""
    
    def test_create_coordinator_default_planning(self, planner, worker, memory):
        """create_coordinator() uses default planning settings."""
        coordinator = create_coordinator(
            planner=planner,
            workers=[worker],
            memory=memory,
        )
        
        assert coordinator.planning_authority is not None
        assert isinstance(coordinator.planning_authority, ToolRankingPlanner)
    
    def test_create_coordinator_custom_max_steps(self, planner, worker, memory):
        """create_coordinator() accepts max_plan_steps parameter."""
        coordinator = create_coordinator(
            planner=planner,
            workers=[worker],
            memory=memory,
            max_plan_steps=15,
        )
        
        assert coordinator.planning_authority.max_steps == 15
    
    def test_create_coordinator_custom_budget(self, planner, worker, memory):
        """create_coordinator() accepts default_budget parameter."""
        custom_budget = ToolBudget(cost_ceiling=200.0)
        
        coordinator = create_coordinator(
            planner=planner,
            workers=[worker],
            memory=memory,
            default_budget=custom_budget,
        )
        
        assert coordinator.planning_authority.default_budget.cost_ceiling == 200.0
    
    def test_create_coordinator_combined_parameters(self, planner, worker, memory):
        """create_coordinator() accepts routing and planning parameters."""
        custom_budget = ToolBudget(cost_ceiling=150.0, call_ceiling=25)
        
        coordinator = create_coordinator(
            planner=planner,
            workers=[worker],
            memory=memory,
            routing_strategy=RoutingStrategy.ROUND_ROBIN,
            max_plan_steps=20,
            default_budget=custom_budget,
        )
        
        # Verify routing authority
        assert coordinator.routing_authority is not None
        
        # Verify planning authority
        assert coordinator.planning_authority.max_steps == 20
        assert coordinator.planning_authority.default_budget.cost_ceiling == 150.0


class TestPlanningErrors:
    """Test error handling in planning."""
    
    @pytest.mark.asyncio
    async def test_empty_goal_raises_error(self, coordinator):
        """Empty goal raises OrchestrationError (wraps ValueError)."""
        from cuga.orchestrator.protocol import OrchestrationError
        
        context = ExecutionContext(trace_id="test", profile="test")
        
        with pytest.raises(OrchestrationError, match="Goal cannot be empty"):
            async for event in coordinator.orchestrate("", context):
                pass
    
    @pytest.mark.asyncio
    async def test_planning_failure_propagates(self, planner, worker, memory):
        """Planning failures propagate as OrchestrationError."""
        # Create planner that always fails
        failing_planner = Mock(spec=PlannerAgent)
        failing_planner.plan = Mock(side_effect=RuntimeError("Planning failed"))
        
        coordinator = CoordinatorAgent(
            planner=failing_planner,
            workers=[worker],
            memory=memory,
        )
        
        context = ExecutionContext(trace_id="test", profile="test")
        
        from cuga.orchestrator.protocol import OrchestrationError
        
        with pytest.raises(OrchestrationError, match="Planning failed"):
            async for event in coordinator.orchestrate("test goal", context):
                pass


class TestPlanStepFormat:
    """Test PlanStep format and conversion."""
    
    @pytest.mark.asyncio
    async def test_plan_steps_have_required_fields(self, coordinator):
        """Plan steps have tool, input, name, reason."""
        context = ExecutionContext(trace_id="test", profile="test")
        
        async for event in coordinator.orchestrate("test goal", context):
            if event["stage"] == LifecycleStage.PLAN:
                plan = event["data"]["plan"]
                
                for step in plan.steps:
                    assert hasattr(step, "tool")
                    assert hasattr(step, "input")
                    assert hasattr(step, "name")
                    assert hasattr(step, "reason")
                    assert hasattr(step, "estimated_cost")
                    assert hasattr(step, "estimated_tokens")
                break
    
    @pytest.mark.asyncio
    async def test_plan_steps_converted_for_worker(self, coordinator, worker):
        """Plan steps are converted to legacy format for worker execution."""
        context = ExecutionContext(trace_id="test", profile="test")
        
        async for event in coordinator.orchestrate("test goal", context):
            if event["stage"] == LifecycleStage.EXECUTE:
                # Worker.execute was called with converted steps
                assert worker.execute.called
                
                call_args = worker.execute.call_args
                steps_arg = call_args[0][0]  # First positional argument
                
                # Verify legacy format
                assert isinstance(steps_arg, list)
                for step in steps_arg:
                    assert isinstance(step, dict)
                    assert "tool" in step
                    assert "input" in step
                break

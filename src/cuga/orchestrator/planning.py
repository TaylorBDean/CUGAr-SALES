"""
Canonical Planning Authority

This module defines the single source of truth for planning decisions in CUGAR agent system.
All planning logic operates in coordination with RoutingAuthority for deterministic
Plan → Route → Execute transitions.

Key Principles:
1. Deterministic Planning: Same inputs → same plan with explicit budgets
2. Idempotent Transitions: Plan→Route→Execute state machine with transition guards
3. Budget Enforcement: Tool budgets tracked and enforced throughout lifecycle
4. Audit Trail: All decisions recorded with reasoning for observability

See docs/orchestrator/PLANNING_AUTHORITY.md for detailed architecture.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone


class PlanningStage(str, Enum):
    """State machine stages for Plan → Route → Execute transitions."""
    
    CREATED = "created"          # Plan created, not yet routed
    ROUTED = "routed"            # Routing decisions made
    EXECUTING = "executing"      # Execution in progress
    COMPLETED = "completed"      # Execution completed successfully
    FAILED = "failed"            # Execution failed
    CANCELLED = "cancelled"      # Execution cancelled


@dataclass(frozen=True)
class ToolBudget:
    """
    Immutable tool budget tracking for plan execution.
    
    Tracks resource consumption (cost, calls, tokens) with explicit
    ceilings and enforcement policy.
    """
    
    cost_ceiling: float = 100.0      # Maximum cost allowed
    cost_spent: float = 0.0          # Cost consumed so far
    call_ceiling: int = 50           # Maximum tool calls allowed
    call_spent: int = 0              # Tool calls consumed
    token_ceiling: int = 100000      # Maximum tokens allowed
    token_spent: int = 0             # Tokens consumed
    policy: str = "warn"             # "warn" or "block"
    
    def within_limits(self) -> bool:
        """Check if budget is within all limits."""
        return (
            self.cost_spent <= self.cost_ceiling
            and self.call_spent <= self.call_ceiling
            and self.token_spent <= self.token_ceiling
        )
    
    def with_cost(self, cost: float) -> ToolBudget:
        """Create new budget with additional cost."""
        return ToolBudget(
            cost_ceiling=self.cost_ceiling,
            cost_spent=self.cost_spent + cost,
            call_ceiling=self.call_ceiling,
            call_spent=self.call_spent,
            token_ceiling=self.token_ceiling,
            token_spent=self.token_spent,
            policy=self.policy,
        )
    
    def with_call(self) -> ToolBudget:
        """Create new budget with one additional call."""
        return ToolBudget(
            cost_ceiling=self.cost_ceiling,
            cost_spent=self.cost_spent,
            call_ceiling=self.call_ceiling,
            call_spent=self.call_spent + 1,
            token_ceiling=self.token_ceiling,
            token_spent=self.token_spent,
            policy=self.policy,
        )
    
    def with_tokens(self, tokens: int) -> ToolBudget:
        """Create new budget with additional tokens."""
        return ToolBudget(
            cost_ceiling=self.cost_ceiling,
            cost_spent=self.cost_spent,
            call_ceiling=self.call_ceiling,
            call_spent=self.call_spent,
            token_ceiling=self.token_ceiling,
            token_spent=self.token_spent + tokens,
            policy=self.policy,
        )
    
    def remaining_cost(self) -> float:
        """Get remaining cost budget."""
        return self.cost_ceiling - self.cost_spent
    
    def remaining_calls(self) -> int:
        """Get remaining call budget."""
        return self.call_ceiling - self.call_spent
    
    def remaining_tokens(self) -> int:
        """Get remaining token budget."""
        return self.token_ceiling - self.token_spent


@dataclass
class PlanStep:
    """
    Single executable step in a plan.
    
    Represents one tool invocation with inputs, expected cost,
    and routing information.
    """
    
    tool: str                                  # Tool identifier (e.g., "cuga.modular.tools.echo")
    input: Dict[str, Any]                      # Tool input parameters
    name: str = ""                             # Human-readable step name
    reason: str = ""                           # Why this tool was selected
    estimated_cost: float = 0.0                # Estimated execution cost
    estimated_tokens: int = 0                  # Estimated token usage
    worker: str = ""                           # Assigned worker (after routing)
    index: int = 0                             # Step position in plan
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Plan:
    """
    Immutable execution plan with budget and lifecycle tracking.
    
    Represents complete plan from creation through execution with
    idempotent state transitions and budget enforcement.
    """
    
    plan_id: str                               # Unique plan identifier
    goal: str                                  # User goal/intent
    steps: List[PlanStep]                      # Ordered execution steps
    stage: PlanningStage                       # Current lifecycle stage
    budget: ToolBudget                         # Budget tracking
    trace_id: str                              # Trace identifier
    profile: str = "default"                   # Security profile
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    routed_at: Optional[str] = None            # Routing completion timestamp
    started_at: Optional[str] = None           # Execution start timestamp
    completed_at: Optional[str] = None         # Execution completion timestamp
    error: Optional[str] = None                # Error message if failed
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def transition_to(self, new_stage: PlanningStage, **kwargs) -> Plan:
        """
        Create new plan with transitioned stage.
        
        Enforces valid state transitions and updates timestamps.
        Raises ValueError for invalid transitions.
        """
        # Validate transition
        valid_transitions = {
            PlanningStage.CREATED: [PlanningStage.ROUTED, PlanningStage.CANCELLED],
            PlanningStage.ROUTED: [PlanningStage.EXECUTING, PlanningStage.CANCELLED],
            PlanningStage.EXECUTING: [
                PlanningStage.COMPLETED,
                PlanningStage.FAILED,
                PlanningStage.CANCELLED,
            ],
            PlanningStage.COMPLETED: [],
            PlanningStage.FAILED: [],
            PlanningStage.CANCELLED: [],
        }
        
        if new_stage not in valid_transitions.get(self.stage, []):
            raise ValueError(
                f"Invalid transition from {self.stage} to {new_stage}. "
                f"Valid transitions: {valid_transitions.get(self.stage, [])}"
            )
        
        # Update timestamps based on stage
        updates = {"stage": new_stage}
        
        if new_stage == PlanningStage.ROUTED:
            updates["routed_at"] = datetime.now(timezone.utc).isoformat()
        elif new_stage == PlanningStage.EXECUTING:
            updates["started_at"] = datetime.now(timezone.utc).isoformat()
        elif new_stage in [
            PlanningStage.COMPLETED,
            PlanningStage.FAILED,
            PlanningStage.CANCELLED,
        ]:
            updates["completed_at"] = datetime.now(timezone.utc).isoformat()
        
        # Merge with provided kwargs
        updates.update(kwargs)
        
        # Create new plan with updates
        return Plan(
            plan_id=self.plan_id,
            goal=self.goal,
            steps=updates.get("steps", self.steps),
            stage=updates["stage"],
            budget=updates.get("budget", self.budget),
            trace_id=self.trace_id,
            profile=self.profile,
            created_at=self.created_at,
            routed_at=updates.get("routed_at", self.routed_at),
            started_at=updates.get("started_at", self.started_at),
            completed_at=updates.get("completed_at", self.completed_at),
            error=updates.get("error", self.error),
            metadata=updates.get("metadata", self.metadata),
        )
    
    def with_budget(self, budget: ToolBudget) -> Plan:
        """Create new plan with updated budget."""
        return Plan(
            plan_id=self.plan_id,
            goal=self.goal,
            steps=self.steps,
            stage=self.stage,
            budget=budget,
            trace_id=self.trace_id,
            profile=self.profile,
            created_at=self.created_at,
            routed_at=self.routed_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            error=self.error,
            metadata=self.metadata,
        )
    
    def with_routed_steps(self, steps: List[PlanStep]) -> Plan:
        """Create new plan with worker-assigned steps."""
        return Plan(
            plan_id=self.plan_id,
            goal=self.goal,
            steps=steps,
            stage=self.stage,
            budget=self.budget,
            trace_id=self.trace_id,
            profile=self.profile,
            created_at=self.created_at,
            routed_at=self.routed_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            error=self.error,
            metadata=self.metadata,
        )
    
    def estimated_total_cost(self) -> float:
        """Calculate total estimated cost for all steps."""
        return sum(step.estimated_cost for step in self.steps)
    
    def estimated_total_tokens(self) -> int:
        """Calculate total estimated tokens for all steps."""
        return sum(step.estimated_tokens for step in self.steps)
    
    def budget_sufficient(self) -> bool:
        """Check if budget is sufficient for estimated plan execution."""
        return (
            self.estimated_total_cost() <= self.budget.remaining_cost()
            and len(self.steps) <= self.budget.remaining_calls()
            and self.estimated_total_tokens() <= self.budget.remaining_tokens()
        )


class PlanningAuthority(ABC):
    """
    Abstract planning authority interface.
    
    All planning decisions MUST go through a PlanningAuthority implementation.
    This is the single source of truth for "what steps to execute and in what order".
    
    Works in coordination with RoutingAuthority for complete orchestration:
    - PlanningAuthority: What to do and in what order (steps, budget)
    - RoutingAuthority: Who should do it (worker/agent selection)
    """
    
    @abstractmethod
    def create_plan(
        self,
        goal: str,
        trace_id: str,
        profile: str = "default",
        budget: Optional[ToolBudget] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Plan:
        """
        Create execution plan for goal.
        
        Args:
            goal: User goal/intent
            trace_id: Trace identifier
            profile: Security profile
            budget: Tool budget (default if None)
            constraints: Additional planning constraints
            
        Returns:
            Plan with ordered steps and budget
            
        Raises:
            ValueError: If goal is invalid or planning fails
            BudgetError: If budget insufficient for minimal plan
        """
        ...
    
    @abstractmethod
    def validate_plan(self, plan: Plan) -> bool:
        """
        Validate plan completeness and budget sufficiency.
        
        Args:
            plan: Plan to validate
            
        Returns:
            True if plan is valid
            
        Raises:
            ValueError: If plan is invalid with reason
        """
        ...


class BudgetError(Exception):
    """Raised when budget is insufficient for plan execution."""
    
    def __init__(
        self,
        message: str,
        required_cost: float = 0.0,
        available_cost: float = 0.0,
    ):
        super().__init__(message)
        self.required_cost = required_cost
        self.available_cost = available_cost


class ToolRankingPlanner(PlanningAuthority):
    """
    Planning authority using tool ranking by goal similarity.
    
    Ranks available tools by capability overlap with goal, then
    selects top-k tools within budget constraints.
    """
    
    def __init__(
        self,
        max_steps: int = 10,
        default_budget: Optional[ToolBudget] = None,
    ):
        """
        Initialize tool ranking planner.
        
        Args:
            max_steps: Maximum steps per plan
            default_budget: Default budget if none provided
        """
        self.max_steps = max_steps
        self.default_budget = default_budget or ToolBudget()
    
    def create_plan(
        self,
        goal: str,
        trace_id: str,
        profile: str = "default",
        budget: Optional[ToolBudget] = None,
        constraints: Optional[Dict[str, Any]] = None,
    ) -> Plan:
        """Create plan by ranking tools by goal similarity."""
        import uuid
        import re
        
        if not goal:
            raise ValueError("Goal cannot be empty")
        
        budget = budget or self.default_budget
        constraints = constraints or {}
        
        # Extract keywords from goal
        keywords = set(re.split(r"\W+", goal.lower()))
        keywords.discard("")
        
        # Get available tools from constraints (or use default)
        available_tools = constraints.get("available_tools", [])
        if not available_tools:
            # Default fallback tool
            available_tools = [
                {
                    "name": "cuga.modular.tools.echo",
                    "description": "Echo input message",
                    "cost": 0.1,
                    "tokens": 10,
                }
            ]
        
        # Rank tools by keyword overlap
        ranked_tools = []
        for tool in available_tools:
            tool_text = f"{tool.get('name', '')} {tool.get('description', '')}".lower()
            tool_words = set(re.split(r"\W+", tool_text))
            overlap = len(keywords.intersection(tool_words))
            score = overlap / max(len(keywords), 1)
            
            if score > 0 or not ranked_tools:  # Include at least one tool
                ranked_tools.append((score, tool))
        
        ranked_tools.sort(key=lambda x: x[0], reverse=True)
        
        # Select tools within budget
        steps: List[PlanStep] = []
        cumulative_cost = 0.0
        cumulative_tokens = 0
        
        for idx, (score, tool) in enumerate(ranked_tools):
            if idx >= self.max_steps:
                break
            
            cost = float(tool.get("cost", 0.1))
            tokens = int(tool.get("tokens", 10))
            
            # Check if adding this step exceeds budget
            if cumulative_cost + cost > budget.cost_ceiling:
                break
            if cumulative_tokens + tokens > budget.token_ceiling:
                break
            if len(steps) >= budget.call_ceiling:
                break
            
            steps.append(
                PlanStep(
                    tool=tool["name"],
                    input={"text": goal},
                    name=f"step_{idx}",
                    reason=f"Ranked {idx + 1} with similarity score {score:.2f}",
                    estimated_cost=cost,
                    estimated_tokens=tokens,
                    index=idx,
                )
            )
            
            cumulative_cost += cost
            cumulative_tokens += tokens
        
        if not steps:
            raise BudgetError(
                "Insufficient budget for minimal plan",
                required_cost=ranked_tools[0][1].get("cost", 0.1) if ranked_tools else 0.0,
                available_cost=budget.cost_ceiling,
            )
        
        plan_id = str(uuid.uuid4())
        
        return Plan(
            plan_id=plan_id,
            goal=goal,
            steps=steps,
            stage=PlanningStage.CREATED,
            budget=budget,
            trace_id=trace_id,
            profile=profile,
            metadata={
                "available_tool_count": len(available_tools),
                "selected_step_count": len(steps),
                "estimated_cost": cumulative_cost,
                "estimated_tokens": cumulative_tokens,
            },
        )
    
    def validate_plan(self, plan: Plan) -> bool:
        """Validate plan has steps and budget is sufficient."""
        if not plan.steps:
            raise ValueError("Plan must have at least one step")
        
        if not plan.budget_sufficient():
            raise ValueError(
                f"Insufficient budget: need cost={plan.estimated_total_cost():.2f} "
                f"(have {plan.budget.remaining_cost():.2f}), "
                f"calls={len(plan.steps)} (have {plan.budget.remaining_calls()}), "
                f"tokens={plan.estimated_total_tokens()} (have {plan.budget.remaining_tokens()})"
            )
        
        return True


# Convenience function for creating default planning authority
def create_planning_authority(
    max_steps: int = 10,
    budget: Optional[ToolBudget] = None,
) -> PlanningAuthority:
    """
    Create planning authority with default configuration.
    
    Args:
        max_steps: Maximum steps per plan
        budget: Default budget
        
    Returns:
        Configured PlanningAuthority instance
    """
    return ToolRankingPlanner(max_steps=max_steps, default_budget=budget)

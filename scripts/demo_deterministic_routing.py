#!/usr/bin/env python3
"""
Demonstration of deterministic routing and planning workflow.

Shows complete integration of:
1. Plan creation with budget enforcement
2. Worker routing with round-robin
3. Audit trail persistence and querying
"""

import sys
import tempfile
from pathlib import Path

# Add src to path for direct execution
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cuga.orchestrator import (
    # Planning
    create_planning_authority,
    ToolBudget,
    PlanningStage,
    BudgetError,
    # Routing
    create_routing_authority,
    RoutingCandidate,
    RoutingContext,
    RoutingStrategy,
    # Audit
    create_audit_trail,
)


def main():
    print("=" * 80)
    print("Deterministic Routing & Planning Demonstration")
    print("=" * 80)
    print()
    
    # Setup
    print("1. Setting up components...")
    planner = create_planning_authority(max_steps=5)
    router = create_routing_authority(worker_strategy=RoutingStrategy.ROUND_ROBIN)
    
    # Use temporary directory for audit trail
    with tempfile.TemporaryDirectory() as tmpdir:
        audit = create_audit_trail(
            backend_type="sqlite",
            storage_path=Path(tmpdir) / "audit.db",
        )
        
        # Define available tools
        tools = [
            {
                "name": "cuga.modular.tools.web_search",
                "description": "Search the web for information",
                "cost": 2.0,
                "tokens": 200,
            },
            {
                "name": "cuga.modular.tools.rag_query",
                "description": "Query RAG knowledge base",
                "cost": 1.0,
                "tokens": 100,
            },
            {
                "name": "cuga.modular.tools.summarize",
                "description": "Summarize text content",
                "cost": 1.5,
                "tokens": 150,
            },
        ]
        
        # Define budget
        budget = ToolBudget(
            cost_ceiling=10.0,
            call_ceiling=5,
            token_ceiling=1000,
            policy="block",
        )
        
        print(f"   Budget: cost_ceiling={budget.cost_ceiling}, call_ceiling={budget.call_ceiling}")
        print(f"   Available tools: {len(tools)}")
        print()
        
        # Create plan
        print("2. Creating plan...")
        trace_id = "demo-trace-001"
        goal = "search web for Python documentation and summarize results"
        
        plan = planner.create_plan(
            goal=goal,
            trace_id=trace_id,
            profile="demo",
            budget=budget,
            constraints={"available_tools": tools},
        )
        
        print(f"   Plan ID: {plan.plan_id}")
        print(f"   Goal: {plan.goal}")
        print(f"   Stage: {plan.stage.value}")
        print(f"   Steps: {len(plan.steps)}")
        print(f"   Estimated cost: ${plan.estimated_total_cost():.2f}")
        print(f"   Estimated tokens: {plan.estimated_total_tokens()}")
        print()
        
        # Show plan steps
        print("   Plan steps:")
        for i, step in enumerate(plan.steps, 1):
            print(f"     {i}. {step.tool}")
            print(f"        Reason: {step.reason}")
            print(f"        Cost: ${step.estimated_cost:.2f}, Tokens: {step.estimated_tokens}")
        print()
        
        # Record plan to audit
        audit.record_plan(plan, stage="plan_created")
        
        # Route workers to steps
        print("3. Routing workers to steps...")
        workers = [
            RoutingCandidate(id="worker-1", name="Worker 1", type="worker"),
            RoutingCandidate(id="worker-2", name="Worker 2", type="worker"),
            RoutingCandidate(id="worker-3", name="Worker 3", type="worker"),
        ]
        
        routed_steps = []
        for step in plan.steps:
            context = RoutingContext(
                trace_id=trace_id,
                profile=plan.profile,
                task=step.tool,
            )
            
            decision = router.route_to_worker(context, workers)
            
            print(f"   Step '{step.tool}' → {decision.selected.name}")
            print(f"     Reason: {decision.reason}")
            
            # Record routing decision
            audit.record_routing_decision(decision, trace_id, stage="worker_routing")
            
            # Update step with worker assignment
            from cuga.orchestrator.planning import PlanStep
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
        
        print()
        
        # Update plan with routed steps
        plan = plan.with_routed_steps(routed_steps)
        plan = plan.transition_to(PlanningStage.ROUTED)
        
        print(f"4. Plan transitioned to {plan.stage.value}")
        print()
        
        # Query audit trail
        print("5. Querying audit trail...")
        history = audit.get_trace_history(trace_id)
        
        print(f"   Total decisions recorded: {len(history)}")
        print()
        
        planning_records = [r for r in history if r.decision_type == "planning"]
        routing_records = [r for r in history if r.decision_type == "routing"]
        
        print(f"   Planning decisions: {len(planning_records)}")
        for record in planning_records:
            print(f"     - {record.stage}: {record.reason}")
        print()
        
        print(f"   Routing decisions: {len(routing_records)}")
        for record in routing_records:
            print(f"     - {record.target}: {record.reason}")
        print()
        
        # Test determinism
        print("6. Testing determinism...")
        plan2 = planner.create_plan(
            goal=goal,
            trace_id="demo-trace-002",
            profile="demo",
            budget=budget,
            constraints={"available_tools": tools},
        )
        
        # Compare tool selection
        tools1 = [s.tool for s in plan.steps]
        tools2 = [s.tool for s in plan2.steps]
        
        if tools1 == tools2:
            print("   ✓ Same inputs produced identical plans (deterministic)")
            print(f"   Tools selected: {', '.join(t.split('.')[-1] for t in tools1)}")
        else:
            print("   ✗ Plans differ (non-deterministic)")
        print()
        
        # Test budget enforcement
        print("7. Testing budget enforcement...")
        low_budget = ToolBudget(cost_ceiling=1.0, call_ceiling=10, token_ceiling=1000)
        
        try:
            plan3 = planner.create_plan(
                goal=goal,
                trace_id="demo-trace-003",
                profile="demo",
                budget=low_budget,
                constraints={"available_tools": tools},
            )
            print("   ✗ Budget enforcement failed (should have raised BudgetError)")
        except BudgetError as e:
            print(f"   ✓ Budget enforcement working: {e}")
            print(f"   Required: ${e.required_cost:.2f}, Available: ${e.available_cost:.2f}")
        print()
        
        print("=" * 80)
        print("Demonstration complete!")
        print("=" * 80)


if __name__ == "__main__":
    main()

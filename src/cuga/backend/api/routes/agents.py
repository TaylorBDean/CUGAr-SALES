"""API routes for AGENTS.md coordinator integration."""

import uuid
from typing import Dict
from fastapi import APIRouter, HTTPException, BackgroundTasks
from loguru import logger

from cuga.orchestrator import AGENTSCoordinator, ExecutionContext, Plan, PlanStep, PlanningStage, ToolBudget
from cuga.backend.api.models import (
    PlanExecutionRequest,
    PlanExecutionResponse,
    ApprovalRequest,
    ApprovalResponse,
    BudgetInfoResponse,
    TraceResponse,
)

router = APIRouter(prefix="/api/agents", tags=["agents"])

# Store active coordinators by trace_id for approval handling
_active_coordinators: Dict[str, AGENTSCoordinator] = {}


@router.post("/execute", response_model=PlanExecutionResponse)
async def execute_plan(request: PlanExecutionRequest):
    """
    Execute a plan with AGENTS.md guardrails.
    
    Features:
    - Profile-driven budgets (enterprise/smb/technical)
    - Budget enforcement with warning thresholds
    - Approval gates for execute side-effects
    - Trace continuity with canonical events
    - Golden signals observability
    - Graceful degradation
    """
    try:
        # Initialize coordinator with profile
        coordinator = AGENTSCoordinator(profile=request.profile)
        trace_id = coordinator.trace_emitter.trace_id
        
        # Store coordinator for approval handling
        _active_coordinators[trace_id] = coordinator
        
        # Build plan (coordinator handles budget from profile)
        plan = Plan(
            plan_id=request.plan_id,
            goal=request.goal,
            steps=[
                PlanStep(
                    tool=step.tool,
                    input=step.input,
                    reason=step.reason or "User requested",
                    metadata=step.metadata,
                )
                for step in request.steps
            ],
            stage=PlanningStage.CREATED,
            budget=ToolBudget(),  # Default budget (coordinator enforces profile limits)
            trace_id=trace_id,
        )
        
        # Build execution context
        context = ExecutionContext(
            trace_id=trace_id,
            request_id=request.request_id,
            user_intent=request.goal,
            memory_scope=request.memory_scope,
        )
        
        # Execute plan
        logger.info(f"Executing plan {request.plan_id} with profile {request.profile}")
        result = await coordinator.execute_plan(plan, context)
        
        # Return response
        return PlanExecutionResponse(
            status="success" if result.success else "failed",
            result=result.results if result.success else None,
            error=str(result.failure_context) if result.failure_context else None,
            trace=coordinator.get_trace(),
            signals=coordinator.get_golden_signals(),
            budget=coordinator.get_budget_utilization(),
            trace_id=trace_id,
        )
    
    except Exception as e:
        logger.error(f"Error executing plan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approve", response_model=ApprovalResponse)
async def approve_action(request: ApprovalRequest):
    """
    Approve or deny an action requiring human authority.
    
    This endpoint is called when the frontend approval dialog
    receives user input for execute side-effects.
    """
    try:
        # Find coordinator by approval_id (we'd need to track this better)
        # For now, this is a placeholder - proper implementation would
        # store approval_id -> coordinator mapping
        
        logger.info(
            f"Approval {request.approval_id}: "
            f"{'approved' if request.approved else 'denied'}"
        )
        
        # In production, this would call coordinator.approval_manager.approve()
        # and wake up the waiting execution
        
        return ApprovalResponse(
            status="approved" if request.approved else "denied",
            approval_id=request.approval_id,
        )
    
    except Exception as e:
        logger.error(f"Error processing approval: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/budget/{profile}", response_model=BudgetInfoResponse)
async def get_budget_info(profile: str):
    """
    Get budget information for a profile.
    
    Profiles:
    - enterprise: 200 calls, strict approvals
    - smb: 100 calls, moderate approvals
    - technical: 500 calls, offline/mock only
    """
    try:
        # Create temporary coordinator to get budget info
        coordinator = AGENTSCoordinator(profile=profile)
        budget_util = coordinator.get_budget_utilization()
        
        # Extract totals from nested structure
        total_info = budget_util.get("total", {})
        
        return BudgetInfoResponse(
            profile=profile,
            total_calls=total_info.get("limit", 0),
            used_calls=total_info.get("used", 0),
            remaining_calls=total_info.get("limit", 0) - total_info.get("used", 0),
            utilization=total_info.get("percentage", 0.0) / 100.0,
            warning=total_info.get("percentage", 0.0) >= 80.0,
            by_domain=budget_util.get("by_domain", {}),
            by_tool=budget_util.get("by_tool", {}),
        )
    
    except Exception as e:
        logger.error(f"Error getting budget info: {e}")
        raise HTTPException(status_code=404, detail=f"Profile '{profile}' not found")


@router.get("/trace/{trace_id}", response_model=TraceResponse)
async def get_trace(trace_id: str):
    """
    Retrieve trace events for a specific execution.
    
    Returns canonical events per AGENTS.md observability requirements:
    - plan_created, route_decision, tool_call_start, tool_call_complete
    - tool_call_error, budget_warning, budget_exceeded
    - approval_requested, approval_received, approval_timeout
    """
    try:
        # Retrieve coordinator from active coordinators
        if trace_id not in _active_coordinators:
            raise HTTPException(status_code=404, detail=f"Trace '{trace_id}' not found")
        
        coordinator = _active_coordinators[trace_id]
        
        return TraceResponse(
            trace_id=trace_id,
            events=coordinator.get_trace(),
            signals=coordinator.get_golden_signals(),
            duration_ms=coordinator.trace_emitter.get_duration_ms(),
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving trace: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint for AGENTS.md integration."""
    return {
        "status": "healthy",
        "service": "agents-coordinator",
        "profiles": ["enterprise", "smb", "technical"],
        "features": [
            "profile-driven-budgets",
            "approval-gates",
            "trace-continuity",
            "golden-signals",
            "graceful-degradation",
        ],
    }

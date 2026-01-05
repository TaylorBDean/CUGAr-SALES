"""Pydantic models for AGENTS.md API requests and responses."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PlanStepRequest(BaseModel):
    """Plan step for execution request."""
    
    tool: str = Field(..., description="Tool name to execute")
    input: Dict[str, Any] = Field(..., description="Tool input parameters")
    reason: Optional[str] = Field(None, description="Reasoning for this step")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Step metadata")


class ToolBudgetRequest(BaseModel):
    """Tool budget configuration."""
    
    total_calls: int = Field(100, description="Total call limit")
    calls_per_domain: Dict[str, int] = Field(default_factory=dict, description="Per-domain limits")
    calls_per_tool: Dict[str, int] = Field(default_factory=dict, description="Per-tool limits")
    warning_threshold: float = Field(0.8, description="Budget warning threshold")


class PlanExecutionRequest(BaseModel):
    """Request to execute a plan with AGENTS.md guardrails."""
    
    plan_id: str = Field(..., description="Unique plan identifier")
    goal: str = Field(..., description="Plan goal/intent")
    steps: List[PlanStepRequest] = Field(..., description="Plan steps to execute")
    profile: str = Field("enterprise", description="Profile name (enterprise/smb/technical)")
    budget: Optional[ToolBudgetRequest] = Field(None, description="Custom budget (uses profile default if not provided)")
    request_id: str = Field(..., description="Request identifier")
    memory_scope: str = Field("default/session", description="Memory scope for execution")


class PlanExecutionResponse(BaseModel):
    """Response from plan execution."""
    
    status: str = Field(..., description="Execution status (success/partial/failed)")
    result: Any = Field(None, description="Execution result")
    error: Optional[str] = Field(None, description="Error message if failed")
    trace: List[Dict[str, Any]] = Field(..., description="Trace events")
    signals: Dict[str, Any] = Field(..., description="Golden signals (success_rate, latency, etc.)")
    budget: Dict[str, Any] = Field(..., description="Budget utilization")
    trace_id: str = Field(..., description="Trace identifier for continuity")


class ApprovalRequest(BaseModel):
    """Request to approve/deny an action."""
    
    approval_id: str = Field(..., description="Approval request identifier")
    approved: bool = Field(..., description="Approval decision")
    reason: Optional[str] = Field(None, description="Reason for decision")


class ApprovalResponse(BaseModel):
    """Response from approval request."""
    
    status: str = Field(..., description="Status (approved/denied)")
    approval_id: str = Field(..., description="Approval request identifier")


class BudgetInfoResponse(BaseModel):
    """Budget information for a profile."""
    
    profile: str = Field(..., description="Profile name")
    total_calls: int = Field(..., description="Total call limit")
    used_calls: int = Field(..., description="Used calls")
    remaining_calls: int = Field(..., description="Remaining calls")
    utilization: float = Field(..., description="Budget utilization (0.0-1.0)")
    warning: bool = Field(..., description="Whether warning threshold exceeded")
    by_domain: Dict[str, Dict[str, int]] = Field(default_factory=dict, description="Per-domain usage")
    by_tool: Dict[str, Dict[str, int]] = Field(default_factory=dict, description="Per-tool usage")


class TraceResponse(BaseModel):
    """Trace events response."""
    
    trace_id: str = Field(..., description="Trace identifier")
    events: List[Dict[str, Any]] = Field(..., description="Trace events")
    signals: Dict[str, Any] = Field(..., description="Golden signals")
    duration_ms: float = Field(..., description="Total duration in milliseconds")

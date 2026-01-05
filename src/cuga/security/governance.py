"""MCP & OpenAPI governance with policy gates, approval flows, and capability maps."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from ..agents.policy import PolicyViolation


logger = logging.getLogger(__name__)


class ActionType(Enum):
    """Classification of tool action severity."""
    
    READ = "read"  # Non-mutating queries (e.g., list files, get user)
    WRITE = "write"  # Mutating operations (e.g., send message, update record)
    DELETE = "delete"  # Destructive operations (e.g., delete file, drop table)
    FINANCIAL = "financial"  # Financial transactions (e.g., place order, transfer funds)
    EXTERNAL = "external"  # External API calls with side effects


class ApprovalStatus(Enum):
    """Status of approval request."""
    
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass
class ApprovalRequest:
    """Request for human-in-the-loop approval before tool execution."""
    
    request_id: str
    tool_name: str
    action_type: ActionType
    tenant: str
    inputs: Dict[str, Any]
    context: Dict[str, Any]
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    rejection_reason: Optional[str] = None
    
    def is_expired(self) -> bool:
        """Check if approval request has expired."""
        if self.expires_at is None:
            return False
        return datetime.utcnow() > self.expires_at


@dataclass
class ToolCapability:
    """Capability definition for a tool with governance rules."""
    
    name: str
    action_type: ActionType
    requires_approval: bool = False
    approval_timeout_seconds: int = 300  # 5 minutes default
    allowed_tenants: Set[str] = field(default_factory=set)  # Empty = all tenants
    denied_tenants: Set[str] = field(default_factory=set)
    max_rate_per_minute: Optional[int] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_allowed_for_tenant(self, tenant: str) -> bool:
        """Check if tenant is authorized to use this tool."""
        if tenant in self.denied_tenants:
            return False
        if not self.allowed_tenants:  # Empty set = allow all
            return True
        return tenant in self.allowed_tenants


@dataclass
class TenantCapabilityMap:
    """Per-tenant capability mapping with allowlist/denylist semantics."""
    
    tenant: str
    allowed_tools: Set[str] = field(default_factory=set)  # Empty = all allowed
    denied_tools: Set[str] = field(default_factory=set)
    max_concurrent_calls: int = 10
    budget_ceiling: int = 100  # Arbitrary budget units per tenant
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def can_use_tool(self, tool_name: str) -> bool:
        """Check if tenant can use the specified tool."""
        if tool_name in self.denied_tools:
            return False
        if not self.allowed_tools:  # Empty set = allow all
            return True
        return tool_name in self.allowed_tools


class GovernanceEngine:
    """Central governance engine for MCP/OpenAPI tool execution."""
    
    def __init__(
        self,
        capabilities: Dict[str, ToolCapability],
        tenant_maps: Dict[str, TenantCapabilityMap],
        approval_handler: Optional[Callable[[ApprovalRequest], ApprovalStatus]] = None,
    ) -> None:
        """
        Initialize governance engine.
        
        Args:
            capabilities: Tool name -> ToolCapability mapping
            tenant_maps: Tenant ID -> TenantCapabilityMap mapping
            approval_handler: Optional async approval callback (for HITL)
        """
        self.capabilities = capabilities
        self.tenant_maps = tenant_maps
        self.approval_handler = approval_handler
        self._pending_approvals: Dict[str, ApprovalRequest] = {}
        self._rate_limits: Dict[tuple[str, str], List[datetime]] = {}  # (tenant, tool) -> timestamps
        
    def validate_tool_call(
        self,
        tool_name: str,
        tenant: str,
        inputs: Dict[str, Any],
        context: Dict[str, Any],
    ) -> None:
        """
        Validate tool call against governance policies.
        
        Raises:
            PolicyViolation: If governance check fails
        """
        # Check if tool is registered in capability map
        capability = self.capabilities.get(tool_name)
        if capability is None:
            raise PolicyViolation(
                profile=tenant,
                tool=tool_name,
                code="tool_not_registered",
                message=f"Tool '{tool_name}' not found in governance capability map",
            )
        
        # Check tenant capability map
        tenant_map = self.tenant_maps.get(tenant)
        if tenant_map and not tenant_map.can_use_tool(tool_name):
            raise PolicyViolation(
                profile=tenant,
                tool=tool_name,
                code="tenant_tool_denied",
                message=f"Tenant '{tenant}' is not authorized to use tool '{tool_name}'",
                details={"allowed_tools": list(tenant_map.allowed_tools) if tenant_map.allowed_tools else "all"},
            )
        
        # Check tool-level tenant restrictions
        if not capability.is_allowed_for_tenant(tenant):
            raise PolicyViolation(
                profile=tenant,
                tool=tool_name,
                code="tool_tenant_denied",
                message=f"Tool '{tool_name}' is not available to tenant '{tenant}'",
                details={"allowed_tenants": list(capability.allowed_tenants) if capability.allowed_tenants else "all"},
            )
        
        # Check rate limits
        if capability.max_rate_per_minute:
            self._check_rate_limit(tenant, tool_name, capability.max_rate_per_minute)
        
        logger.info(
            "Governance validation passed",
            extra={
                "tool": tool_name,
                "tenant": tenant,
                "action_type": capability.action_type.value,
                "requires_approval": capability.requires_approval,
            },
        )
    
    def _check_rate_limit(self, tenant: str, tool_name: str, max_per_minute: int) -> None:
        """Check and enforce rate limits for tenant/tool combination."""
        key = (tenant, tool_name)
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)
        
        # Clean old timestamps
        if key in self._rate_limits:
            self._rate_limits[key] = [ts for ts in self._rate_limits[key] if ts > cutoff]
        else:
            self._rate_limits[key] = []
        
        # Check limit
        if len(self._rate_limits[key]) >= max_per_minute:
            raise PolicyViolation(
                profile=tenant,
                tool=tool_name,
                code="rate_limit_exceeded",
                message=f"Rate limit exceeded for tool '{tool_name}' (max {max_per_minute}/min)",
                details={"current_calls": len(self._rate_limits[key]), "max_per_minute": max_per_minute},
            )
        
        # Record this call
        self._rate_limits[key].append(now)
    
    def request_approval(
        self,
        tool_name: str,
        tenant: str,
        inputs: Dict[str, Any],
        context: Dict[str, Any],
        request_id: str,
    ) -> ApprovalRequest:
        """
        Create approval request for tools requiring HITL approval.
        
        Returns:
            ApprovalRequest with PENDING status
        """
        capability = self.capabilities.get(tool_name)
        if not capability:
            raise ValueError(f"Tool '{tool_name}' not found in capability map")
        
        if not capability.requires_approval:
            # Auto-approve tools that don't require human review
            logger.debug(f"Tool '{tool_name}' does not require approval, auto-approving")
            return ApprovalRequest(
                request_id=request_id,
                tool_name=tool_name,
                action_type=capability.action_type,
                tenant=tenant,
                inputs=inputs,
                context=context,
                status=ApprovalStatus.APPROVED,
                approved_by="auto",
            )
        
        approval_request = ApprovalRequest(
            request_id=request_id,
            tool_name=tool_name,
            action_type=capability.action_type,
            tenant=tenant,
            inputs=inputs,
            context=context,
            expires_at=datetime.utcnow() + timedelta(seconds=capability.approval_timeout_seconds),
        )
        
        self._pending_approvals[request_id] = approval_request
        
        logger.info(
            "Approval request created",
            extra={
                "request_id": request_id,
                "tool": tool_name,
                "tenant": tenant,
                "action_type": capability.action_type.value,
                "expires_at": approval_request.expires_at.isoformat() if approval_request.expires_at else None,
            },
        )
        
        # Invoke approval handler if provided
        if self.approval_handler:
            try:
                status = self.approval_handler(approval_request)
                approval_request.status = status
            except Exception as e:
                logger.error(f"Approval handler failed: {e}", exc_info=True)
        
        return approval_request
    
    def approve_request(self, request_id: str, approved_by: str) -> None:
        """Approve a pending request."""
        approval_request = self._pending_approvals.get(request_id)
        if not approval_request:
            raise ValueError(f"Approval request '{request_id}' not found")
        
        if approval_request.is_expired():
            approval_request.status = ApprovalStatus.EXPIRED
            raise PolicyViolation(
                profile=approval_request.tenant,
                tool=approval_request.tool_name,
                code="approval_expired",
                message=f"Approval request '{request_id}' has expired",
            )
        
        approval_request.status = ApprovalStatus.APPROVED
        approval_request.approved_by = approved_by
        
        logger.info(
            "Approval request approved",
            extra={
                "request_id": request_id,
                "tool": approval_request.tool_name,
                "approved_by": approved_by,
            },
        )
    
    def reject_request(self, request_id: str, reason: str) -> None:
        """Reject a pending request."""
        approval_request = self._pending_approvals.get(request_id)
        if not approval_request:
            raise ValueError(f"Approval request '{request_id}' not found")
        
        approval_request.status = ApprovalStatus.REJECTED
        approval_request.rejection_reason = reason
        
        logger.info(
            "Approval request rejected",
            extra={
                "request_id": request_id,
                "tool": approval_request.tool_name,
                "reason": reason,
            },
        )
    
    def get_approval_status(self, request_id: str) -> ApprovalStatus:
        """Get current status of approval request."""
        approval_request = self._pending_approvals.get(request_id)
        if not approval_request:
            raise ValueError(f"Approval request '{request_id}' not found")
        
        if approval_request.is_expired() and approval_request.status == ApprovalStatus.PENDING:
            approval_request.status = ApprovalStatus.EXPIRED
        
        return approval_request.status

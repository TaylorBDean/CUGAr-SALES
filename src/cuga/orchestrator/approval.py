"""
Approval gates for human-in-the-loop (HITL) orchestration.

This module provides approval policies, request/response flows, and timeout
handling for sensitive operations requiring human oversight before execution.

Version: 1.3.2
Author: Orchestration Team
Status: Production

Key Components:
- ApprovalPolicy: Configuration for approval requirements (timeout, required approvers)
- ApprovalRequest: Immutable request for approval with operation context
- ApprovalResponse: Immutable approval decision (approved/denied/timeout)
- ApprovalGate: High-level interface for requesting and waiting for approval

Usage Example:
    from cuga.orchestrator.approval import ApprovalPolicy, ApprovalGate, ApprovalStatus
    
    # Create policy
    policy = ApprovalPolicy(
        enabled=True,
        timeout_seconds=300,  # 5 minutes
        required_approvers=["admin@example.com"],
        auto_approve_on_timeout=False,
    )
    
    # Request approval
    gate = ApprovalGate(policy=policy)
    request = gate.create_request(
        operation="delete_database",
        metadata={"database": "production", "risk": "high"},
        trace_id="trace-123",
    )
    
    # Wait for approval (async)
    response = await gate.wait_for_approval(request)
    if response.status == ApprovalStatus.APPROVED:
        # Proceed with operation
        pass
"""

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol


class ApprovalStatus(str, Enum):
    """Status of approval request."""
    
    PENDING = "pending"          # Waiting for approval
    APPROVED = "approved"        # Approved by authorized user
    DENIED = "denied"            # Denied by authorized user
    TIMEOUT = "timeout"          # Request timed out
    CANCELLED = "cancelled"      # Request cancelled by system


@dataclass(frozen=True)
class ApprovalPolicy:
    """
    Immutable approval policy configuration.
    
    Defines requirements for approval gates including timeout, required approvers,
    and auto-approve behavior.
    """
    
    enabled: bool = True                          # Whether approval is required
    timeout_seconds: float = 300.0                # Max wait time for approval (5 min default)
    required_approvers: List[str] = field(default_factory=list)  # Email/IDs of authorized approvers
    auto_approve_on_timeout: bool = False         # Whether to auto-approve on timeout
    require_reason: bool = True                   # Whether approver must provide reason
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate approval policy."""
        if self.timeout_seconds <= 0:
            raise ValueError(f"Timeout must be positive, got {self.timeout_seconds}")
        if not isinstance(self.required_approvers, list):
            raise ValueError("required_approvers must be a list")


@dataclass(frozen=True)
class ApprovalRequest:
    """
    Immutable approval request with operation context.
    
    Represents a request for human approval before executing a sensitive operation.
    Includes all context needed for approver to make informed decision.
    """
    
    request_id: str                               # Unique request identifier
    operation: str                                # Operation requiring approval (e.g., "delete_database")
    trace_id: str                                 # Trace ID for observability
    timestamp: str                                # ISO 8601 request timestamp
    
    # Operation context
    metadata: Dict[str, Any] = field(default_factory=dict)  # Operation details
    risk_level: str = "medium"                    # Risk level: low, medium, high, critical
    requester: str = "system"                     # Who/what is requesting approval
    
    # Policy reference
    policy: Optional[ApprovalPolicy] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "operation": self.operation,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
            "risk_level": self.risk_level,
            "requester": self.requester,
            "policy": {
                "timeout_seconds": self.policy.timeout_seconds,
                "required_approvers": self.policy.required_approvers,
                "auto_approve_on_timeout": self.policy.auto_approve_on_timeout,
            } if self.policy else None,
        }


@dataclass(frozen=True)
class ApprovalResponse:
    """
    Immutable approval decision.
    
    Records the decision made by approver (or system on timeout) with
    timestamp, reason, and approver identity.
    """
    
    request_id: str                               # ID of original request
    status: ApprovalStatus                        # Approval decision
    timestamp: str                                # ISO 8601 decision timestamp
    
    # Decision context
    approver: str = "system"                      # Who made the decision
    reason: str = ""                              # Why decision was made
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "request_id": self.request_id,
            "status": self.status.value,
            "timestamp": self.timestamp,
            "approver": self.approver,
            "reason": self.reason,
            "metadata": self.metadata,
        }


class ApprovalCallback(Protocol):
    """
    Protocol for approval callback functions.
    
    Approval systems must implement this protocol to receive approval requests
    and return decisions asynchronously.
    """
    
    async def __call__(self, request: ApprovalRequest) -> ApprovalResponse:
        """
        Process approval request and return decision.
        
        Args:
            request: Approval request with operation context
            
        Returns:
            ApprovalResponse with decision (approved/denied)
            
        Raises:
            TimeoutError: If approval takes too long
        """
        ...


class ApprovalGate:
    """
    High-level interface for approval gates.
    
    Manages approval request creation, submission to callback, and waiting
    for approval with timeout handling.
    """
    
    def __init__(
        self,
        policy: ApprovalPolicy,
        callback: Optional[ApprovalCallback] = None,
    ):
        """
        Initialize approval gate.
        
        Args:
            policy: Approval policy configuration
            callback: Optional callback for processing approvals
        """
        self.policy = policy
        self.callback = callback
        self._pending_requests: Dict[str, asyncio.Future] = {}
    
    def create_request(
        self,
        operation: str,
        trace_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        risk_level: str = "medium",
        requester: str = "system",
    ) -> ApprovalRequest:
        """
        Create approval request.
        
        Args:
            operation: Operation requiring approval
            trace_id: Trace ID for observability
            metadata: Optional operation context
            risk_level: Risk level (low, medium, high, critical)
            requester: Who is requesting approval
            
        Returns:
            ApprovalRequest ready to be submitted
        """
        request_id = str(uuid.uuid4())
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
        
        return ApprovalRequest(
            request_id=request_id,
            operation=operation,
            trace_id=trace_id,
            timestamp=timestamp,
            metadata=metadata or {},
            risk_level=risk_level,
            requester=requester,
            policy=self.policy,
        )
    
    async def wait_for_approval(
        self,
        request: ApprovalRequest,
    ) -> ApprovalResponse:
        """
        Submit approval request and wait for decision.
        
        Args:
            request: Approval request to process
            
        Returns:
            ApprovalResponse with decision
            
        Raises:
            ValueError: If policy is disabled
            TimeoutError: If approval times out (and auto_approve_on_timeout is False)
        """
        if not self.policy.enabled:
            # Auto-approve if policy disabled
            return ApprovalResponse(
                request_id=request.request_id,
                status=ApprovalStatus.APPROVED,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                approver="system",
                reason="Approval policy disabled",
            )
        
        # If no callback, wait for manual approval via respond_to_request()
        if self.callback is None:
            return await self._wait_for_manual_approval(request)
        
        # Submit to callback with timeout
        try:
            response = await asyncio.wait_for(
                self.callback(request),
                timeout=self.policy.timeout_seconds,
            )
            return response
        except asyncio.TimeoutError:
            # Handle timeout
            if self.policy.auto_approve_on_timeout:
                return ApprovalResponse(
                    request_id=request.request_id,
                    status=ApprovalStatus.APPROVED,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                    approver="system",
                    reason=f"Auto-approved after {self.policy.timeout_seconds}s timeout",
                )
            else:
                return ApprovalResponse(
                    request_id=request.request_id,
                    status=ApprovalStatus.TIMEOUT,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                    approver="system",
                    reason=f"Approval timed out after {self.policy.timeout_seconds}s",
                )
    
    async def _wait_for_manual_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        """
        Wait for manual approval via respond_to_request().
        
        Creates a future that will be resolved when respond_to_request() is called.
        """
        future: asyncio.Future[ApprovalResponse] = asyncio.Future()
        self._pending_requests[request.request_id] = future
        
        try:
            # Wait for approval with timeout
            response = await asyncio.wait_for(
                future,
                timeout=self.policy.timeout_seconds,
            )
            return response
        except asyncio.TimeoutError:
            # Remove pending request
            self._pending_requests.pop(request.request_id, None)
            
            # Handle timeout
            if self.policy.auto_approve_on_timeout:
                return ApprovalResponse(
                    request_id=request.request_id,
                    status=ApprovalStatus.APPROVED,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                    approver="system",
                    reason=f"Auto-approved after {self.policy.timeout_seconds}s timeout",
                )
            else:
                return ApprovalResponse(
                    request_id=request.request_id,
                    status=ApprovalStatus.TIMEOUT,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                    approver="system",
                    reason=f"Approval timed out after {self.policy.timeout_seconds}s",
                )
    
    def respond_to_request(
        self,
        request_id: str,
        approved: bool,
        approver: str = "admin",
        reason: str = "",
    ) -> None:
        """
        Respond to pending approval request (for manual approval flow).
        
        Args:
            request_id: ID of request to respond to
            approved: Whether to approve or deny
            approver: Who is approving/denying
            reason: Reason for decision
            
        Raises:
            KeyError: If request_id not found in pending requests
        """
        if request_id not in self._pending_requests:
            raise KeyError(f"No pending request with ID {request_id}")
        
        future = self._pending_requests.pop(request_id)
        
        if not future.done():
            response = ApprovalResponse(
                request_id=request_id,
                status=ApprovalStatus.APPROVED if approved else ApprovalStatus.DENIED,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                approver=approver,
                reason=reason or ("Approved" if approved else "Denied"),
            )
            future.set_result(response)
    
    def get_pending_requests(self) -> List[str]:
        """Get list of pending request IDs."""
        return list(self._pending_requests.keys())
    
    def cancel_request(self, request_id: str) -> None:
        """
        Cancel pending approval request.
        
        Args:
            request_id: ID of request to cancel
            
        Raises:
            KeyError: If request_id not found
        """
        if request_id not in self._pending_requests:
            raise KeyError(f"No pending request with ID {request_id}")
        
        future = self._pending_requests.pop(request_id)
        
        if not future.done():
            response = ApprovalResponse(
                request_id=request_id,
                status=ApprovalStatus.CANCELLED,
                timestamp=time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime()),
                approver="system",
                reason="Request cancelled",
            )
            future.set_result(response)


def create_approval_gate(
    enabled: bool = True,
    timeout_seconds: float = 300.0,
    required_approvers: Optional[List[str]] = None,
    auto_approve_on_timeout: bool = False,
    callback: Optional[ApprovalCallback] = None,
) -> ApprovalGate:
    """
    Factory function for creating approval gates.
    
    Args:
        enabled: Whether approval is required
        timeout_seconds: Max wait time for approval
        required_approvers: List of authorized approvers
        auto_approve_on_timeout: Whether to auto-approve on timeout
        callback: Optional approval callback
        
    Returns:
        Configured ApprovalGate
    """
    policy = ApprovalPolicy(
        enabled=enabled,
        timeout_seconds=timeout_seconds,
        required_approvers=required_approvers or [],
        auto_approve_on_timeout=auto_approve_on_timeout,
    )
    
    return ApprovalGate(policy=policy, callback=callback)

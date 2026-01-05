"""
Human approval management per AGENTS.md human authority preservation.
Implements approval requests for irreversible actions with timeout handling.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
import uuid
import logging

logger = logging.getLogger(__name__)


@dataclass
class ApprovalRequest:
    """
    Approval request data structure.
    
    Per AGENTS.md:
    - Human authority preserved for irreversible actions
    - Explicit consequences surfaced
    - Risk level classification
    """
    approval_id: str
    action: str
    tool_name: str
    inputs: Dict[str, Any]
    reasoning: str
    risk_level: str  # low, medium, high
    consequences: List[str]
    requested_at: str
    expires_at: str
    status: str  # pending, approved, rejected, timeout
    profile: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for API responses."""
        return asdict(self)


class ApprovalManager:
    """
    Manages human approval requests per AGENTS.md guardrails.
    
    Per AGENTS.md Over-Automation Prohibitions:
    - Auto-sending emails/messages FORBIDDEN
    - Auto-assigning territories FORBIDDEN
    - Auto-closing deals FORBIDDEN
    - Auto-modifying pricing/contracts FORBIDDEN
    
    Systems MUST:
    - Propose actions
    - Explain reasoning
    - Simulate outcomes
    - Require human approval for irreversible changes
    """
    
    # Side-effect classes requiring approval per AGENTS.md
    REQUIRES_APPROVAL = {"execute", "propose"}
    
    # Timeout for approval requests (24 hours)
    APPROVAL_TIMEOUT = timedelta(hours=24)
    
    def __init__(self, trace_emitter=None):
        """
        Initialize approval manager.
        
        Args:
            trace_emitter: Optional TraceEmitter for canonical events
        """
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        self.trace_emitter = trace_emitter
    
    def request_approval(
        self,
        action: str,
        tool_name: str,
        inputs: Dict[str, Any],
        reasoning: str,
        side_effect_class: str,
        profile: Optional[str] = None
    ) -> str:
        """
        Request human approval for action.
        
        Per AGENTS.md:
        - Emits approval_requested canonical event
        - Infers consequences from side-effect class
        - Classifies risk level
        
        Args:
            action: Human-readable action description
            tool_name: Tool requiring approval
            inputs: Tool input parameters
            reasoning: Agent reasoning for this action
            side_effect_class: From tool metadata (read-only, propose, execute)
            profile: Optional sales profile for context
        
        Returns:
            approval_id: Unique approval request identifier
        """
        approval_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        # Infer risk level and consequences
        risk_level = self._classify_risk(tool_name, side_effect_class)
        consequences = self._infer_consequences(tool_name, side_effect_class, inputs)
        
        request = ApprovalRequest(
            approval_id=approval_id,
            action=action,
            tool_name=tool_name,
            inputs=inputs,
            reasoning=reasoning,
            risk_level=risk_level,
            consequences=consequences,
            requested_at=now.isoformat(),
            expires_at=(now + self.APPROVAL_TIMEOUT).isoformat(),
            status="pending",
            profile=profile
        )
        
        self.pending_approvals[approval_id] = request
        
        # Emit canonical event
        if self.trace_emitter:
            self.trace_emitter.emit(
                "approval_requested",
                {
                    "approval_id": approval_id,
                    "tool_name": tool_name,
                    "risk_level": risk_level,
                    "profile": profile
                },
                status="pending"
            )
        
        logger.info(
            f"Approval requested: {action}",
            extra={"approval_id": approval_id, "tool": tool_name}
        )
        
        return approval_id
    
    def get_approval(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Retrieve approval request details."""
        request = self.pending_approvals.get(approval_id)
        
        # Check for timeout
        if request and request.status == "pending":
            expires_at = datetime.fromisoformat(request.expires_at)
            if datetime.now(timezone.utc) > expires_at:
                request.status = "timeout"
                if self.trace_emitter:
                    self.trace_emitter.emit(
                        "approval_timeout",
                        {"approval_id": approval_id},
                        status="error"
                    )
        
        return request
    
    def approve(self, approval_id: str) -> bool:
        """
        Mark approval as approved.
        
        Emits approval_received canonical event per AGENTS.md.
        """
        request = self.get_approval(approval_id)
        if not request or request.status != "pending":
            return False
        
        request.status = "approved"
        
        # Emit canonical event
        if self.trace_emitter:
            self.trace_emitter.emit(
                "approval_received",
                {"approval_id": approval_id, "decision": "approved"},
                status="success"
            )
        
        logger.info(f"Approval granted: {approval_id}")
        return True
    
    def reject(self, approval_id: str, reason: str = "") -> bool:
        """
        Mark approval as rejected.
        
        Emits approval_received canonical event per AGENTS.md.
        """
        request = self.get_approval(approval_id)
        if not request or request.status != "pending":
            return False
        
        request.status = "rejected"
        
        # Emit canonical event
        if self.trace_emitter:
            self.trace_emitter.emit(
                "approval_received",
                {
                    "approval_id": approval_id,
                    "decision": "rejected",
                    "reason": reason
                },
                status="error"
            )
        
        logger.info(f"Approval rejected: {approval_id}", extra={"reason": reason})
        return True
    
    def list_pending(self, profile: Optional[str] = None) -> List[ApprovalRequest]:
        """List all pending approval requests, optionally filtered by profile."""
        pending = [
            req for req in self.pending_approvals.values()
            if req.status == "pending"
        ]
        
        if profile:
            pending = [req for req in pending if req.profile == profile]
        
        return pending
    
    def _classify_risk(self, tool_name: str, side_effect_class: str) -> str:
        """
        Classify risk level based on tool and side-effect class.
        
        Per AGENTS.md side-effect classification:
        - read-only: low risk
        - propose: medium risk
        - execute: high risk
        """
        if side_effect_class == "execute":
            return "high"
        elif side_effect_class == "propose":
            return "medium"
        return "low"
    
    def _infer_consequences(
        self,
        tool_name: str,
        side_effect_class: str,
        inputs: Dict[str, Any]
    ) -> List[str]:
        """
        Infer consequences based on tool's side-effect class.
        
        Per AGENTS.md domain guardrails:
        - Engagement: draft/propose only, human approval required
        - Territory: simulation-only, no ownership mutation
        - Qualification: conservative bias, surface unknowns
        """
        consequences = []
        
        # Per AGENTS.md Over-Automation Prohibitions
        if "send" in tool_name or "publish" in tool_name:
            consequences.extend([
                "Message will be sent to external party",
                "Action cannot be undone",
                "Recipient will see sender information"
            ])
        elif "assign" in tool_name or "update" in tool_name:
            consequences.extend([
                "CRM record will be modified",
                "Change will be visible to team",
                "Audit log will record this action"
            ])
        elif "close" in tool_name or "forecast" in tool_name:
            consequences.extend([
                "Deal status will change permanently",
                "Revenue forecast will be affected",
                "Team metrics will be impacted"
            ])
        else:
            consequences.append("Action will be executed")
        
        # Add generic consequence
        consequences.append("Review impact before approving")
        
        return consequences

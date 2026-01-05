"""
Canonical Orchestrator Contract

This module defines the explicit, single orchestrator interface for CUGAR agent system.
All orchestration implementations MUST implement this protocol to ensure:
- Clear lifecycle boundaries
- Deterministic routing decisions via RoutingAuthority
- Explicit error propagation with failure modes
- Well-defined execution context

See docs/orchestrator/ORCHESTRATOR_CONTRACT.md for detailed architecture.
See docs/orchestrator/ROUTING_AUTHORITY.md for routing decision authority.
See docs/orchestrator/FAILURE_MODES.md for failure taxonomy and retry semantics.
"""

from .protocol import (
    AgentLifecycle,
    ExecutionContext,
    OrchestrationError,
    OrchestratorProtocol,
    RoutingDecision,
    LifecycleStage,
    ErrorPropagation,
)

from .routing import (
    # Core Authority
    RoutingAuthority,
    PolicyBasedRoutingAuthority,
    create_routing_authority,
    
    # Context and Decisions
    RoutingContext,
    RoutingDecision as RoutingDecisionV2,  # New canonical version
    RoutingCandidate,
    
    # Policies
    RoutingPolicy,
    RoundRobinPolicy,
    CapabilityBasedPolicy,
    
    # Enums
    RoutingStrategy,
    RoutingDecisionType,
)

from .failures import (
    # Failure Taxonomy
    FailureMode,
    FailureCategory,
    FailureSeverity,
    
    # Failure Context
    FailureContext,
    PartialResult,
    
    # Retry Policies
    RetryPolicy,
    ExponentialBackoffPolicy,
    LinearBackoffPolicy,
    NoRetryPolicy,
    
    # Retry Execution
    RetryExecutor,
    create_retry_policy,
)

from .planning import (
    # Planning Authority
    PlanningAuthority,
    ToolRankingPlanner,
    create_planning_authority,
    
    # Plan and Steps
    Plan,
    PlanStep,
    PlanningStage,
    
    # Budget
    ToolBudget,
    BudgetError,
)

from .audit import (
    # Audit Records
    DecisionRecord,
    AuditTrail,
    create_audit_trail,
    
    # Backends
    AuditBackend,
    JSONAuditBackend,
    SQLiteAuditBackend,
)

from .trace_emitter import (
    # Canonical Trace Emission (AGENTS.md)
    TraceEmitter,
)

from .budget_enforcer import (
    # Budget Enforcement (AGENTS.md)
    ToolBudget as ToolBudgetEnforcer,  # Avoid conflict with planning.ToolBudget
    BudgetEnforcer,
)

from .approval_manager import (
    # Human Approval (AGENTS.md)
    ApprovalRequest as ApprovalRequestAGENTS,  # Avoid conflict with approval.ApprovalRequest
    ApprovalManager,
)

from .profile_loader import (
    # Profile-Driven Behavior (AGENTS.md)
    ProfileConfig,
    ProfileLoader,
)

from .coordinator import (
    # Integrated Coordinator (AGENTS.md)
    AGENTSCoordinator,
    ExecutionResult,
)

__all__ = [
    # Protocol
    "OrchestratorProtocol",
    "AgentLifecycle",
    
    # Core Types (Legacy)
    "ExecutionContext",
    "RoutingDecision",  # Legacy - migrate to RoutingDecisionV2
    "OrchestrationError",
    
    # Enums (Legacy)
    "LifecycleStage",
    "ErrorPropagation",
    
    # Routing Authority (Canonical)
    "RoutingAuthority",
    "PolicyBasedRoutingAuthority",
    "create_routing_authority",
    "RoutingContext",
    "RoutingDecisionV2",
    "RoutingCandidate",
    "RoutingPolicy",
    "RoundRobinPolicy",
    "CapabilityBasedPolicy",
    "RoutingStrategy",
    "RoutingDecisionType",
    
    # Failure Modes and Retry Semantics (Canonical)
    "FailureMode",
    "FailureCategory",
    "FailureSeverity",
    "FailureContext",
    "PartialResult",
    "RetryPolicy",
    "ExponentialBackoffPolicy",
    "LinearBackoffPolicy",
    "NoRetryPolicy",
    "RetryExecutor",
    "create_retry_policy",
    
    # Planning Authority (Canonical)
    "PlanningAuthority",
    "ToolRankingPlanner",
    "create_planning_authority",
    "Plan",
    "PlanStep",
    "PlanningStage",
    "ToolBudget",
    "BudgetError",
    
    # Audit Trail (Canonical)
    "DecisionRecord",
    "AuditTrail",
    "create_audit_trail",
    "AuditBackend",
    "JSONAuditBackend",
    "SQLiteAuditBackend",
    
    # AGENTS.md Compliance Components
    "TraceEmitter",
    "ToolBudgetEnforcer",
    "BudgetEnforcer",
    "ApprovalRequestAGENTS",
    "ApprovalManager",
    "ProfileConfig",
    "ProfileLoader",
    "AGENTSCoordinator",
    "ExecutionResult",
]


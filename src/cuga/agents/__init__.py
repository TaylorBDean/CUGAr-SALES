"""
Controller-led multi-agent pipeline primitives with lifecycle management and I/O contracts.

Includes canonical lifecycle protocols for agent initialization, shutdown, and state management,
plus standardized input/output contracts for clean routing and orchestration.
"""

from .controller import Controller
from .executor import ExecutionContext, ExecutionResult, Executor
from .policy import PolicyEnforcer, PolicyViolation
from .planner import PlanStep, Planner
from .registry import ToolRegistry

# Lifecycle Management (Canonical)
from .lifecycle import (
    # Core Protocol
    AgentLifecycleProtocol,
    
    # Base Implementation
    ManagedAgent,
    
    # State Enums
    AgentState,
    StateOwnership,
    
    # Configuration
    LifecycleConfig,
    LifecycleMetrics,
    
    # Utilities
    requires_state,
    agent_lifecycle,
    
    # Exceptions
    StartupError,
    ShutdownError,
    StateViolationError,
)

# I/O Contracts (Canonical)
from .contracts import (
    # Core Protocol
    AgentProtocol,
    
    # Request/Response
    AgentRequest,
    AgentResponse,
    RequestMetadata,
    AgentError,
    
    # Enums
    ResponseStatus,
    ErrorType,
    
    # Convenience Constructors
    success_response,
    error_response,
    partial_response,
    
    # Validation
    validate_request,
    validate_response,
)

__all__ = [
    # Existing Multi-Agent Primitives
    "Controller",
    "ExecutionContext",
    "ExecutionResult",
    "Executor",
    "PolicyEnforcer",
    "PolicyViolation",
    "PlanStep",
    "Planner",
    "ToolRegistry",
    
    # Lifecycle Management (Canonical)
    "AgentLifecycleProtocol",
    "ManagedAgent",
    "AgentState",
    "StateOwnership",
    "LifecycleConfig",
    "LifecycleMetrics",
    "requires_state",
    "agent_lifecycle",
    "StartupError",
    "ShutdownError",
    "StateViolationError",
    
    # I/O Contracts (Canonical)
    "AgentProtocol",
    "AgentRequest",
    "AgentResponse",
    "RequestMetadata",
    "AgentError",
    "ResponseStatus",
    "ErrorType",
    "success_response",
    "error_response",
    "partial_response",
    "validate_request",
    "validate_response",
]

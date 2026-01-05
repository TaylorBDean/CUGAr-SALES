"""
Canonical Orchestrator Protocol

This module defines the single source of truth for orchestrator interfaces
in the CUGAR agent system. All orchestration logic MUST conform to this protocol.

Key Principles:
1. Single Responsibility: Orchestrators manage lifecycle, routing, and coordination only
2. Explicit Contracts: All inputs, outputs, and state transitions are typed
3. Error Transparency: Failures propagate with context, never silently swallowed
4. Trace Continuity: trace_id flows through all stages without mutation
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol


class LifecycleStage(str, Enum):
    """Canonical lifecycle stages for agent execution."""
    
    INITIALIZE = "initialize"  # Agent/resources are being initialized
    PLAN = "plan"              # Planning/decomposition phase
    ROUTE = "route"            # Routing decision made
    EXECUTE = "execute"        # Tool/step execution
    AGGREGATE = "aggregate"    # Results aggregation
    COMPLETE = "complete"      # Successful completion
    FAILED = "failed"          # Terminal failure
    CANCELLED = "cancelled"    # User/system cancellation


@dataclass(frozen=True)
class ExecutionContext:
    """
    Explicit, immutable execution context passed through all orchestrator operations.
    
    Provides complete observability and safe orchestration across agents by making
    all context (request ID, user intent, memory scope, trace info) explicit and
    type-checked rather than implied.
    
    Attributes:
        trace_id: Unique identifier for this execution trace (required, immutable)
        request_id: Unique request identifier for API/user interactions
        profile: Security/configuration profile name
        user_intent: Explicit user goal/intent for this execution
        memory_scope: Memory namespace for session/user isolation
        conversation_id: Conversation thread identifier for multi-turn interactions
        session_id: Session identifier for user session tracking
        user_id: User identifier for access control and personalization
        metadata: Additional execution metadata (read-only)
        parent_context: Optional parent context for nested orchestrations
        created_at: Context creation timestamp (ISO 8601)
    
    Immutability:
        All fields are frozen. Use with_* methods to create updated contexts
        while preserving trace continuity and parent relationships.
    
    Example:
        >>> # Create root context
        >>> ctx = ExecutionContext(
        ...     trace_id="trace-123",
        ...     request_id="req-456",
        ...     user_intent="Find flight to NYC",
        ...     memory_scope="user:alice/session:789",
        ...     conversation_id="conv-101",
        ...     session_id="sess-789",
        ...     user_id="user-alice",
        ... )
        >>> 
        >>> # Create child context with updated intent
        >>> child_ctx = ctx.with_user_intent("Book cheapest flight")
        >>> child_ctx.parent_context == ctx  # True
        >>> child_ctx.trace_id == ctx.trace_id  # True (preserved)
    """
    
    # Required fields
    trace_id: str
    
    # Request tracking
    request_id: str = ""
    
    # Configuration
    profile: str = "default"
    
    # User context
    user_intent: str = ""
    user_id: str = ""
    
    # Memory & session management
    memory_scope: str = ""
    conversation_id: str = ""
    session_id: str = ""
    
    # Additional context
    metadata: Dict[str, Any] = field(default_factory=dict)
    parent_context: Optional[ExecutionContext] = None
    
    # Timestamp
    created_at: str = field(default_factory=lambda: __import__('datetime').datetime.utcnow().isoformat())
    
    def with_metadata(self, **kwargs: Any) -> ExecutionContext:
        """
        Create new context with merged metadata.
        
        Args:
            **kwargs: Metadata key-value pairs to merge
        
        Returns:
            New ExecutionContext with merged metadata, preserving all other fields
        """
        return ExecutionContext(
            trace_id=self.trace_id,
            request_id=self.request_id,
            profile=self.profile,
            user_intent=self.user_intent,
            user_id=self.user_id,
            memory_scope=self.memory_scope,
            conversation_id=self.conversation_id,
            session_id=self.session_id,
            metadata={**self.metadata, **kwargs},
            parent_context=self.parent_context,
            created_at=self.created_at,
        )
    
    def with_user_intent(self, intent: str) -> ExecutionContext:
        """
        Create new context with updated user intent (nested orchestration).
        
        Args:
            intent: New user intent
        
        Returns:
            New ExecutionContext with updated intent and current context as parent
        """
        return ExecutionContext(
            trace_id=self.trace_id,
            request_id=self.request_id,
            profile=self.profile,
            user_intent=intent,
            user_id=self.user_id,
            memory_scope=self.memory_scope,
            conversation_id=self.conversation_id,
            session_id=self.session_id,
            metadata=self.metadata.copy(),
            parent_context=self,
            created_at=__import__('datetime').datetime.utcnow().isoformat(),
        )
    
    def with_request_id(self, request_id: str) -> ExecutionContext:
        """
        Create new context with updated request ID (new request in same trace).
        
        Args:
            request_id: New request identifier
        
        Returns:
            New ExecutionContext with updated request_id
        """
        return ExecutionContext(
            trace_id=self.trace_id,
            request_id=request_id,
            profile=self.profile,
            user_intent=self.user_intent,
            user_id=self.user_id,
            memory_scope=self.memory_scope,
            conversation_id=self.conversation_id,
            session_id=self.session_id,
            metadata=self.metadata.copy(),
            parent_context=self.parent_context,
            created_at=self.created_at,
        )
    
    def with_profile(self, profile: str) -> ExecutionContext:
        """
        Create new context with updated profile (configuration change).
        
        Args:
            profile: New security/configuration profile
        
        Returns:
            New ExecutionContext with updated profile
        """
        return ExecutionContext(
            trace_id=self.trace_id,
            request_id=self.request_id,
            profile=profile,
            user_intent=self.user_intent,
            user_id=self.user_id,
            memory_scope=self.memory_scope,
            conversation_id=self.conversation_id,
            session_id=self.session_id,
            metadata=self.metadata.copy(),
            parent_context=self.parent_context,
            created_at=self.created_at,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert context to dictionary for serialization/logging.
        
        Returns:
            Dictionary representation with all non-None fields
        """
        return {
            "trace_id": self.trace_id,
            "request_id": self.request_id,
            "profile": self.profile,
            "user_intent": self.user_intent,
            "user_id": self.user_id,
            "memory_scope": self.memory_scope,
            "conversation_id": self.conversation_id,
            "session_id": self.session_id,
            "metadata": self.metadata,
            "has_parent": self.parent_context is not None,
            "created_at": self.created_at,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExecutionContext:
        """
        Create context from dictionary representation.
        
        Args:
            data: Dictionary with context fields
        
        Returns:
            New ExecutionContext instance
        """
        return cls(
            trace_id=data.get("trace_id", ""),
            request_id=data.get("request_id", ""),
            profile=data.get("profile", "default"),
            user_intent=data.get("user_intent", ""),
            user_id=data.get("user_id", ""),
            memory_scope=data.get("memory_scope", ""),
            conversation_id=data.get("conversation_id", ""),
            session_id=data.get("session_id", ""),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", ""),
        )
    
    def validate(self) -> List[str]:
        """
        Validate context has required fields.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not self.trace_id:
            errors.append("trace_id is required")
        
        if self.memory_scope and not self.user_id:
            errors.append("memory_scope requires user_id to be set")
        
        if self.conversation_id and not self.session_id:
            errors.append("conversation_id requires session_id to be set")
        
        return errors


@dataclass(frozen=True)
class RoutingDecision:
    """
    Explicit routing decision made by orchestrator.
    
    Attributes:
        target: Target agent/worker identifier
        reason: Human-readable justification
        metadata: Additional routing context
        fallback: Optional fallback target if primary fails
    """
    
    target: str
    reason: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    fallback: Optional[str] = None


class ErrorPropagation(str, Enum):
    """Defines how errors should be handled during orchestration."""
    
    FAIL_FAST = "fail_fast"        # Stop immediately on first error
    CONTINUE = "continue"          # Log error, continue with remaining steps
    RETRY = "retry"                # Attempt retry with backoff
    FALLBACK = "fallback"          # Use fallback routing decision


@dataclass
class OrchestrationError(Exception):
    """
    Structured error for orchestration failures.
    
    Attributes:
        stage: Lifecycle stage where error occurred
        message: Human-readable error description
        context: Execution context at time of failure
        cause: Original exception (if any)
        recoverable: Whether error is recoverable
        metadata: Additional error context
    """
    
    stage: LifecycleStage
    message: str
    context: ExecutionContext
    cause: Optional[Exception] = None
    recoverable: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __str__(self) -> str:
        parts = [
            f"OrchestrationError at {self.stage.value}:",
            self.message,
            f"trace_id={self.context.trace_id}",
        ]
        if self.cause:
            parts.append(f"caused by {type(self.cause).__name__}: {self.cause}")
        return " ".join(parts)


class AgentLifecycle(Protocol):
    """
    Protocol defining agent lifecycle management.
    Orchestrators MUST implement this to manage agent state transitions.
    """
    
    async def initialize(self, context: ExecutionContext) -> None:
        """
        Initialize agent for execution.
        
        Args:
            context: Execution context
            
        Raises:
            OrchestrationError: If initialization fails
        """
        ...
    
    async def teardown(self, context: ExecutionContext) -> None:
        """
        Clean up agent resources.
        
        Args:
            context: Execution context
            
        Note:
            MUST NOT raise exceptions - log failures internally
        """
        ...
    
    def get_stage(self) -> LifecycleStage:
        """Return current lifecycle stage."""
        ...


class OrchestratorProtocol(ABC):
    """
    Canonical orchestrator interface.
    
    All orchestrator implementations (Coordinator, AgentRunner, etc.) MUST
    implement this protocol to ensure consistent behavior across the system.
    
    Responsibilities:
    1. Lifecycle Management: Initialize/teardown agents and resources
    2. Routing Decisions: Determine which agent/worker handles each task
    3. Error Propagation: Handle failures with explicit recovery strategy
    4. Context Management: Maintain execution context across operations
    5. Trace Continuity: Ensure trace_id flows through all stages
    
    Non-Responsibilities (delegated to other components):
    - Tool registration (handled by ToolRegistry)
    - Policy enforcement (handled by PolicyEnforcer)
    - Memory management (handled by VectorMemory)
    - Observability emission (handled by BaseEmitter)
    """
    
    @abstractmethod
    async def orchestrate(
        self,
        goal: str,
        context: ExecutionContext,
        *,
        error_strategy: ErrorPropagation = ErrorPropagation.FAIL_FAST,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Primary orchestration method.
        
        Args:
            goal: User goal/task description
            context: Execution context with trace_id and profile
            error_strategy: How to handle errors during orchestration
            
        Yields:
            Dict containing:
                - stage: LifecycleStage
                - data: Stage-specific output
                - context: Updated execution context
                
        Raises:
            OrchestrationError: On unrecoverable failures
            
        Example:
            >>> orchestrator = MyOrchestrator(...)
            >>> context = ExecutionContext(trace_id="abc123", profile="demo")
            >>> async for event in orchestrator.orchestrate("search web", context):
            ...     print(f"Stage: {event['stage']}, Data: {event['data']}")
        """
        ...
    
    @abstractmethod
    def make_routing_decision(
        self,
        task: str,
        context: ExecutionContext,
        available_agents: List[str],
    ) -> RoutingDecision:
        """
        Make explicit routing decision.
        
        Args:
            task: Task description to route
            context: Current execution context
            available_agents: List of available agent identifiers
            
        Returns:
            RoutingDecision with target, reason, and optional fallback
            
        Note:
            MUST be deterministic for same inputs (for testing/replay)
        """
        ...
    
    @abstractmethod
    async def handle_error(
        self,
        error: OrchestrationError,
        strategy: ErrorPropagation,
    ) -> Optional[Dict[str, Any]]:
        """
        Handle orchestration error with specified strategy.
        
        Args:
            error: Orchestration error to handle
            strategy: Error handling strategy
            
        Returns:
            Recovery result if strategy != FAIL_FAST, None otherwise
            
        Raises:
            OrchestrationError: If strategy is FAIL_FAST or recovery fails
        """
        ...
    
    @abstractmethod
    def get_lifecycle(self) -> AgentLifecycle:
        """
        Get lifecycle manager for this orchestrator.
        
        Returns:
            AgentLifecycle implementation
        """
        ...


@dataclass
class OrchestratorMetrics:
    """
    Metrics collected during orchestration.
    
    Orchestrators SHOULD emit these metrics for observability.
    """
    
    total_steps: int = 0
    successful_steps: int = 0
    failed_steps: int = 0
    retries: int = 0
    routing_decisions: int = 0
    average_step_duration_ms: float = 0.0
    
    def record_success(self) -> None:
        """Record successful step execution."""
        self.successful_steps += 1
        self.total_steps += 1
    
    def record_failure(self) -> None:
        """Record failed step execution."""
        self.failed_steps += 1
        self.total_steps += 1
    
    def record_retry(self) -> None:
        """Record retry attempt."""
        self.retries += 1
    
    def record_routing(self) -> None:
        """Record routing decision made."""
        self.routing_decisions += 1


# Type aliases for common patterns
OrchestratorEvent = Dict[str, Any]
OrchestrationStream = AsyncIterator[OrchestratorEvent]

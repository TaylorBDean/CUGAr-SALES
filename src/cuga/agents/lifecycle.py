"""
Agent Lifecycle Protocol

Defines explicit contracts for agent initialization, shutdown, and state management.
All agents MUST implement this protocol to ensure clean startup/teardown and
unambiguous state ownership.

Clarifies ambiguity between agents/, mcp-*, and src/ agent implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional, Protocol
from contextlib import asynccontextmanager, contextmanager


class AgentState(str, Enum):
    """Canonical agent lifecycle states."""
    
    UNINITIALIZED = "uninitialized"  # Agent created but not initialized
    INITIALIZING = "initializing"    # Initialization in progress
    READY = "ready"                  # Initialized and ready for work
    BUSY = "busy"                    # Actively processing
    PAUSED = "paused"                # Temporarily suspended
    SHUTTING_DOWN = "shutting_down" # Cleanup in progress
    TERMINATED = "terminated"        # Fully cleaned up


class StateOwnership(str, Enum):
    """
    Defines who owns what state.
    
    Critical for preventing ambiguous state management between:
    - Agent (ephemeral, request-scoped)
    - Memory (persistent, cross-request)
    - Orchestrator (coordination, trace propagation)
    """
    
    AGENT = "agent"              # Owned by agent instance (ephemeral)
    MEMORY = "memory"            # Owned by memory system (persistent)
    ORCHESTRATOR = "orchestrator"  # Owned by orchestrator (coordination)
    SHARED = "shared"            # Shared ownership with explicit protocol


@dataclass(frozen=True)
class LifecycleConfig:
    """
    Configuration for agent lifecycle management.
    
    Attributes:
        timeout_seconds: Maximum time for startup/shutdown
        retry_on_failure: Whether to retry failed initialization
        max_retries: Maximum initialization retries
        cleanup_on_error: Whether to cleanup on initialization error
        state_persistence: Where to persist agent state
    """
    
    timeout_seconds: float = 30.0
    retry_on_failure: bool = False
    max_retries: int = 3
    cleanup_on_error: bool = True
    state_persistence: StateOwnership = StateOwnership.MEMORY


@dataclass
class LifecycleMetrics:
    """Metrics collected during agent lifecycle."""
    
    startup_time_ms: float = 0.0
    shutdown_time_ms: float = 0.0
    active_time_ms: float = 0.0
    total_requests: int = 0
    failed_requests: int = 0
    state_transitions: int = 0
    
    def record_transition(self, from_state: AgentState, to_state: AgentState) -> None:
        """Record state transition."""
        self.state_transitions += 1


class AgentLifecycleProtocol(Protocol):
    """
    Canonical protocol for agent lifecycle management.
    
    All agents (PlannerAgent, WorkerAgent, CoordinatorAgent, MCP agents) MUST
    implement this protocol to ensure:
    1. Clean startup/shutdown
    2. Clear state ownership
    3. Resource cleanup guarantees
    4. Composability across agent types
    
    State Ownership Rules:
    - **AGENT**: Ephemeral state (current request, temp data)
    - **MEMORY**: Persistent state (history, embeddings, facts)
    - **ORCHESTRATOR**: Coordination state (trace_id, routing)
    
    Lifecycle Guarantees:
    - startup() called before any work
    - shutdown() called on termination (even on error)
    - get_state() reflects current lifecycle state
    - State transitions are atomic and logged
    """
    
    @abstractmethod
    async def startup(self, config: Optional[LifecycleConfig] = None) -> None:
        """
        Initialize agent resources.
        
        Args:
            config: Optional lifecycle configuration
            
        Raises:
            StartupError: If initialization fails unrecoverably
            
        Responsibilities:
        - Allocate resources (connections, memory, etc.)
        - Validate configuration
        - Register with orchestrator (if managed)
        - Transition to READY state
        
        State Ownership:
        - AGENT state initialized here (empty on first call)
        - MEMORY state loaded if exists
        - ORCHESTRATOR state NOT managed by agent
        
        Must be idempotent: calling multiple times should be safe.
        """
        ...
    
    @abstractmethod
    async def shutdown(self, timeout_seconds: Optional[float] = None) -> None:
        """
        Clean up agent resources.
        
        Args:
            timeout_seconds: Maximum time to wait for cleanup
            
        Responsibilities:
        - Release resources (close connections, free memory)
        - Persist state to MEMORY if configured
        - Deregister from orchestrator (if managed)
        - Transition to TERMINATED state
        
        MUST NOT raise exceptions - log errors internally.
        MUST complete within timeout or forcefully terminate.
        
        State Ownership:
        - AGENT state discarded (ephemeral)
        - MEMORY state persisted if dirty
        - ORCHESTRATOR notified of shutdown
        """
        ...
    
    @abstractmethod
    def get_state(self) -> AgentState:
        """
        Get current lifecycle state.
        
        Returns:
            Current AgentState enum value
            
        Must be thread-safe and non-blocking.
        """
        ...
    
    @abstractmethod
    def get_metrics(self) -> LifecycleMetrics:
        """
        Get lifecycle metrics.
        
        Returns:
            LifecycleMetrics with current values
        """
        ...
    
    @abstractmethod
    def owns_state(self, key: str) -> StateOwnership:
        """
        Determine who owns a specific state key.
        
        Args:
            key: State key to check
            
        Returns:
            StateOwnership enum indicating owner
            
        Examples:
            >>> agent.owns_state("current_request")
            StateOwnership.AGENT
            
            >>> agent.owns_state("user_history")
            StateOwnership.MEMORY
            
            >>> agent.owns_state("trace_id")
            StateOwnership.ORCHESTRATOR
        """
        ...


class ManagedAgent(ABC):
    """
    Base class for agents with lifecycle management.
    
    Provides default implementations and context manager support.
    Agents can inherit this or implement AgentLifecycleProtocol directly.
    """
    
    def __init__(self, config: Optional[LifecycleConfig] = None) -> None:
        self._state = AgentState.UNINITIALIZED
        self._config = config or LifecycleConfig()
        self._metrics = LifecycleMetrics()
        self._agent_state: Dict[str, Any] = {}  # Ephemeral
    
    async def startup(self, config: Optional[LifecycleConfig] = None) -> None:
        """Default startup implementation."""
        if self._state != AgentState.UNINITIALIZED:
            return  # Idempotent
        
        self._state = AgentState.INITIALIZING
        
        try:
            await self._do_startup(config or self._config)
            self._state = AgentState.READY
        except Exception:
            if self._config.cleanup_on_error:
                await self.shutdown()
            raise
    
    async def shutdown(self, timeout_seconds: Optional[float] = None) -> None:
        """Default shutdown implementation."""
        if self._state == AgentState.TERMINATED:
            return  # Already shut down
        
        self._state = AgentState.SHUTTING_DOWN
        
        try:
            await self._do_shutdown(timeout_seconds or self._config.timeout_seconds)
        except Exception as e:
            # Log but don't raise - shutdown must not fail
            import logging
            logging.error(f"Error during shutdown: {e}", exc_info=True)
        finally:
            self._state = AgentState.TERMINATED
            self._agent_state.clear()  # Discard ephemeral state
    
    def get_state(self) -> AgentState:
        """Get current lifecycle state."""
        return self._state
    
    def get_metrics(self) -> LifecycleMetrics:
        """Get lifecycle metrics."""
        return self._metrics
    
    def owns_state(self, key: str) -> StateOwnership:
        """
        Default state ownership determination.
        
        Override for custom ownership rules.
        """
        # Default rules - can be overridden
        if key.startswith("_"):
            return StateOwnership.AGENT
        if key in {"history", "embeddings", "facts", "memory"}:
            return StateOwnership.MEMORY
        if key in {"trace_id", "routing", "context"}:
            return StateOwnership.ORCHESTRATOR
        return StateOwnership.AGENT
    
    # Context manager support
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.startup()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.shutdown()
        return False  # Don't suppress exceptions
    
    def __enter__(self):
        """Sync context manager entry (for sync agents)."""
        raise RuntimeError("Use async context manager (async with) for agents")
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Sync context manager exit."""
        raise RuntimeError("Use async context manager (async with) for agents")
    
    # Abstract methods for subclasses
    
    @abstractmethod
    async def _do_startup(self, config: LifecycleConfig) -> None:
        """Subclass-specific startup logic."""
        ...
    
    @abstractmethod
    async def _do_shutdown(self, timeout_seconds: float) -> None:
        """Subclass-specific shutdown logic."""
        ...


# Helper decorators and utilities

def requires_state(*required_states: AgentState):
    """
    Decorator to enforce agent state requirements.
    
    Usage:
        @requires_state(AgentState.READY, AgentState.BUSY)
        async def process(self, request):
            ...
    """
    def decorator(func):
        async def wrapper(self, *args, **kwargs):
            current = self.get_state()
            if current not in required_states:
                raise RuntimeError(
                    f"Agent must be in {required_states} state, "
                    f"currently {current}"
                )
            return await func(self, *args, **kwargs)
        return wrapper
    return decorator


@asynccontextmanager
async def agent_lifecycle(agent: AgentLifecycleProtocol, config: Optional[LifecycleConfig] = None):
    """
    Context manager for agent lifecycle.
    
    Usage:
        async with agent_lifecycle(my_agent) as agent:
            result = await agent.process(request)
    """
    await agent.startup(config)
    try:
        yield agent
    finally:
        await agent.shutdown()


# Exceptions

class StartupError(Exception):
    """Raised when agent startup fails unrecoverably."""
    pass


class ShutdownError(Exception):
    """Raised when agent shutdown fails (should be logged, not raised)."""
    pass


class StateViolationError(Exception):
    """Raised when state ownership rules are violated."""
    
    def __init__(self, key: str, expected: StateOwnership, actual: StateOwnership):
        self.key = key
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"State '{key}' owned by {actual.value}, "
            f"but {expected.value} attempted to modify"
        )

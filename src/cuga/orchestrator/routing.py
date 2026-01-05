"""
Canonical Routing Authority

This module defines the single source of truth for routing decisions in CUGAR agent system.
All routing logic MUST go through RoutingAuthority to ensure clean orchestration.

See docs/orchestrator/ROUTING_AUTHORITY.md for detailed architecture.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol


class RoutingStrategy(str, Enum):
    """Strategy for routing requests to agents/workers."""
    
    ROUND_ROBIN = "round_robin"      # Cycle through available agents
    CAPABILITY = "capability"         # Match based on agent capabilities
    LOAD_BALANCED = "load_balanced"   # Route based on current load
    PRIORITY = "priority"             # Route based on priority rules
    LEARNED = "learned"               # ML-based routing decisions
    MANUAL = "manual"                 # Explicitly specified routing


class RoutingDecisionType(str, Enum):
    """Type of routing decision made."""
    
    AGENT_SELECTION = "agent_selection"       # Select which agent handles request
    WORKER_SELECTION = "worker_selection"     # Select which worker executes step
    TOOL_SELECTION = "tool_selection"         # Select which tool to use
    SUBGRAPH_SELECTION = "subgraph_selection" # Select which subgraph to enter
    FALLBACK = "fallback"                     # Fallback routing decision


@dataclass(frozen=True)
class RoutingContext:
    """
    Immutable routing context passed through all routing operations.
    
    This context provides all information needed to make routing decisions
    without coupling routing logic to specific orchestrator implementations.
    """
    
    trace_id: str
    profile: str
    goal: Optional[str] = None
    task: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    parent_context: Optional[RoutingContext] = None
    
    def with_goal(self, goal: str) -> RoutingContext:
        """Create new context with updated goal."""
        return RoutingContext(
            trace_id=self.trace_id,
            profile=self.profile,
            goal=goal,
            task=self.task,
            metadata=self.metadata,
            constraints=self.constraints,
            parent_context=self,
        )
    
    def with_task(self, task: str) -> RoutingContext:
        """Create new context with updated task."""
        return RoutingContext(
            trace_id=self.trace_id,
            profile=self.profile,
            goal=self.goal,
            task=task,
            metadata=self.metadata,
            constraints=self.constraints,
            parent_context=self,
        )


@dataclass
class RoutingCandidate:
    """
    Candidate for routing decision.
    
    Represents a potential target (agent, worker, tool) with its capabilities
    and current state for routing evaluation.
    """
    
    id: str                                    # Unique identifier
    name: str                                  # Human-readable name
    type: str                                  # "agent", "worker", "tool", etc.
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    available: bool = True                     # Whether candidate is available
    load: float = 0.0                          # Current load (0.0 = idle, 1.0 = full)
    priority: int = 0                          # Priority (higher = preferred)


@dataclass
class RoutingDecision:
    """
    Explicit routing decision with justification.
    
    Immutable decision record that documents who/what/why for observability
    and debugging. All routing decisions MUST produce a RoutingDecision.
    """
    
    strategy: RoutingStrategy                  # Strategy used
    decision_type: RoutingDecisionType         # Type of decision
    selected: RoutingCandidate                 # Selected candidate
    reason: str                                # Human-readable justification
    alternatives: List[RoutingCandidate] = field(default_factory=list)
    fallback: Optional[RoutingCandidate] = None
    confidence: float = 1.0                    # Confidence in decision (0.0-1.0)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate routing decision."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be 0.0-1.0, got {self.confidence}")
        if not self.reason:
            raise ValueError("Routing decision must include justification")


class RoutingPolicy(Protocol):
    """
    Protocol for routing policies that determine selection criteria.
    
    Routing policies are pluggable strategy implementations that evaluate
    candidates and return routing decisions. Policies MUST be deterministic
    given the same context and candidates.
    """
    
    def evaluate(
        self,
        context: RoutingContext,
        candidates: List[RoutingCandidate],
    ) -> RoutingDecision:
        """
        Evaluate candidates and return routing decision.
        
        Args:
            context: Routing context with request information
            candidates: Available routing candidates
            
        Returns:
            RoutingDecision with selected candidate and justification
            
        Raises:
            ValueError: If no candidates available or invalid context
        """
        ...


class RoundRobinPolicy:
    """
    Round-robin routing policy with thread-safe counter.
    
    Distributes requests evenly across candidates. Maintains internal
    counter state that advances on each evaluation.
    """
    
    def __init__(self) -> None:
        import threading
        self._counter = 0
        self._lock = threading.Lock()
    
    def evaluate(
        self,
        context: RoutingContext,
        candidates: List[RoutingCandidate],
    ) -> RoutingDecision:
        """Select next candidate in round-robin order."""
        if not candidates:
            raise ValueError("No routing candidates available")
        
        # Filter to available candidates
        available = [c for c in candidates if c.available]
        if not available:
            raise ValueError("No available routing candidates")
        
        with self._lock:
            selected = available[self._counter % len(available)]
            self._counter += 1
        
        return RoutingDecision(
            strategy=RoutingStrategy.ROUND_ROBIN,
            decision_type=RoutingDecisionType.WORKER_SELECTION,
            selected=selected,
            reason=f"Round-robin selection: {selected.name}",
            alternatives=[c for c in available if c.id != selected.id],
            confidence=1.0,
            metadata={"counter": self._counter, "available_count": len(available)},
        )


class CapabilityBasedPolicy:
    """
    Capability-based routing policy.
    
    Routes based on matching request requirements to candidate capabilities.
    Uses simple overlap scoring - more sophisticated matching can be plugged in.
    """
    
    def evaluate(
        self,
        context: RoutingContext,
        candidates: List[RoutingCandidate],
    ) -> RoutingDecision:
        """Select candidate with best capability match."""
        if not candidates:
            raise ValueError("No routing candidates available")
        
        available = [c for c in candidates if c.available]
        if not available:
            raise ValueError("No available routing candidates")
        
        # Extract required capabilities from context
        required = set(context.constraints.get("required_capabilities", []))
        
        if not required:
            # No requirements - use first available
            selected = available[0]
            return RoutingDecision(
                strategy=RoutingStrategy.CAPABILITY,
                decision_type=RoutingDecisionType.AGENT_SELECTION,
                selected=selected,
                reason=f"No capability requirements, selected first available: {selected.name}",
                alternatives=available[1:],
                confidence=0.5,
            )
        
        # Score candidates by capability overlap
        scored: List[tuple[RoutingCandidate, float]] = []
        for candidate in available:
            overlap = len(required.intersection(set(candidate.capabilities)))
            score = overlap / len(required) if required else 0.0
            scored.append((candidate, score))
        
        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        selected, score = scored[0]
        
        return RoutingDecision(
            strategy=RoutingStrategy.CAPABILITY,
            decision_type=RoutingDecisionType.AGENT_SELECTION,
            selected=selected,
            reason=f"Capability match score {score:.2f}: {selected.name}",
            alternatives=[c for c, _ in scored[1:]],
            confidence=score,
            metadata={"required_capabilities": list(required), "match_score": score},
        )


class RoutingAuthority(ABC):
    """
    Abstract routing authority interface.
    
    All routing decisions MUST go through a RoutingAuthority implementation.
    This is the single source of truth for "who decides what runs next".
    
    Orchestrators MUST delegate routing decisions to RoutingAuthority and
    MUST NOT make routing decisions directly. This ensures clean separation
    between orchestration (lifecycle/coordination) and routing (selection).
    """
    
    @abstractmethod
    def route_to_agent(
        self,
        context: RoutingContext,
        agents: List[RoutingCandidate],
    ) -> RoutingDecision:
        """
        Route request to agent.
        
        Args:
            context: Routing context with request information
            agents: Available agent candidates
            
        Returns:
            RoutingDecision with selected agent
            
        Raises:
            ValueError: If no agents available or routing fails
        """
        ...
    
    @abstractmethod
    def route_to_worker(
        self,
        context: RoutingContext,
        workers: List[RoutingCandidate],
    ) -> RoutingDecision:
        """
        Route task to worker.
        
        Args:
            context: Routing context with task information
            workers: Available worker candidates
            
        Returns:
            RoutingDecision with selected worker
            
        Raises:
            ValueError: If no workers available or routing fails
        """
        ...
    
    @abstractmethod
    def route_to_tool(
        self,
        context: RoutingContext,
        tools: List[RoutingCandidate],
    ) -> RoutingDecision:
        """
        Route action to tool.
        
        Args:
            context: Routing context with action information
            tools: Available tool candidates
            
        Returns:
            RoutingDecision with selected tool
            
        Raises:
            ValueError: If no tools available or routing fails
        """
        ...


class PolicyBasedRoutingAuthority(RoutingAuthority):
    """
    Routing authority that delegates to pluggable policies.
    
    This is the recommended RoutingAuthority implementation. It supports
    different routing strategies per decision type (agent/worker/tool)
    and allows runtime policy swapping.
    
    Example:
        >>> authority = PolicyBasedRoutingAuthority(
        ...     agent_policy=CapabilityBasedPolicy(),
        ...     worker_policy=RoundRobinPolicy(),
        ... )
        >>> decision = authority.route_to_agent(context, agent_candidates)
    """
    
    def __init__(
        self,
        agent_policy: Optional[RoutingPolicy] = None,
        worker_policy: Optional[RoutingPolicy] = None,
        tool_policy: Optional[RoutingPolicy] = None,
    ) -> None:
        """
        Initialize policy-based routing authority.
        
        Args:
            agent_policy: Policy for agent routing (default: capability-based)
            worker_policy: Policy for worker routing (default: round-robin)
            tool_policy: Policy for tool routing (default: capability-based)
        """
        self.agent_policy = agent_policy or CapabilityBasedPolicy()
        self.worker_policy = worker_policy or RoundRobinPolicy()
        self.tool_policy = tool_policy or CapabilityBasedPolicy()
    
    def route_to_agent(
        self,
        context: RoutingContext,
        agents: List[RoutingCandidate],
    ) -> RoutingDecision:
        """Route using agent policy."""
        return self.agent_policy.evaluate(context, agents)
    
    def route_to_worker(
        self,
        context: RoutingContext,
        workers: List[RoutingCandidate],
    ) -> RoutingDecision:
        """Route using worker policy."""
        return self.worker_policy.evaluate(context, workers)
    
    def route_to_tool(
        self,
        context: RoutingContext,
        tools: List[RoutingCandidate],
    ) -> RoutingDecision:
        """Route using tool policy."""
        return self.tool_policy.evaluate(context, tools)


# Convenience function for creating default routing authority
def create_routing_authority(
    agent_strategy: RoutingStrategy = RoutingStrategy.CAPABILITY,
    worker_strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN,
    tool_strategy: RoutingStrategy = RoutingStrategy.CAPABILITY,
) -> RoutingAuthority:
    """
    Create routing authority with specified strategies.
    
    Args:
        agent_strategy: Strategy for agent routing
        worker_strategy: Strategy for worker routing
        tool_strategy: Strategy for tool routing
        
    Returns:
        Configured RoutingAuthority instance
    """
    # Map strategies to policy implementations
    policy_map = {
        RoutingStrategy.ROUND_ROBIN: RoundRobinPolicy,
        RoutingStrategy.CAPABILITY: CapabilityBasedPolicy,
    }
    
    agent_policy = policy_map.get(agent_strategy, CapabilityBasedPolicy)()
    worker_policy = policy_map.get(worker_strategy, RoundRobinPolicy)()
    tool_policy = policy_map.get(tool_strategy, CapabilityBasedPolicy)()
    
    return PolicyBasedRoutingAuthority(
        agent_policy=agent_policy,
        worker_policy=worker_policy,
        tool_policy=tool_policy,
    )

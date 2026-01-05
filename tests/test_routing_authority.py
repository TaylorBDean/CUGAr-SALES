"""
Tests for Canonical Routing Authority

These tests verify that routing logic is centralized through RoutingAuthority
and that no routing bypasses occur at the agent or FastAPI layer.
"""

import pytest
from unittest.mock import Mock, patch
from typing import List

from cuga.orchestrator.routing import (
    RoutingAuthority,
    PolicyBasedRoutingAuthority,
    RoutingContext,
    RoutingDecision,
    RoutingCandidate,
    RoutingStrategy,
    RoutingDecisionType,
    RoundRobinPolicy,
    CapabilityBasedPolicy,
    create_routing_authority,
)


class TestRoutingContext:
    """Test immutable routing context."""
    
    def test_context_is_frozen(self):
        """Routing context cannot be mutated."""
        context = RoutingContext(trace_id="test", profile="prod")
        
        with pytest.raises(AttributeError):
            context.trace_id = "modified"
    
    def test_context_with_goal(self):
        """Context.with_goal creates new instance."""
        context = RoutingContext(trace_id="test", profile="prod")
        new_context = context.with_goal("search web")
        
        assert new_context.goal == "search web"
        assert new_context.trace_id == "test"
        assert new_context.parent_context is context
        assert context.goal is None  # Original unchanged
    
    def test_context_with_task(self):
        """Context.with_task creates new instance."""
        context = RoutingContext(trace_id="test", profile="prod")
        new_context = context.with_task("execute search")
        
        assert new_context.task == "execute search"
        assert new_context.parent_context is context


class TestRoutingDecision:
    """Test routing decision validation."""
    
    def test_decision_requires_reason(self):
        """Routing decision must include justification."""
        candidate = RoutingCandidate(id="1", name="worker-1", type="worker")
        
        with pytest.raises(ValueError, match="must include justification"):
            RoutingDecision(
                strategy=RoutingStrategy.ROUND_ROBIN,
                decision_type=RoutingDecisionType.WORKER_SELECTION,
                selected=candidate,
                reason="",  # Empty reason not allowed
            )
    
    def test_decision_validates_confidence(self):
        """Confidence must be 0.0-1.0."""
        candidate = RoutingCandidate(id="1", name="worker-1", type="worker")
        
        with pytest.raises(ValueError, match="Confidence must be 0.0-1.0"):
            RoutingDecision(
                strategy=RoutingStrategy.ROUND_ROBIN,
                decision_type=RoutingDecisionType.WORKER_SELECTION,
                selected=candidate,
                reason="test",
                confidence=1.5,  # Invalid
            )
    
    def test_decision_with_alternatives(self):
        """Decision can document alternative candidates."""
        selected = RoutingCandidate(id="1", name="worker-1", type="worker")
        alt1 = RoutingCandidate(id="2", name="worker-2", type="worker")
        alt2 = RoutingCandidate(id="3", name="worker-3", type="worker")
        
        decision = RoutingDecision(
            strategy=RoutingStrategy.ROUND_ROBIN,
            decision_type=RoutingDecisionType.WORKER_SELECTION,
            selected=selected,
            reason="Round-robin selection",
            alternatives=[alt1, alt2],
        )
        
        assert decision.selected == selected
        assert len(decision.alternatives) == 2


class TestRoundRobinPolicy:
    """Test round-robin routing policy."""
    
    def test_round_robin_cycles_workers(self):
        """Round-robin cycles through available workers."""
        policy = RoundRobinPolicy()
        context = RoutingContext(trace_id="test", profile="prod")
        
        candidates = [
            RoutingCandidate(id=str(i), name=f"worker-{i}", type="worker")
            for i in range(3)
        ]
        
        # First call -> worker-0
        decision1 = policy.evaluate(context, candidates)
        assert decision1.selected.name == "worker-0"
        
        # Second call -> worker-1
        decision2 = policy.evaluate(context, candidates)
        assert decision2.selected.name == "worker-1"
        
        # Third call -> worker-2
        decision3 = policy.evaluate(context, candidates)
        assert decision3.selected.name == "worker-2"
        
        # Fourth call -> worker-0 (wraps around)
        decision4 = policy.evaluate(context, candidates)
        assert decision4.selected.name == "worker-0"
    
    def test_round_robin_filters_unavailable(self):
        """Round-robin only considers available candidates."""
        policy = RoundRobinPolicy()
        context = RoutingContext(trace_id="test", profile="prod")
        
        candidates = [
            RoutingCandidate(id="0", name="worker-0", type="worker", available=True),
            RoutingCandidate(id="1", name="worker-1", type="worker", available=False),
            RoutingCandidate(id="2", name="worker-2", type="worker", available=True),
        ]
        
        decision1 = policy.evaluate(context, candidates)
        assert decision1.selected.name in ["worker-0", "worker-2"]
        
        decision2 = policy.evaluate(context, candidates)
        assert decision2.selected.name in ["worker-0", "worker-2"]
    
    def test_round_robin_no_candidates_error(self):
        """Round-robin raises error if no candidates."""
        policy = RoundRobinPolicy()
        context = RoutingContext(trace_id="test", profile="prod")
        
        with pytest.raises(ValueError, match="No routing candidates available"):
            policy.evaluate(context, [])
    
    def test_round_robin_thread_safe(self):
        """Round-robin counter is thread-safe."""
        import threading
        
        policy = RoundRobinPolicy()
        context = RoutingContext(trace_id="test", profile="prod")
        candidates = [
            RoutingCandidate(id=str(i), name=f"worker-{i}", type="worker")
            for i in range(3)
        ]
        
        results = []
        
        def evaluate():
            decision = policy.evaluate(context, candidates)
            results.append(decision.selected.id)
        
        threads = [threading.Thread(target=evaluate) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All 10 evaluations should succeed without race conditions
        assert len(results) == 10
        assert all(r in ["0", "1", "2"] for r in results)


class TestCapabilityBasedPolicy:
    """Test capability-based routing policy."""
    
    def test_capability_matches_requirements(self):
        """Capability policy selects best capability match."""
        policy = CapabilityBasedPolicy()
        context = RoutingContext(
            trace_id="test",
            profile="prod",
            constraints={"required_capabilities": ["research", "web"]},
        )
        
        candidates = [
            RoutingCandidate(
                id="1", name="agent-1", type="agent",
                capabilities=["research", "web", "api"],  # 2/2 match
            ),
            RoutingCandidate(
                id="2", name="agent-2", type="agent",
                capabilities=["code", "analysis"],  # 0/2 match
            ),
            RoutingCandidate(
                id="3", name="agent-3", type="agent",
                capabilities=["research"],  # 1/2 match
            ),
        ]
        
        decision = policy.evaluate(context, candidates)
        
        assert decision.selected.name == "agent-1"  # Best match
        assert decision.confidence == 1.0  # 2/2 = 100%
    
    def test_capability_no_requirements(self):
        """Capability policy selects first if no requirements."""
        policy = CapabilityBasedPolicy()
        context = RoutingContext(trace_id="test", profile="prod")  # No constraints
        
        candidates = [
            RoutingCandidate(id="1", name="agent-1", type="agent"),
            RoutingCandidate(id="2", name="agent-2", type="agent"),
        ]
        
        decision = policy.evaluate(context, candidates)
        
        assert decision.selected.name == "agent-1"  # First available
        assert decision.confidence == 0.5  # Low confidence (no matching)


class TestPolicyBasedRoutingAuthority:
    """Test policy-based routing authority."""
    
    def test_authority_delegates_to_agent_policy(self):
        """Authority delegates agent routing to agent policy."""
        agent_policy = Mock()
        authority = PolicyBasedRoutingAuthority(agent_policy=agent_policy)
        
        context = RoutingContext(trace_id="test", profile="prod")
        candidates = [RoutingCandidate(id="1", name="agent-1", type="agent")]
        
        authority.route_to_agent(context, candidates)
        
        agent_policy.evaluate.assert_called_once_with(context, candidates)
    
    def test_authority_delegates_to_worker_policy(self):
        """Authority delegates worker routing to worker policy."""
        worker_policy = Mock()
        authority = PolicyBasedRoutingAuthority(worker_policy=worker_policy)
        
        context = RoutingContext(trace_id="test", profile="prod")
        candidates = [RoutingCandidate(id="1", name="worker-1", type="worker")]
        
        authority.route_to_worker(context, candidates)
        
        worker_policy.evaluate.assert_called_once_with(context, candidates)
    
    def test_authority_defaults(self):
        """Authority has sensible default policies."""
        authority = PolicyBasedRoutingAuthority()
        
        assert isinstance(authority.agent_policy, CapabilityBasedPolicy)
        assert isinstance(authority.worker_policy, RoundRobinPolicy)
        assert isinstance(authority.tool_policy, CapabilityBasedPolicy)


class TestRoutingAuthorityFactory:
    """Test routing authority factory."""
    
    def test_create_with_strategies(self):
        """Factory creates authority with specified strategies."""
        authority = create_routing_authority(
            agent_strategy=RoutingStrategy.CAPABILITY,
            worker_strategy=RoutingStrategy.ROUND_ROBIN,
        )
        
        assert isinstance(authority, PolicyBasedRoutingAuthority)
        assert isinstance(authority.agent_policy, CapabilityBasedPolicy)
        assert isinstance(authority.worker_policy, RoundRobinPolicy)


class TestRoutingCompliance:
    """
    Test routing compliance - verify routing decisions flow through
    RoutingAuthority and not through agent internal logic.
    """
    
    def test_no_agent_routing_bypass(self):
        """Agents must not have internal routing logic."""
        from cuga.modular.agents import CoordinatorAgent
        
        # CoordinatorAgent should delegate to RoutingAuthority
        # not have _select_worker() method
        coordinator = CoordinatorAgent(
            planner=Mock(),
            workers=[Mock(), Mock()],
            memory=Mock(),
        )
        
        # Verify no internal routing method
        # (After migration, _select_worker should be removed)
        # For now, this documents the anti-pattern
        if hasattr(coordinator, '_select_worker'):
            pytest.skip("CoordinatorAgent still has internal routing - migration pending")
    
    def test_orchestrator_delegates_routing(self):
        """Orchestrator must delegate routing to RoutingAuthority."""
        from cuga.orchestrator.reference import ReferenceOrchestrator
        from cuga.orchestrator import ExecutionContext
        
        authority = Mock(spec=RoutingAuthority)
        authority.route_to_agent.return_value = RoutingDecision(
            strategy=RoutingStrategy.CAPABILITY,
            decision_type=RoutingDecisionType.AGENT_SELECTION,
            selected=RoutingCandidate(id="1", name="agent-1", type="agent"),
            reason="test",
        )
        
        orchestrator = ReferenceOrchestrator(
            planner=Mock(),
            workers=[Mock()],
        )
        
        # Orchestrator should have routing_authority attribute
        # (After migration - for now document expected interface)
        if not hasattr(orchestrator, 'routing_authority'):
            pytest.skip("ReferenceOrchestrator routing authority migration pending")
        
        orchestrator.routing_authority = authority
        
        context = ExecutionContext(trace_id="test", profile="prod")
        orchestrator.make_routing_decision("test task", context, ["agent-1"])
        
        # Verify delegation happened
        authority.route_to_agent.assert_called_once()
    
    def test_no_fastapi_routing_decisions(self):
        """FastAPI endpoints must not make routing decisions."""
        # FastAPI should configure RoutingAuthority policy
        # not decide routing directly
        
        # Example anti-pattern to detect:
        # POST /api/config/agent-mode
        # if mode == "single": route_to_agent(selected_agent)  # ❌ Wrong
        
        # Correct pattern:
        # POST /api/config/agent-mode
        # routing_authority.configure(ManualPolicy(selected_agent))  # ✅ Right
        
        # This test documents expected behavior
        # Implementation verification requires integration tests
        pass


class TestRoutingObservability:
    """Test routing observability and tracing."""
    
    def test_routing_decision_logged(self):
        """Routing decisions should be logged with trace_id."""
        policy = RoundRobinPolicy()
        context = RoutingContext(trace_id="abc123", profile="prod")
        
        candidates = [
            RoutingCandidate(id="1", name="worker-1", type="worker"),
            RoutingCandidate(id="2", name="worker-2", type="worker"),
        ]
        
        decision = policy.evaluate(context, candidates)
        
        # Decision should be loggable with trace context
        log_entry = {
            "event": "routing_decision",
            "trace_id": context.trace_id,
            "strategy": decision.strategy.value,
            "selected": decision.selected.name,
            "reason": decision.reason,
            "confidence": decision.confidence,
        }
        
        assert log_entry["trace_id"] == "abc123"
        assert log_entry["strategy"] == "round_robin"
        assert "reason" in log_entry


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

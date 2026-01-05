"""
Integration tests verifying AGENTS.md canonical compliance.
Tests budget enforcement, approval flows, trace emission, and profile behavior.
"""
import pytest
from datetime import datetime, timedelta, timezone
from cuga.orchestrator.budget_enforcer import ToolBudget, BudgetEnforcer
from cuga.orchestrator.approval_manager import ApprovalManager
from cuga.orchestrator.trace_emitter import TraceEmitter
from cuga.orchestrator.profile_loader import ProfileLoader


def test_budget_enforcement():
    """Verify AGENTS.md budget enforcement."""
    budget = ToolBudget(total_calls=5)
    emitter = TraceEmitter()
    enforcer = BudgetEnforcer(budget, emitter)
    
    # Execute 5 tasks
    for i in range(5):
        allowed, reason = enforcer.check_budget(f"tool_{i}", "test_domain")
        assert allowed, f"Task {i} should be allowed"
        enforcer.record_usage(f"tool_{i}", "test_domain")
    
    # 6th task should fail with budget_exceeded
    allowed, reason = enforcer.check_budget("tool_6", "test_domain")
    assert not allowed
    assert reason == "budget_exceeded:total"
    
    # Check canonical event emitted
    events = emitter.get_trace()
    assert any(e["event"] == "budget_exceeded" for e in events)


def test_approval_required_for_irreversible():
    """Verify AGENTS.md human approval preservation."""
    emitter = TraceEmitter()
    manager = ApprovalManager(emitter)
    
    # Request approval for execute side-effect
    approval_id = manager.request_approval(
        action="Send email to prospect",
        tool_name="send_email",
        inputs={"to": "prospect@example.com"},
        reasoning="Follow up on demo",
        side_effect_class="execute",
        profile="enterprise"
    )
    
    # Check approval request created
    request = manager.get_approval(approval_id)
    assert request is not None
    assert request.status == "pending"
    assert request.risk_level == "high"
    
    # Check canonical event emitted
    events = emitter.get_trace()
    assert any(e["event"] == "approval_requested" for e in events)


def test_offline_first_capability():
    """Verify AGENTS.md offline-first requirement."""
    loader = ProfileLoader()
    
    # Technical profile should allow mock adapter (offline-first)
    tech_profile = loader.load_profile("technical")
    assert "mock" in tech_profile.allowed_adapters
    
    # Mock adapter always allowed per AGENTS.md
    assert loader.is_adapter_allowed("technical", "mock")
    assert loader.is_adapter_allowed("enterprise", "mock")


def test_profile_driven_budgets():
    """Verify AGENTS.md profile-driven behavior."""
    loader = ProfileLoader()
    
    # Enterprise has higher budget
    enterprise_budget = loader.get_budget("enterprise")
    assert enterprise_budget["total_calls"] == 200
    
    # SMB has lower budget
    smb_budget = loader.get_budget("smb")
    assert smb_budget["total_calls"] == 100
    
    # Technical has highest budget
    technical_budget = loader.get_budget("technical")
    assert technical_budget["total_calls"] == 500


def test_trace_continuity():
    """Verify AGENTS.md mandatory trace_id propagation."""
    emitter = TraceEmitter()
    
    # Emit canonical events
    emitter.emit("plan_created", {"steps": 3})
    emitter.emit("tool_call_start", {"tool": "test_tool"})
    emitter.emit("tool_call_complete", {"result": "success"})
    
    # Check trace_id continuity
    trace = emitter.get_trace()
    assert len(trace) == 3
    trace_ids = {e["trace_id"] for e in trace}
    assert len(trace_ids) == 1  # Same trace_id for all events


def test_canonical_events_only():
    """Verify AGENTS.md canonical event enforcement."""
    emitter = TraceEmitter()
    
    # Canonical event should work
    emitter.emit("plan_created", {})
    
    # Non-canonical event should raise error
    with pytest.raises(ValueError, match="Non-canonical event"):
        emitter.emit("custom_event", {})


def test_approval_timeout():
    """Verify AGENTS.md approval timeout handling."""
    from datetime import datetime, timedelta
    
    manager = ApprovalManager()
    approval_id = manager.request_approval(
        action="Test action",
        tool_name="test_tool",
        inputs={},
        reasoning="Test",
        side_effect_class="execute"
    )
    
    # Manually expire the approval
    request = manager.pending_approvals[approval_id]
    request.expires_at = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    
    # Get approval should detect timeout
    expired_request = manager.get_approval(approval_id)
    assert expired_request.status == "timeout"


def test_graceful_degradation():
    """Verify AGENTS.md graceful degradation."""
    loader = ProfileLoader()
    
    # System should work with mock adapters only
    tech_profile = loader.load_profile("technical")
    assert tech_profile.allowed_adapters == ["mock"]
    
    # Check adapter allowlist enforcement
    assert not loader.is_adapter_allowed("technical", "salesforce")
    assert loader.is_adapter_allowed("technical", "mock")


def test_budget_warning_threshold():
    """Verify AGENTS.md budget warning emission."""
    budget = ToolBudget(total_calls=10, warning_threshold=0.8)
    emitter = TraceEmitter()
    enforcer = BudgetEnforcer(budget, emitter)
    
    # Use 7 calls (70% - no warning)
    for i in range(7):
        enforcer.check_budget(f"tool_{i}", "test_domain")
        enforcer.record_usage(f"tool_{i}", "test_domain")
    
    events = emitter.get_trace()
    assert not any(e["event"] == "budget_warning" for e in events)
    
    # Use 8th call (80% - warning)
    enforcer.check_budget("tool_8", "test_domain")
    enforcer.record_usage("tool_8", "test_domain")
    
    events = emitter.get_trace()
    assert any(e["event"] == "budget_warning" for e in events)


def test_profile_approval_requirements():
    """Verify AGENTS.md profile-driven approval requirements."""
    loader = ProfileLoader()
    
    # Enterprise requires approval for execute and propose
    assert loader.requires_approval("enterprise", "execute")
    assert loader.requires_approval("enterprise", "propose")
    assert not loader.requires_approval("enterprise", "read-only")
    
    # SMB only requires approval for execute
    assert loader.requires_approval("smb", "execute")
    assert not loader.requires_approval("smb", "propose")
    
    # Technical requires no approvals
    assert not loader.requires_approval("technical", "execute")
    assert not loader.requires_approval("technical", "propose")

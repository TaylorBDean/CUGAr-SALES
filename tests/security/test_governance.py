"""Tests for MCP/OpenAPI governance with policy gates and capability maps."""

import pytest
from datetime import datetime, timedelta

from cuga.agents.policy import PolicyViolation
from cuga.security.governance import (
    ActionType,
    ApprovalRequest,
    ApprovalStatus,
    GovernanceEngine,
    TenantCapabilityMap,
    ToolCapability,
)


@pytest.fixture
def sample_capabilities():
    """Sample tool capabilities for testing."""
    return {
        "slack_send": ToolCapability(
            name="slack_send",
            action_type=ActionType.WRITE,
            requires_approval=True,
            approval_timeout_seconds=300,
            allowed_tenants={"marketing", "support"},
            max_rate_per_minute=10,
        ),
        "file_read": ToolCapability(
            name="file_read",
            action_type=ActionType.READ,
            requires_approval=False,
            allowed_tenants=set(),  # All tenants
        ),
        "file_delete": ToolCapability(
            name="file_delete",
            action_type=ActionType.DELETE,
            requires_approval=True,
            approval_timeout_seconds=600,
            allowed_tenants={"engineering"},
            max_rate_per_minute=5,
        ),
        "stock_order": ToolCapability(
            name="stock_order",
            action_type=ActionType.FINANCIAL,
            requires_approval=True,
            approval_timeout_seconds=120,
            allowed_tenants={"trading"},
            denied_tenants={"marketing", "support"},
            max_rate_per_minute=5,
        ),
    }


@pytest.fixture
def sample_tenant_maps():
    """Sample tenant capability maps for testing."""
    return {
        "marketing": TenantCapabilityMap(
            tenant="marketing",
            allowed_tools={"slack_send", "file_read"},
            denied_tools={"stock_order"},
            max_concurrent_calls=15,
            budget_ceiling=200,
        ),
        "trading": TenantCapabilityMap(
            tenant="trading",
            allowed_tools={"stock_order", "file_read"},
            denied_tools={"slack_send"},
            max_concurrent_calls=20,
            budget_ceiling=500,
        ),
        "engineering": TenantCapabilityMap(
            tenant="engineering",
            allowed_tools=set(),  # All allowed
            denied_tools=set(),
            max_concurrent_calls=50,
            budget_ceiling=1000,
        ),
    }


@pytest.fixture
def governance_engine(sample_capabilities, sample_tenant_maps):
    """Governance engine with test data."""
    return GovernanceEngine(
        capabilities=sample_capabilities,
        tenant_maps=sample_tenant_maps,
    )


def test_tool_not_registered(governance_engine):
    """Test validation fails for unregistered tool."""
    with pytest.raises(PolicyViolation) as exc_info:
        governance_engine.validate_tool_call(
            tool_name="unknown_tool",
            tenant="marketing",
            inputs={},
            context={},
        )
    
    assert exc_info.value.code == "tool_not_registered"
    assert "unknown_tool" in exc_info.value.message


def test_tenant_tool_denied_by_map(governance_engine):
    """Test tenant denied by tenant capability map."""
    with pytest.raises(PolicyViolation) as exc_info:
        governance_engine.validate_tool_call(
            tool_name="slack_send",
            tenant="trading",
            inputs={"message": "test"},
            context={},
        )
    
    assert exc_info.value.code == "tenant_tool_denied"
    assert "trading" in exc_info.value.message
    assert "slack_send" in exc_info.value.message


def test_tenant_tool_denied_by_capability(governance_engine):
    """Test tenant denied by tool capability restrictions."""
    with pytest.raises(PolicyViolation) as exc_info:
        governance_engine.validate_tool_call(
            tool_name="stock_order",
            tenant="marketing",
            inputs={"symbol": "AAPL"},
            context={},
        )
    
    assert exc_info.value.code == "tool_tenant_denied"
    assert "marketing" in exc_info.value.message


def test_tool_allowed_for_tenant(governance_engine):
    """Test successful validation for allowed tool."""
    # Should not raise
    governance_engine.validate_tool_call(
        tool_name="slack_send",
        tenant="marketing",
        inputs={"message": "test"},
        context={},
    )


def test_tool_allowed_for_all_tenants(governance_engine):
    """Test tool with empty allowed_tenants set allows all."""
    # Should not raise for any tenant
    governance_engine.validate_tool_call(
        tool_name="file_read",
        tenant="marketing",
        inputs={"path": "/tmp/test.txt"},
        context={},
    )
    
    governance_engine.validate_tool_call(
        tool_name="file_read",
        tenant="trading",
        inputs={"path": "/tmp/test.txt"},
        context={},
    )


def test_rate_limit_enforcement(governance_engine):
    """Test rate limiting per tenant/tool combination."""
    # Make max allowed calls
    for _ in range(10):
        governance_engine.validate_tool_call(
            tool_name="slack_send",
            tenant="marketing",
            inputs={"message": "test"},
            context={},
        )
    
    # Next call should fail
    with pytest.raises(PolicyViolation) as exc_info:
        governance_engine.validate_tool_call(
            tool_name="slack_send",
            tenant="marketing",
            inputs={"message": "test"},
            context={},
        )
    
    assert exc_info.value.code == "rate_limit_exceeded"
    assert "10" in exc_info.value.message


def test_approval_required_tool(governance_engine):
    """Test approval request creation for tools requiring approval."""
    approval = governance_engine.request_approval(
        tool_name="slack_send",
        tenant="marketing",
        inputs={"message": "test"},
        context={},
        request_id="test-req-1",
    )
    
    assert approval.status == ApprovalStatus.PENDING
    assert approval.tool_name == "slack_send"
    assert approval.action_type == ActionType.WRITE
    assert approval.expires_at is not None


def test_approval_not_required_auto_approve(governance_engine):
    """Test auto-approval for tools not requiring approval."""
    approval = governance_engine.request_approval(
        tool_name="file_read",
        tenant="marketing",
        inputs={"path": "/tmp/test.txt"},
        context={},
        request_id="test-req-2",
    )
    
    assert approval.status == ApprovalStatus.APPROVED
    assert approval.approved_by == "auto"


def test_approve_pending_request(governance_engine):
    """Test approval of pending request."""
    approval = governance_engine.request_approval(
        tool_name="slack_send",
        tenant="marketing",
        inputs={"message": "test"},
        context={},
        request_id="test-req-3",
    )
    
    governance_engine.approve_request("test-req-3", approved_by="admin@example.com")
    
    assert approval.status == ApprovalStatus.APPROVED
    assert approval.approved_by == "admin@example.com"


def test_reject_pending_request(governance_engine):
    """Test rejection of pending request."""
    approval = governance_engine.request_approval(
        tool_name="slack_send",
        tenant="marketing",
        inputs={"message": "test"},
        context={},
        request_id="test-req-4",
    )
    
    governance_engine.reject_request("test-req-4", reason="Not authorized")
    
    assert approval.status == ApprovalStatus.REJECTED
    assert approval.rejection_reason == "Not authorized"


def test_approval_expiration(governance_engine):
    """Test approval request expiration."""
    approval = governance_engine.request_approval(
        tool_name="slack_send",
        tenant="marketing",
        inputs={"message": "test"},
        context={},
        request_id="test-req-5",
    )
    
    # Force expiration
    approval.expires_at = datetime.utcnow() - timedelta(seconds=1)
    
    assert approval.is_expired()
    
    with pytest.raises(PolicyViolation) as exc_info:
        governance_engine.approve_request("test-req-5", approved_by="admin@example.com")
    
    assert exc_info.value.code == "approval_expired"


def test_tenant_capability_map_empty_allowlist():
    """Test tenant map with empty allowed_tools (allows all)."""
    tenant_map = TenantCapabilityMap(
        tenant="engineering",
        allowed_tools=set(),
        denied_tools={"dangerous_tool"},
    )
    
    assert tenant_map.can_use_tool("any_tool")
    assert not tenant_map.can_use_tool("dangerous_tool")


def test_tenant_capability_map_explicit_allowlist():
    """Test tenant map with explicit allowed_tools."""
    tenant_map = TenantCapabilityMap(
        tenant="marketing",
        allowed_tools={"slack_send", "file_read"},
        denied_tools=set(),
    )
    
    assert tenant_map.can_use_tool("slack_send")
    assert tenant_map.can_use_tool("file_read")
    assert not tenant_map.can_use_tool("file_delete")


def test_tool_capability_empty_allowed_tenants():
    """Test tool capability with empty allowed_tenants (allows all)."""
    capability = ToolCapability(
        name="file_read",
        action_type=ActionType.READ,
        allowed_tenants=set(),
    )
    
    assert capability.is_allowed_for_tenant("any_tenant")


def test_tool_capability_explicit_allowed_tenants():
    """Test tool capability with explicit allowed_tenants."""
    capability = ToolCapability(
        name="slack_send",
        action_type=ActionType.WRITE,
        allowed_tenants={"marketing", "support"},
    )
    
    assert capability.is_allowed_for_tenant("marketing")
    assert capability.is_allowed_for_tenant("support")
    assert not capability.is_allowed_for_tenant("trading")


def test_tool_capability_denied_tenants():
    """Test tool capability with denied_tenants."""
    capability = ToolCapability(
        name="stock_order",
        action_type=ActionType.FINANCIAL,
        allowed_tenants={"trading"},
        denied_tenants={"marketing"},
    )
    
    assert capability.is_allowed_for_tenant("trading")
    assert not capability.is_allowed_for_tenant("marketing")


def test_get_approval_status(governance_engine):
    """Test retrieving approval status."""
    approval = governance_engine.request_approval(
        tool_name="slack_send",
        tenant="marketing",
        inputs={"message": "test"},
        context={},
        request_id="test-req-6",
    )
    
    status = governance_engine.get_approval_status("test-req-6")
    assert status == ApprovalStatus.PENDING
    
    governance_engine.approve_request("test-req-6", approved_by="admin@example.com")
    
    status = governance_engine.get_approval_status("test-req-6")
    assert status == ApprovalStatus.APPROVED


def test_approval_status_unknown_request(governance_engine):
    """Test getting status for unknown request."""
    with pytest.raises(ValueError) as exc_info:
        governance_engine.get_approval_status("unknown-request")
    
    assert "not found" in str(exc_info.value)

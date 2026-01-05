"""
Tests for approval gates (HITL - Human-In-The-Loop).

This test suite validates:
- ApprovalPolicy configuration and validation
- ApprovalRequest creation and serialization
- ApprovalResponse decision recording
- ApprovalGate request/response flow
- Timeout handling (auto-approve vs denial)
- Manual approval flow
- Callback-based approval flow
- Request cancellation
- Pending request management

Version: 1.3.2
Author: Orchestration Team
"""

import asyncio
import pytest
from datetime import datetime

from cuga.orchestrator.approval import (
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalStatus,
    ApprovalGate,
    create_approval_gate,
)


# ========================================
# Test: ApprovalPolicy Configuration
# ========================================

def test_approval_policy_creation():
    """Test that ApprovalPolicy can be created with defaults."""
    policy = ApprovalPolicy()
    assert policy.enabled is True
    assert policy.timeout_seconds == 300.0
    assert policy.required_approvers == []
    assert policy.auto_approve_on_timeout is False


def test_approval_policy_custom_values():
    """Test ApprovalPolicy with custom values."""
    policy = ApprovalPolicy(
        enabled=True,
        timeout_seconds=60.0,
        required_approvers=["admin@example.com", "manager@example.com"],
        auto_approve_on_timeout=True,
    )
    
    assert policy.enabled is True
    assert policy.timeout_seconds == 60.0
    assert len(policy.required_approvers) == 2
    assert "admin@example.com" in policy.required_approvers
    assert policy.auto_approve_on_timeout is True


def test_approval_policy_validation_negative_timeout():
    """Test that negative timeout raises ValueError."""
    with pytest.raises(ValueError, match="Timeout must be positive"):
        ApprovalPolicy(timeout_seconds=-10.0)


def test_approval_policy_validation_zero_timeout():
    """Test that zero timeout raises ValueError."""
    with pytest.raises(ValueError, match="Timeout must be positive"):
        ApprovalPolicy(timeout_seconds=0.0)


# ========================================
# Test: ApprovalRequest Creation
# ========================================

def test_approval_request_creation():
    """Test ApprovalRequest creation with basic fields."""
    policy = ApprovalPolicy()
    request = ApprovalRequest(
        request_id="req-123",
        operation="delete_database",
        trace_id="trace-456",
        timestamp="2026-01-02T12:00:00+00:00",
        policy=policy,
    )
    
    assert request.request_id == "req-123"
    assert request.operation == "delete_database"
    assert request.trace_id == "trace-456"
    assert request.policy == policy


def test_approval_request_with_metadata():
    """Test ApprovalRequest with metadata and risk level."""
    request = ApprovalRequest(
        request_id="req-789",
        operation="deploy_production",
        trace_id="trace-101",
        timestamp="2026-01-02T12:00:00+00:00",
        metadata={"environment": "production", "version": "v1.2.3"},
        risk_level="high",
        requester="user@example.com",
    )
    
    assert request.metadata["environment"] == "production"
    assert request.risk_level == "high"
    assert request.requester == "user@example.com"


def test_approval_request_to_dict():
    """Test ApprovalRequest serialization to dict."""
    policy = ApprovalPolicy(timeout_seconds=120.0)
    request = ApprovalRequest(
        request_id="req-abc",
        operation="update_config",
        trace_id="trace-xyz",
        timestamp="2026-01-02T12:00:00+00:00",
        metadata={"key": "value"},
        policy=policy,
    )
    
    data = request.to_dict()
    assert data["request_id"] == "req-abc"
    assert data["operation"] == "update_config"
    assert data["metadata"]["key"] == "value"
    assert data["policy"]["timeout_seconds"] == 120.0


# ========================================
# Test: ApprovalResponse Creation
# ========================================

def test_approval_response_approved():
    """Test ApprovalResponse for approved request."""
    response = ApprovalResponse(
        request_id="req-123",
        status=ApprovalStatus.APPROVED,
        timestamp="2026-01-02T12:05:00+00:00",
        approver="admin@example.com",
        reason="Reviewed and approved",
    )
    
    assert response.status == ApprovalStatus.APPROVED
    assert response.approver == "admin@example.com"
    assert response.reason == "Reviewed and approved"


def test_approval_response_denied():
    """Test ApprovalResponse for denied request."""
    response = ApprovalResponse(
        request_id="req-456",
        status=ApprovalStatus.DENIED,
        timestamp="2026-01-02T12:05:00+00:00",
        approver="manager@example.com",
        reason="Risk too high",
    )
    
    assert response.status == ApprovalStatus.DENIED
    assert response.reason == "Risk too high"


def test_approval_response_timeout():
    """Test ApprovalResponse for timed out request."""
    response = ApprovalResponse(
        request_id="req-789",
        status=ApprovalStatus.TIMEOUT,
        timestamp="2026-01-02T12:10:00+00:00",
        approver="system",
        reason="Approval timed out after 300s",
    )
    
    assert response.status == ApprovalStatus.TIMEOUT
    assert response.approver == "system"


def test_approval_response_to_dict():
    """Test ApprovalResponse serialization to dict."""
    response = ApprovalResponse(
        request_id="req-111",
        status=ApprovalStatus.APPROVED,
        timestamp="2026-01-02T12:00:00+00:00",
        approver="admin",
        reason="OK",
        metadata={"duration_ms": 1500},
    )
    
    data = response.to_dict()
    assert data["request_id"] == "req-111"
    assert data["status"] == "approved"
    assert data["metadata"]["duration_ms"] == 1500


# ========================================
# Test: ApprovalGate Request Creation
# ========================================

def test_approval_gate_create_request():
    """Test ApprovalGate creates requests with unique IDs."""
    policy = ApprovalPolicy()
    gate = ApprovalGate(policy=policy)
    
    request1 = gate.create_request(
        operation="test_op",
        trace_id="trace-1",
    )
    request2 = gate.create_request(
        operation="test_op",
        trace_id="trace-1",
    )
    
    # Request IDs should be unique
    assert request1.request_id != request2.request_id
    assert request1.operation == "test_op"
    assert request1.trace_id == "trace-1"


def test_approval_gate_create_request_with_metadata():
    """Test ApprovalGate creates requests with metadata."""
    policy = ApprovalPolicy()
    gate = ApprovalGate(policy=policy)
    
    request = gate.create_request(
        operation="critical_op",
        trace_id="trace-999",
        metadata={"key": "value"},
        risk_level="critical",
        requester="api@example.com",
    )
    
    assert request.metadata["key"] == "value"
    assert request.risk_level == "critical"
    assert request.requester == "api@example.com"


# ========================================
# Test: Manual Approval Flow
# ========================================

@pytest.mark.asyncio
async def test_manual_approval_approved():
    """Test manual approval flow - request approved."""
    policy = ApprovalPolicy(timeout_seconds=5.0)
    gate = ApprovalGate(policy=policy)
    
    request = gate.create_request(
        operation="test_operation",
        trace_id="trace-manual-1",
    )
    
    # Start waiting for approval in background
    async def wait_and_respond():
        await asyncio.sleep(0.1)  # Small delay
        gate.respond_to_request(
            request_id=request.request_id,
            approved=True,
            approver="admin",
            reason="Looks good",
        )
    
    asyncio.create_task(wait_and_respond())
    
    # Wait for approval
    response = await gate.wait_for_approval(request)
    
    assert response.status == ApprovalStatus.APPROVED
    assert response.approver == "admin"
    assert response.reason == "Looks good"


@pytest.mark.asyncio
async def test_manual_approval_denied():
    """Test manual approval flow - request denied."""
    policy = ApprovalPolicy(timeout_seconds=5.0)
    gate = ApprovalGate(policy=policy)
    
    request = gate.create_request(
        operation="risky_operation",
        trace_id="trace-manual-2",
    )
    
    # Deny in background
    async def wait_and_deny():
        await asyncio.sleep(0.1)
        gate.respond_to_request(
            request_id=request.request_id,
            approved=False,
            approver="manager",
            reason="Too risky",
        )
    
    asyncio.create_task(wait_and_deny())
    
    response = await gate.wait_for_approval(request)
    
    assert response.status == ApprovalStatus.DENIED
    assert response.approver == "manager"
    assert response.reason == "Too risky"


@pytest.mark.asyncio
async def test_manual_approval_timeout_auto_approve():
    """Test manual approval timeout with auto-approve enabled."""
    policy = ApprovalPolicy(
        timeout_seconds=0.2,  # Very short timeout
        auto_approve_on_timeout=True,
    )
    gate = ApprovalGate(policy=policy)
    
    request = gate.create_request(
        operation="timeout_test",
        trace_id="trace-timeout-1",
    )
    
    # Don't respond - let it timeout
    response = await gate.wait_for_approval(request)
    
    assert response.status == ApprovalStatus.APPROVED
    assert response.approver == "system"
    assert "timeout" in response.reason.lower()


@pytest.mark.asyncio
async def test_manual_approval_timeout_no_auto_approve():
    """Test manual approval timeout without auto-approve."""
    policy = ApprovalPolicy(
        timeout_seconds=0.2,
        auto_approve_on_timeout=False,
    )
    gate = ApprovalGate(policy=policy)
    
    request = gate.create_request(
        operation="timeout_test_2",
        trace_id="trace-timeout-2",
    )
    
    response = await gate.wait_for_approval(request)
    
    assert response.status == ApprovalStatus.TIMEOUT
    assert response.approver == "system"


# ========================================
# Test: Callback-Based Approval Flow
# ========================================

@pytest.mark.asyncio
async def test_callback_approval_approved():
    """Test callback-based approval - request approved."""
    async def approval_callback(request: ApprovalRequest) -> ApprovalResponse:
        # Simulate quick approval
        await asyncio.sleep(0.05)
        return ApprovalResponse(
            request_id=request.request_id,
            status=ApprovalStatus.APPROVED,
            timestamp="2026-01-02T12:00:00+00:00",
            approver="callback_approver",
            reason="Auto-approved by callback",
        )
    
    policy = ApprovalPolicy(timeout_seconds=5.0)
    gate = ApprovalGate(policy=policy, callback=approval_callback)
    
    request = gate.create_request(
        operation="callback_test",
        trace_id="trace-callback-1",
    )
    
    response = await gate.wait_for_approval(request)
    
    assert response.status == ApprovalStatus.APPROVED
    assert response.approver == "callback_approver"


@pytest.mark.asyncio
async def test_callback_approval_timeout():
    """Test callback-based approval with timeout."""
    async def slow_callback(request: ApprovalRequest) -> ApprovalResponse:
        # Simulate slow approval that will timeout
        await asyncio.sleep(10.0)
        return ApprovalResponse(
            request_id=request.request_id,
            status=ApprovalStatus.APPROVED,
            timestamp="2026-01-02T12:00:00+00:00",
            approver="slow_approver",
            reason="Too late",
        )
    
    policy = ApprovalPolicy(
        timeout_seconds=0.2,
        auto_approve_on_timeout=True,
    )
    gate = ApprovalGate(policy=policy, callback=slow_callback)
    
    request = gate.create_request(
        operation="slow_callback_test",
        trace_id="trace-callback-2",
    )
    
    response = await gate.wait_for_approval(request)
    
    # Should timeout and auto-approve
    assert response.status == ApprovalStatus.APPROVED
    assert response.approver == "system"
    assert "timeout" in response.reason.lower()


# ========================================
# Test: Disabled Policy
# ========================================

@pytest.mark.asyncio
async def test_disabled_policy_auto_approves():
    """Test that disabled policy auto-approves immediately."""
    policy = ApprovalPolicy(enabled=False)
    gate = ApprovalGate(policy=policy)
    
    request = gate.create_request(
        operation="no_approval_needed",
        trace_id="trace-disabled",
    )
    
    response = await gate.wait_for_approval(request)
    
    assert response.status == ApprovalStatus.APPROVED
    assert response.approver == "system"
    assert "disabled" in response.reason.lower()


# ========================================
# Test: Request Management
# ========================================

@pytest.mark.asyncio
async def test_get_pending_requests():
    """Test getting list of pending requests."""
    policy = ApprovalPolicy()
    gate = ApprovalGate(policy=policy)
    
    # Create requests but don't wait for approval
    request1 = gate.create_request(operation="op1", trace_id="trace1")
    request2 = gate.create_request(operation="op2", trace_id="trace2")
    
    # Start waiting (but don't await)
    asyncio.create_task(gate.wait_for_approval(request1))
    asyncio.create_task(gate.wait_for_approval(request2))
    
    # Give tasks time to start
    await asyncio.sleep(0.05)
    
    pending = gate.get_pending_requests()
    assert request1.request_id in pending or request2.request_id in pending


@pytest.mark.asyncio
async def test_cancel_request():
    """Test cancelling a pending request."""
    policy = ApprovalPolicy(timeout_seconds=10.0)
    gate = ApprovalGate(policy=policy)
    
    request = gate.create_request(
        operation="cancel_test",
        trace_id="trace-cancel",
    )
    
    # Start waiting in background
    async def wait_and_cancel():
        await asyncio.sleep(0.1)
        gate.cancel_request(request.request_id)
    
    asyncio.create_task(wait_and_cancel())
    
    response = await gate.wait_for_approval(request)
    
    assert response.status == ApprovalStatus.CANCELLED
    assert response.approver == "system"


def test_cancel_nonexistent_request():
    """Test that cancelling nonexistent request raises KeyError."""
    policy = ApprovalPolicy()
    gate = ApprovalGate(policy=policy)
    
    with pytest.raises(KeyError):
        gate.cancel_request("nonexistent-id")


def test_respond_to_nonexistent_request():
    """Test that responding to nonexistent request raises KeyError."""
    policy = ApprovalPolicy()
    gate = ApprovalGate(policy=policy)
    
    with pytest.raises(KeyError):
        gate.respond_to_request(
            request_id="nonexistent-id",
            approved=True,
            approver="admin",
        )


# ========================================
# Test: Factory Function
# ========================================

def test_create_approval_gate_defaults():
    """Test create_approval_gate factory with defaults."""
    gate = create_approval_gate()
    
    assert gate.policy.enabled is True
    assert gate.policy.timeout_seconds == 300.0
    assert gate.policy.required_approvers == []
    assert gate.callback is None


def test_create_approval_gate_custom():
    """Test create_approval_gate factory with custom values."""
    async def dummy_callback(request):
        return ApprovalResponse(
            request_id=request.request_id,
            status=ApprovalStatus.APPROVED,
            timestamp="2026-01-02T12:00:00+00:00",
        )
    
    gate = create_approval_gate(
        enabled=True,
        timeout_seconds=60.0,
        required_approvers=["admin@example.com"],
        auto_approve_on_timeout=True,
        callback=dummy_callback,
    )
    
    assert gate.policy.timeout_seconds == 60.0
    assert gate.policy.auto_approve_on_timeout is True
    assert gate.callback == dummy_callback

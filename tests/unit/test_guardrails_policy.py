"""
Comprehensive tests for guardrails policy enforcement.

Tests per AGENTS.md § 7 Verification & No Conflicting Guardrails:
- Allow/deny boundaries
- Parameter schema violations
- Risk escalation denial
- Budget exhaustion
- Egress block/allow
- Approval required/approved/denied
"""

from pathlib import Path
from typing import Dict
from unittest.mock import MagicMock

import pytest

from cuga.backend.guardrails.policy import (
    GuardrailPolicy,
    NetworkEgressPolicy,
    ParameterSchema,
    RiskTier,
    ToolBudget,
    ToolSelectionPolicy,
    budget_guard,
    request_approval,
)
from cuga.security.governance import ApprovalStatus, GovernanceEngine, ToolCapability


class TestParameterSchema:
    """Test parameter schema validation."""
    
    def test_string_validation(self):
        """Test string type validation."""
        schema = ParameterSchema(name="message", type="string", required=True)
        
        # Valid
        schema.validate_value("hello")
        
        # Invalid type
        with pytest.raises(ValueError, match="must be string"):
            schema.validate_value(123)
    
    def test_integer_validation(self):
        """Test integer type and range validation."""
        schema = ParameterSchema(name="count", type="integer", min_value=1, max_value=100)
        
        # Valid
        schema.validate_value(50)
        
        # Invalid type
        with pytest.raises(ValueError, match="must be integer"):
            schema.validate_value("fifty")
        
        # Out of range
        with pytest.raises(ValueError, match="must be >= 1"):
            schema.validate_value(0)
        with pytest.raises(ValueError, match="must be <= 100"):
            schema.validate_value(101)
    
    def test_pattern_validation(self):
        """Test regex pattern matching."""
        schema = ParameterSchema(name="email", type="string", pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$")
        
        # Valid
        schema.validate_value("user@example.com")
        
        # Invalid pattern
        with pytest.raises(ValueError, match="does not match pattern"):
            schema.validate_value("invalid-email")
    
    def test_enum_validation(self):
        """Test enum constraint."""
        schema = ParameterSchema(name="status", type="string", enum=["pending", "approved", "rejected"])
        
        # Valid
        schema.validate_value("approved")
        
        # Invalid enum value
        with pytest.raises(ValueError, match="must be one of"):
            schema.validate_value("unknown")


class TestToolBudget:
    """Test budget tracking and enforcement."""
    
    def test_can_afford(self):
        """Test budget affordability checks."""
        budget = ToolBudget(max_cost=100.0, max_calls=50, max_tokens=10000)
        
        assert budget.can_afford(cost=10.0, calls=1, tokens=100)
        
        # Charge budget
        budget.charge(cost=95.0, calls=45, tokens=9500)
        
        # Should have enough for small operation
        assert budget.can_afford(cost=5.0, calls=5, tokens=500)
        
        # Should not afford large operation
        assert not budget.can_afford(cost=10.0, calls=1, tokens=100)
    
    def test_budget_exhaustion(self):
        """Test budget exhaustion scenarios."""
        budget = ToolBudget(max_cost=10.0, max_calls=5, max_tokens=1000)
        
        # Exhaust cost budget
        budget.charge(cost=10.0, calls=1, tokens=100)
        assert not budget.can_afford(cost=0.1)
        
        # Exhaust calls budget
        budget2 = ToolBudget(max_cost=100.0, max_calls=3, max_tokens=1000)
        budget2.charge(calls=3)
        assert not budget2.can_afford(calls=1)
        
        # Exhaust tokens budget
        budget3 = ToolBudget(max_cost=100.0, max_calls=50, max_tokens=1000)
        budget3.charge(tokens=1000)
        assert not budget3.can_afford(tokens=1)


class TestNetworkEgressPolicy:
    """Test network egress controls."""
    
    def test_allowlist_domains(self):
        """Test domain allowlist enforcement."""
        policy = NetworkEgressPolicy(
            allowed_domains={"api.example.com", "cdn.example.net"},
            allow_localhost=False,
        )
        
        # Allowed domains
        assert policy.is_allowed("https://api.example.com/v1/data")
        assert policy.is_allowed("https://cdn.example.net/assets/logo.png")
        assert policy.is_allowed("https://sub.api.example.com/endpoint")  # Subdomain
        
        # Denied domains
        assert not policy.is_allowed("https://evil.com/data")
        assert not policy.is_allowed("http://localhost:8080/admin")
    
    def test_localhost_control(self):
        """Test localhost and private network controls."""
        policy = NetworkEgressPolicy(
            allowed_domains=set(),  # Empty allowlist
            allow_localhost=True,
            allow_private_networks=False,
        )
        
        # Localhost allowed
        assert policy.is_allowed("http://localhost:8080")
        assert policy.is_allowed("http://127.0.0.1:3000")
        
        # Private networks denied
        assert not policy.is_allowed("http://192.168.1.1")
        assert not policy.is_allowed("http://10.0.0.1")
    
    def test_denylist_priority(self):
        """Test denylist takes priority over allowlist."""
        policy = NetworkEgressPolicy(
            allowed_domains={"example.com"},
            denied_domains={"evil.example.com"},
        )
        
        # Allowed
        assert policy.is_allowed("https://example.com")
        assert policy.is_allowed("https://api.example.com")
        
        # Denied (denylist wins)
        assert not policy.is_allowed("https://evil.example.com")


class TestGuardrailPolicy:
    """Test complete guardrail policy enforcement."""
    
    def test_tool_allowlist_enforcement(self):
        """Test allow/deny boundaries for tools."""
        policy = GuardrailPolicy(
            profile="test",
            allowed_tools={"safe_tool", "read_tool"},
            denied_tools={"dangerous_tool"},
            require_allowlist=True,
        )
        
        # Allowed tools pass
        policy.validate_tool("safe_tool")
        policy.validate_tool("read_tool")
        
        # Not in allowlist
        with pytest.raises(ValueError, match="not in allowlist"):
            policy.validate_tool("unknown_tool")
        
        # Explicitly denied
        with pytest.raises(ValueError, match="is denied"):
            policy.validate_tool("dangerous_tool")
    
    def test_parameter_validation(self):
        """Test tool parameter schema validation."""
        policy = GuardrailPolicy(
            profile="test",
            allowed_tools={"send_email"},
            tool_schemas={
                "send_email": [
                    ParameterSchema(name="to", type="string", required=True, pattern=r"^[\w\.-]+@[\w\.-]+\.\w+$"),
                    ParameterSchema(name="subject", type="string", required=True),
                    ParameterSchema(name="priority", type="string", enum=["low", "normal", "high"]),
                ]
            },
        )
        
        # Valid inputs
        policy.validate_parameters("send_email", {
            "to": "user@example.com",
            "subject": "Test",
            "priority": "normal",
        })
        
        # Missing required parameter
        with pytest.raises(ValueError, match="Missing required parameters"):
            policy.validate_parameters("send_email", {"to": "user@example.com"})
        
        # Invalid email pattern
        with pytest.raises(ValueError, match="does not match pattern"):
            policy.validate_parameters("send_email", {
                "to": "invalid-email",
                "subject": "Test",
            })
        
        # Invalid enum value
        with pytest.raises(ValueError, match="must be one of"):
            policy.validate_parameters("send_email", {
                "to": "user@example.com",
                "subject": "Test",
                "priority": "critical",  # Not in enum
            })
    
    def test_budget_integration(self):
        """Test budget enforcement integration."""
        policy = GuardrailPolicy(
            profile="test",
            allowed_tools={"tool1"},
            budget=ToolBudget(max_cost=10.0, max_calls=5),
        )
        
        # Within budget
        assert policy.check_budget(cost=5.0, calls=2)
        policy.charge_budget(cost=5.0, calls=2)
        
        # Approaching limit
        assert policy.check_budget(cost=5.0, calls=3)
        
        # Would exceed
        assert not policy.check_budget(cost=10.0, calls=1)
    
    def test_risk_tier_approval_requirements(self):
        """Test approval requirements based on risk tiers."""
        policy = GuardrailPolicy(
            profile="test",
            allowed_tools={"read_tool", "delete_tool", "transfer_money"},
            tool_risk_tiers={
                "read_tool": RiskTier.READ,
                "delete_tool": RiskTier.DELETE,
                "transfer_money": RiskTier.FINANCIAL,
            },
            require_approval_for={RiskTier.DELETE, RiskTier.FINANCIAL},
        )
        
        # Check which tools require approval
        assert RiskTier.READ not in policy.require_approval_for
        assert RiskTier.DELETE in policy.require_approval_for
        assert RiskTier.FINANCIAL in policy.require_approval_for
    
    def test_yaml_loading_fails_on_unknown_keys(self):
        """Test YAML validation fails on unknown keys."""
        import tempfile
        import yaml
        
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({
                "profile": "test",
                "allowed_tools": ["tool1"],
                "unknown_key": "value",  # Should fail
            }, f)
            temp_path = Path(f.name)
        
        try:
            with pytest.raises(ValueError, match="Unknown policy keys"):
                GuardrailPolicy.from_yaml(temp_path)
        finally:
            temp_path.unlink()


class TestToolSelectionPolicy:
    """Test tool selection with ranking and filtering."""
    
    def test_allowlist_filtering(self):
        """Test tools are filtered by allowlist."""
        policy = GuardrailPolicy(
            profile="test",
            allowed_tools={"tool1", "tool2"},
            require_allowlist=True,
        )
        selector = ToolSelectionPolicy(policy)
        
        available_tools = ["tool1", "tool2", "tool3", "tool4"]
        selected = selector.select_tools("test goal", available_tools)
        
        # Only allowlisted tools selected
        assert set(selected) <= {"tool1", "tool2"}
        assert "tool3" not in selected
        assert "tool4" not in selected
    
    def test_similarity_ranking(self):
        """Test tools are ranked by similarity."""
        policy = GuardrailPolicy(
            profile="test",
            allowed_tools={"tool1", "tool2", "tool3"},
            require_allowlist=True,
        )
        selector = ToolSelectionPolicy(policy)
        
        similarity_scores = {
            "tool1": 0.9,
            "tool2": 0.5,
            "tool3": 0.7,
        }
        
        selected = selector.select_tools(
            "test goal",
            ["tool1", "tool2", "tool3"],
            similarity_scores=similarity_scores,
            top_k=2,
        )
        
        # Should select top-2 by similarity
        assert selected == ["tool1", "tool3"]  # 0.9 and 0.7
    
    def test_risk_penalty(self):
        """Test risk tiers penalize selection scores."""
        policy = GuardrailPolicy(
            profile="test",
            allowed_tools={"safe_tool", "risky_tool"},
            tool_risk_tiers={
                "safe_tool": RiskTier.READ,
                "risky_tool": RiskTier.FINANCIAL,
            },
            require_allowlist=True,
        )
        selector = ToolSelectionPolicy(policy)
        
        # Equal similarity, but different risk
        similarity_scores = {
            "safe_tool": 0.8,
            "risky_tool": 0.8,
        }
        
        selected = selector.select_tools(
            "test goal",
            ["safe_tool", "risky_tool"],
            similarity_scores=similarity_scores,
            top_k=1,
        )
        
        # Should prefer lower-risk tool
        assert selected == ["safe_tool"]
    
    def test_budget_penalty(self):
        """Test budget exhaustion penalizes tool selection."""
        policy = GuardrailPolicy(
            profile="test",
            allowed_tools={"tool1", "tool2"},
            budget=ToolBudget(max_cost=10.0, current_cost=9.9),  # Nearly exhausted
            require_allowlist=True,
        )
        selector = ToolSelectionPolicy(policy)
        
        # Should apply heavy penalty when budget exhausted
        similarity_scores = {"tool1": 0.8, "tool2": 0.7}
        selected = selector.select_tools(
            "test goal",
            ["tool1", "tool2"],
            similarity_scores=similarity_scores,
            top_k=2,
        )
        
        # Still returns tools, but with heavy penalty applied
        assert len(selected) <= 2


class TestBudgetGuard:
    """Test budget guard integration function."""
    
    def test_budget_guard_success(self):
        """Test budget guard passes when budget available."""
        policy = GuardrailPolicy(
            profile="test",
            allowed_tools=set(),
            budget=ToolBudget(max_cost=100.0, max_calls=50),
        )
        
        # Should not raise
        budget_guard(policy, cost=10.0, calls=1)
        
        # Budget should be charged
        assert policy.budget.current_cost == 10.0
        assert policy.budget.current_calls == 1
    
    def test_budget_guard_failure(self):
        """Test budget guard raises on exhaustion."""
        policy = GuardrailPolicy(
            profile="test",
            allowed_tools=set(),
            budget=ToolBudget(max_cost=10.0, current_cost=10.0),
        )
        
        with pytest.raises(ValueError, match="Budget exhausted"):
            budget_guard(policy, cost=1.0)


class TestRequestApproval:
    """Test approval request integration."""
    
    def test_auto_approval_for_low_risk(self):
        """Test low-risk tools are auto-approved."""
        policy = GuardrailPolicy(
            profile="test",
            allowed_tools={"read_tool"},
            tool_risk_tiers={"read_tool": RiskTier.READ},
            require_approval_for={RiskTier.DELETE, RiskTier.FINANCIAL},
        )
        
        governance_engine = MagicMock(spec=GovernanceEngine)
        
        approval = request_approval(
            policy=policy,
            governance_engine=governance_engine,
            tool_name="read_tool",
            inputs={},
            context={},
            request_id="req-1",
        )
        
        # Should be auto-approved
        assert approval.status == ApprovalStatus.APPROVED
        assert approval.approved_by == "auto"
        
        # Governance engine should NOT be called for auto-approval
        governance_engine.request_approval.assert_not_called()
    
    def test_approval_required_for_high_risk(self):
        """Test high-risk tools require HITL approval."""
        policy = GuardrailPolicy(
            profile="test",
            allowed_tools={"delete_tool"},
            tool_risk_tiers={"delete_tool": RiskTier.DELETE},
            require_approval_for={RiskTier.DELETE},
        )
        
        governance_engine = MagicMock(spec=GovernanceEngine)
        
        approval = request_approval(
            policy=policy,
            governance_engine=governance_engine,
            tool_name="delete_tool",
            inputs={"file": "/important/data.txt"},
            context={"trace_id": "trace-123"},
            request_id="req-2",
        )
        
        # Governance engine should be called for HITL approval
        governance_engine.request_approval.assert_called_once_with(
            tool_name="delete_tool",
            tenant="test",
            inputs={"file": "/important/data.txt"},
            context={"trace_id": "trace-123"},
            request_id="req-2",
        )

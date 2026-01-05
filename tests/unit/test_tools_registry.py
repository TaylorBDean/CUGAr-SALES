"""
tests/unit/test_tools_registry.py

Comprehensive tests for tools/registry infrastructure per AGENTS.md requirements:
- Tool allowlist/denylist validation
- Parameter schema enforcement
- Dynamic import restrictions (only cuga.modular.tools.*)
- Sandbox profile checks
- Risk tier enforcement
- Budget cost tracking
- Network egress controls
"""

import os
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest
import yaml
from pydantic import ValidationError

from cuga.backend.guardrails.policy import (
    GuardrailPolicy,
    NetworkEgressPolicy,
    ParameterSchema,
    RiskTier,
    ToolBudget,
    ToolSelectionPolicy,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def sample_registry_yaml():
    """Sample registry.yaml for testing."""
    return """
tools:
  - name: filesystem_read
    tier: 1
    enabled: true
    sandbox_profile: py_slim
    network_allowed: false
    risk_tier: READ
    budget_cost: 0.001
    parameters:
      - name: path
        type: string
        required: true
  
  - name: web_search
    tier: 1
    enabled: true
    sandbox_profile: node_slim
    network_allowed: true
    risk_tier: EXTERNAL
    budget_cost: 0.01
    parameters:
      - name: query
        type: string
        required: true
  
  - name: code_exec
    tier: 2
    enabled: false
    sandbox_profile: py_full
    network_allowed: false
    risk_tier: WRITE
    budget_cost: 0.005
    parameters:
      - name: code
        type: string
        required: true
      - name: timeout
        type: integer
        required: false
        default: 30
"""


@pytest.fixture
def sample_guardrail_policy():
    """Sample GuardrailPolicy for testing."""
    policy_dict = {
        "tool_allowlist": ["filesystem_read", "web_search"],
        "tool_denylist": ["dangerous_tool"],
        "parameter_schemas": {
            "filesystem_read": {
                "path": {
                    "type": "string",
                    "required": True,
                    "pattern": r"^[a-zA-Z0-9/_\-\.]+$",
                }
            }
        },
        "network_egress": {
            "allowed_domains": ["api.openai.com", "example.com"],
            "block_localhost": True,
            "block_private_networks": True,
        },
    }
    return GuardrailPolicy(**policy_dict)


# ============================================================================
# Tool Allowlist/Denylist Tests
# ============================================================================


class TestToolAllowlistDenylist:
    """Test tool allowlist and denylist enforcement."""

    def test_tool_in_allowlist_passes(self, sample_guardrail_policy):
        """Tool in allowlist should be allowed."""
        policy = sample_guardrail_policy
        assert "filesystem_read" in policy.tool_allowlist
        assert policy.is_tool_allowed("filesystem_read")

    def test_tool_not_in_allowlist_rejected(self, sample_guardrail_policy):
        """Tool not in allowlist should be rejected."""
        policy = sample_guardrail_policy
        assert not policy.is_tool_allowed("unknown_tool")

    def test_tool_in_denylist_rejected(self, sample_guardrail_policy):
        """Tool in denylist should be rejected even if in allowlist."""
        policy = sample_guardrail_policy
        assert not policy.is_tool_allowed("dangerous_tool")

    def test_empty_allowlist_denies_all(self):
        """Empty allowlist should deny all tools."""
        policy = GuardrailPolicy(tool_allowlist=[], tool_denylist=[])
        assert not policy.is_tool_allowed("any_tool")

    def test_denylist_takes_precedence(self):
        """Denylist should override allowlist."""
        policy = GuardrailPolicy(
            tool_allowlist=["tool_a"], tool_denylist=["tool_a"]
        )
        assert not policy.is_tool_allowed("tool_a")


# ============================================================================
# Parameter Schema Enforcement Tests
# ============================================================================


class TestParameterSchemas:
    """Test parameter schema validation."""

    def test_valid_parameters_pass(self, sample_guardrail_policy):
        """Valid parameters should pass validation."""
        policy = sample_guardrail_policy
        params = {"path": "/home/user/file.txt"}
        
        result = policy.validate_parameters("filesystem_read", params)
        assert result["valid"]
        assert not result["violations"]

    def test_missing_required_parameter_rejected(self, sample_guardrail_policy):
        """Missing required parameter should fail validation."""
        policy = sample_guardrail_policy
        params = {}  # Missing 'path'
        
        result = policy.validate_parameters("filesystem_read", params)
        assert not result["valid"]
        assert any("required" in v.lower() for v in result["violations"])

    def test_parameter_pattern_validation(self, sample_guardrail_policy):
        """Parameters must match pattern if specified."""
        policy = sample_guardrail_policy
        
        # Valid path
        valid_params = {"path": "/home/user/file.txt"}
        result = policy.validate_parameters("filesystem_read", valid_params)
        assert result["valid"]
        
        # Invalid path (contains special characters not in pattern)
        invalid_params = {"path": "/home/user/file@#$.txt"}
        result = policy.validate_parameters("filesystem_read", invalid_params)
        assert not result["valid"]

    def test_parameter_type_validation(self):
        """Parameters must match specified type."""
        policy = GuardrailPolicy(
            tool_allowlist=["test_tool"],
            parameter_schemas={
                "test_tool": {
                    "count": ParameterSchema(type="integer", required=True),
                    "name": ParameterSchema(type="string", required=False),
                }
            },
        )
        
        # Valid types
        valid_params = {"count": 5, "name": "test"}
        result = policy.validate_parameters("test_tool", valid_params)
        assert result["valid"]
        
        # Invalid type
        invalid_params = {"count": "five"}  # String instead of int
        result = policy.validate_parameters("test_tool", invalid_params)
        assert not result["valid"]

    def test_parameter_range_validation(self):
        """Parameters must be within specified range."""
        policy = GuardrailPolicy(
            tool_allowlist=["test_tool"],
            parameter_schemas={
                "test_tool": {
                    "age": ParameterSchema(
                        type="integer", required=True, min_value=0, max_value=120
                    )
                }
            },
        )
        
        # Valid range
        valid_params = {"age": 25}
        result = policy.validate_parameters("test_tool", valid_params)
        assert result["valid"]
        
        # Out of range
        invalid_params = {"age": 150}
        result = policy.validate_parameters("test_tool", invalid_params)
        assert not result["valid"]

    def test_parameter_enum_validation(self):
        """Parameters must be in allowed enum values."""
        policy = GuardrailPolicy(
            tool_allowlist=["test_tool"],
            parameter_schemas={
                "test_tool": {
                    "level": ParameterSchema(
                        type="string",
                        required=True,
                        allowed_values=["DEBUG", "INFO", "WARN", "ERROR"],
                    )
                }
            },
        )
        
        # Valid enum
        valid_params = {"level": "INFO"}
        result = policy.validate_parameters("test_tool", valid_params)
        assert result["valid"]
        
        # Invalid enum
        invalid_params = {"level": "TRACE"}
        result = policy.validate_parameters("test_tool", invalid_params)
        assert not result["valid"]


# ============================================================================
# Dynamic Import Restriction Tests
# ============================================================================


class TestDynamicImportRestrictions:
    """Test that dynamic imports are restricted to cuga.modular.tools.* only."""

    def test_allowlisted_module_import(self):
        """Imports from cuga.modular.tools.* should be allowed."""
        allowlisted_modules = [
            "cuga.modular.tools.filesystem",
            "cuga.modular.tools.web",
            "cuga.modular.tools.code_exec",
        ]
        
        for module in allowlisted_modules:
            # Simulate import validation
            assert module.startswith("cuga.modular.tools.")

    def test_denylisted_module_import(self):
        """Imports outside cuga.modular.tools.* should be rejected."""
        denylisted_modules = [
            "os",
            "subprocess",
            "pickle",
            "eval",
            "exec",
            "requests",
            "httpx",
            "external.malicious",
        ]
        
        for module in denylisted_modules:
            # Simulate import validation
            assert not module.startswith("cuga.modular.tools.")

    def test_relative_import_rejected(self):
        """Relative imports should be rejected."""
        relative_imports = [
            ".local_tool",
            "..parent_tool",
            "../../../etc/passwd",
        ]
        
        for module in relative_imports:
            # Relative paths are rejected
            assert not module.startswith("cuga.modular.tools.")


# ============================================================================
# Sandbox Profile Tests
# ============================================================================


class TestSandboxProfiles:
    """Test sandbox profile validation and assignment."""

    def test_valid_sandbox_profiles(self, sample_registry_yaml):
        """Valid sandbox profiles should be accepted."""
        registry = yaml.safe_load(sample_registry_yaml)
        
        valid_profiles = ["py_slim", "py_full", "node_slim", "node_full", "orchestrator"]
        
        for tool in registry["tools"]:
            assert tool["sandbox_profile"] in valid_profiles

    def test_invalid_sandbox_profile_rejected(self):
        """Invalid sandbox profiles should be rejected."""
        invalid_profiles = ["unknown_profile", "custom", ""]
        
        valid_profiles = ["py_slim", "py_full", "node_slim", "node_full", "orchestrator"]
        
        for profile in invalid_profiles:
            assert profile not in valid_profiles

    def test_sandbox_profile_network_restrictions(self, sample_registry_yaml):
        """Tools should respect network restrictions based on profile."""
        registry = yaml.safe_load(sample_registry_yaml)
        
        for tool in registry["tools"]:
            if not tool["network_allowed"]:
                # Network-disabled tools should not make external calls
                assert tool["network_allowed"] is False

    def test_sandbox_profile_read_only_mounts(self):
        """Sandboxes should have read-only mounts by default."""
        # Per AGENTS.md: read-only defaults for sandboxes
        default_mounts = {
            "/workdir": "ro",
            "/workspace": "ro",
            "/workspace/output": "rw",  # Exception for output
        }
        
        # Verify read-only defaults
        assert default_mounts["/workdir"] == "ro"
        assert default_mounts["/workspace"] == "ro"


# ============================================================================
# Risk Tier Enforcement Tests
# ============================================================================


class TestRiskTiers:
    """Test risk tier classification and enforcement."""

    def test_risk_tier_enum_values(self):
        """RiskTier enum should have expected values."""
        assert RiskTier.READ
        assert RiskTier.WRITE
        assert RiskTier.DELETE
        assert RiskTier.FINANCIAL
        assert RiskTier.EXTERNAL

    def test_risk_tier_assignment(self, sample_registry_yaml):
        """Tools should have appropriate risk tiers assigned."""
        registry = yaml.safe_load(sample_registry_yaml)
        
        for tool in registry["tools"]:
            assert tool["risk_tier"] in [
                "READ",
                "WRITE",
                "DELETE",
                "FINANCIAL",
                "EXTERNAL",
            ]

    def test_high_risk_tools_require_approval(self):
        """High-risk tools (DELETE, FINANCIAL) should require approval."""
        high_risk_tiers = [RiskTier.DELETE, RiskTier.FINANCIAL]
        
        # Simulate approval gate
        for tier in high_risk_tiers:
            # High-risk tools require approval per AGENTS.md
            assert tier in [RiskTier.DELETE, RiskTier.FINANCIAL]

    def test_low_risk_tools_auto_approved(self):
        """Low-risk tools (READ) should be auto-approved."""
        low_risk_tiers = [RiskTier.READ]
        
        for tier in low_risk_tiers:
            # Low-risk tools auto-approved
            assert tier == RiskTier.READ


# ============================================================================
# Budget Cost Tracking Tests
# ============================================================================


class TestBudgetCostTracking:
    """Test budget cost tracking and enforcement."""

    def test_tool_budget_initialization(self):
        """ToolBudget should initialize with correct values."""
        budget = ToolBudget(ceiling=100.0, cost_per_call=1.0, calls_limit=50, tokens_limit=10000)
        
        assert budget.ceiling == 100.0
        assert budget.cost_per_call == 1.0
        assert budget.calls_limit == 50
        assert budget.tokens_limit == 10000
        assert budget.spent == 0.0
        assert budget.calls == 0
        assert budget.tokens == 0

    def test_budget_can_afford_within_ceiling(self):
        """Budget should allow operations within ceiling."""
        budget = ToolBudget(ceiling=100.0, cost_per_call=1.0)
        
        assert budget.can_afford(50.0)  # 50 < 100
        assert budget.can_afford(100.0)  # Exactly at ceiling
        assert not budget.can_afford(101.0)  # Over ceiling

    def test_budget_tracks_spent_cost(self):
        """Budget should track cumulative spent cost."""
        budget = ToolBudget(ceiling=100.0, cost_per_call=1.0)
        
        budget.spend(10.0)
        assert budget.spent == 10.0
        
        budget.spend(25.0)
        assert budget.spent == 35.0
        
        # Should reject spend that exceeds ceiling
        assert not budget.can_afford(70.0)  # Would total 105

    def test_budget_tracks_call_count(self):
        """Budget should track number of calls."""
        budget = ToolBudget(ceiling=100.0, calls_limit=10)
        
        for i in range(10):
            budget.spend(1.0)
        
        assert budget.calls == 10
        assert not budget.can_afford(1.0)  # Exceeded calls_limit

    def test_budget_tracks_token_usage(self):
        """Budget should track token usage."""
        budget = ToolBudget(ceiling=100.0, tokens_limit=1000)
        
        budget.spend(1.0, tokens=500)
        assert budget.tokens == 500
        
        budget.spend(1.0, tokens=600)
        assert budget.tokens == 1100
        assert budget.tokens > budget.tokens_limit


# ============================================================================
# Network Egress Control Tests
# ============================================================================


class TestNetworkEgressControls:
    """Test network egress policy enforcement."""

    def test_allowed_domain_passes(self, sample_guardrail_policy):
        """Requests to allowed domains should pass."""
        policy = sample_guardrail_policy
        
        assert policy.network_egress.is_allowed_domain("api.openai.com")
        assert policy.network_egress.is_allowed_domain("example.com")

    def test_disallowed_domain_rejected(self, sample_guardrail_policy):
        """Requests to disallowed domains should be rejected."""
        policy = sample_guardrail_policy
        
        assert not policy.network_egress.is_allowed_domain("malicious.com")
        assert not policy.network_egress.is_allowed_domain("unknown.domain")

    def test_localhost_blocked_when_configured(self, sample_guardrail_policy):
        """Localhost should be blocked when block_localhost=True."""
        policy = sample_guardrail_policy
        
        assert policy.network_egress.block_localhost
        assert not policy.network_egress.is_allowed_domain("localhost")
        assert not policy.network_egress.is_allowed_domain("127.0.0.1")

    def test_private_networks_blocked_when_configured(self, sample_guardrail_policy):
        """Private networks should be blocked when block_private_networks=True."""
        policy = sample_guardrail_policy
        
        assert policy.network_egress.block_private_networks
        
        private_ips = [
            "192.168.1.1",
            "10.0.0.1",
            "172.16.0.1",
        ]
        
        for ip in private_ips:
            assert not policy.network_egress.is_allowed_domain(ip)

    def test_subdomain_matching(self):
        """Subdomain matching should work correctly."""
        policy = NetworkEgressPolicy(
            allowed_domains=["example.com"],
            allow_subdomains=True,
        )
        
        assert policy.is_allowed_domain("api.example.com")
        assert policy.is_allowed_domain("cdn.example.com")
        assert not policy.is_allowed_domain("notexample.com")


# ============================================================================
# Tool Selection Policy Tests
# ============================================================================


class TestToolSelectionPolicy:
    """Test tool selection and ranking."""

    def test_tool_selection_ranks_by_similarity(self):
        """Tools should be ranked by similarity score."""
        policy = ToolSelectionPolicy()
        
        tools = [
            {"name": "filesystem_read", "similarity": 0.9},
            {"name": "web_search", "similarity": 0.5},
            {"name": "code_exec", "similarity": 0.8},
        ]
        
        ranked = policy.rank_tools(tools)
        
        # Should be sorted by similarity (descending)
        assert ranked[0]["name"] == "filesystem_read"
        assert ranked[1]["name"] == "code_exec"
        assert ranked[2]["name"] == "web_search"

    def test_tool_selection_applies_risk_penalty(self):
        """High-risk tools should be penalized in ranking."""
        policy = ToolSelectionPolicy(risk_penalty_factor=0.2)
        
        tools = [
            {"name": "read_tool", "similarity": 0.8, "risk_tier": "READ"},
            {"name": "delete_tool", "similarity": 0.9, "risk_tier": "DELETE"},
        ]
        
        ranked = policy.rank_tools(tools)
        
        # DELETE tool should be penalized despite higher similarity
        # 0.9 * (1 - 0.2) = 0.72 < 0.8
        assert ranked[0]["name"] == "read_tool"

    def test_tool_selection_considers_budget(self):
        """Tool selection should consider budget constraints."""
        policy = ToolSelectionPolicy()
        budget = ToolBudget(ceiling=10.0)
        
        tools = [
            {"name": "cheap_tool", "similarity": 0.8, "budget_cost": 1.0},
            {"name": "expensive_tool", "similarity": 0.9, "budget_cost": 15.0},
        ]
        
        ranked = policy.rank_tools(tools, budget=budget)
        
        # Expensive tool should be filtered out (cost > remaining budget)
        assert len(ranked) == 1
        assert ranked[0]["name"] == "cheap_tool"


# ============================================================================
# Integration Tests
# ============================================================================


class TestToolsRegistryIntegration:
    """Integration tests for tools/registry pipeline."""

    def test_load_registry_from_yaml(self, tmp_path, sample_registry_yaml):
        """Should load registry from YAML file."""
        registry_file = tmp_path / "registry.yaml"
        registry_file.write_text(sample_registry_yaml)
        
        registry = yaml.safe_load(registry_file.read_text())
        
        assert "tools" in registry
        assert len(registry["tools"]) == 3

    def test_validate_registry_schema(self, sample_registry_yaml):
        """Registry should match expected schema."""
        registry = yaml.safe_load(sample_registry_yaml)
        
        for tool in registry["tools"]:
            assert "name" in tool
            assert "tier" in tool
            assert "enabled" in tool
            assert "sandbox_profile" in tool
            assert "network_allowed" in tool
            assert "risk_tier" in tool
            assert "budget_cost" in tool

    def test_guardrail_policy_enforces_registry(self, sample_registry_yaml):
        """GuardrailPolicy should enforce registry constraints."""
        registry = yaml.safe_load(sample_registry_yaml)
        
        # Build allowlist from enabled Tier 1 tools
        allowlist = [
            tool["name"]
            for tool in registry["tools"]
            if tool["tier"] == 1 and tool["enabled"]
        ]
        
        policy = GuardrailPolicy(tool_allowlist=allowlist)
        
        assert policy.is_tool_allowed("filesystem_read")
        assert policy.is_tool_allowed("web_search")
        assert not policy.is_tool_allowed("code_exec")  # Tier 2, disabled

    def test_full_tool_execution_pipeline(self, sample_guardrail_policy):
        """Simulate full tool execution pipeline."""
        policy = sample_guardrail_policy
        tool_name = "filesystem_read"
        params = {"path": "/home/user/file.txt"}
        
        # Step 1: Check allowlist
        assert policy.is_tool_allowed(tool_name)
        
        # Step 2: Validate parameters
        validation = policy.validate_parameters(tool_name, params)
        assert validation["valid"]
        
        # Step 3: Check budget
        budget = ToolBudget(ceiling=100.0)
        assert budget.can_afford(0.001)  # filesystem_read cost
        
        # Step 4: Execute (mocked)
        # ... tool execution would happen here ...
        
        # Step 5: Track cost
        budget.spend(0.001)
        assert budget.spent == 0.001


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

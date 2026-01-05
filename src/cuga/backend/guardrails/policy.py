"""
Comprehensive guardrail policy schema and enforcement.

Per AGENTS.md guardrails:
- Allowlist/denylist tool selection with deny-by-default
- Parameter schema validation with type checking
- Risk tier enforcement (READ/WRITE/DELETE/FINANCIAL)
- Budget and quota tracking per session/step
- Network egress allowlist with domain validation
- Approval gates for high-risk operations (HITL)
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import yaml
from pydantic import BaseModel, Field, ValidationError, validator

from ...observability import emit_event
from ...security.governance import ActionType, ApprovalRequest, ApprovalStatus, GovernanceEngine


logger = logging.getLogger(__name__)


class RiskTier(str, Enum):
    """Risk classification for tools following AGENTS.md § 3 Registry Hygiene."""
    
    READ = "read"  # Low risk: read-only operations
    WRITE = "write"  # Medium risk: mutating operations
    DELETE = "delete"  # High risk: destructive operations
    FINANCIAL = "financial"  # Critical risk: financial transactions
    EXTERNAL = "external"  # Variable risk: external API calls
    
    def to_action_type(self) -> ActionType:
        """Convert to governance ActionType for compatibility."""
        return ActionType[self.name]


class ParameterSchema(BaseModel):
    """Parameter validation schema for tool inputs."""
    
    name: str
    type: str  # "string", "integer", "boolean", "array", "object"
    required: bool = False
    default: Optional[Any] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    pattern: Optional[str] = None  # Regex pattern for strings
    enum: Optional[List[str]] = None  # Allowed values
    description: Optional[str] = None
    
    @validator("type")
    def validate_type(cls, v: str) -> str:
        """Validate parameter type."""
        allowed_types = {"string", "integer", "float", "boolean", "array", "object", "any"}
        if v not in allowed_types:
            raise ValueError(f"Invalid parameter type '{v}', must be one of {allowed_types}")
        return v
    
    def validate_value(self, value: Any) -> None:
        """Validate parameter value against schema."""
        # Type checking
        if self.type == "string" and not isinstance(value, str):
            raise ValueError(f"Parameter '{self.name}' must be string, got {type(value)}")
        elif self.type == "integer" and not isinstance(value, int):
            raise ValueError(f"Parameter '{self.name}' must be integer, got {type(value)}")
        elif self.type == "float" and not isinstance(value, (int, float)):
            raise ValueError(f"Parameter '{self.name}' must be float, got {type(value)}")
        elif self.type == "boolean" and not isinstance(value, bool):
            raise ValueError(f"Parameter '{self.name}' must be boolean, got {type(value)}")
        elif self.type == "array" and not isinstance(value, list):
            raise ValueError(f"Parameter '{self.name}' must be array, got {type(value)}")
        elif self.type == "object" and not isinstance(value, dict):
            raise ValueError(f"Parameter '{self.name}' must be object, got {type(value)}")
        
        # Range checking for numeric types
        if self.type in {"integer", "float"}:
            if self.min_value is not None and value < self.min_value:
                raise ValueError(f"Parameter '{self.name}' must be >= {self.min_value}, got {value}")
            if self.max_value is not None and value > self.max_value:
                raise ValueError(f"Parameter '{self.name}' must be <= {self.max_value}, got {value}")
        
        # Pattern matching for strings
        if self.type == "string" and self.pattern:
            if not re.match(self.pattern, value):
                raise ValueError(f"Parameter '{self.name}' does not match pattern '{self.pattern}'")
        
        # Enum validation
        if self.enum and value not in self.enum:
            raise ValueError(f"Parameter '{self.name}' must be one of {self.enum}, got '{value}'")


class ToolBudget(BaseModel):
    """Budget tracking for tool execution."""
    
    max_cost: float = 100.0  # Maximum cost units per session
    max_calls: int = 50  # Maximum tool calls per session
    max_tokens: int = 100_000  # Maximum tokens per session
    current_cost: float = 0.0
    current_calls: int = 0
    current_tokens: int = 0
    
    def can_afford(self, cost: float = 0.0, calls: int = 1, tokens: int = 0) -> bool:
        """Check if budget can afford the operation."""
        return (
            self.current_cost + cost <= self.max_cost
            and self.current_calls + calls <= self.max_calls
            and self.current_tokens + tokens <= self.max_tokens
        )
    
    def charge(self, cost: float = 0.0, calls: int = 1, tokens: int = 0) -> None:
        """Charge the budget for an operation."""
        self.current_cost += cost
        self.current_calls += calls
        self.current_tokens += tokens


class NetworkEgressPolicy(BaseModel):
    """Network egress control with domain allowlist."""
    
    allowed_domains: Set[str] = Field(default_factory=set)  # e.g., {"api.example.com"}
    denied_domains: Set[str] = Field(default_factory=set)
    allow_localhost: bool = False
    allow_private_networks: bool = False
    
    def is_allowed(self, url: str) -> bool:
        """Check if URL is allowed by egress policy."""
        from urllib.parse import urlparse
        
        parsed = urlparse(url)
        domain = parsed.netloc.split(":")[0]  # Remove port
        
        # Check deny list first
        if domain in self.denied_domains:
            return False
        
        # Check localhost/private networks
        if domain in {"localhost", "127.0.0.1", "::1"}:
            return self.allow_localhost
        if domain.startswith("192.168.") or domain.startswith("10.") or domain.startswith("172."):
            return self.allow_private_networks
        
        # Check allow list
        if not self.allowed_domains:
            return True  # Empty allowlist = allow all (override with deny-by-default in production)
        
        # Exact match or subdomain match
        for allowed in self.allowed_domains:
            if domain == allowed or domain.endswith(f".{allowed}"):
                return True
        
        return False


class GuardrailPolicy(BaseModel):
    """Complete guardrail policy document per AGENTS.md."""
    
    version: str = "1.0"
    profile: str
    
    # Tool selection
    allowed_tools: Set[str] = Field(default_factory=set)  # Empty = deny-by-default
    denied_tools: Set[str] = Field(default_factory=set)
    require_allowlist: bool = True  # Deny-by-default unless in allowlist
    
    # Parameter schemas per tool
    tool_schemas: Dict[str, List[ParameterSchema]] = Field(default_factory=dict)
    
    # Risk tiers per tool
    tool_risk_tiers: Dict[str, RiskTier] = Field(default_factory=dict)
    
    # Budget enforcement
    budget: ToolBudget = Field(default_factory=ToolBudget)
    
    # Network egress
    network_egress: NetworkEgressPolicy = Field(default_factory=NetworkEgressPolicy)
    
    # Approval requirements
    require_approval_for: Set[RiskTier] = Field(default_factory=lambda: {RiskTier.DELETE, RiskTier.FINANCIAL})
    approval_timeout_seconds: int = 300  # 5 minutes
    
    # Observability
    emit_events: bool = True
    log_tool_calls: bool = True
    
    @classmethod
    def from_yaml(cls, path: Path) -> GuardrailPolicy:
        """Load policy from YAML file with validation."""
        with open(path) as f:
            data = yaml.safe_load(f)
        
        # Fail on unknown keys
        known_keys = set(cls.__fields__.keys())
        unknown_keys = set(data.keys()) - known_keys
        if unknown_keys:
            raise ValueError(f"Unknown policy keys: {unknown_keys}. Known keys: {known_keys}")
        
        return cls(**data)
    
    def validate_tool(self, tool_name: str) -> None:
        """Validate tool is allowed by policy."""
        # Deny-by-default if allowlist is required
        if self.require_allowlist and tool_name not in self.allowed_tools:
            raise ValueError(
                f"Tool '{tool_name}' not in allowlist for profile '{self.profile}'. "
                f"Allowed: {sorted(self.allowed_tools)}"
            )
        
        # Check denylist
        if tool_name in self.denied_tools:
            raise ValueError(f"Tool '{tool_name}' is denied for profile '{self.profile}'")
    
    def validate_parameters(self, tool_name: str, inputs: Dict[str, Any]) -> None:
        """Validate tool inputs against parameter schemas."""
        schemas = self.tool_schemas.get(tool_name, [])
        if not schemas:
            return  # No schema = no validation
        
        # Check required parameters
        required_params = {s.name for s in schemas if s.required}
        missing_params = required_params - set(inputs.keys())
        if missing_params:
            raise ValueError(f"Missing required parameters for '{tool_name}': {missing_params}")
        
        # Validate each parameter
        for schema in schemas:
            if schema.name in inputs:
                try:
                    schema.validate_value(inputs[schema.name])
                except ValueError as e:
                    raise ValueError(f"Parameter validation failed for '{tool_name}': {e}")
    
    def check_budget(self, cost: float = 0.0, calls: int = 1, tokens: int = 0) -> bool:
        """Check if budget allows the operation."""
        return self.budget.can_afford(cost, calls, tokens)
    
    def charge_budget(self, cost: float = 0.0, calls: int = 1, tokens: int = 0) -> None:
        """Charge budget for an operation."""
        self.budget.charge(cost, calls, tokens)
        
        if self.emit_events:
            # Emit budget event if approaching limits
            utilization = max(
                self.budget.current_cost / self.budget.max_cost,
                self.budget.current_calls / self.budget.max_calls,
                self.budget.current_tokens / self.budget.max_tokens,
            )
            
            if utilization >= 1.0:
                emit_event("budget_exceeded", {
                    "profile": self.profile,
                    "cost": self.budget.current_cost,
                    "calls": self.budget.current_calls,
                    "tokens": self.budget.current_tokens,
                })
            elif utilization >= 0.8:
                emit_event("budget_warning", {
                    "profile": self.profile,
                    "utilization": utilization,
                    "cost": self.budget.current_cost,
                    "calls": self.budget.current_calls,
                })


class ToolSelectionPolicy:
    """
    Tool selection with similarity ranking, risk penalties, and budget awareness.
    
    Per AGENTS.md § 2 Planning Protocol:
    - Must not select all tools blindly
    - Must rank by similarity/metadata with risk consideration
    - Respects budget availability before selection
    """
    
    def __init__(self, policy: GuardrailPolicy):
        self.policy = policy
    
    def select_tools(
        self,
        goal: str,
        available_tools: List[str],
        similarity_scores: Optional[Dict[str, float]] = None,
        top_k: int = 5,
    ) -> List[str]:
        """
        Select top-k tools for goal based on similarity and risk.
        
        Args:
            goal: User goal/query
            available_tools: List of available tool names
            similarity_scores: Optional pre-computed similarity scores
            top_k: Maximum number of tools to select
            
        Returns:
            Ordered list of selected tool names (highest score first)
        """
        if similarity_scores is None:
            similarity_scores = {tool: 0.5 for tool in available_tools}  # Default neutral score
        
        # Filter by allowlist/denylist
        filtered_tools = []
        for tool in available_tools:
            try:
                self.policy.validate_tool(tool)
                filtered_tools.append(tool)
            except ValueError:
                logger.debug(f"Tool '{tool}' filtered by policy")
        
        if not filtered_tools:
            logger.warning(f"No tools available after policy filtering for goal: {goal}")
            return []
        
        # Compute adjusted scores: similarity - risk_penalty
        adjusted_scores = {}
        for tool in filtered_tools:
            similarity = similarity_scores.get(tool, 0.0)
            risk_tier = self.policy.tool_risk_tiers.get(tool, RiskTier.READ)
            
            # Risk penalty: higher risk = lower score
            risk_penalty = {
                RiskTier.READ: 0.0,
                RiskTier.WRITE: 0.1,
                RiskTier.DELETE: 0.2,
                RiskTier.FINANCIAL: 0.3,
                RiskTier.EXTERNAL: 0.15,
            }[risk_tier]
            
            # Budget penalty: if budget is tight, penalize expensive tools
            budget_penalty = 0.0
            if not self.policy.check_budget(cost=1.0):
                budget_penalty = 0.5  # Heavy penalty if budget exhausted
            
            adjusted_scores[tool] = similarity - risk_penalty - budget_penalty
        
        # Sort by adjusted score (descending) and return top-k
        ranked_tools = sorted(adjusted_scores.items(), key=lambda x: x[1], reverse=True)
        selected = [tool for tool, score in ranked_tools[:top_k]]
        
        logger.info(
            f"Selected {len(selected)}/{len(filtered_tools)} tools for goal",
            extra={"selected": selected, "goal": goal[:50]},
        )
        
        return selected


# Integration functions for backward compatibility with existing code

def budget_guard(policy: GuardrailPolicy, cost: float = 0.0, calls: int = 1, tokens: int = 0) -> None:
    """
    Guard function to check and charge budget.
    
    Raises:
        ValueError: If budget is exhausted
    """
    if not policy.check_budget(cost, calls, tokens):
        raise ValueError(
            f"Budget exhausted for profile '{policy.profile}': "
            f"cost={policy.budget.current_cost}/{policy.budget.max_cost}, "
            f"calls={policy.budget.current_calls}/{policy.budget.max_calls}, "
            f"tokens={policy.budget.current_tokens}/{policy.budget.max_tokens}"
        )
    
    policy.charge_budget(cost, calls, tokens)


def request_approval(
    policy: GuardrailPolicy,
    governance_engine: GovernanceEngine,
    tool_name: str,
    inputs: Dict[str, Any],
    context: Dict[str, Any],
    request_id: str,
) -> ApprovalRequest:
    """
    Request approval for high-risk tool execution.
    
    Returns:
        ApprovalRequest with status (PENDING or APPROVED)
    """
    risk_tier = policy.tool_risk_tiers.get(tool_name, RiskTier.READ)
    
    # Check if approval is required
    if risk_tier not in policy.require_approval_for:
        if policy.emit_events:
            emit_event("approval_auto_approved", {
                "tool": tool_name,
                "risk_tier": risk_tier.value,
                "request_id": request_id,
            })
        return ApprovalRequest(
            request_id=request_id,
            tool_name=tool_name,
            action_type=risk_tier.to_action_type(),
            tenant=policy.profile,
            inputs=inputs,
            context=context,
            status=ApprovalStatus.APPROVED,
            approved_by="auto",
        )
    
    # Request HITL approval
    if policy.emit_events:
        emit_event("approval_requested", {
            "tool": tool_name,
            "risk_tier": risk_tier.value,
            "request_id": request_id,
            "timeout_seconds": policy.approval_timeout_seconds,
        })
    
    return governance_engine.request_approval(
        tool_name=tool_name,
        tenant=policy.profile,
        inputs=inputs,
        context=context,
        request_id=request_id,
    )

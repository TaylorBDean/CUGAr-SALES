"""Guards/routing schema for validation."""

from typing import Dict, List, Optional, Union, Literal
from pydantic import BaseModel, Field, field_validator


class GuardCondition(BaseModel):
    """Routing guard condition."""
    
    field: str = Field(..., description="Dot-separated field path (e.g., 'context.user_role')")
    operator: Literal["eq", "ne", "in", "not_in", "gt", "lt", "gte", "lte", "contains", "regex"]
    value: Union[str, int, float, List[str]]
    
    @field_validator("field")
    @classmethod
    def validate_field_path(cls, v: str) -> str:
        """Validate field path syntax."""
        if not v:
            raise ValueError("Field path cannot be empty")
        parts = v.split(".")
        for part in parts:
            if not part.replace("_", "").isalnum():
                raise ValueError(
                    f"Invalid field path component '{part}'. "
                    f"Must be alphanumeric with underscores"
                )
        return v
    
    @field_validator("value")
    @classmethod
    def validate_value_for_operator(cls, v: Union[str, int, float, List[str]], info) -> Union[str, int, float, List[str]]:
        """Validate value type matches operator requirements."""
        operator = info.data.get("operator")
        
        # Operators requiring list values
        if operator in ["in", "not_in"]:
            if not isinstance(v, list):
                raise ValueError(f"Operator '{operator}' requires list value, got {type(v).__name__}")
        
        # Operators requiring scalar values
        if operator in ["eq", "ne", "gt", "lt", "gte", "lte"]:
            if isinstance(v, list):
                raise ValueError(f"Operator '{operator}' requires scalar value, got list")
        
        return v
    
    model_config = {"extra": "forbid"}


class GuardAction(BaseModel):
    """Action to take when guard matches."""
    
    type: Literal["allow", "deny", "route_to", "log", "alert"]
    target: Optional[str] = Field(None, description="Target for route_to actions (agent/tool name)")
    reason: Optional[str] = Field(None, description="Human-readable reason for action")
    
    @field_validator("target")
    @classmethod
    def validate_target_required(cls, v: Optional[str], info) -> Optional[str]:
        """Ensure target provided for route_to actions."""
        action_type = info.data.get("type")
        if action_type == "route_to" and not v:
            raise ValueError("Action type 'route_to' requires 'target' field")
        return v
    
    model_config = {"extra": "forbid"}


class RoutingGuard(BaseModel):
    """Single routing guard rule."""
    
    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    description: str = Field(..., min_length=10, max_length=300)
    priority: int = Field(..., ge=0, le=100, description="Higher priority evaluated first")
    conditions: List[GuardCondition] = Field(..., min_length=1)
    action: GuardAction
    enabled: bool = True
    
    @field_validator("name")
    @classmethod
    def validate_name_convention(cls, v: str) -> str:
        """Validate guard name follows snake_case convention."""
        if v.startswith("_"):
            raise ValueError("Guard name cannot start with underscore")
        if "--" in v or "__" in v:
            raise ValueError("Guard name cannot contain consecutive underscores/hyphens")
        return v
    
    model_config = {"extra": "forbid"}


class GuardsConfig(BaseModel):
    """Complete guards configuration."""
    
    guards: List[RoutingGuard]
    default_action: GuardAction = Field(..., description="Action when no guard matches")
    
    @field_validator("guards")
    @classmethod
    def validate_unique_names(cls, v: List[RoutingGuard]) -> List[RoutingGuard]:
        """Ensure guard names are unique."""
        names = [guard.name for guard in v]
        if len(names) != len(set(names)):
            duplicates = [n for n in names if names.count(n) > 1]
            raise ValueError(f"Duplicate guard names found: {set(duplicates)}")
        return v
    
    @field_validator("guards")
    @classmethod
    def validate_priority_conflicts(cls, v: List[RoutingGuard]) -> List[RoutingGuard]:
        """Warn about guards with same priority (ambiguous ordering)."""
        priorities = [guard.priority for guard in v if guard.enabled]
        if len(priorities) != len(set(priorities)):
            import warnings
            warnings.warn(
                "Multiple guards have same priority. Evaluation order is undefined for ties.",
                UserWarning
            )
        return v
    
    model_config = {"extra": "forbid"}

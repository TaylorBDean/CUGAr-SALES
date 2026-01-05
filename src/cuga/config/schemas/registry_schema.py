"""Tool registry schema for validation."""

from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class SandboxProfile(str, Enum):
    """Allowed sandbox profiles per AGENTS.md guardrails."""
    
    PY_SLIM = "py_slim"
    PY_FULL = "py_full"
    NODE_SLIM = "node_slim"
    NODE_FULL = "node_full"
    ORCHESTRATOR = "orchestrator"


class ToolBudget(BaseModel):
    """Tool budget limits for cost control."""
    
    max_tokens: Optional[int] = Field(None, ge=1, description="Max LLM tokens per call")
    max_calls_per_session: Optional[int] = Field(None, ge=1, description="Max calls per session")
    max_calls_per_minute: Optional[int] = Field(None, ge=1, description="Rate limit per minute")
    
    model_config = {"extra": "forbid"}


class ToolSchema(BaseModel):
    """JSON Schema for tool inputs (subset of JSON Schema spec)."""
    
    type: Literal["object"] = "object"
    properties: Dict[str, Dict]
    required: List[str] = Field(default_factory=list)
    
    @field_validator("properties")
    @classmethod
    def validate_properties(cls, v: Dict[str, Dict]) -> Dict[str, Dict]:
        """Ensure all properties have 'type' field."""
        for prop_name, prop_def in v.items():
            if "type" not in prop_def:
                raise ValueError(f"Property '{prop_name}' missing 'type' field")
        return v
    
    model_config = {"extra": "forbid"}


class ToolRegistryEntry(BaseModel):
    """Single tool registry entry with full validation."""
    
    module: str = Field(..., pattern=r"^cuga\.modular\.tools\.[a-z_]+(\.[a-z_]+)*$")
    function: Optional[str] = None  # Defaults to last part of module name
    description: str = Field(..., min_length=10, max_length=500)
    schema: ToolSchema
    sandbox_profile: SandboxProfile
    mounts: List[str] = Field(default_factory=list)
    budget: Optional[ToolBudget] = None
    enabled: bool = True
    emits_telemetry: bool = False
    
    @field_validator("module")
    @classmethod
    def validate_module_allowlist(cls, v: str) -> str:
        """Enforce module allowlist per AGENTS.md (cuga.modular.tools.* only)."""
        if not v.startswith("cuga.modular.tools."):
            raise ValueError(
                f"Tool module '{v}' not in allowlist. "
                f"Must be 'cuga.modular.tools.*' (see AGENTS.md)"
            )
        return v
    
    @field_validator("mounts")
    @classmethod
    def validate_mounts(cls, v: List[str]) -> List[str]:
        """Validate mount syntax (source:dest:mode)."""
        for mount in v:
            parts = mount.split(":")
            if len(parts) != 3:
                raise ValueError(
                    f"Invalid mount syntax '{mount}'. "
                    f"Expected 'source:dest:mode' (e.g., '/workdir:/workdir:ro')"
                )
            source, dest, mode = parts
            if mode not in ["ro", "rw"]:
                raise ValueError(
                    f"Invalid mount mode '{mode}' in '{mount}'. "
                    f"Must be 'ro' (read-only) or 'rw' (read-write)"
                )
            if not dest.startswith("/"):
                raise ValueError(f"Mount destination '{dest}' must be absolute path")
        return v
    
    @field_validator("description")
    @classmethod
    def validate_description_quality(cls, v: str) -> str:
        """Ensure description is useful for planner ranking."""
        if len(v.split()) < 3:
            raise ValueError("Description must be at least 3 words for planner ranking")
        return v
    
    model_config = {"extra": "forbid"}


class ToolRegistry(BaseModel):
    """Complete tool registry with uniqueness constraints."""
    
    tools: Dict[str, ToolRegistryEntry]
    
    @field_validator("tools")
    @classmethod
    def validate_unique_modules(cls, v: Dict[str, ToolRegistryEntry]) -> Dict[str, ToolRegistryEntry]:
        """Ensure no duplicate module paths (prevent ambiguous imports)."""
        modules = [entry.module for entry in v.values()]
        if len(modules) != len(set(modules)):
            duplicates = [m for m in modules if modules.count(m) > 1]
            raise ValueError(f"Duplicate tool modules found: {set(duplicates)}")
        return v
    
    @field_validator("tools")
    @classmethod
    def validate_tool_names(cls, v: Dict[str, ToolRegistryEntry]) -> Dict[str, ToolRegistryEntry]:
        """Validate tool names follow naming conventions."""
        for tool_name in v.keys():
            if not tool_name.replace("_", "").isalnum():
                raise ValueError(
                    f"Tool name '{tool_name}' invalid. "
                    f"Must be alphanumeric with underscores only"
                )
            if tool_name.startswith("_"):
                raise ValueError(f"Tool name '{tool_name}' cannot start with underscore")
        return v
    
    model_config = {"extra": "forbid"}

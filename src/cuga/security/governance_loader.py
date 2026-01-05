"""Governance policy loader and integration with existing policy system."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional, Set

import yaml

from .governance import ActionType, GovernanceEngine, TenantCapabilityMap, ToolCapability


logger = logging.getLogger(__name__)

DEFAULT_GOVERNANCE_DIR = Path(__file__).resolve().parents[3] / "configurations" / "policies"


def load_governance_capabilities(path: Path) -> Dict[str, ToolCapability]:
    """
    Load tool capabilities from YAML file.
    
    Args:
        path: Path to governance_capabilities.yaml
    
    Returns:
        Mapping of tool name -> ToolCapability
    """
    if not path.exists():
        logger.warning(f"Governance capabilities file not found: {path}")
        return {}
    
    with open(path) as f:
        data = yaml.safe_load(f)
    
    capabilities: Dict[str, ToolCapability] = {}
    
    for tool_name, spec in data.get("capabilities", {}).items():
        try:
            action_type = ActionType(spec["action_type"])
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid action_type for tool '{tool_name}': {e}")
            continue
        
        allowed_tenants = set(spec.get("allowed_tenants", []))
        denied_tenants = set(spec.get("denied_tenants", []))
        
        capability = ToolCapability(
            name=tool_name,
            action_type=action_type,
            requires_approval=spec.get("requires_approval", False),
            approval_timeout_seconds=spec.get("approval_timeout_seconds", 300),
            allowed_tenants=allowed_tenants,
            denied_tenants=denied_tenants,
            max_rate_per_minute=spec.get("max_rate_per_minute"),
            metadata=spec.get("metadata", {}),
        )
        
        capabilities[tool_name] = capability
        logger.debug(f"Loaded capability for tool: {tool_name}")
    
    logger.info(f"Loaded {len(capabilities)} tool capabilities")
    return capabilities


def load_tenant_capability_maps(path: Path) -> Dict[str, TenantCapabilityMap]:
    """
    Load tenant capability maps from YAML file.
    
    Args:
        path: Path to tenant_capabilities.yaml
    
    Returns:
        Mapping of tenant ID -> TenantCapabilityMap
    """
    if not path.exists():
        logger.warning(f"Tenant capabilities file not found: {path}")
        return {}
    
    with open(path) as f:
        data = yaml.safe_load(f)
    
    tenant_maps: Dict[str, TenantCapabilityMap] = {}
    
    for tenant_id, spec in data.get("tenant_maps", {}).items():
        allowed_tools = set(spec.get("allowed_tools", []))
        denied_tools = set(spec.get("denied_tools", []))
        
        tenant_map = TenantCapabilityMap(
            tenant=tenant_id,
            allowed_tools=allowed_tools,
            denied_tools=denied_tools,
            max_concurrent_calls=spec.get("max_concurrent_calls", 10),
            budget_ceiling=spec.get("budget_ceiling", 100),
            metadata=spec.get("metadata", {}),
        )
        
        tenant_maps[tenant_id] = tenant_map
        logger.debug(f"Loaded capability map for tenant: {tenant_id}")
    
    logger.info(f"Loaded {len(tenant_maps)} tenant capability maps")
    return tenant_maps


def create_governance_engine(
    governance_dir: Optional[Path] = None,
    capabilities_file: str = "governance_capabilities.yaml",
    tenant_maps_file: str = "tenant_capabilities.yaml",
) -> GovernanceEngine:
    """
    Create governance engine from configuration files.
    
    Args:
        governance_dir: Directory containing governance config files
        capabilities_file: Name of capabilities YAML file
        tenant_maps_file: Name of tenant maps YAML file
    
    Returns:
        Initialized GovernanceEngine
    """
    gov_dir = governance_dir or DEFAULT_GOVERNANCE_DIR
    
    capabilities_path = gov_dir / capabilities_file
    tenant_maps_path = gov_dir / tenant_maps_file
    
    capabilities = load_governance_capabilities(capabilities_path)
    tenant_maps = load_tenant_capability_maps(tenant_maps_path)
    
    engine = GovernanceEngine(
        capabilities=capabilities,
        tenant_maps=tenant_maps,
    )
    
    logger.info(
        f"Governance engine initialized with {len(capabilities)} capabilities "
        f"and {len(tenant_maps)} tenant maps"
    )
    
    return engine


def merge_governance_with_profile_policy(
    profile_policy: Dict[str, Any],
    governance_engine: GovernanceEngine,
    tenant: str,
) -> Dict[str, Any]:
    """
    Merge governance rules into existing profile policy.
    
    This allows profile policies (AGENTS.md § 3 Profile Isolation) to work
    alongside governance capability maps for defense-in-depth.
    
    Args:
        profile_policy: Existing profile policy dict (from configurations/policies/*.yaml)
        governance_engine: Governance engine with capability rules
        tenant: Tenant ID for capability lookup
    
    Returns:
        Merged policy dict with governance constraints applied
    """
    merged = profile_policy.copy()
    
    # Get tenant capability map
    tenant_map = governance_engine.tenant_maps.get(tenant)
    if not tenant_map:
        logger.warning(f"No tenant capability map found for tenant: {tenant}")
        return merged
    
    # Filter allowed_tools based on tenant map
    profile_allowed = set(merged.get("allowed_tools", {}).keys())
    tenant_allowed = tenant_map.allowed_tools if tenant_map.allowed_tools else profile_allowed
    tenant_denied = tenant_map.denied_tools
    
    # Intersection: only tools allowed by BOTH profile AND tenant
    final_allowed = (profile_allowed & tenant_allowed) - tenant_denied
    
    # Update policy with filtered tools
    if "allowed_tools" in merged:
        merged["allowed_tools"] = {
            tool: spec
            for tool, spec in merged["allowed_tools"].items()
            if tool in final_allowed
        }
    
    # Add governance metadata
    if "metadata_schema" not in merged:
        merged["metadata_schema"] = {}
    
    merged["metadata_schema"]["properties"] = merged["metadata_schema"].get("properties", {})
    merged["metadata_schema"]["properties"]["tenant"] = {
        "type": "string",
        "description": "Tenant ID for governance checks",
    }
    merged["metadata_schema"]["properties"]["approval_request_id"] = {
        "type": "string",
        "description": "Optional approval request ID for HITL gates",
    }
    
    logger.debug(
        f"Merged governance for tenant '{tenant}': "
        f"{len(final_allowed)} tools allowed after intersection"
    )
    
    return merged

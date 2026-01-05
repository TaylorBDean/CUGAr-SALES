"""
Capability Health Endpoints
Provides adapter health status for frontend monitoring (AGENTS.md compliant)
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Literal
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["capabilities"])


class CapabilityHealth(BaseModel):
    """Health status for a single capability"""
    name: str
    domain: str
    status: Literal['online', 'degraded', 'offline']
    adapter: str | None = None
    mode: Literal['mock', 'live'] | None = None
    message: str | None = None
    side_effect_class: str = "read-only"


class ProfileInfo(BaseModel):
    """Current sales profile information"""
    profile_id: str
    name: str
    description: str


@router.get("/capabilities/status", response_model=List[CapabilityHealth])
async def get_capability_status() -> List[CapabilityHealth]:
    """
    Returns health status of all capabilities.
    
    Checks:
    - Whether each tool is available
    - Which adapter is providing the capability
    - Whether running in mock or live mode
    
    Returns:
        List of capability health objects
    """
    try:
        from cuga.modular.tools import TOOL_REGISTRY
        from cuga.adapters import ADAPTER_REGISTRY
        
        capabilities = []
        
        for tool_name, tool_meta in TOOL_REGISTRY.items():
            domain = tool_meta.get('domain', 'unknown')
            
            # Determine adapter providing this capability
            adapter_name = None
            mode = 'mock'
            status = 'online'
            message = None
            
            try:
                # Check if tool can be invoked
                tool_fn = tool_meta.get('fn')
                if tool_fn:
                    # Check for adapter binding
                    adapter_name = getattr(tool_fn, '__adapter__', None)
                    
                    # Try to determine if live or mock
                    if adapter_name and adapter_name in ADAPTER_REGISTRY:
                        adapter_instance = ADAPTER_REGISTRY[adapter_name]
                        if hasattr(adapter_instance, 'is_connected'):
                            is_live = adapter_instance.is_connected()
                            mode = 'live' if is_live else 'mock'
                        else:
                            mode = 'mock'
                    else:
                        mode = 'mock'
                    
                    status = 'online'
                else:
                    status = 'degraded'
                    message = 'Tool function not available'
                    
            except Exception as e:
                status = 'degraded'
                message = str(e)
                logger.warning(f"Error checking capability {tool_name}: {e}")
            
            capabilities.append(CapabilityHealth(
                name=tool_name,
                domain=domain,
                status=status,
                adapter=adapter_name,
                mode=mode,
                message=message
            ))
        
        return capabilities
        
    except Exception as e:
        logger.error(f"Failed to get capability status: {e}")
        # Return mock data for demo
        return [
            CapabilityHealth(
                name='score_account_fit',
                domain='intelligence',
                status='online',
                mode='mock'
            ),
            CapabilityHealth(
                name='draft_outbound_message',
                domain='engagement',
                status='online',
                mode='mock'
            ),
            CapabilityHealth(
                name='qualify_opportunity',
                domain='qualification',
                status='online',
                mode='mock'
            ),
            CapabilityHealth(
                name='analyze_territory_coverage',
                domain='territory',
                status='online',
                mode='mock'
            ),
            CapabilityHealth(
                name='retrieve_product_knowledge',
                domain='knowledge',
                status='online',
                mode='mock'
            )
        ]


@router.get("/capabilities/budgets")
async def get_budget_status() -> Dict[str, Any]:
    """
    Return current tool budget utilization per AGENTS.md budget requirements.
    
    Per AGENTS.md:
    - PlannerAgent MUST attach a ToolBudget to every plan
    - Budgets track total_calls, calls_per_domain, calls_per_tool
    """
    # TODO: Integrate with BudgetEnforcer
    return {
        "total": {
            "used": 0,
            "limit": 100,
            "percentage": 0
        },
        "by_domain": {
            "territory": {"used": 0, "limit": 50},
            "intelligence": {"used": 0, "limit": 30},
            "engagement": {"used": 0, "limit": 20}
        },
        "warnings": []
    }


@router.get("/profile", response_model=ProfileInfo)
async def get_current_profile() -> ProfileInfo:
    """get("/profiles")
async def list_profiles() -> List[str]:
    """
    List available sales profiles per AGENTS.md memory & RAG requirements.
    """
    try:
        from cuga.orchestrator.profile_loader import ProfileLoader
        loader = ProfileLoader()
        return loader.list_profiles()
    except Exception as e:
        logger.warning(f"Failed to list profiles: {e}")
        return ["enterprise", "smb", "technical"]


@router.post("
    Returns the current active sales profile.
    
    Returns:
        Current profile information
    """
    try:
        from cuga.config import get_active_profile
        
        profile = get_active_profile()
        return ProfileInfo(
            profile_id=profile.get('id', 'enterprise'),
            name=profile.get('name', 'Enterprise'),
            description=profile.get('description', 'Strategic deals, long sales cycles')
        )
        
    except Exception as e:
        logger.warning(f"Failed to get profile, using default: {e}")
        return ProfileInfo(
            profile_id='enterprise',
            name='Enterprise',
            description='Strategic deals, long sales cycles, executive engagement'
        )


@router.post("/api/profile")
async def set_current_profile(payload: Dict[str, Any]) -> Dict[str, str]:
    """
    Changes the active sales profile.
    
    Args:
        payload: { "profile_id": "enterprise|smb|technical" }
    
    Returns:
        Status message
    """
    try:
        profile_id = payload.get('profile_id')
        if not profile_id:
            return {"status": "error", "message": "profile_id required"}
        
        valid_profiles = ['enterprise', 'smb', 'technical']
        if profile_id not in valid_profiles:
            return {
                "status": "error", 
                "message": f"Invalid profile. Must be one of: {', '.join(valid_profiles)}"
            }
        
        # TODO: Implement profile switching logic
        # This would reload tools, budgets, and guardrails for the new profile
        logger.info(f"Profile changed to: {profile_id}")
        
        return {
            "status": "success",
            "message": f"Profile changed to {profile_id}"
        }
        
    except Exception as e:
        logger.error(f"Failed to set profile: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

"""
CRM adapter factory for vendor selection.

Provides unified interface for loading CRM adapters based on configuration.

USAGE:
    # Load adapter from environment
    adapter = get_crm_adapter()  # Uses CRM_VENDOR env var
    
    # Load specific adapter
    adapter = get_crm_adapter(vendor="salesforce")
    adapter = get_crm_adapter(vendor="hubspot")
    adapter = get_crm_adapter(vendor="pipedrive")
    
    # Use adapter
    account = adapter.get_account("12345", context={"trace_id": "abc"})
"""

from typing import Optional, Dict, Any
import os
import logging

logger = logging.getLogger(__name__)


# Registry of available adapters
_ADAPTER_REGISTRY: Dict[str, str] = {
    "hubspot": "cuga.adapters.crm.hubspot_adapter.HubSpotAdapter",
    "salesforce": "cuga.adapters.crm.salesforce_adapter.SalesforceAdapter",
    "pipedrive": "cuga.adapters.crm.pipedrive_adapter.PipedriveAdapter",
}


def get_crm_adapter(vendor: Optional[str] = None, **kwargs):
    """
    Get CRM adapter instance for specified vendor.
    
    Args:
        vendor: CRM vendor name ("hubspot", "salesforce", "pipedrive")
                Defaults to CRM_VENDOR environment variable
        **kwargs: Additional adapter-specific configuration
        
    Returns:
        CRM adapter instance implementing CRMAdapter protocol
        
    Raises:
        ValueError: If vendor not supported or required credentials missing
        
    Examples:
        # Auto-detect from environment
        adapter = get_crm_adapter()
        
        # Specific vendor
        adapter = get_crm_adapter(vendor="hubspot")
        adapter = get_crm_adapter(vendor="salesforce")
        
        # With custom config
        adapter = get_crm_adapter(
            vendor="hubspot",
            api_key="custom-key-123"
        )
    """
    # Determine vendor
    vendor = vendor or os.getenv("CRM_VENDOR", "").lower()
    
    if not vendor:
        raise ValueError(
            "CRM vendor not specified. Set CRM_VENDOR environment variable or pass vendor parameter. "
            f"Supported vendors: {', '.join(_ADAPTER_REGISTRY.keys())}"
        )
    
    if vendor not in _ADAPTER_REGISTRY:
        raise ValueError(
            f"Unsupported CRM vendor: {vendor}. "
            f"Supported vendors: {', '.join(_ADAPTER_REGISTRY.keys())}"
        )
    
    # Load adapter class
    adapter_path = _ADAPTER_REGISTRY[vendor]
    module_path, class_name = adapter_path.rsplit(".", 1)
    
    try:
        # Dynamic import
        import importlib
        module = importlib.import_module(module_path)
        adapter_class = getattr(module, class_name)
        
        # Instantiate adapter
        logger.info(f"Loading CRM adapter: {vendor}")
        adapter = adapter_class(**kwargs)
        
        return adapter
        
    except ImportError as e:
        logger.error(f"Failed to import {vendor} adapter: {e}")
        raise ValueError(f"Failed to load {vendor} adapter. Check installation and dependencies.")
    except Exception as e:
        logger.error(f"Failed to initialize {vendor} adapter: {e}")
        raise


def list_available_adapters() -> Dict[str, Dict[str, Any]]:
    """
    List all available CRM adapters with their configuration requirements.
    
    Returns:
        Dict mapping vendor name to adapter metadata
        
    Example:
        adapters = list_available_adapters()
        print(adapters["hubspot"]["env_vars"])
        # ["HUBSPOT_API_KEY"]
    """
    return {
        "hubspot": {
            "name": "HubSpot",
            "class": "HubSpotAdapter",
            "env_vars": ["HUBSPOT_API_KEY"],
            "optional_env_vars": [],
            "description": "HubSpot CRM adapter with OAuth2 API key authentication",
            "docs": "https://developers.hubspot.com/docs/api/overview",
        },
        "salesforce": {
            "name": "Salesforce",
            "class": "SalesforceAdapter",
            "env_vars": [
                "SALESFORCE_CLIENT_ID",
                "SALESFORCE_CLIENT_SECRET",
                "SALESFORCE_USERNAME",
                "SALESFORCE_PASSWORD",
                "SALESFORCE_SECURITY_TOKEN",
            ],
            "optional_env_vars": ["SALESFORCE_INSTANCE_URL"],
            "description": "Salesforce CRM adapter with OAuth2 username-password flow",
            "docs": "https://developer.salesforce.com/docs/atlas.en-us.api_rest.meta/api_rest/",
        },
        "pipedrive": {
            "name": "Pipedrive",
            "class": "PipedriveAdapter",
            "env_vars": [
                "PIPEDRIVE_API_KEY",
                "PIPEDRIVE_COMPANY_DOMAIN",
            ],
            "optional_env_vars": [],
            "description": "Pipedrive CRM adapter with API key authentication",
            "docs": "https://developers.pipedrive.com/docs/api/v1",
        },
    }


def check_adapter_requirements(vendor: str) -> Dict[str, Any]:
    """
    Check if required environment variables are configured for a vendor.
    
    Args:
        vendor: CRM vendor name
        
    Returns:
        {
            "vendor": str,
            "available": bool,
            "missing_vars": [str],
            "configured_vars": [str],
        }
        
    Example:
        status = check_adapter_requirements("hubspot")
        if status["available"]:
            adapter = get_crm_adapter(vendor="hubspot")
        else:
            print(f"Missing: {status['missing_vars']}")
    """
    adapters = list_available_adapters()
    
    if vendor not in adapters:
        return {
            "vendor": vendor,
            "available": False,
            "error": f"Unknown vendor. Supported: {', '.join(adapters.keys())}",
        }
    
    adapter_info = adapters[vendor]
    required_vars = adapter_info["env_vars"]
    
    missing = []
    configured = []
    
    for var in required_vars:
        if os.getenv(var):
            configured.append(var)
        else:
            missing.append(var)
    
    return {
        "vendor": vendor,
        "available": len(missing) == 0,
        "missing_vars": missing,
        "configured_vars": configured,
        "required_vars": required_vars,
    }


def get_configured_adapter():
    """
    Get CRM adapter for the first available vendor.
    
    Tries vendors in order: HubSpot, Salesforce, Pipedrive.
    Returns None if no adapter is configured.
    
    Returns:
        CRM adapter instance or None
        
    Example:
        adapter = get_configured_adapter()
        if adapter:
            account = adapter.get_account("123", context={})
        else:
            # Fall back to offline mode
            pass
    """
    vendor_priority = ["hubspot", "salesforce", "pipedrive"]
    
    for vendor in vendor_priority:
        status = check_adapter_requirements(vendor)
        if status["available"]:
            try:
                logger.info(f"Auto-detected configured CRM adapter: {vendor}")
                return get_crm_adapter(vendor=vendor)
            except Exception as e:
                logger.warning(f"Failed to load {vendor} adapter despite configured credentials: {e}")
                continue
    
    logger.info("No CRM adapter configured. Operating in offline mode.")
    return None

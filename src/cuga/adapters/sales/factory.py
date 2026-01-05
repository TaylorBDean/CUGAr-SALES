"""
Adapter factory with hot-swap config support.

Reads configuration from:
1. configs/adapters.yaml (frontend API-managed)
2. Environment variables (fallback)
3. Default (mock mode)

Zero code changes needed for mock/live toggle.
"""

from typing import Dict, Any, Optional
from pathlib import Path
import yaml
import os

from .protocol import VendorAdapter, AdapterMode, AdapterConfig
from .mock_adapter import MockAdapter


CONFIG_PATH = Path("configs/adapters.yaml")


def _load_adapter_config(vendor: str) -> Dict[str, Any]:
    """
    Load adapter config with precedence:
    1. configs/adapters.yaml (frontend-managed)
    2. Environment variables
    3. Default (mock mode)
    """
    
    # Try config file first (frontend API writes here)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r") as f:
                config_data = yaml.safe_load(f) or {}
                vendor_config = config_data.get("adapters", {}).get(vendor, {})
                if vendor_config:
                    return vendor_config
        except Exception:
            pass  # Fall through to env vars
    
    # Fallback to environment variables
    env_prefix = f"SALES_{vendor.upper().replace('.', '_')}_"
    mode = os.getenv(f"{env_prefix}ADAPTER_MODE", "mock")
    
    return {
        "mode": mode,
        "credentials": {
            k.replace(env_prefix, "").lower(): v
            for k, v in os.environ.items()
            if k.startswith(env_prefix) and "MODE" not in k
        }
    }


def create_adapter(
    vendor: str,
    trace_id: Optional[str] = None
) -> VendorAdapter:
    """
    Create adapter with automatic mock/live selection.
    
    Args:
        vendor: Vendor ID (ibm_sales_cloud, salesforce, hubspot, etc.)
        trace_id: Optional trace ID for observability
    
    Returns:
        VendorAdapter instance (mock or live based on config)
    
    Examples:
        >>> # Mock mode (default, no credentials)
        >>> adapter = create_adapter("ibm_sales_cloud")
        >>> accounts = adapter.fetch_accounts()
        
        >>> # Live mode (after frontend config or env vars)
        >>> adapter = create_adapter("ibm_sales_cloud")  # Auto-detects live
        >>> accounts = adapter.fetch_accounts()  # Calls real API
    """
    
    # Load config
    config_dict = _load_adapter_config(vendor)
    mode = AdapterMode(config_dict.get("mode", "mock"))
    credentials = config_dict.get("credentials", {})
    
    config = AdapterConfig(
        mode=mode,
        credentials=credentials,
        trace_id=trace_id
    )
    
    # Emit observability event
    try:
        from cuga.observability import emit_event
        from cuga.observability.events import StructuredEvent, EventType
        
        emit_event(StructuredEvent(
            event_type=EventType.ROUTE_DECISION,
            trace_id=trace_id or "unknown",
            attributes={
                "adapter_vendor": vendor,
                "adapter_mode": mode.value,
                "config_source": "yaml" if CONFIG_PATH.exists() else "env",
            }
        ))
    except ImportError:
        pass  # Observability not available
    
    # Route to appropriate adapter implementation
    if mode == AdapterMode.MOCK:
        return MockAdapter(vendor=vendor, config=config)
    elif mode == AdapterMode.LIVE:
        # Import live adapter based on vendor
        if vendor == "ibm_sales_cloud":
            try:
                from .ibm_live import IBMLiveAdapter
                return IBMLiveAdapter(config=config)
            except ImportError as e:
                print(f"[ERROR] Failed to import IBMLiveAdapter: {e}")
                print(f"[WARNING] Falling back to mock adapter")
                return MockAdapter(vendor=vendor, config=config)
        elif vendor == "salesforce":
            try:
                from .salesforce_live import SalesforceLiveAdapter
                return SalesforceLiveAdapter(config=config)
            except ImportError as e:
                print(f"[ERROR] Failed to import SalesforceLiveAdapter: {e}")
                print(f"[WARNING] Falling back to mock adapter")
                return MockAdapter(vendor=vendor, config=config)
        elif vendor == "zoominfo":
            try:
                from .zoominfo_live import ZoomInfoLiveAdapter
                return ZoomInfoLiveAdapter(config=config)
            except ImportError as e:
                print(f"[ERROR] Failed to import ZoomInfoLiveAdapter: {e}")
                print(f"[WARNING] Falling back to mock adapter")
                return MockAdapter(vendor=vendor, config=config)
        elif vendor == "clearbit":
            try:
                from .clearbit_live import ClearbitLiveAdapter
                return ClearbitLiveAdapter(config=config)
            except ImportError as e:
                print(f"[ERROR] Failed to import ClearbitLiveAdapter: {e}")
                print(f"[WARNING] Falling back to mock adapter")
                return MockAdapter(vendor=vendor, config=config)
        elif vendor == "hubspot":
            try:
                from .hubspot_live import HubSpotLiveAdapter
                return HubSpotLiveAdapter(config=config)
            except ImportError as e:
                print(f"[ERROR] Failed to import HubSpotLiveAdapter: {e}")
                print(f"[WARNING] Falling back to mock adapter")
                return MockAdapter(vendor=vendor, config=config)
        elif vendor == "sixsense":
            try:
                from .sixsense_live import SixSenseLiveAdapter
                return SixSenseLiveAdapter(config=config)
            except ImportError as e:
                print(f"[ERROR] Failed to import SixSenseLiveAdapter: {e}")
                print(f"[WARNING] Falling back to mock adapter")
                return MockAdapter(vendor=vendor, config=config)
        elif vendor == "apollo":
            try:
                from .apollo_live import ApolloLiveAdapter
                return ApolloLiveAdapter(config=config)
            except ImportError as e:
                print(f"[ERROR] Failed to import ApolloLiveAdapter: {e}")
                print(f"[WARNING] Falling back to mock adapter")
                return MockAdapter(vendor=vendor, config=config)
        elif vendor == "pipedrive":
            try:
                from .pipedrive_live import PipedriveLiveAdapter
                return PipedriveLiveAdapter(config=config)
            except ImportError as e:
                print(f"[ERROR] Failed to import PipedriveLiveAdapter: {e}")
                print(f"[WARNING] Falling back to mock adapter")
                return MockAdapter(vendor=vendor, config=config)
        elif vendor == "crunchbase":
            try:
                from .crunchbase_live import CrunchbaseLiveAdapter
                return CrunchbaseLiveAdapter(config=config)
            except ImportError as e:
                print(f"[ERROR] Failed to import CrunchbaseLiveAdapter: {e}")
                print(f"[WARNING] Falling back to mock adapter")
                return MockAdapter(vendor=vendor, config=config)
        elif vendor == "builtwith":
            try:
                from .builtwith_live import BuiltWithLiveAdapter
                return BuiltWithLiveAdapter(config=config)
            except ImportError as e:
                print(f"[ERROR] Failed to import BuiltWithLiveAdapter: {e}")
                print(f"[WARNING] Falling back to mock adapter")
                return MockAdapter(vendor=vendor, config=config)
        else:
            # Live adapter not implemented for this vendor yet
            print(f"[WARNING] Live mode requested for {vendor} but not implemented - using mock")
            return MockAdapter(vendor=vendor, config=config)
    else:
        # HYBRID mode - not yet implemented
        print(f"[WARNING] Hybrid mode not yet implemented - using mock")
        return MockAdapter(vendor=vendor, config=config)


def get_adapter_status(vendor: str) -> Dict[str, Any]:
    """
    Get current adapter configuration status.
    
    Returns:
        Status dict with mode, configured, credentials_valid
    """
    config_dict = _load_adapter_config(vendor)
    mode = AdapterMode(config_dict.get("mode", "mock"))
    credentials = config_dict.get("credentials", {})
    
    # Define required fields per vendor
    required_fields = {
        "ibm_sales_cloud": ["api_endpoint", "api_key", "tenant_id"],
        "salesforce": ["instance_url", "client_id", "client_secret", "username", "password"],
        "zoominfo": ["api_key"],
        "clearbit": ["api_key"],
        "hubspot": ["api_key"],
        "sixsense": ["api_key"],
        "apollo": ["api_key"],
        "pipedrive": ["api_token"],
        "crunchbase": ["api_key"],
        "builtwith": ["api_key"],
    }.get(vendor, [])
    
    missing_fields = [
        f for f in required_fields
        if f not in credentials or not credentials[f]
    ]
    
    # Mock mode is always configured (no credentials needed)
    configured = mode == AdapterMode.MOCK or len(missing_fields) == 0
    
    return {
        "vendor": vendor,
        "mode": mode.value,
        "configured": configured,
        "credentials_valid": mode == AdapterMode.MOCK or len(missing_fields) == 0,
        "required_fields": required_fields,
        "missing_fields": missing_fields,
    }


# Convenience aliases for common vendors
def create_ibm_adapter(trace_id: Optional[str] = None) -> VendorAdapter:
    """Create IBM Sales Cloud adapter"""
    return create_adapter("ibm_sales_cloud", trace_id)


def create_salesforce_adapter(trace_id: Optional[str] = None) -> VendorAdapter:
    """Create Salesforce adapter"""
    return create_adapter("salesforce", trace_id)


def create_hubspot_adapter(trace_id: Optional[str] = None) -> VendorAdapter:
    """Create HubSpot adapter"""
    return create_adapter("hubspot", trace_id)


def create_sixsense_adapter(trace_id: Optional[str] = None) -> VendorAdapter:
    """Create 6sense adapter"""
    return create_adapter("sixsense", trace_id)


def create_apollo_adapter(trace_id: Optional[str] = None) -> VendorAdapter:
    """Create Apollo.io adapter"""
    return create_adapter("apollo", trace_id)


def create_pipedrive_adapter(trace_id: Optional[str] = None) -> VendorAdapter:
    """Create Pipedrive adapter"""
    return create_adapter("pipedrive", trace_id)


def create_crunchbase_adapter(trace_id: Optional[str] = None) -> VendorAdapter:
    """Create Crunchbase adapter"""
    return create_adapter("crunchbase", trace_id)


def create_builtwith_adapter(trace_id: Optional[str] = None) -> VendorAdapter:
    """Create BuiltWith adapter"""
    return create_adapter("builtwith", trace_id)

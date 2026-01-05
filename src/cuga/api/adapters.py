"""
FastAPI endpoints for adapter hot-swap configuration.

Frontend UI manages adapter modes and credentials via these endpoints.
Configuration written to configs/adapters.yaml for persistence.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import yaml

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from cuga.adapters import (
    create_adapter,
    get_adapter_status,
    AdapterMode,
)


router = APIRouter(prefix="/api/adapters", tags=["adapters"])

CONFIG_PATH = Path("configs/adapters.yaml")


# Pydantic models

class AdapterConfigRequest(BaseModel):
    """Request to configure adapter credentials and mode"""
    mode: AdapterMode = Field(description="Adapter mode (mock, live, hybrid)")
    credentials: Dict[str, str] = Field(
        default_factory=dict,
        description="Vendor-specific credentials (API keys, endpoints, etc.)"
    )


class AdapterStatusResponse(BaseModel):
    """Adapter configuration status"""
    vendor: str = Field(description="Vendor ID")
    mode: str = Field(description="Current adapter mode")
    configured: bool = Field(description="Whether all required credentials provided")
    credentials_valid: bool = Field(description="Whether adapter can connect")
    required_fields: List[str] = Field(description="Required credential fields")
    missing_fields: List[str] = Field(description="Missing credential fields")


class AdapterListResponse(BaseModel):
    """List of all adapter statuses"""
    adapters: List[AdapterStatusResponse]


class AdapterToggleRequest(BaseModel):
    """Quick toggle between mock and live"""
    mode: AdapterMode = Field(description="Target mode (mock or live)")


class AdapterTestResponse(BaseModel):
    """Connection test result"""
    vendor: str
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


# Helper: Read/write adapter config file

def _read_config() -> Dict[str, Any]:
    """Read configs/adapters.yaml"""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f) or {"adapters": {}}
    return {"adapters": {}}


def _write_config(config: Dict[str, Any]) -> None:
    """Write configs/adapters.yaml"""
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)


# Endpoints

@router.get("/", response_model=AdapterListResponse)
def list_adapters() -> AdapterListResponse:
    """
    List all configured adapters with status.
    
    Returns adapter statuses for all known vendors.
    """
    vendors = [
        "ibm_sales_cloud",
        "salesforce",
        "hubspot",
        "pipedrive",
        "zoominfo",
        "clearbit",
        "apollo",
        "sixsense",
    ]
    
    statuses = [
        AdapterStatusResponse(**get_adapter_status(vendor))
        for vendor in vendors
    ]
    
    return AdapterListResponse(adapters=statuses)


@router.get("/{vendor}", response_model=AdapterStatusResponse)
def get_adapter(vendor: str) -> AdapterStatusResponse:
    """
    Get specific adapter status.
    
    Args:
        vendor: Vendor ID (ibm_sales_cloud, salesforce, etc.)
    
    Returns:
        Current configuration status including missing credentials
    """
    try:
        status = get_adapter_status(vendor)
        return AdapterStatusResponse(**status)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get adapter status: {exc}"
        )


@router.post("/{vendor}/configure", response_model=AdapterStatusResponse)
def configure_adapter(vendor: str, config: AdapterConfigRequest) -> AdapterStatusResponse:
    """
    Configure adapter mode and credentials.
    
    Args:
        vendor: Vendor ID
        config: Mode and credentials
    
    Returns:
        Updated adapter status
    
    Notes:
        - Writes to configs/adapters.yaml for persistence
        - Credentials redacted in logs per AGENTS.md
        - Factory auto-detects mode on next create_adapter() call
    """
    try:
        # Read current config
        full_config = _read_config()
        
        # Update vendor config
        full_config["adapters"][vendor] = {
            "mode": config.mode.value,
            "credentials": config.credentials,
        }
        
        # Write back
        _write_config(full_config)
        
        # Emit observability event
        try:
            from cuga.observability import emit_event
            emit_event(
                "adapter_configured",
                metadata={
                    "vendor": vendor,
                    "mode": config.mode.value,
                    "credentials_provided": list(config.credentials.keys()),
                }
            )
        except ImportError:
            pass
        
        # Return updated status
        return AdapterStatusResponse(**get_adapter_status(vendor))
        
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to configure adapter: {exc}"
        )


@router.post("/{vendor}/toggle", response_model=AdapterStatusResponse)
def toggle_adapter(vendor: str, toggle_req: AdapterToggleRequest) -> AdapterStatusResponse:
    """
    Quick toggle between mock and live mode.
    
    Args:
        vendor: Vendor ID
        toggle_req: Target mode
    
    Returns:
        Updated adapter status
    
    Notes:
        - Preserves existing credentials
        - Returns error if toggling to live without credentials
    """
    try:
        # Read current config
        full_config = _read_config()
        vendor_config = full_config["adapters"].get(vendor, {})
        
        # Check if live mode requires credentials
        if toggle_req.mode == AdapterMode.LIVE:
            status = get_adapter_status(vendor)
            if not status["configured"]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Cannot toggle to live mode: missing credentials. "
                        f"Required fields: {status['required_fields']}"
                    )
                )
        
        # Update mode
        vendor_config["mode"] = toggle_req.mode.value
        full_config["adapters"][vendor] = vendor_config
        
        # Write back
        _write_config(full_config)
        
        # Return updated status
        return AdapterStatusResponse(**get_adapter_status(vendor))
        
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle adapter: {exc}"
        )


@router.post("/{vendor}/test", response_model=AdapterTestResponse)
def test_adapter(vendor: str) -> AdapterTestResponse:
    """
    Test adapter connection.
    
    Args:
        vendor: Vendor ID
    
    Returns:
        Connection test result
    
    Notes:
        - Mock mode always succeeds
        - Live mode attempts actual API call
    """
    try:
        adapter = create_adapter(vendor)
        
        # Validate connection
        is_valid = adapter.validate_connection()
        
        # Try fetching sample data
        try:
            accounts = adapter.fetch_accounts()
            account_count = len(accounts)
        except Exception as fetch_exc:
            return AdapterTestResponse(
                vendor=vendor,
                success=False,
                message=f"Connection failed: {fetch_exc}",
                details={"mode": adapter.get_mode().value}
            )
        
        return AdapterTestResponse(
            vendor=vendor,
            success=is_valid,
            message=f"Connection successful ({adapter.get_mode().value} mode)",
            details={
                "mode": adapter.get_mode().value,
                "account_count": account_count,
            }
        )
        
    except Exception as exc:
        return AdapterTestResponse(
            vendor=vendor,
            success=False,
            message=f"Test failed: {exc}",
        )


@router.delete("/{vendor}", status_code=status.HTTP_204_NO_CONTENT)
def reset_adapter(vendor: str) -> None:
    """
    Reset adapter to mock mode (delete credentials).
    
    Args:
        vendor: Vendor ID
    
    Notes:
        - Removes vendor from configs/adapters.yaml
        - Next create_adapter() call uses mock mode
    """
    try:
        # Read current config
        full_config = _read_config()
        
        # Remove vendor config
        if vendor in full_config["adapters"]:
            del full_config["adapters"][vendor]
        
        # Write back
        _write_config(full_config)
        
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset adapter: {exc}"
        )
